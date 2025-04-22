import numpy as np
import cv2
import imutils
import threading
from queue import Queue
from ultralytics import YOLO
import supervision.detection.core as sv
from annotator import Annotator
import coordinateMapping
import redis
import asyncio
import os
import torch


if torch.cuda.is_available():
    print(f"[INFO] PyTorch CUDA detected. Available devices: {torch.cuda.device_count()}")
else:
    print("[INFO] PyTorch CUDA not detected. YOLO will use CPU.")

# Global YOLO model (för att inte skapa den varje gång)
model = YOLO("best.pt")

redis_url = os.environ.get("REDIS_URL", "localhost")
# Redis connection (skapa en Redis-klient om den inte finns)
r = redis.StrictRedis(host='redis', port=6379, db=0, decode_responses=True)

## ---- HELPER FUNCTIONS ----

async def consume_async_generator(gen, queue, stop_event):
    """Consume an async generator and push frames into a queue."""
    async for frame in gen:
        if stop_event.is_set():
            break
        queue.put(frame)
    queue.put(None)  # Signal the end of the stream

def detect_objects(frame):
    """ Kör YOLO för objektspårning på en frame. """
    results = model.track(frame, persist=True, conf=0.75, imgsz=448)
    detections = sv.Detections.from_ultralytics(results[0])
    return detections

def get_weighted_gps(pixel_x, frame_width, left_gps, right_gps):
    """Beräknar en viktad GPS-position baserat på objektets position i bilden."""
    alpha = pixel_x / frame_width  # Normaliserad position (0 = vänster, 1 = höger)
    gps_lat = left_gps[0] * (1 - alpha) + right_gps[0] * alpha
    gps_lon = left_gps[1] * (1 - alpha) + right_gps[1] * alpha
    return (gps_lat, gps_lon)

async def set_frame(img: np.ndarray):  # Tar emot en frame och skickar till Redis
    """Sätt en frame i Redis"""
    try:
        # Konvertera till JPEG-buffer
        ret, buffer = cv2.imencode(".jpg", img)
        if ret:
            frame_str = buffer.tobytes().decode("latin1")
            # Redis-pipeline för att spara frame och sätt TTL
            redis_key = f"frame_drone_merged"
            with r.pipeline() as pipe:
                pipe.set(redis_key, frame_str)  # Spara bilden
                pipe.expire(redis_key, 60)  # Sätt expiration (60 sekunder)
                pipe.execute()  # Exekvera båda kommandon tillsammans
        else:
            print(f"Misslyckades att koda sammansatta frames")
    except Exception as e:
        print(f"Fel i set_frame: {e}")

