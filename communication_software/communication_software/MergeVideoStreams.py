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


def your_processing_function(frame):
    # Example: Convert to grayscale
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


async def process_stream(drone_id):
    async for frame in stream_drone_frames(drone_id):
        try:
            # Extract JPEG payload from MJPEG multipart
            jpg = frame.split(b'\r\n\r\n', 1)[1].rsplit(b'\r\n', 1)[0]
            frame_array = np.frombuffer(jpg, dtype=np.uint8)
            bgr_frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)

            if bgr_frame is not None:
                processed = your_processing_function(bgr_frame)
                window_name = f"Drone {drone_id}"
                cv2.imshow(window_name, processed)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        except Exception as e:
            print(f"[ERROR] Processing Drone {drone_id}: {e}")


async def main():
    print("[INFO] Starting drone video processors...")
    await asyncio.gather(
        process_stream(1),  # Left drone
        process_stream(2)   # Right drone
    )


### SEND THE MERGED STREAM TO REDIS PIPELINE (SEND STREAM TO FRONTEND) ###
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


