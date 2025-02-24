import asyncio
import random
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn
from typing import List

app = FastAPI()


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


@app.websocket("/api/v1/ws/drone")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            
            drone_data = {
                "latitude": round(random.uniform(40.0, 50.0), 6),
                "longitude": round(random.uniform(-80.0, -70.0), 6),
                "altitude": round(random.uniform(100, 500), 2)
            }
            
            await websocket.send_json(drone_data)
            print(f"Sent: {drone_data}")

            await asyncio.sleep(1)  # Wait 1 second before sending again
    # await manager.connect(websocket)
    # try:
    #     while True:
    #         data = await websocket.receive_text()
    #         print(f"Received data: {data}")
    #         await manager.broadcast(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("Client disconnected")


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