### MERGE STREAMS ###
async def stream_drone_frames(drone_id: int):
    """Läser frames från Redis, dekodar, och yieldar råa JPEG bytes."""
    redis_key = f"frame_drone{drone_id}"
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8) # Pre-create dummy frame

    while True:
        frame_to_encode = None
        # Hämta en frame från Redis
        # Ensure r.get runs in a thread as it can block
        frame_data = await asyncio.to_thread(r.get, redis_key)

        if frame_data:
            try:
                # Directly use bytes if decode_responses=False in Redis client
                # If decode_responses=True, you stored latin1 string, so encode back
                # Assuming decode_responses=True based on your original code:
                frame_bytes = frame_data.encode("latin1")

                # If you change Redis client to decode_responses=False:
                # frame_bytes = frame_data # frame_data would already be bytes

                frame_array = np.frombuffer(frame_bytes, dtype=np.uint8)
                frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)

                if frame is not None:
                    frame_to_encode = frame
                else:
                    # Om dekodningen misslyckas, förbered en dummy-bild för kodning
                    print(f"[WARNING] Failed to decode frame from Redis for drone {drone_id}")
                    dummy_frame_copy = dummy_frame.copy() # Use a copy
                    cv2.putText(dummy_frame_copy, f"Drone {drone_id}: invalid frame data",
                                (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                    frame_to_encode = dummy_frame_copy

            except Exception as e:
                 print(f"[ERROR] Error processing frame data from Redis for drone {drone_id}: {e}")
                 dummy_frame_copy = dummy_frame.copy()
                 cv2.putText(dummy_frame_copy, f"Drone {drone_id}: error reading",
                            (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                 frame_to_encode = dummy_frame_copy

        else:
            # Om ingen frame finns i Redis, förbered en dummy-bild för kodning
            dummy_frame_copy = dummy_frame.copy()
            cv2.putText(
                dummy_frame_copy,
                f"Drone {drone_id} not connected",
                (50, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (255, 255, 255),
                2,
            )
            frame_to_encode = dummy_frame_copy

        # Konvertera vald frame (verklig eller dummy) till JPEG bytes
        ret, buffer = cv2.imencode(".jpg", frame_to_encode)
        if not ret:
            # Om kodning misslyckas, logga och hoppa över (yield None eller vänta?)
            # Yielding None might be better handled by the consumer
            print(f"[ERROR] Failed to encode frame to JPEG for drone {drone_id}")
            await asyncio.sleep(0.033) # Vänta lite innan nästa försök
            continue # Skip this iteration

        # *** FIX: Yield ONLY the raw JPEG bytes ***
        yield buffer.tobytes()

        await asyncio.sleep(0.033)  # Ungefär 30 fps
async def merge_stream(drone_ids):
    """Slår ihop videoströmmarna från två drönare."""
    id1, id2 = drone_ids

    # Skapa köer för frames
    left_queue, right_queue = Queue(), Queue()
    stop_event = threading.Event()

    # Skapa async-generatorer för att konsumera drönarströmmar
    frameLeft = stream_drone_frames(id1)
    frameRight = stream_drone_frames(id2)

    # Standardramstorlek
    frame_width = 600
    frame_height = None
    overlap_width = int(frame_width * 0.495)

    # Kamerans GPS-positioner och höjd
    left_camera_location = (57.6900, 11.9800)  # Exempelkoordinater
    right_camera_location = (57.6901, 11.9802)  # Exempelkoordinater
    altitude = 10  # Exempelhöjd
    fov = 83.0
    resolution = (1920, 1080)

    # Starta async uppgifter för att konsumera frames
    asyncio.create_task(consume_async_generator(frameLeft, left_queue, stop_event))
    asyncio.create_task(consume_async_generator(frameRight, right_queue, stop_event))

    try:
        while True:
            left_frame_data = await asyncio.to_thread(left_queue.get)
            right_frame_data = await asyncio.to_thread(right_queue.get)

            if left_frame_data is None or right_frame_data is None:
                print("[INFO] Slut på videoström.")
                stop_event.set()
                break
            # Decode frames till OpenCV

            left_frame_array = np.frombuffer(left_frame_data, dtype=np.uint8)
            left = cv2.imdecode(left_frame_array, cv2.IMREAD_COLOR)

            right_frame_array = np.frombuffer(right_frame_data, dtype=np.uint8)
            right = cv2.imdecode(right_frame_array, cv2.IMREAD_COLOR)
            
            # Kontrollera om dekodningen misslyckades
            if left is None or right is None:
                print("[INFO] Left or right image is None")
                print(f"left: {left}")
                print(f"right: {right}")
                continue  # Skippa om decoding misslyckades
            # Skala bilderna
            if frame_height is None:
                frame_height = int(left.shape[0] * (frame_width / left.shape[1]))

            left = imutils.resize(left, width=frame_width)
            right = imutils.resize(right, width=frame_width)
            right = cv2.resize(right, (frame_width, frame_height))
            left = cv2.resize(left, (frame_width, frame_height))

            # Skapa tom bild för stitching
            stitched_frame = np.zeros((frame_height, frame_width * 2, 3), dtype="uint8")
            stitched_frame[:, :frame_width] = left

            # Mjuk övergång mellan vänster och höger bild
            for i in range(overlap_width):
                alpha = i / overlap_width
                stitched_frame[:, frame_width - overlap_width + i] = cv2.addWeighted(
                    left[:, frame_width - overlap_width + i], 1 - alpha,
                    right[:, i], alpha, 0)

            # Justera höger bild och sätt den till slutet
            right_fixed = cv2.resize(right[:, overlap_width:], (frame_width, frame_height))
            stitched_frame[:, frame_width:] = right_fixed

            # ---- OBJEKTDETEKTION ----
            detections = detect_objects(stitched_frame)

            # ---- GPS-BERÄKNING ----
            gps_positions = []
            if detections.tracker_id is not None:  # Kontrollera om tracker_id finns
                for i, box in enumerate(detections.xyxy):
                    x_center = int((box[0] + box[2]) / 2)
                    y_center = int((box[1] + box[3]) / 2)

                    # Beräkna GPS från vänster och höger kamera
                    gps_left = coordinateMapping.pixelToGps((x_center, y_center), left_camera_location, altitude, fov=fov, resolution=resolution)
                    gps_right = coordinateMapping.pixelToGps((x_center, y_center), right_camera_location, altitude, fov=fov, resolution=resolution)

                    # Viktad medelvärdesberäkning
                    best_gps = get_weighted_gps(x_center, frame_width * 2, gps_left, gps_right)
                    gps_positions.append(best_gps)

                # ---- VISA RESULTAT ----
                labels = [f"ID: {d} GPS: {round(g[0], 6)}, {round(g[1], 6)}" for d, g in zip(detections.tracker_id, gps_positions)]
                position_labels = [f"({int(d[0])}, {int(d[1])})" for d in detections.xyxy]

                annotator = Annotator()  # Skapa en annotator
                annotated_frame = annotator.annotateFrame(frame=stitched_frame, detections=detections, labels=labels, positionLabels=position_labels)
            else:
                annotated_frame = stitched_frame  # Ingen detektion, visa bara sammansatt bild

            # Skicka den sammansatta och annoterade bilden till Redis
            await set_frame(annotated_frame)
            print("Setting stitched video frame in Redis")
            # Visa den annoterade bilden i OpenCV
            # cv2.imshow("Stitched Frame with Detections", annotated_frame)
            # if cv2.waitKey(1) & 0xFF == ord('q'):
            #     break
    finally:
        stop_event.set()
        cv2.destroyAllWindows()

async def main():
    print("[INFO] Startar drönarvideoprocessorer...")
    while True:
        await merge_stream((1, 2))  # Anropa med drone-id 1 och 2

if __name__ == "__main__":
    asyncio.run(main())