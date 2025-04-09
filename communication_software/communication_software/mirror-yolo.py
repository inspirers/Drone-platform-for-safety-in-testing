import numpy as np
import cv2
import imutils
import time
import threading
from queue import Queue
from ultralytics import YOLO
import supervision as sv
from annotator import Annotator
import coordinateMapping  # Se till att denna fil finns

# Initialize the video streams and allow them to warm up
print("[INFO] starting cameras...")
leftStream = cv2.VideoCapture(r'C:\Users\User\Chalmers\year3\kandidatarbete\prog\yolo_custom_model\TEST2_L.mp4')
rightStream = cv2.VideoCapture(r'C:\Users\User\Chalmers\year3\kandidatarbete\prog\yolo_custom_model\TEST2_R.mp4')
time.sleep(2.0)

# Check if the video streams are opened successfully
if not leftStream.isOpened() or not rightStream.isOpened():
    print("[ERROR] Could not open video streams.")
    exit()

# Initialize YOLO model for object detection
model_filename = r'C:\Users\User\Chalmers\year3\kandidatarbete\prog\Drone-platform-for-safety-in-testing\communication_software\communication_software\yolov8s.pt'
model = YOLO(model_filename)
annotator = Annotator()

# GPS metadata
left_camera_location = (57.6900, 11.9800)
right_camera_location = (57.6901, 11.9802)
altitude = 10
fov = 83.0
resolution = (1920, 1080)

# Get the width and height of the frames
frame_width = 600  # Fixed width after resizing
frame_height = int(leftStream.get(cv2.CAP_PROP_FRAME_HEIGHT) * (frame_width / leftStream.get(cv2.CAP_PROP_FRAME_WIDTH)))

# Calculate the overlap width (49.5% of the frame width)
overlap_width = int(frame_width * 0.495)

# Function to run object detection on a frame
def detect_objects(frame):
    results = model.track(frame, persist=True, conf=0.75, imgsz=448)
    detections = sv.Detections.from_ultralytics(results[0])
    valid_classes = [0, 1]  # person, car
    detections = detections[np.isin(detections.class_id, valid_classes) & (detections.area < 100000)]
    return detections

# Interpolera GPS-koordinater
def get_weighted_gps(pixel_x, frame_width, left_gps, right_gps):
    alpha = pixel_x / frame_width
    gps_lat = left_gps[0] * (1 - alpha) + right_gps[0] * alpha
    gps_lon = left_gps[1] * (1 - alpha) + right_gps[1] * alpha
    return (gps_lat, gps_lon)

# Function to capture frames from a video stream
def capture_frames(stream, queue, stop_event):
    while not stop_event.is_set():
        ret, frame = stream.read()
        if not ret:
            queue.put(None)
            break
        queue.put(frame)

# Create queues for frames
left_queue = Queue()
right_queue = Queue()
stop_event = threading.Event()

# Start threads for capturing frames
left_thread = threading.Thread(target=capture_frames, args=(leftStream, left_queue, stop_event))
right_thread = threading.Thread(target=capture_frames, args=(rightStream, right_queue, stop_event))
left_thread.start()
right_thread.start()

while True:
    left = left_queue.get()
    right = right_queue.get()

    if left is None or right is None:
        print("[INFO] End of video stream reached.")
        stop_event.set()
        break

    left = imutils.resize(left, width=frame_width)
    right = imutils.resize(right, width=frame_width)
    left = cv2.resize(left, (frame_width, frame_height))
    right = cv2.resize(right, (frame_width, frame_height))

    stitched_frame = np.zeros((frame_height, frame_width * 2, 3), dtype="uint8")
    stitched_frame[0:frame_height, 0:frame_width] = left

    for i in range(overlap_width):
        alpha = i / overlap_width
        stitched_frame[0:frame_height, frame_width - overlap_width + i] = cv2.addWeighted(
            left[0:frame_height, frame_width - overlap_width + i], 1 - alpha,
            right[0:frame_height, i], alpha, 0)

    stitched_frame[0:frame_height, frame_width:frame_width + (frame_width - overlap_width)] = right[:, overlap_width:]

    # Object detection
    stitched_detections = detect_objects(stitched_frame)
    gps_positions = []

    if stitched_detections.tracker_id is not None:
        for i, box in enumerate(stitched_detections.xyxy):
            x_center = int((box[0] + box[2]) / 2)
            y_center = int((box[1] + box[3]) / 2)

            gps_left = coordinateMapping.pixelToGps((x_center, y_center), left_camera_location, altitude, fov=fov, resolution=resolution)
            gps_right = coordinateMapping.pixelToGps((x_center, y_center), right_camera_location, altitude, fov=fov, resolution=resolution)

            gps = get_weighted_gps(x_center, frame_width * 2, gps_left, gps_right)
            gps_positions.append(gps)

        labels = [f"ID: {d} GPS: {round(g[0], 6)}, {round(g[1], 6)}" for d, g in zip(stitched_detections.tracker_id, gps_positions)]
        position_labels = [f"({int(d[0])}, {int(d[1])})" for d in stitched_detections.xyxy]

        stitched_annotated = annotator.annotateFrame(
            frame=stitched_frame,
            detections=stitched_detections,
            labels=labels,
            positionLabels=position_labels
        )
    else:
        stitched_annotated = stitched_frame

    cv2.imshow("Stitched Frame with Detections and GPS", stitched_annotated)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        stop_event.set()
        break

print("[INFO] cleaning up...")
cv2.destroyAllWindows()
leftStream.release()
rightStream.release()
left_thread.join()
right_thread.join()
