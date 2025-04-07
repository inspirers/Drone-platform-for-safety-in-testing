import json
import websockets
from communication_software.CoordinateHandler import Coordinate
import redis

# redis = redis.Redis(host='redis', port=6379, decode_responses=True)

try:
    r = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)
    r.ping() # Check if the connection is successful
    print("Successfully connected to Redis!")
except redis.exceptions.ConnectionError as e:
    print(f"Error connecting to Redis: {e}")
    exit() # Exit if we can't connect

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
        
        try:
            data = json.loads(frame)

            # Check 1: Is the parsed data a dictionary?
            # Check 2: Does it have the key 'msg_type'? (Using .get is safer than direct access)
            # Check 3: Is the value of 'msg_type' equal to 'Coordinate_request'?
            if isinstance(data, dict) and data.get("msg_type") == "Coordinate_request":
                print(f"Processing JSON Coordinate_request from {connection_id}")
                await self.send_coords(connection_id)  # Send coordinates to requesting client

            # Optional: You could add elif blocks here to handle other msg_types
            elif isinstance(data, dict) and data.get("msg_type") == "Position":
                incoming_position_handler(data)
            elif isinstance(data, dict) and data.get("msg_type") == "Debug":
                msg = data.get("msg")
                print(f"Debug msg: {msg}")
            elif isinstance(data, dict) and data.get("msg_type") == "WEBRTC_Candidate":
                print("Run some candidate func")
            elif isinstance(data, dict) and data.get("msg_type") == "WEBRTC_Offer":
                print("Run some offer func")
            elif isinstance(data, dict) and data.get("msg_type") == "WEBRTC_Answer":
                print("Run some answer func")
            else:
                # It was valid JSON, but not the type we explicitly handle here
                if isinstance(data, dict):
                    print(f"Received known JSON structure but unhandled msg_type: {data.get('msg_type')}")
                else:
                    print(f"Received valid JSON, but it's not a dictionary: {type(data)}")

        except json.JSONDecodeError:
            # The frame was not valid JSON, it might be the old format or something else
            print(f"Received non-JSON message or malformed JSON from {connection_id}. Text data: {frame}")
        except Exception as e:
            # Catch any other unexpected errors during processing
            print(f"An unexpected error occurred processing message from {connection_id}: {e}")

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

def incoming_position_handler(data):
    lat = data.get("latitude")
    long = data.get("longitude")
    altitude = data.get("altitude")
    print(f"Handling incoming position: lat: {long}, long: {lat}, altitude: {altitude}")
    try:
        json_data_string = json.dumps(data)
    except TypeError as e:
        print(f"Error serializing data to JSON: {e}")
        return # Can't store if we can't serialize
    
    try:
        # Use the established Redis connection 'r'
        r.set("position_drone1", json_data_string)
        r.set("position_drone2", json_data_string)
        print(f"Stored position data for drone1 and drone2 in Redis.")
    except redis.exceptions.RedisError as e:
        print(f"Error setting data in Redis: {e}")

