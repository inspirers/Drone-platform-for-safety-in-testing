from ultralytics import YOLO
import cv2
import supervision as sv
from annotator import Annotator
import numpy as np

stream_url1 = r'/home/viggof/Drone-platform-for-safety-in-testing/communication_software/communication_software/TEST1_R (1).mp4'
stream_url2 = r'/home/viggof/Drone-platform-for-safety-in-testing/communication_software/communication_software/TEST1_R (2).mp4'
model_filename = '/home/viggof/Drone-platform-for-safety-in-testing/communication_software/communication_software/yolov8n.pt'
window_size = (1200, 650)

crop = False
crop_x = (500, 1974)
crop_y = (250, 1080)

annotator = Annotator()

def cropFrame(frame):
    frame = frame[crop_y[0]:crop_y[1], crop_x[0]:crop_x[1]]
    return frame

def printID(detections):
    boxes = detections.xyxy
    track_ids = detections.tracker_id

    if track_ids is not None:
        for box, track_id in zip(boxes, track_ids):
            x1, y1, x2, y2 = box
            pos_x = (x2 - x1) / 2
            pos_y = (y2 - y1) / 2
            print(f'Object {track_id} at ({pos_x:>6.3f}, {pos_y:>6.3f})')
    else:
        for box in boxes:
            x1, y1, x2, y2 = box
            pos_x = (x2 - x1) / 2
            pos_y = (y2 - y1) / 2
            print(f'Object at ({pos_x:>6.3f}, {pos_y:>6.3f})')

def process_frame(frame, model):
    results = model.track(frame, persist=True, tracker='bytetrack.yaml')
    detections = sv.Detections.from_ultralytics(results[0])

    printID(detections)

    labels = [
        f"Object: {model.model.names[class_id]} {confidence:0.2f}"
        for class_id, confidence
        in zip(detections.class_id, detections.confidence)
    ]

    positionLabels = [f"({box[0]:0.2f},{box[1]:0.2f})" for box in detections.xyxy]

    annotated_frame = annotator.annotateFrame(frame=frame, detections=detections, labels=labels, positionLabels=positionLabels)
    return annotated_frame, detections

def main():
    model = YOLO(model_filename)

    cv2.namedWindow('Combined Video', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('Combined Video', window_size[0], window_size[1])
    vid1 = cv2.VideoCapture(stream_url1)
    vid2 = cv2.VideoCapture(stream_url2)

    while True:
        success1, frame1 = vid1.read()
        success2, frame2 = vid2.read()

        if crop:
            frame1 = cropFrame(frame1)
            frame2 = cropFrame(frame2)

        if success1 and success2:
            frame1, detections1 = process_frame(frame1, model)
            frame2, detections2 = process_frame(frame2, model)

            combined_frame = cv2.addWeighted(frame1, 0.5, frame2, 0.5, 0)
            cv2.imshow('Combined Video', combined_frame)

        if cv2.waitKey(1) == ord('q'):
            break

    vid1.release()
    vid2.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()