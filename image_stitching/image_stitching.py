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
from frontendWebsocket import stream_drone_frames

## ---- HELPER FUNCTIONS ----import time
from asyncio import Event

# Global YOLO model (för att inte skapa den varje gång)
model = YOLO("best.pt")

# Redis connection (skapa en Redis-klient om den inte finns)
r = redis.StrictRedis(host='redis', port=6379, db=0, decode_responses=True)

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

async def merge_stream(drone_ids):
    id1, id2 = drone_ids
    left_queue, right_queue = Queue(), Queue()
    stop_event = Event()

    frameLeft = stream_drone_frames(id1)
    frameRight = stream_drone_frames(id2)

    frame_width = 448
    frame_height = None
    overlap_width = int(frame_width * 0.495)

    left_camera_location = (57.6900, 11.9800)
    right_camera_location = (57.6901, 11.9802)
    altitude = 10
    fov = 83.0
    resolution = (1920, 1080)

    asyncio.create_task(consume_async_generator(frameLeft, left_queue, stop_event))
    asyncio.create_task(consume_async_generator(frameRight, right_queue, stop_event))

    frame_counter = 0

    try:
        while True:
            left_frame_data = await left_queue.get()
            right_frame_data = await right_queue.get()

            if left_frame_data is None or right_frame_data is None:
                print("[INFO] Slut på videoström.")
                stop_event.set()
                break

            left = cv2.imdecode(np.frombuffer(left_frame_data, np.uint8), cv2.IMREAD_COLOR)
            right = cv2.imdecode(np.frombuffer(right_frame_data, np.uint8), cv2.IMREAD_COLOR)

            if left is None or right is None:
                print("[INFO] Left or right image is None")
                continue

            if frame_height is None:
                aspect_ratio = left.shape[0] / left.shape[1]
                frame_height = int(frame_width * aspect_ratio)

            left = cv2.resize(left, (frame_width, frame_height))
            right = cv2.resize(right, (frame_width, frame_height))

            stitched_frame = np.zeros((frame_height, frame_width * 2, 3), dtype="uint8")
            stitched_frame[:, :frame_width] = left

            for i in range(overlap_width):
                alpha = i / overlap_width
                stitched_frame[:, frame_width - overlap_width + i] = cv2.addWeighted(
                    left[:, frame_width - overlap_width + i], 1 - alpha,
                    right[:, i], alpha, 0)

            right_fixed = right[:, overlap_width:]
            stitched_frame[:, frame_width:] = cv2.resize(right_fixed, (frame_width, frame_height))

            # === ROI-baserad detektion (sista 60% av bilden) ===
            roi_y_start = int(frame_height * 0.4)
            roi = stitched_frame[roi_y_start:, :]
            detections = await asyncio.to_thread(detect_objects, roi)

            gps_positions = []
            if detections.tracker_id is not None:
                for i, box in enumerate(detections.xyxy):
                    x_center = int((box[0] + box[2]) / 2)
                    y_center = int((box[1] + box[3]) / 2) + roi_y_start  # Justera y för ROI

                    gps_left = coordinateMapping.pixelToGps(
                        (x_center, y_center), left_camera_location, altitude, fov=fov, resolution=resolution
                    )
                    gps_right = coordinateMapping.pixelToGps(
                        (x_center, y_center), right_camera_location, altitude, fov=fov, resolution=resolution
                    )

                    best_gps = get_weighted_gps(x_center, frame_width * 2, gps_left, gps_right)
                    gps_positions.append(best_gps)

                labels = [f"ID: {d} GPS: {round(g[0], 6)}, {round(g[1], 6)}" for d, g in zip(detections.tracker_id, gps_positions)]
                position_labels = [f"({int(d[0])}, {int(d[1])})" for d in detections.xyxy]

                annotator = Annotator()
                annotated_frame = annotator.annotateFrame(
                    frame=stitched_frame, detections=detections,
                    labels=labels, positionLabels=position_labels
                )
            else:
                annotated_frame = stitched_frame

            frame_counter += 1
            if frame_counter % 3 == 0:
                try:
                    ret, buffer = cv2.imencode(".jpg", annotated_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
                    if ret:
                        frame_str = buffer.tobytes().decode("latin1")
                        redis_key = f"frame_drone_merged"
                        with r.pipeline() as pipe:
                            pipe.set(redis_key, frame_str)
                            pipe.expire(redis_key, 60)
                            pipe.execute()
                        print("Setting stitched video frame in Redis")
                    else:
                        print("JPEG encoding failed")
                except Exception as e:
                    print(f"Redis error: {e}")

            await asyncio.sleep(0.1)  # ~10 FPS
    finally:
        stop_event.set()
        cv2.destroyAllWindows()
