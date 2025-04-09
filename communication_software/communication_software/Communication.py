from datetime import time
import json
import websockets
from websockets import WebSocketServerProtocol
from communication_software.CoordinateHandler import Coordinate
import threading
import cv2
import asyncio
import redis
from aiortc import RTCSessionDescription, RTCPeerConnection, RTCIceCandidate

try:
    r = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)
    r.ping()
    print("Successfully connected to Redis (Communication Server)!")
except redis.exceptions.ConnectionError as e:
    print(f"Error connecting to Redis (Communication Server): {e}")
    exit()

COMMAND_CHANNEL = "drone_commands"

class Communication:
    def __init__(self) -> None:
        self.connections = {}  # Active WebSocket connections
        self.coordinates = {}  # Coordinates for each client
        self.peer_connections = {}  # RTCPeerConnections per client
        self.drone_coordinates = []  # List of drone coordinates
        self.client_index = 0  # Tracks which coordinate to assign next
        self.video_feeds = {}  # Video streams per connection

        self.redis_listener_stop_event = threading.Event()
        self.redis_listener_task = None

    async def send_coordinates_websocket(self, ip: str, droneOrigins: list, angles: list) -> None:
        """Starts WebSocket server and initializes drone coordinates."""
        print(f"Initializing WebSocket on IP: {ip}")
        self.drone_coordinates = [
            (self.transform_coordinates(coord, angle)) for coord, angle in zip(droneOrigins, angles)
        ]
        server = await websockets.serve(self.webs_server, ip, 14500)
        print("WebSocket server started.")

        """Listens for messages on the specified Redis channel in a blocking loop."""
        print(f"[REDIS THREAD] Listener thread started for channel '{COMMAND_CHANNEL}'.")
        pubsub = None
        listener_redis_conn = None
        while not self.redis_listener_stop_event.is_set(): # Loop until stop event is set
            try:

                listener_redis_conn = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)
                listener_redis_conn.ping() # Verify connection
                pubsub = listener_redis_conn.pubsub(ignore_subscribe_messages=True)
                pubsub.subscribe(COMMAND_CHANNEL)
                print(f"[REDIS THREAD] Subscribed successfully to '{COMMAND_CHANNEL}'. Waiting...")

                # Blocking listen loop
                for message in pubsub.listen():
                    if self.redis_listener_stop_event.is_set():
                        print("[REDIS THREAD] Stop event detected, exiting listen loop.")
                        break
                    # message['data'] will be decoded string if decode_responses=True
                    self.process_redis_command(message['data'])

                # If loop exits normally (e.g., stop_event set), break outer loop too
                break

            except redis.exceptions.ConnectionError as e:
                print(f"[REDIS THREAD] Connection error: {e}. Retrying in 5 seconds...")
                if pubsub: pubsub.close()
                if listener_redis_conn: listener_redis_conn.close()
                pubsub = None
                listener_redis_conn = None
                time.sleep(5) # Wait before attempting to reconnect
            except Exception as e:
                print(f"[REDIS THREAD] Unexpected error in listener loop: {e}. Stopping thread.")
                # Consider if retry is appropriate for other errors
                break # Exit outer loop on unexpected errors
            finally:
                # Ensure cleanup even if loop breaks unexpectedly
                if pubsub:
                    try: pubsub.unsubscribe(COMMAND_CHANNEL)
                    except: pass # Ignore errors during cleanup
                    try: pubsub.close()
                    except: pass
                if listener_redis_conn:
                    try: listener_redis_conn.close()
                    except: pass

        print("[REDIS THREAD] Listener thread finished.")

        await server.wait_closed()

    def transform_coordinates(self, coordinates: Coordinate, angle: int) -> tuple:
        """Transforms coordinates into required format."""
        lat = str(coordinates.lat)[:9]
        lng = str(coordinates.lng)[:9]
        alt = str(coordinates.alt)[:2]
        angle = str(angle)
        return (lat, lng, alt, angle)

    def redis_command_listener(self,redis_client, channel, stop_event, instance=None):
        """Listens for messages on the specified Redis channel in a blocking loop."""
        print(f"[REDIS THREAD] Listener thread started for channel '{channel}'.")
        pubsub = None
        listener_redis_conn = None
        while not stop_event.is_set(): # Loop until stop event is set
            try:
                # Create a connection specifically for this thread is often safer
                # Ensure decode_responses=True for easier handling in process_redis_command
                listener_redis_conn = redis.Redis(
                    host=redis_client.connection_pool.connection_kwargs.get('host', 'localhost'),
                    port=redis_client.connection_pool.connection_kwargs.get('port', 6379),
                    db=redis_client.connection_pool.connection_kwargs.get('db', 0),
                    decode_responses=True # Recommended
                )
                r = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)


                listener_redis_conn.ping() # Verify connection
                pubsub = listener_redis_conn.pubsub(ignore_subscribe_messages=True)
                pubsub.subscribe(channel)
                print(f"[REDIS THREAD] Subscribed successfully to '{channel}'. Waiting...")

                # Blocking listen loop
                for message in pubsub.listen():
                    if stop_event.is_set():
                        print("[REDIS THREAD] Stop event detected, exiting listen loop.")
                        break
                    # message['data'] will be decoded string if decode_responses=True
                    self.process_redis_command(self,message['data'], instance)

                # If loop exits normally (e.g., stop_event set), break outer loop too
                break

            except redis.exceptions.ConnectionError as e:
                print(f"[REDIS THREAD] Connection error: {e}. Retrying in 5 seconds...")
                if pubsub: pubsub.close()
                if listener_redis_conn: listener_redis_conn.close()
                pubsub = None
                listener_redis_conn = None
                time.sleep(5) # Wait before attempting to reconnect
            except Exception as e:
                print(f"[REDIS THREAD] Unexpected error in listener loop: {e}. Stopping thread.")
                # Consider if retry is appropriate for other errors
                break # Exit outer loop on unexpected errors
            finally:
                # Ensure cleanup even if loop breaks unexpectedly
                if pubsub:
                    try: pubsub.unsubscribe(channel)
                    except: pass # Ignore errors during cleanup
                    try: pubsub.close()
                    except: pass
                if listener_redis_conn:
                    try: listener_redis_conn.close()
                    except: pass

        print("[REDIS THREAD] Listener thread finished.")

    def process_redis_command(self, message_data):
        """Processes command messages received from the Redis channel."""
        # 'instance' would be 'self' from the class if passed, allowing
        # interaction with the main object if needed (using thread-safe methods)
        print(f"\n[REDIS SUB] Raw Command Data Received (type: {type(message_data)}): {message_data}")
        try:
            data = json.loads(str(message_data))

            target_drone_id = data.get("target_drone_id")
            command = data.get("command")
            payload = data.get("payload") # Access the nested payload
            timestamp = data.get("timestamp")

            print(f"[REDIS SUB] Processing Command: Drone={target_drone_id}, Cmd='{command}', Payload={payload}, TS={timestamp}")
            response = {
                "msg_type": command
            }
            self.connections[target_drone_id-1].send(json.dumps(response))
            print(f"[REDIS SUB] Finished processing command for drone {target_drone_id}.")
            # ----------------------------------------------------------

        except json.JSONDecodeError:
            print(f"[REDIS SUB] ERROR: Failed to decode JSON: {message_data}")
        except Exception as e:
            print(f"[REDIS SUB] ERROR: Unexpected error processing command: {e}")

    async def webs_server(self, ws: WebSocketServerProtocol) -> None:
        """Handles WebSocket connections."""
        print("Client connected.")
        connection_id = str(id(ws))
        self.connections[connection_id] = ws

        # Assign unique drone coordinate
        available_coords = [coord for coord in self.drone_coordinates if coord not in self.coordinates.values()]
        assigned_coord = available_coords[0] if available_coords else self.drone_coordinates[self.client_index % len(self.drone_coordinates)]
        self.coordinates[connection_id] = assigned_coord
        self.client_index += 1
        print(f"Assigned coordinate {assigned_coord} to client {connection_id}")

        try:
            while True:
                data = await ws.recv()
                print(f"Received from {connection_id}: {data}")
                await self.on_message(data, connection_id)
        except websockets.exceptions.ConnectionClosedError:
            print(f"Client {connection_id} disconnected.")
        finally:
            self.cleanup_connection(connection_id)

    async def on_message(self, frame: str, connection_id: str) -> None:
        """Processes incoming messages."""
        try:
            data = json.loads(frame)
            print(f"Received message: {data}")

            msg_type = data.get("msg_type")
            if not msg_type:
                raise ValueError(f"Missing `msg_type` in message: {data}")

            # Route messages based on `msg_type`
            if msg_type == "Coordinate_request":
                await self.send_coords(connection_id)
            elif msg_type == "Position":
                incoming_position_handler(data, connection_id)
            elif msg_type == "Debug":
                msg = data.get("msg", "")
                print(f"Debug message: {msg}")
            elif msg_type == "offer":
                await self.handle_offer(data, connection_id)
            elif msg_type == "candidate":
                await self.handle_candidate(data, connection_id)
            elif msg_type == "answer":
                print(f"Received SDP answer from {connection_id}: {data}")
            else:
                print(f"Unhandled `msg_type`: {msg_type}")
        except json.JSONDecodeError:
            print(f"Malformed JSON received from {connection_id}: {frame}")
        except Exception as e:
            print(f"Error processing message from {connection_id}: {e}")

    async def handle_offer(self, data, connection_id):
        """Handles SDP offers from the client."""
        try:
            pc = self.peer_connections.get(connection_id)
            if not pc:
                pc = RTCPeerConnection()
                self.peer_connections[connection_id] = pc

                @pc.on("track")
                def on_track(track):
                    print(f"Track received from {connection_id}, type: {track.kind}")
                    if track.kind == "video":
                        self.video_feeds[connection_id] = track
                        threading.Thread(target=self.display_video, args=(connection_id, track)).start()

            sdp = data.get("sdp")
            if not sdp:
                raise ValueError("Missing `sdp` field in offer message.")
            offer = RTCSessionDescription(sdp=sdp, type="offer")
            await pc.setRemoteDescription(offer)

            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)
            response = {
                "msg_type": "answer",
                "sdp": pc.localDescription.sdp
            }
            await self.connections[connection_id].send(json.dumps(response))
            print(f"Sent SDP answer to client {connection_id}")
        except Exception as e:
            print(f"Error handling SDP offer for {connection_id}: {e}")

    async def handle_candidate(self, data, connection_id):
        """Handles ICE candidates from the client."""
        try:
            pc = self.peer_connections.get(connection_id)
            if not pc:
                raise ValueError(f"No PeerConnection found for client {connection_id}.")

            sdpMid = data.get("sdpMid")
            sdpMLineIndex = data.get("sdpMLineIndex")
            candidate = data.get("candidate")
            if not all([sdpMid, sdpMLineIndex, candidate]):
                raise ValueError("Missing ICE candidate fields in message.")
            ice_candidate = RTCIceCandidate(sdpMid=sdpMid, sdpMLineIndex=sdpMLineIndex, candidate=candidate)
            await pc.addIceCandidate(ice_candidate)
            print(f"Added ICE candidate for client {connection_id}")
        except Exception as e:
            print(f"Error handling ICE candidate for {connection_id}: {e}")

    async def send_coords(self, connection_id: str) -> None:
        """Sends assigned coordinates to the client."""
        if connection_id in self.coordinates:
            lat, lng, alt, angle = self.coordinates[connection_id]
            message = {
                "msg_type": "Coordinate_request",
                "lat": lat,
                "lng": lng,
                "alt": alt,
                "angle": angle
            }
            try:
                await self.connections[connection_id].send(json.dumps(message))
                print(f"Sent coordinates to client {connection_id}: {message}")
            except websockets.exceptions.ConnectionClosed:
                print(f"Connection {connection_id} closed, cleaning up.")
                self.cleanup_connection(connection_id)
        else:
            print(f"No coordinates found for {connection_id}")

    def cleanup_connection(self, connection_id: str) -> None:
        """Cleans up connections and PeerConnections when a client disconnects."""
        self.connections.pop(connection_id, None)
        self.coordinates.pop(connection_id, None)
        pc = self.peer_connections.pop(connection_id, None)
        if pc:
            pc.close()
            print(f"Closed PeerConnection for client {connection_id}")
        print(f"Connection {connection_id} removed.")

    def display_video(self, connection_id, track):
        """Displays incoming video feed using OpenCV."""
        print(f"Starting video feed for connection: {connection_id}")
        for frame in track.frames():
            img = frame.to_ndarray(format="bgr24")
            cv2.imshow(f"Video Feed - {connection_id}", img)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print(f"Closing video feed for connection: {connection_id}")
                break
        cv2.destroyWindow(f"Video Feed - {connection_id}")

def incoming_position_handler(data, connection_id):
    """Handles incoming position data."""
    lat = data.get("latitude")
    long = data.get("longitude")
    altitude = data.get("altitude")
    print(f"Handling position: lat={lat}, long={long}, altitude={altitude}")
    try:
        json_data_string = json.dumps(data)
        r.set(f"position_drone{connection_id}", json_data_string, ex=10)
        # print("Stored position data in Redis.")
    except (TypeError, redis.exceptions.RedisError) as e:
        print(f"Error processing position data: {e}")
