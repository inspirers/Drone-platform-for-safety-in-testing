import cv2
from ultralytics import YOLO
import numpy as np
from eric_merge import process_frame, printID

# Load the two videos
video1 = cv2.VideoCapture('/home/viggof/Drone-platform-for-safety-in-testing/communication_software/communication_software/TEST3L (1).mp4')
video2 = cv2.VideoCapture('/home/viggof/Drone-platform-for-safety-in-testing/communication_software/communication_software/TEST3L (2).mp4')
model_filename = '/home/viggof/Drone-platform-for-safety-in-testing/communication_software/communication_software/yolov8n.pt'
model = YOLO(model_filename)

# Get video properties
fps = int(video1.get(cv2.CAP_PROP_FPS))
frame_width = int(video1.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_height = int(video1.get(cv2.CAP_PROP_FRAME_HEIGHT))

# Define output video writer
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter('stitched_video.mp4', fourcc, fps, (frame_width * 2, frame_height))

# Create a Stitcher instance with PANORAMA mode
stitcher = cv2.Stitcher.create(cv2.Stitcher_SCANS)
stitcher.setPanoConfidenceThresh(0.0)

while True:
    ret1, frame1 = video1.read()
    ret2, frame2 = video2.read()

    # Stop when either video ends
    if not ret1 or not ret2:
        break

    # Resize frame2 to match frame1
    frame2 = cv2.resize(frame2, (frame_width, frame_height))

    # Stitch the frames
    status, stitched_frame = stitcher.stitch([frame1, frame2])

    if status == cv2.Stitcher_OK:
        # Write the stitched frame to the output video
        frame, detections = process_frame(frame2, model)
        out.write(stitched_frame)
        cv2.imshow('Stitched Video', stitched_frame)
    else: 
        pass

    # Exit on pressing 'q'
    if cv2.waitKey(int(1000 / fps)) & 0xFF == ord('q'):
        break

# Release resources
video1.release()
video2.release()
out.release()
cv2.destroyAllWindows()
