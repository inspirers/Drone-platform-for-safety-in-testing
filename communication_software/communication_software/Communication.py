# Communication.py
# from datetime import time
import time
import json
import redis.exceptions
import websockets
from websockets import WebSocketServerProtocol
# Assuming Coordinate is defined correctly elsewhere or remove if not used directly here
# from communication_software.CoordinateHandler import Coordinate
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
        self.connections = {}  # Active WebSocket connections: {connection_id: ws}
        self.coordinates = {}  # Coordinates for each client: {connection_id: (lat, lng, alt, angle)}
        self.peer_connections = {}  # RTCPeerConnections per client: {connection_id: pc}
        self.drone_coordinates = []  # List of available drone coordinate tuples (lat, lng, alt, angle)
        self.client_index = 0  # Tracks which coordinate to assign next - might need better logic for reuse
        self.video_feeds = {}  # Video streams per connection: {connection_id: track}

        self.loop = None # <<< ADDED: To store the main event loop
        self.redis_listener_stop_event = threading.Event()
        self.redis_listener_task = None

    async def send_coordinates_websocket(self, ip: str, droneOrigins: list, angles: list) -> None:
        """Starts WebSocket server and initializes drone coordinates."""
        print(f"Initializing WebSocket on IP: {ip}")
        # Transform coordinates from Coordinate objects (if they are) to tuples
        self.drone_coordinates = [
            self.transform_coordinates_tuple(coord, angle) for coord, angle in zip(droneOrigins, angles)
        ]
        print(f"Prepared drone coordinates: {self.drone_coordinates}")

        # --- Ensure self.loop is set before starting the server ---
        # This should be guaranteed by the new structure in main.py
        if not self.loop:
            print("ERROR: Event loop not set before starting WebSocket server!")
            # Optionally raise an exception or handle this state
            # raise RuntimeError("Event loop not available.")
            # Attempt to get it here as a fallback (less ideal)
            try:
                 self.loop = asyncio.get_running_loop()
                 print("Fallback: Acquired event loop within send_coordinates_websocket.")
            except RuntimeError:
                 print("FATAL: Could not acquire event loop.")
                 return # Exit if loop cannot be found

        # --- Start Redis Listener if not already started ---
        # It's better started from main.py after loop is confirmed,
        # but checking here adds robustness.
        if not self.redis_listener_task or not self.redis_listener_task.is_alive():
             print("Warning: Redis listener thread not started or alive. Starting it now.")
             self.start_redis_listener_thread() # Assumes self.loop is set

        server = await websockets.serve(self.webs_server, ip, 14500)
        print(f"WebSocket server started on ws://{ip}:14500")

        try:
            # Keep the server running until it's closed externally or by error
            await server.wait_closed()
        finally:
            print("WebSocket server stopping...")
            # Signal the listener thread to stop
            self.redis_listener_stop_event.set()
            if self.redis_listener_task and self.redis_listener_task.is_alive():
                print("Waiting for Redis listener thread to finish...")
                self.redis_listener_task.join(timeout=5) # Wait briefly for cleanup
                if self.redis_listener_task.is_alive():
                    print("Warning: Redis listener thread did not stop gracefully.")
            print("WebSocket server stopped.")

    # Assuming CoordinateHandler.Coordinate has lat, lng, alt attributes
    # If droneOrigins are already tuples, adjust this or add a check
    def transform_coordinates_tuple(self, coordinates: tuple or object, angle: int) -> tuple:
        """Transforms coordinates into required string tuple format."""
        # Check if coordinates is an object with attributes or already a tuple/list
        if hasattr(coordinates, 'lat') and hasattr(coordinates, 'lng') and hasattr(coordinates, 'alt'):
            lat = str(coordinates.lat)[:9]
            lng = str(coordinates.lng)[:9]
            alt = str(coordinates.alt)[:2] # Check if alt needs more precision
        elif isinstance(coordinates, (tuple, list)) and len(coordinates) >= 3:
             lat = str(coordinates[0])[:9]
             lng = str(coordinates[1])[:9]
             alt = str(coordinates[2])[:2] # Check if alt needs more precision
        else:
             print(f"Warning: Unexpected coordinate format: {coordinates}. Using defaults.")
             lat, lng, alt = "0.0", "0.0", "0"

        new_angle = str(angle)
        return (lat, lng, alt, new_angle)

    # <<< MODIFIED redis_command_listener >>>
    def redis_command_listener(self, redis_client, channel, stop_event): # Removed 'instance' arg
        """Listens for messages on the specified Redis channel in a blocking loop."""
        print(f"[REDIS THREAD] Listener thread started for channel '{channel}'.")
        pubsub = None
        listener_redis_conn = None

        # Ensure the event loop reference is available
        if not self.loop:
            print("[REDIS THREAD] FATAL: Event loop not available. Listener thread cannot proceed.")
            return # Exit thread if loop isn't set

        while not stop_event.is_set(): # Loop until stop event is set
            try:
                # Use connection details from the initially connected client 'r'
                listener_redis_conn = redis.Redis(
                    host=redis_client.connection_pool.connection_kwargs.get('host', 'redis'), # Use 'redis' as default host
                    port=redis_client.connection_pool.connection_kwargs.get('port', 6379),
                    db=redis_client.connection_pool.connection_kwargs.get('db', 0),
                    decode_responses=True,
                    socket_connect_timeout=5, # Add timeout
                    socket_keepalive=True     # Add keepalive
                )
                listener_redis_conn.ping() # Verify connection
                pubsub = listener_redis_conn.pubsub(ignore_subscribe_messages=True)
                pubsub.subscribe(channel)
                print(f"[REDIS THREAD] Subscribed successfully to '{channel}'. Waiting...")

                for message in pubsub.listen():
                    if stop_event.is_set():
                        print("[REDIS THREAD] Stop event detected, exiting listen loop.")
                        break # Exit inner listen loop

                    if message and message.get('type') == 'message':
                        # <<< THE FIX: Use run_coroutine_threadsafe >>>
                        print(f"[REDIS THREAD] Received message: {message['data']}")
                        coro = self.process_redis_command(message['data'])
                        future = asyncio.run_coroutine_threadsafe(coro, self.loop)

                        # Optional: Add error handling for the future if needed
                        try:
                            # You could wait for the result with timeout, but often not needed
                            # future.result(timeout=1.0)
                            pass # Fire-and-forget is usually fine here
                        except Exception as e:
                            print(f"[REDIS THREAD] Error submitting/executing command: {e}")
                    else:
                        # Handle other message types if necessary (e.g., 'subscribe')
                        # print(f"[REDIS THREAD] Received non-message type: {message}")
                        pass

                # If listen() finishes without stop_event (e.g., connection lost), break outer loop
                if not stop_event.is_set():
                     print("[REDIS THREAD] Pubsub listen loop finished unexpectedly. Will attempt reconnect.")
                     # Force cleanup before retry delay
                     if pubsub: pubsub.close()
                     if listener_redis_conn: listener_redis_conn.close()
                     pubsub = None
                     listener_redis_conn = None
                     time.sleep(5) # Wait before attempting to reconnect
                     continue # Continue the outer while loop to retry connection


            except redis.exceptions.ConnectionError as e:
                print(f"[REDIS THREAD] Connection error: {e}. Retrying in 5 seconds...")
                if pubsub: pubsub.close() # Use close() for pubsub
                if listener_redis_conn: listener_redis_conn.close() # Use close() for connection
                pubsub = None
                listener_redis_conn = None
                time.sleep(5) # Wait before attempting to reconnect
            except redis.exceptions.TimeoutError as e:
                 print(f"[REDIS THREAD] Redis command timeout: {e}. Retrying in 5 seconds...")
                 if pubsub: pubsub.close()
                 if listener_redis_conn: listener_redis_conn.close()
                 pubsub = None
                 listener_redis_conn = None
                 time.sleep(5)
            except Exception as e:
                # Log unexpected errors more informatively
                import traceback
                print(f"[REDIS THREAD] Unexpected error in listener loop: {e}")
                print(traceback.format_exc())
                # Decide whether to break or retry based on the error
                break # Exit outer loop on unexpected errors for safety now
            finally:
                # Ensure cleanup happens before retry or exit
                 if pubsub:
                    try: pubsub.unsubscribe(channel)
                    except: pass # Ignore errors during cleanup
                    try: pubsub.close()
                    except: pass
                 if listener_redis_conn:
                    try: listener_redis_conn.close()
                    except: pass

        print("[REDIS THREAD] Listener thread finished.")


    async def process_redis_command(self, message_data):
        """Processes a command received from Redis (runs in the main event loop)."""
        print(f"\n[PROCESS CMD] Processing command received from Redis. Data type: {type(message_data)}")
        try:
            # message_data should already be a string if decode_responses=True
            if isinstance(message_data, bytes):
                message_data = message_data.decode('utf-8') # Decode if necessary

            print(f"[PROCESS CMD] Raw Command Data: {message_data}")
            data = json.loads(message_data) # Directly load the string

            target_drone_id_str = data.get("target_drone_id") # Get ID (might be string or int)
            command = data.get("command")
            payload = data.get("payload", {}) # Default to empty dict if missing
            timestamp = data.get("timestamp")

            print(f"[PROCESS CMD] Parsed: Drone='{target_drone_id_str}', Cmd='{command}', Payload={payload}, TS={timestamp}")

            if target_drone_id_str is None or command is None:
                 print(f"[PROCESS CMD] ERROR: Missing 'target_drone_id' or 'command' in message: {data}")
                 return

            try:
                # Convert target_drone_id to integer for indexing
                target_drone_id = int(target_drone_id_str)
            except ValueError:
                 print(f"[PROCESS CMD] ERROR: Invalid 'target_drone_id': {target_drone_id_str}. Must be an integer.")
                 return


            response = {
                "msg_type": command,
                **payload # Merge payload into the response if needed, or handle separately
            }
            response_json = json.dumps(response)

            # --- Find the correct WebSocket connection ---
            # This assumes connections are ordered by drone ID, which might be fragile.
            # A better approach would be to map drone IDs directly to websocket connections
            # when they connect or identify themselves.
            # For now, using the index-based approach:

            active_connections = list(self.connections.items()) # Get list of (id, ws) pairs
            print(f"[PROCESS CMD] Current active connections: {len(active_connections)}")
            # Print connection IDs for debugging:
            # for cid, _ in active_connections: print(f"  - {cid}")

            # Drone IDs often start from 1, list indices start from 0
            connection_index = target_drone_id - 1

            if 0 <= connection_index < len(active_connections):
                connection_id, connection_ws = active_connections[connection_index]
                print(f"[PROCESS CMD] Target Index: {connection_index}, Connection ID: {connection_id}")

                if connection_ws:
                    try:
                        print(f"Sending message to WebSocket {connection_id}: {response_json}")
                        await connection_ws.send(response_json)
                        print(f"[PROCESS CMD] Successfully sent command '{command}' to drone {target_drone_id} (WS: {connection_id}).")
                    except websockets.exceptions.ConnectionClosed:
                        print(f"[PROCESS CMD] ERROR: WebSocket connection {connection_id} closed before sending.")
                        self.cleanup_connection(connection_id) # Clean up if closed
                    except Exception as send_err:
                        print(f"[PROCESS CMD] ERROR: Failed to send message to WebSocket {connection_id}: {send_err}")
                else:
                    print(f"[PROCESS CMD] ERROR: WebSocket connection {connection_id} not open or not found.")
                    if connection_id in self.connections: # Check if it still exists in dict
                         self.cleanup_connection(connection_id)

            else:
                print(f"[PROCESS CMD] ERROR: Target drone ID {target_drone_id} (index {connection_index}) is out of range for available connections ({len(active_connections)}).")

        except json.JSONDecodeError:
            print(f"[PROCESS CMD] ERROR: Failed to decode JSON from Redis message: {message_data}")
        except Exception as e:
            # Log unexpected errors more informatively
            import traceback
            print(f"[PROCESS CMD] ERROR: Unexpected error processing command: {e}")
            print(traceback.format_exc())


    async def webs_server(self, ws: WebSocketServerProtocol) -> None:
        """Handles WebSocket connections."""
        connection_id = str(ws.id) # Use websocket's unique ID
        print(f"Client connected: {connection_id} from {ws.remote_address}")
        self.connections[connection_id] = ws

        # Assign unique drone coordinate - Need more robust assignment logic
        assigned_coord = None
        if self.drone_coordinates:
             # Simple round-robin for now, assuming more connections than coords is ok short-term
             coord_index = len(self.connections) - 1 # Index based on current connection count
             if coord_index < len(self.drone_coordinates):
                  assigned_coord = self.drone_coordinates[coord_index]
                  self.coordinates[connection_id] = assigned_coord
                  print(f"Assigned coordinate {assigned_coord} to client {connection_id} (Index: {coord_index})")
             else:
                  print(f"Warning: More connections ({len(self.connections)}) than available coordinates ({len(self.drone_coordinates)}). Client {connection_id} gets no initial coordinate.")
                  # Assign the last available one, or None? Needs defined behaviour.
                  assigned_coord = self.drone_coordinates[-1] # Assign last one for now
                  self.coordinates[connection_id] = assigned_coord
                  print(f"Assigned last coordinate {assigned_coord} to client {connection_id} as fallback.")

        else:
             print("Warning: No drone coordinates available to assign.")


        # Optionally send initial coordinates right away if assigned
        if assigned_coord:
            await self.send_coords(connection_id) # Send initial coords

        try:
            async for message in ws: # Iterate messages
                # print(f"Received raw from {connection_id}: {message}") # Keep for debug if needed
                await self.on_message(message, connection_id)
        except websockets.exceptions.ConnectionClosedError as e:
            print(f"Client {connection_id} disconnected (ClosedError): Code {e.code}, Reason: {e.reason}")
        except websockets.exceptions.ConnectionClosedOK as e:
            print(f"Client {connection_id} disconnected normally (ClosedOK): Code {e.code}, Reason: {e.reason}")
        except Exception as e:
             print(f"Error in WebSocket handler for {connection_id}: {e}")
             import traceback
             print(traceback.format_exc())
        finally:
            print(f"Cleaning up connection for {connection_id}")
            await self.cleanup_connection(connection_id) # Make cleanup async if needed


    async def on_message(self, frame: str, connection_id: str) -> None:
        """Processes incoming messages."""
        try:
            data = json.loads(frame)
            # print(f"Received message from {connection_id}: {data}") # Less verbose logging

            msg_type = data.get("msg_type")
            if not msg_type:
                print(f"Warning: Missing `msg_type` in message from {connection_id}: {data}")
                # Optionally send an error response back to the client
                # await self.connections[connection_id].send(json.dumps({"error": "Missing msg_type"}))
                return # Ignore message without type

            # Route messages based on `msg_type`
            if msg_type == "Coordinate_request":
                await self.send_coords(connection_id)
            elif msg_type == "Position":
                # Pass to handler, consider making it async if it does I/O
                incoming_position_handler(data, connection_id)
            elif msg_type == "Debug":
                msg = data.get("msg", "")
                print(f"[Debug WS {connection_id}]: {msg}")
            elif msg_type == "offer":
                await self.handle_offer(data, connection_id)
            elif msg_type == "candidate":
                await self.handle_candidate(data, connection_id)
            elif msg_type == "answer":
                 # Client should not send 'answer', server sends it. Log if received.
                 print(f"Warning: Received unexpected SDP 'answer' from client {connection_id}")
            # Add handling for drone identification? E.g., drone sends its ID on connect.
            # elif msg_type == "Identify":
            #     drone_id = data.get("drone_id")
            #     # Update internal mapping of connection_id to drone_id
            else:
                print(f"Warning: Unhandled `msg_type` '{msg_type}' from {connection_id}")
        except json.JSONDecodeError:
            print(f"Malformed JSON received from {connection_id}: {frame}")
        except websockets.exceptions.ConnectionClosed:
             # This might be caught by the outer handler, but good practice here too
             print(f"Connection {connection_id} closed during message processing.")
             await self.cleanup_connection(connection_id)
        except Exception as e:
            print(f"Error processing message from {connection_id}: {e}")
            import traceback
            print(traceback.format_exc())


    async def handle_offer(self, data, connection_id):
        """Handles SDP offers from the client."""
        if connection_id not in self.connections:
             print(f"Warning: Received offer for unknown/disconnected client {connection_id}")
             return
        try:
            pc = self.peer_connections.get(connection_id)
            if not pc:
                print(f"Creating new PeerConnection for {connection_id}")
                pc = RTCPeerConnection()
                self.peer_connections[connection_id] = pc

                @pc.on("track")
                async def on_track(track): # Make on_track async
                    print(f"Track received from {connection_id}, kind: {track.kind}, ID: {track.id}")
                    if track.kind == "video":
                        # Avoid blocking the event loop with cv2.imshow directly
                        # Use run_in_executor or a separate process/thread managed carefully
                        print(f"Video track received for {connection_id}. Display function needs modification.")
                        # For now, just store the track
                        self.video_feeds[connection_id] = track
                        # TODO: Implement non-blocking video display (e.g., using asyncio queues and separate thread/process)
                        # threading.Thread(target=self.display_video_threadsafe, args=(connection_id, track, self.loop)).start()
                    elif track.kind == "audio":
                        print(f"Audio track received for {connection_id}. Ignoring.")
                        # Add handling if needed
                        await track.recv() # Consume data to prevent buffer buildup

                    @track.on("ended")
                    async def on_ended():
                        print(f"Track {track.kind} ({track.id}) ended for {connection_id}")
                        if connection_id in self.video_feeds and self.video_feeds[connection_id] == track:
                             del self.video_feeds[connection_id]
                             # Add logic to close display window if using separate thread/process

                @pc.on("connectionstatechange")
                async def on_connectionstatechange():
                    print(f"PeerConnection state for {connection_id}: {pc.connectionState}")
                    if pc.connectionState == "failed" or pc.connectionState == "closed":
                        print(f"PeerConnection for {connection_id} failed or closed. Cleaning up.")
                        await self.cleanup_peer_connection(connection_id)


            sdp = data.get("sdp")
            offer_type = data.get("type", "offer") # Assume 'offer' if type not specified
            if not sdp:
                raise ValueError("Missing `sdp` field in offer message.")

            offer = RTCSessionDescription(sdp=sdp, type=offer_type)

            print(f"Received offer from {connection_id}, setting remote description...")
            await pc.setRemoteDescription(offer)

            print(f"Creating answer for {connection_id}...")
            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)

            response = {
                "msg_type": "answer",
                "sdp": pc.localDescription.sdp,
                "type": pc.localDescription.type # Explicitly include type
            }
            ws = self.connections.get(connection_id)
            if ws:
                 await ws.send(json.dumps(response))
                 print(f"Sent SDP answer to client {connection_id}")
            else:
                 print(f"Client {connection_id} disconnected before answer could be sent.")

        except Exception as e:
            print(f"Error handling SDP offer for {connection_id}: {e}")
            import traceback
            print(traceback.format_exc())
            # Optionally close PC on error
            await self.cleanup_peer_connection(connection_id)


    async def handle_candidate(self, data, connection_id):
        """Handles ICE candidates from the client."""
        if connection_id not in self.connections:
             print(f"Warning: Received candidate for unknown/disconnected client {connection_id}")
             return
        try:
            pc = self.peer_connections.get(connection_id)
            if not pc or not pc.remoteDescription: # Must have remote description set first
                print(f"Warning: Received ICE candidate for {connection_id} but no PeerConnection or remote description is ready. Ignoring.")
                return

            candidate_data = data.get("candidate")
            if candidate_data: # Check if 'candidate' field exists (can be null for end-of-candidates)
                # Standard ICE candidate format
                sdpMid = candidate_data.get("sdpMid")
                sdpMLineIndex = candidate_data.get("sdpMLineIndex")
                candidate_str = candidate_data.get("candidate")

                # Fallback for potentially simpler format (just candidate string)
                if candidate_str is None and isinstance(data.get("candidate"), str):
                     candidate_str = data.get("candidate")
                     # sdpMid and sdpMLineIndex might be missing, handle gracefully if possible
                     sdpMid = data.get("sdpMid") # Might be None
                     sdpMLineIndex = data.get("sdpMLineIndex") # Might be None

                if candidate_str:
                    # print(f"Received candidate: {candidate_str[:30]}... mid={sdpMid} line={sdpMLineIndex}")
                    ice_candidate = RTCIceCandidate(sdpMid=sdpMid, sdpMLineIndex=sdpMLineIndex, sdp=candidate_str) # Use sdp=...
                    await pc.addIceCandidate(ice_candidate)
                    # print(f"Added ICE candidate for client {connection_id}")
                else:
                    print(f"Received end-of-candidates signal (null candidate) for {connection_id}")
                    # Handle end-of-candidates if necessary (often just means client sent all it had initially)
                    # await pc.addIceCandidate(None) # Syntax might vary based on aiortc version or intent

            else:
                 print(f"Received message for ICE candidate for {connection_id}, but 'candidate' field is missing or null.")


        except Exception as e:
            print(f"Error handling ICE candidate for {connection_id}: {e}")
            import traceback
            print(traceback.format_exc())


    async def send_coords(self, connection_id: str) -> None:
        """Sends assigned coordinates to the client."""
        if connection_id in self.coordinates and connection_id in self.connections:
            coord_data = self.coordinates[connection_id]
            if coord_data: # Check if coordinates were actually assigned
                 lat, lng, alt, angle = coord_data
                 message = {
                     "msg_type": "Coordinate_assignment", # Use a more specific type?
                     "lat": lat,
                     "lng": lng,
                     "alt": alt,
                     "angle": angle
                 }
                 try:
                    ws = self.connections[connection_id]
                    await ws.send(json.dumps(message))
                    print(f"Sent coordinates to client {connection_id}: {message}")


                 except websockets.exceptions.ConnectionClosed:
                     print(f"Connection {connection_id} closed before sending coordinates.")
                     await self.cleanup_connection(connection_id)
                 except Exception as e:
                      print(f"Error sending coordinates to {connection_id}: {e}")
            else:
                 print(f"No coordinates assigned to client {connection_id}, cannot send.")
        elif connection_id not in self.connections:
             print(f"Cannot send coordinates: Connection {connection_id} not found.")
             # Clean up dangling coordinate entry if connection is gone
             self.coordinates.pop(connection_id, None)
        else: # Connection exists but no coordinates
             print(f"No coordinates found or assigned for {connection_id}")


    # <<< Make cleanup async >>>
    async def cleanup_connection(self, connection_id: str) -> None:
        """Cleans up WebSocket connections and associated resources."""
        print(f"Initiating cleanup for connection ID: {connection_id}")
        ws = self.connections.pop(connection_id, None)
        if ws:
             # Ensure websocket is closed from server-side too
                  print(f"Closing WebSocket connection {connection_id} from server side.")
                  await ws.close(code=1000, reason="Server cleanup")

        self.coordinates.pop(connection_id, None)
        self.video_feeds.pop(connection_id, None) # Remove video track reference
        # Also cleanup the corresponding PeerConnection
        await self.cleanup_peer_connection(connection_id)

        print(f"Finished cleanup for connection {connection_id}. Remaining connections: {len(self.connections)}")


    async def cleanup_peer_connection(self, connection_id: str) -> None:
        """Cleans up RTCPeerConnection."""
        pc = self.peer_connections.pop(connection_id, None)
        if pc:
            print(f"Closing PeerConnection for client {connection_id}")
            try:
                 await pc.close()
                 print(f"PeerConnection for client {connection_id} closed.")
            except Exception as e:
                 print(f"Error closing PeerConnection for {connection_id}: {e}")


    # display_video needs careful implementation to avoid blocking asyncio loop
    # This is a basic example that WILL BLOCK. DO NOT USE IN PRODUCTION AS IS.
    # You need a separate thread/process and a queue to pass frames.
    def display_video_blocking(self, connection_id, track):
         """Displays incoming video feed using OpenCV (BLOCKING - FOR DEBUG ONLY)."""
         print(f"[VIDEO THREAD {connection_id}] Starting blocking video display.")
         window_name = f"Video Feed - {connection_id}"
         cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

         # This needs to run in a separate thread managed carefully
         async def consume_frames():
             while True:
                 try:
                     frame = await track.recv()
                     img = frame.to_ndarray(format="bgr24")
                     cv2.imshow(window_name, img)
                     if cv2.waitKey(1) & 0xFF == ord('q'):
                          print(f"[VIDEO THREAD {connection_id}] 'q' pressed. Stopping.")
                          break
                 except Exception as e:
                      print(f"[VIDEO THREAD {connection_id}] Error receiving/displaying frame: {e}")
                      break
             print(f"[VIDEO THREAD {connection_id}] Frame consumption loop finished.")
             cv2.destroyWindow(window_name)

         # Need to run this consume_frames coroutine in the main loop or handle it carefully
         # For now, just showing the structure - this won't work directly called like this
         print(f"[VIDEO THREAD {connection_id}] Block display finished.")


    # <<< MODIFIED start_redis_listener_thread >>>
    def start_redis_listener_thread(self):
        """Starts the Redis listener thread."""
        if not self.loop:
             print("ERROR: Cannot start Redis listener thread, event loop is not set.")
             return

        if self.redis_listener_task and self.redis_listener_task.is_alive():
            print("Redis listener thread already running.")
            return

        print("Starting Redis listener thread...")
        self.redis_listener_stop_event.clear() # Ensure stop event is clear
        self.redis_listener_task = threading.Thread(
            target=self.redis_command_listener,
            # Pass the global 'r' redis client, channel name, and stop event
            args=(r, COMMAND_CHANNEL, self.redis_listener_stop_event), # Removed 'self'/'instance' from args
            daemon=True # Thread will exit if main program exits
        )
        self.redis_listener_task.start()
        print("Started Redis listener thread.")


