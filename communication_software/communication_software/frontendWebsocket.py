import asyncio
import random
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn
from typing import List

app = FastAPI()

MAX_DRONES = 1 # Starts from 0 so 1 will be 2 drones etc.

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


@app.websocket("/api/v1/drone/coordinates")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:

            drone_data = {
                "latitude": round(random.uniform(40.0, 50.0), 6),
                "longitude": round(random.uniform(-80.0, -70.0), 6),
                "altitude": round(random.uniform(100, 500), 2),
                "drone_id": random.randint(0, MAX_DRONES),
            }

            await websocket.send_json(drone_data)
            print(f"Sent: {drone_data}")

            await asyncio.sleep(1)  # only for test env
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("Client disconnected")


@app.websocket("/api/v1/drone/status")
async def websocket_status_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            status_data = {
                "status": random.choice(["flying", "idle", "landing", "error"]),
                "drone_id": random.randint(0, MAX_DRONES),
                "errors": (["GPS Signal Lost"] if random.random() < 0.1 else []),
            }

            await websocket.send_json(status_data)
            print(f"Sent status data: {status_data}")

            await asyncio.sleep(3)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("Client disconnected from status")


@app.websocket("/api/v1/drone/battery")
async def websocket_battery_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            battery_data = {
                "battery_level": round(random.uniform(0, 100), 2),
                "drone_id": random.randint(0, MAX_DRONES),
                "voltage": round(random.uniform(10, 12.6), 2),
                "charging": random.choice([True, False]),
            }

            await websocket.send_json(battery_data)
            print(f"Sent battery data: {battery_data}")

            await asyncio.sleep(2)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("Client disconnected from battery")


@app.get("/api/v1/health")
def health_check():
    return {"status": "ok"}


def run_server():
    uvicorn.run(
        "communication_software.frontendWebsocket:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
