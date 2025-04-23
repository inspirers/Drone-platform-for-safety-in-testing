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

# Global YOLO model (to avoid creating it every time)
model = YOLO("models/best.pt")

redis_url = os.environ.get("REDIS_URL", "localhost")
# Redis connection (create a Redis client if not exists)
r = redis.StrictRedis(host=redis_url, port=6379, db=0, decode_responses=True)

## ---- HELPER FUNCTIONS ----

async def consume_async_generator(gen, queue: Queue, stop_event: threading.Event):
    """
    Consume an asynchronous generator and push frames into a queue.

    Args:
        gen (AsyncGenerator): The async generator yielding frames.
        queue (Queue): Queue to store the frames.
        stop_event (threading.Event): Event to stop the loop.
    """
    async for frame in gen:
        if stop_event.is_set():
            break
        queue.put(frame)
    queue.put(None)  # Signal the end of the stream

def detect_objects(frame: np.ndarray) -> sv.Detections:
    """
    Run YOLO for object detection on a frame.

    Args:
        frame (np.ndarray): Input image frame.

    Returns:
        sv.Detections: Detected objects.
    """
    results = model.track(frame, persist=True, conf=0.10, imgsz=1280)
    detections = sv.Detections.from_ultralytics(results[0])
    return detections

def get_weighted_gps(pixel_x: int, frame_width: int, left_gps: tuple, right_gps: tuple) -> tuple:
    """
    Calculate a weighted GPS position based on object position in the image.

    Args:
        pixel_x (int): X coordinate of the object in pixels.
        frame_width (int): Width of the image frame.
        left_gps (tuple): GPS coordinate of the left camera.
        right_gps (tuple): GPS coordinate of the right camera.

    Returns:
        tuple: Weighted GPS position (latitude, longitude).
    """
    alpha = pixel_x / frame_width
    gps_lat = left_gps[0] * (1 - alpha) + right_gps[0] * alpha
    gps_lon = left_gps[1] * (1 - alpha) + right_gps[1] * alpha
    return (gps_lat, gps_lon)

async def set_frame(img: np.ndarray):
    """
    Store a frame in Redis as JPEG.

    Args:
        img (np.ndarray): Image to store.
    """
    try:
        ret, buffer = cv2.imencode(".jpg", img)
        if ret:
            frame_str = buffer.tobytes().decode("latin1")
            redis_key = f"frame_drone_merged"
            with r.pipeline() as pipe:
                pipe.set(redis_key, frame_str)
                pipe.expire(redis_key, 60)
                pipe.execute()
        else:
            print(f"Failed to encode merged frames")
    except Exception as e:
        print(f"Error in set_frame: {e}")

### MERGE STREAMS ###

async def stream_drone_frames(drone_id: int):
    """
    Read frames from Redis, decode and yield raw JPEG bytes.

    Args:
        drone_id (int): Identifier for the drone.

    Yields:
        bytes: JPEG encoded frame.
    """
    redis_key = f"frame_drone{drone_id}"
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    while True:
        frame_to_encode = None
        frame_data = await asyncio.to_thread(r.get, redis_key)

        if frame_data:
            try:
                frame_bytes = frame_data.encode("latin1")
                frame_array = np.frombuffer(frame_bytes, dtype=np.uint8)
                frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)

                if frame is not None:
                    frame_to_encode = frame
                else:
                    print(f"[WARNING] Failed to decode frame from Redis for drone {drone_id}")
                    dummy_frame_copy = dummy_frame.copy()
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

        ret, buffer = cv2.imencode(".jpg", frame_to_encode)
        if not ret:
            print(f"[ERROR] Failed to encode frame to JPEG for drone {drone_id}")
            await asyncio.sleep(0.033)
            continue

        yield buffer.tobytes()
        await asyncio.sleep(0.033)

