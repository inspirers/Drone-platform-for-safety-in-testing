from ultralytics import YOLO
import cv2
import supervision as sv

import coordinateMapping
from annotator import Annotator

#stream_url = 'http://192.168.50.123:8080/screen_stream.mjpeg'
stream_url = 'chalmers2.mp4'
model_filename = 'best.pt'
window_size = (1200, 650)

# set to crop frames
crop = False
crop_x = (500, 1974)
crop_y = (250, 1080)

# set location info manually
cameraLocation = (40.787876, -77.896642)
altitude = 25.0  
fov = 83 
resolution = (1250, 750)  

# annotator object to show boxes, labels, positions
annotator = Annotator()
            
def printID(detections):
    # get detection coordinates and ids
    boxes = detections.xyxy
    track_ids = detections.tracker_id

    # print location and id of each detection
    for box, track_id in zip(boxes, track_ids):
        x1, y1, x2, y2 = box
        pos_x = (x2-x1)/2
        pos_y = (y2-y1)/2
        print(f'Object {track_id} at ({pos_x:>6.3f}, {pos_y:>6.3f})') 

def cropFrame(frame):
    frame = frame[crop_y[0]:crop_y[1], crop_x[0]:crop_x[1]]
    return frame

def main():
    model = YOLO(model_filename)

    cv2.namedWindow('video', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('video', window_size[0], window_size[1])
    vid = cv2.VideoCapture(stream_url)

    while True:
        success, frame = vid.read()
        if crop:
            cropFrame(frame)
        if success: 
            results = model.track(frame, persist=True, conf=0.50, imgsz=448)

            # use supervision library to simplify working with results object
            detections = sv.Detections.from_ultralytics(results[0])

            # filtering conditions can be composed
            # filters out vehicle detections that are too large 
            # these are arbitrary just to show example
            detections = detections[((detections.class_id == 1) & (detections.area < 100000)) |
                                    (detections.class_id == 0)]

            printID(detections)

            # get count of objects of different classes
            # TODO: do something when this exceeds threshold
            personCount = len(detections[detections.class_id == 0])
            vehicleCount = len(detections[detections.class_id == 1])

            # get pixel coords of center of each detection
            positions = [
                (int((position[0] + position[2]) / 2), int((position[1] + position[3]) / 2))
                for position
                in detections.xyxy
            ]

            # calculate gps coords of each detection
            gpsCoords = [
                coordinateMapping.pixelToGps(pixel=position, cameraLocation=cameraLocation, 
                                altitude=altitude, fov=fov,
                                resolution=resolution)
                for position
                in positions
            ]

            # create detection labels
            labels = [
                f"{tracker_id}: {model.model.names[class_id]} {confidence:0.2f}"
                for class_id, confidence, tracker_id
                in zip(detections.class_id, detections.confidence, detections.tracker_id)
            ]

            # create position labels
            positionLabels = [f"({gpsCoord[0]:0.5f},{gpsCoord[1]:0.5f})" for gpsCoord in gpsCoords]

            # annotate frame
            annotated_frame = annotator.annotateFrame(frame=frame, detections=detections,
                                            labels=labels, positionLabels=positionLabels)

        cv2.imshow('video', annotated_frame)
        # run until quit key pressed
        if cv2.waitKey(30) == ord('q'):
            break

    vid.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
