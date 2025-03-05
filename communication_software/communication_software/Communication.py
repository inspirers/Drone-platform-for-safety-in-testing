import json
import websockets
from communication_software.CoordinateHandler import Coordinate

class Communication:
    """Handles WebSocket communication with multiple clients, ensuring unique drone coordinate assignments."""
    
    def __init__(self) -> None:
        self.connections = {}  # Stores active WebSocket connections
        self.coordinates = {}  # Stores unique coordinates per client {connection_id: (Coordinate, angle)}
        self.drone_coordinates = []  # Stores all available drone coordinates
        self.client_index = 0  # Tracks which drone coordinate to assign next

    async def send_coordinates_websocket(self, ip: str, droneOrigins: list, angles: list) -> None:
        """Starts the WebSocket server and stores drone coordinates."""
        print(f"Initializing WebSocket on IP: {ip}")

        # Store transformed drone coordinates
        self.drone_coordinates = [
            (self.transform_coordinates(coord, angle)) for coord, angle in zip(droneOrigins, angles)
        ]

        # Start WebSocket server
        server = await websockets.serve(self.webs_server, ip, 14500)
        print("WebSocket server started.")
        await server.wait_closed()

    def transform_coordinates(self, coordinates: Coordinate, angle: int) -> tuple:
        """Transforms coordinates into the required string format"""
        lat = str(coordinates.lat)[0:9] 
        lng = str(coordinates.lng)[0:9]  
        alt = str(coordinates.alt)[0:2]  
        angle = str(angle) 

        # Return as tuple
        return (lat, lng, alt, angle)

    async def webs_server(self, ws: websockets.WebSocketServerProtocol) -> None:
        """Handles WebSocket connections."""
        print("Client connected.")
        connection_id = str(id(ws))  #Create a unique connection ID
        self.connections[connection_id] = ws  # Store connection

        # Assign a unique drone coordinate to ech client
        available_coords = [coord for coord in self.drone_coordinates if coord not in self.coordinates.values()]
        
        if available_coords:
            assigned_coord = available_coords[0]  
        else:
            assigned_coord = self.drone_coordinates[self.client_index % len(self.drone_coordinates)]
            self.client_index += 1 

        self.coordinates[connection_id] = assigned_coord
        print(f"Assigned coordinate {assigned_coord} to client {connection_id}")

        try:
            while True:
                data = await ws.recv()
                print(f"Received from {connection_id}: {data}")  # Debugging received data
                await self.on_message(data, connection_id)  # Handle incoming message
        
        except websockets.exceptions.ConnectionClosedError:
            print(f"Client {connection_id} disconnected.")
        finally:
            self.cleanup_connection(connection_id)

    def cleanup_connection(self, connection_id: str) -> None:
        """Remove client and connected coordinates when a client disconnects."""
        self.connections.pop(connection_id, None)
        self.coordinates.pop(connection_id, None)
        print(f"Connection {connection_id} removed.")

    async def on_message(self, frame: str, connection_id: str) -> None:
        """Handles received messages."""
        print(f"Received from {connection_id}: {frame}")
        
        if frame.startswith("REQ/COORDS"):
            await self.send_coords(connection_id)  # Send coordinates to requesting client
        else:
            print(f"Unknown command from {connection_id}: {frame}")

    async def send_coords(self, connection_id: str) -> None:
        """Sends assigned coordinates for a specific connection."""
        if connection_id in self.coordinates:
            lat, lng, alt, angle = self.coordinates[connection_id]

            message = json.dumps({
                "lat": lat,
                "lng": lng,
                "alt": alt,
                "angle": angle
            })
            print(f"Sending to {connection_id}: {message}")  # Debugging message before sending
            try:
                await self.connections[connection_id].send(message)
                print(f"Sent to {connection_id}: {message}")
            except websockets.exceptions.ConnectionClosed:
                print(f"Connection {connection_id} closed, removing.")
                self.cleanup_connection(connection_id)
        else:
            print(f"No coordinates found for {connection_id}")