async def merge_stream(drone_ids: tuple):
    """
    Merge video streams from two drones, detect objects, and save annotated output.

    Args:
        drone_ids (tuple): Tuple containing two drone IDs.
    """
    id1, id2 = drone_ids

    left_queue, right_queue = Queue(), Queue()
    stop_event = threading.Event()

    frameLeft = stream_drone_frames(id1)
    frameRight = stream_drone_frames(id2)

    frame_width = 600
    frame_height = None
    overlap_width = int(frame_width * 0.495)

    left_camera_location = (57.6900, 11.9800)
    right_camera_location = (57.6901, 11.9802)
    altitude = 10
    fov = 83.0
    resolution = (1920, 1080)

    asyncio.create_task(consume_async_generator(frameLeft, left_queue, stop_event))
    asyncio.create_task(consume_async_generator(frameRight, right_queue, stop_event))

    try:
        while True:
            left_frame_data = await asyncio.to_thread(left_queue.get)
            right_frame_data = await asyncio.to_thread(right_queue.get)

            if left_frame_data is None or right_frame_data is None:
                print("[INFO] End of video stream.")
                stop_event.set()
                break

            left_frame_array = np.frombuffer(left_frame_data, dtype=np.uint8)
            left = cv2.imdecode(left_frame_array, cv2.IMREAD_COLOR)

            right_frame_array = np.frombuffer(right_frame_data, dtype=np.uint8)
            right = cv2.imdecode(right_frame_array, cv2.IMREAD_COLOR)

            if left is None or right is None:
                print("[INFO] Left or right image is None")
                continue

            if frame_height is None:
                frame_height = int(left.shape[0] * (frame_width / left.shape[1]))

            left = imutils.resize(left, width=frame_width)
            right = imutils.resize(right, width=frame_width)
            right = cv2.resize(right, (frame_width, frame_height))
            left = cv2.resize(left, (frame_width, frame_height))

            stitched_frame = np.zeros((frame_height, frame_width * 2, 3), dtype="uint8")
            stitched_frame[:, :frame_width] = left

            for i in range(overlap_width):
                alpha = i / overlap_width
                stitched_frame[:, frame_width - overlap_width + i] = cv2.addWeighted(
                    left[:, frame_width - overlap_width + i], 1 - alpha,
                    right[:, i], alpha, 0)

            right_fixed = cv2.resize(right[:, overlap_width:], (frame_width, frame_height))
            stitched_frame[:, frame_width:] = right_fixed

            detections = detect_objects(stitched_frame)

            gps_positions = []
            if detections.tracker_id is not None:
                for i, box in enumerate(detections.xyxy):
                    x_center = int((box[0] + box[2]) / 2)
                    y_center = int((box[1] + box[3]) / 2)

                    gps_left = coordinateMapping.pixelToGps((x_center, y_center), left_camera_location, altitude, fov=fov, resolution=resolution)
                    gps_right = coordinateMapping.pixelToGps((x_center, y_center), right_camera_location, altitude, fov=fov, resolution=resolution)

                    best_gps = get_weighted_gps(x_center, frame_width * 2, gps_left, gps_right)
                    gps_positions.append(best_gps)

                labels = [f"ID: {d} GPS: {round(g[0], 6)}, {round(g[1], 6)}" for d, g in zip(detections.tracker_id, gps_positions)]
                position_labels = [f"({int(d[0])}, {int(d[1])})" for d in detections.xyxy]

                annotator = Annotator()
                annotated_frame = annotator.annotateFrame(frame=stitched_frame, detections=detections, labels=labels, positionLabels=position_labels)
            else:
                annotated_frame = stitched_frame

            annotated_frame = cv2.resize(annotated_frame, (640, 380))
            print(annotated_frame.shape)
            await set_frame(annotated_frame)
            print("Setting stitched video frame in Redis")

    finally:
        stop_event.set()
        cv2.destroyAllWindows()

async def main():
    """Start drone video processors."""
    print("[INFO] Starting drone video processors...")
    while True:
        await merge_stream((1, 2))

if __name__ == "__main__":
    asyncio.run(main())
