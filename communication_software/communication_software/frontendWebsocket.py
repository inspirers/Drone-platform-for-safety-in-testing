import asyncio
import random
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
import uvicorn
import cv2
import numpy as np
from datetime import datetime
import os

app = FastAPI()

# ATOS Simulation
class ATOSController:
    def __init__(self):
        self.test_active = False
        self.anomalies = False
        self.drone_data = {
            1: {'lat': 57.705841, 'lng': 11.938096, 'alt': 150, 'speed': 0.0, 'battery': 100.0},
            2: {'lat': 57.705941, 'lng': 11.939096, 'alt': 150, 'speed': 0.0, 'battery': 100.0}
        }

atos = ATOSController()

# Video Generation
async def generate_drone_frames(drone_id):
    while True:
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(frame, f"Drone {drone_id}", (50, 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        _, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

# WebSocket Endpoints
@app.websocket("/api/v1/ws/drone")
async def drone_websocket(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            for drone_id in [1, 2]:
                # Update drone metrics
                atos.drone_data[drone_id].update({
                    'lat': atos.drone_data[drone_id]['lat'] + random.uniform(-0.0001, 0.0001),
                    'lng': atos.drone_data[drone_id]['lng'] + random.uniform(-0.0001, 0.0001),
                    'alt': 150 + random.randint(-5, 5),
                    'speed': random.uniform(0, 15),
                    'battery': max(0, atos.drone_data[drone_id]['battery'] - 0.1)
                })
                
                await websocket.send_json({
                    "drone_id": drone_id,
                    **atos.drone_data[drone_id],
                    "anomaly": atos.anomalies
                })
                await asyncio.sleep(0.5)
                
            # Random anomaly simulation
            if random.random() < 0.02:
                atos.anomalies = not atos.anomalies
    except WebSocketDisconnect:
        print("Drone client disconnected")

@app.websocket("/api/v1/ws/atos")
async def atos_websocket(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            if data.get('command') == 'start':
                atos.test_active = True
                atos.anomalies = False
            elif data.get('command') == 'stop':
                atos.test_active = False
            await websocket.send_json({
                "status": "success",
                "test_active": atos.test_active,
                "anomaly": atos.anomalies
            })
    except WebSocketDisconnect:
        print("ATOS client disconnected")

# Video Endpoints
@app.get("/api/v1/video_feed/drone1")
async def drone1_feed():
    return StreamingResponse(generate_drone_frames(1))

@app.get("/api/v1/video_feed/drone2")
async def drone2_feed():
    return StreamingResponse(generate_drone_frames(2))

@app.get("/api/v1/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

def run_server():
    uvicorn.run(
        "communication_software.frontendWebsocket:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )