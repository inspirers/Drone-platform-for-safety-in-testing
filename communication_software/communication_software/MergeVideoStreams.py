# This file contains the class for merging video streams
import numpy as np
import cv2
import imutils
import time
import threading
from queue import Queue
from ultralytics import YOLO
import supervision as sv
from annotator import Annotator
import coordinateMapping  
import frontendWebsocket
import asyncio
import redis
import redis.exceptions

## ---- HELPER FUNCTIONS ----

async def consume_async_generator(gen, queue, stop_event):
    """Consume an async generator and push frames into a queue."""
    async for frame in gen:
        if stop_event.is_set():
            break
        queue.put(frame)
    queue.put(None)  # Signal the end of the stream

def detect_objects(frame):
    results = model.track(frame, persist=True, conf=0.75, imgsz=448)
    detections = sv.Detections.from_ultralytics(results[0])
    return detections

def capture_frames(stream, queue, stop_event):
    while not stop_event.is_set():
        ret, frame = stream.read()
        if not ret:
            queue.put(None)
            break
        queue.put(frame)

def get_weighted_gps(pixel_x, frame_width, left_gps, right_gps):
    """ Beräknar en viktad GPS-position baserat på objektets position i bilden. """
    alpha = pixel_x / frame_width  # Normaliserad position (0 = vänster, 1 = höger)
    gps_lat = left_gps[0] * (1 - alpha) + right_gps[0] * alpha
    gps_lon = left_gps[1] * (1 - alpha) + right_gps[1] * alpha
    return (gps_lat, gps_lon)

async def set_frame(self, img: np.ndarray): # tar en image frame
        try:
            # Convert the image to a buffer (JPEG format)
            ret, buffer = cv2.imencode(".jpg", img)
            if ret:
                frame_str = buffer.tobytes().decode("latin1")
                # Redis pipeline for storing the frame and setting TTL
                redis_key = f"frame_drone_merged"
                with r.pipeline() as pipe:
                    pipe.set(redis_key, frame_str)  # Save the frame
                    pipe.expire(redis_key, 60)     # Set expiration (60 seconds)
                    pipe.execute()                # Execute both commands together
            else:
                print(f"Failed to encode merged frames")
        except Exception as e:
            print(f"Error in set_frame: {e}")

### MERGE STREAMS ###

# TODO: Function that takes in two frames och return merged

# TODO: merged frame ska matas in i set_frame (frame by frame, viktigt!)


async def stream_drone_frames(drone_id):
    """Dummy version for testing. Replace with actual Redis stream."""
    while True:
        dummy = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(dummy, f"Drone {drone_id}", (50, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        ret, buffer = cv2.imencode(".jpg", dummy)
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
        )
        await asyncio.sleep(1 / 30)  # 30 fps


async def merge_stream(drone_ids):
    
    id1, id2 = drone_ids

    model = YOLO("yolov8s.pt")

    # Create queues for frames
    left_queue, right_queue = Queue(), Queue()
    stop_event = threading.Event()

    # Create async generators
    frameLeft = stream_drone_frames(id1)
    frameRight = stream_drone_frames(id2)

    frame_width = 600
    frame_height = None
    overlap_width = int(frame_width * 0.495)

    # Kamerornas GPS-positioner och höjd
    left_camera_location = (57.6900, 11.9800)  # Exempelkoordinater
    right_camera_location = (57.6901, 11.9802)  # Exempelkoordinater
    altitude = 10  # Exempelvärde
    fov = 83.0
    resolution = (1920, 1080)

    # Start async tasks to consume the generators
    asyncio.create_task(consume_async_generator(frameLeft, left_queue, stop_event))
    asyncio.create_task(consume_async_generator(frameRight, right_queue, stop_event))

    # Process frames from the queues
    try:
        while True:

            left = await asyncio.to_thread(left_queue.get)
            right = await asyncio.to_thread(right_queue.get)


            if left is None or right is None:   
                print("[INFO] End of video stream reached.")
                stop_event.set()
                break
    
            if frame_height is None:
                frame_height = int(left.shape[0] * (frame_width / left.shape[1]))

            # Decode and process frames
            left = cv2.imdecode(np.frombuffer(left, np.uint8), cv2.IMREAD_COLOR)
            right = cv2.imdecode(np.frombuffer(right, np.uint8), cv2.IMREAD_COLOR)

            # Scale and match size
            left = imutils.resize(left, width=frame_width)
            right = imutils.resize(right, width=frame_width)
            right = cv2.resize(right, (frame_width, frame_height))
            left = cv2.resize(left, (frame_width, frame_height))

            # Empty frame for stitching
            stitched_frame = np.zeros((frame_height, frame_width * 2, 3), dtype="uint8")

            stitched_frame[:, :frame_width] = left
            for i in range(overlap_width):
                alpha = i / overlap_width
                stitched_frame[:, frame_width - overlap_width + i] = cv2.addWeighted(
                    left[:, frame_width - overlap_width + i], 1 - alpha,
                    right[:, i], alpha, 0)

            # Säkerställ att den högra delen har rätt storlek
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

                annotator = Annotator()  # Create an instance of Annotator
                annotated_frame = annotator.annotateFrame(frame=stitched_frame, detections=detections, labels=labels, positionLabels=position_labels)
            else:
                annotated_frame = stitched_frame  # Ingen detektion, visa bara sammansatt bild

            cv2.imshow("Stitched Frame with Detections", annotated_frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        stop_event.set()
        cv2.destroyAllWindows()



async def main():
    print("[INFO] Starting drone video processors...")
    while True:
        await merge_stream((1, 2))





