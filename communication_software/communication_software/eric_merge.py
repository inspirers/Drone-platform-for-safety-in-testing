from ultralytics import YOLO
import cv2
import supervision as sv

#from annotator import Annotator
# Annotator-klass, från förra året har Annotator importerats från annotator
class Annotator():
    def __init__(self) -> None:
        self.boxAnnotator = sv.BoundingBoxAnnotator(thickness=5)
        self.labelAnnotator = sv.LabelAnnotator(text_scale=1, 
                                                text_position=sv.Position.TOP_LEFT)
        self.positionAnnotator = sv.LabelAnnotator(text_scale=0.5,
                                                   text_position=sv.Position.BOTTOM_LEFT)
    
    def annotateFrame(self, frame, detections, labels, positionLabels):
        frame = self.boxAnnotator.annotate(
            scene=frame,
            detections=detections
        )

        frame = self.labelAnnotator.annotate(
            scene=frame,
            detections=detections,
            labels=labels
        )

        frame = self.positionAnnotator.annotate(
            scene=frame,
            detections=detections,
            labels=positionLabels
        )

        return frame

# URL:er för videoströmmar
#stream_url1 = 'http://192.168.50.123:8080/screen_stream.mjpeg'
#stream_url2 = 'http://192.168.50.123:8080/screen_stream.mjpeg'
stream_url1 = r'/home/viggo_forsell/Drone-platform-for-safety-in-testing/communication_software/communication_software/Chalmers6.m4v'
stream_url2 = r'/home/viggo_forsell/Drone-platform-for-safety-in-testing/communication_software/communication_software/Chalmers6.m4v'
model_filename = '/home/viggo_forsell/Drone-platform-for-safety-in-testing/communication_software/communication_software/best.pt'
window_size = (1200, 650)

# Inställningar för beskärning (om nödvändigt)
crop = False
crop_x = (500, 1974)
crop_y = (250, 1080)

# Annotator-objekt för att visa ramar, etiketter och positioner
annotator = Annotator()

def cropFrame(frame):
    frame = frame[crop_y[0]:crop_y[1], crop_x[0]:crop_x[1]]
    return frame

def printID(detections):
    # Hämta detekteringskoordinater och ID:n
    boxes = detections.xyxy
    track_ids = detections.tracker_id
    

    # Skriv ut position och ID för varje detektering
    for box in zip(boxes): #, track_ids):
        x1, y1, x2, y2 = box[0]
        pos_x = (x2 - x1) / 2
        pos_y = (y2 - y1) / 2
        print(f'Object {"Object"} at ({pos_x:>6.3f}, {pos_y:>6.3f})') # change object to tracker_id

def process_frame(frame, model):
    results = model(frame)
    detections = sv.Detections.from_ultralytics(results[0])

    # Skriv ut ID och positioner för detekteringar
    printID(detections)

    # Skapa etiketter för detekteringar
    labels = [
        f"{"Object"}: {model.model.names[class_id]} {confidence:0.2f}"
        for class_id, confidence #, tracker_id
        in zip(detections.class_id, detections.confidence) #, detections.tracker_id
    ]

    # Skapa positionsetiketter
    positionLabels = [f"({box[0]:0.2f},{box[1]:0.2f})" for box in detections.xyxy]

    # Annotera ramen
    annotated_frame = annotator.annotateFrame(frame=frame, detections=detections, labels=labels, positionLabels=positionLabels)
    return annotated_frame

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
            frame1 = process_frame(frame1, model)
            frame2 = process_frame(frame2, model)

            combined_frame = cv2.hconcat([frame1, frame2])
            cv2.imshow('Combined Video', combined_frame)

        if cv2.waitKey(30) == ord('q'):
            break

    vid1.release()
    vid2.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()