# Global function - OK as is, but consider making async if it performs I/O later
def incoming_position_handler(data, connection_id):
    """Handles incoming position data."""
    lat = data.get("latitude")
    lon = data.get("longitude") # Correct key name often 'longitude' or 'lon'
    alt = data.get("altitude")
    timestamp = data.get("timestamp", time.time()) # Add timestamp if available

    # print(f"[POS HANDLER {connection_id}] Pos: lat={lat}, lon={lon}, alt={alt}") # Less verbose

    # Map connection_id to drone_id if possible/needed
    # drone_id = map_connection_to_drone_id(connection_id) # Requires mapping logic
    drone_key = f"drone_position:{connection_id}" # Store by connection_id for now

    # It's better practice to store structured data (JSON) than just components
    position_data = {
        "latitude": lat,
        "longitude": lon,
        "altitude": alt,
        "timestamp": timestamp,
        "connection_id": connection_id
    }

    try:
        json_data_string = json.dumps(position_data)
        # Use a reasonable expiry, e.g., 60 seconds
        r.set(drone_key, json_data_string, ex=60)
        # print(f"Stored position data in Redis for {connection_id} (Key: {drone_key})")
    except (TypeError, redis.exceptions.RedisError) as e:
        print(f"Error storing position data for {connection_id} in Redis: {e}")
    except Exception as e:
         print(f"Unexpected error in incoming_position_handler for {connection_id}: {e}")