import numpy as np
import cv2
import imutils
import time
import threading
from queue import Queue
from ultralytics import YOLO
import supervision as sv
from annotator import Annotator
import coordinateMapping  # Importera coordinateMapping

# ---- INITIALISERA KAMEROR ----
print("[INFO] starting cameras...")
leftStream = cv2.VideoCapture(r'C:\Users\User\Chalmers\year3\kandidatarbete\prog\yolo_custom_model\TEST2_L.mp4')  # Vänster video
rightStream = cv2.VideoCapture(r'C:\Users\User\Chalmers\year3\kandidatarbete\prog\yolo_custom_model\TEST2_R.mp4')  # Höger video
time.sleep(2.0)

if not leftStream.isOpened() or not rightStream.isOpened():
    print("[ERROR] Could not open video streams.")
    exit()

# ---- INITIALISERA MODELL OCH PARAMETRAR ----
model = YOLO("yolov8s.pt")  # Anpassa med rätt modellfil
annotator = Annotator()

frame_width = 600
frame_height = int(leftStream.get(cv2.CAP_PROP_FRAME_HEIGHT) * (frame_width / leftStream.get(cv2.CAP_PROP_FRAME_WIDTH)))
overlap_width = int(frame_width * 0.495)

# Kamerornas GPS-positioner och höjd
left_camera_location = (57.6900, 11.9800)  # Exempelkoordinater
right_camera_location = (57.6901, 11.9802)  # Exempelkoordinater
altitude = 10  # Exempelvärde
fov = 83.0
resolution = (1920, 1080)

# ---- HJÄLPFUNKTIONER ----
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

# ---- STARTA TRÅDAR FÖR KAMEROR ----
left_queue, right_queue = Queue(), Queue()
stop_event = threading.Event()

left_thread = threading.Thread(target=capture_frames, args=(leftStream, left_queue, stop_event))
right_thread = threading.Thread(target=capture_frames, args=(rightStream, right_queue, stop_event))

left_thread.start()
right_thread.start()

# ---- HUVUDLOOP ----
while True:
    left = left_queue.get()
    right = right_queue.get()

    if left is None or right is None:
        print("[INFO] End of video stream reached.")
        stop_event.set()
        break

    # Skala och matcha storlek
    left = imutils.resize(left, width=frame_width)
    right = imutils.resize(right, width=frame_width)
    right = cv2.resize(right, (frame_width, frame_height))
    left = cv2.resize(left, (frame_width, frame_height))

    # Kontrollera storlek
    print(f"Left frame shape: {left.shape}, Right frame shape: {right.shape}")

    # Skapa en ny bild för sammansättning
    stitched_frame = np.zeros((frame_height, frame_width * 2, 3), dtype="uint8")

    # Sätt in vänster och höger bild med överlappning
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

        annotated_frame = annotator.annotateFrame(frame=stitched_frame, detections=detections, labels=labels, positionLabels=position_labels)
    else:
        annotated_frame = stitched_frame  # Ingen detektion, visa bara sammansatt bild

    cv2.imshow("Stitched Frame with Detections", annotated_frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        stop_event.set()
        break


    
# ---- STÄNG NER PROGRAMMET ----
print("[INFO] cleaning up...")
cv2.destroyAllWindows()
leftStream.release()
rightStream.release()
left_thread.join()
right_thread.join()
