import asyncio
import json
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
from aiortc.contrib.media import MediaRecorder

# Example ICE configuration
ice_configuration = {
    'iceServers': [{'urls': 'stun:stun.l.google.com:19302'}]
}


class DroneStreamManager:
    ongoing_streams = {}
    socket = None  # Shared socket instance

    @staticmethod
    def setup_socket_event(message_handler):
        """Setup message handler for incoming WebRTC messages."""
        DroneStreamManager.socket = message_handler

    @staticmethod
    async def handle_incoming_webrtc_msg(drone_id, message):
        """Route incoming WebRTC messages to the appropriate DroneStream."""
        try:
            drone_stream = DroneStreamManager.get_stream_by_drone_id(drone_id)
            await drone_stream.handle_incoming_socket_msg(message)
            print(f"[Stream Manager] Message routed to DroneStream ({drone_id}) successfully.")
        except KeyError as e:
            print(f"[Stream Manager] Error: {e}")

    @staticmethod
    def get_stream_by_drone_id(drone_id):
        """Retrieve a DroneStream by its ID."""
        if drone_id in DroneStreamManager.ongoing_streams:
            return DroneStreamManager.ongoing_streams[drone_id]
        else:
            raise KeyError(f"DroneID ('{drone_id}') not found in ongoing streams.")

    @staticmethod
    def create_drone_stream(drone_id, video_tag_id):
        """Create and register a new DroneStream."""
        stream = DroneStream(drone_id, video_tag_id)
        DroneStreamManager.ongoing_streams[drone_id] = stream
        return stream

    @staticmethod
    def close_drone_stream(drone_id):
        """Close and clean up a DroneStream."""
        print(f"[Stream Manager] Closing drone stream for ID: {drone_id}")
        try:
            stream = DroneStreamManager.get_stream_by_drone_id(drone_id)
            asyncio.create_task(stream.peer_connection.close())
            del DroneStreamManager.ongoing_streams[drone_id]
        except KeyError:
            print(f"[Stream Manager] Error: Drone stream not found.")


class DroneStream:
    def __init__(self, drone_socket_id, src_id):
        self.drone_socket_id = drone_socket_id
        self.stream_obj = src_id  # Placeholder for stream display/output
        self.peer_connection = None
        self.recorder = None
        self.create_peer_connection()

    def send_message(self, message):
        """Send a message to the WebSocket server."""
        print(f"[DroneStream] Sending message: {message} to drone ID: {self.drone_socket_id}")
        if DroneStreamManager.socket:
            try:
                websocket = DroneStreamManager.socket.get(self.drone_socket_id)
                if websocket:
                    asyncio.create_task(websocket.send(json.dumps(message)))
                else:
                    print(f"[DroneStream] No WebSocket connection found for drone ID: {self.drone_socket_id}")
            except Exception as e:
                print(f"[DroneStream] Error sending message: {e}")

    async def handle_incoming_socket_msg(self, message):
        """Handle incoming WebSocket messages."""
        print(f"[DroneStream] Received message: {message}")
        try:
            if message['type'] == 'answer':
                await self.peer_connection.setRemoteDescription(
                    RTCSessionDescription(sdp=message['sdp'], type=message['type'])
                )
            elif message['type'] == 'candidate':
                candidate = RTCIceCandidate(
                    sdp=message['candidate']['candidate'],
                    sdpMid=message['candidate']['sdpMid'],
                    sdpMLineIndex=message['candidate']['sdpMLineIndex']
                )
                await self.peer_connection.addIceCandidate(candidate)
            else:
                print(f"[DroneStream] Unhandled WebRTC message type: {message['type']}")
        except Exception as e:
            print(f"[DroneStream] Error processing message: {e}")

    async def start_drone_stream(self):
        """Initiates the WebRTC stream with the drone."""
        try:
            offer = await self.peer_connection.createOffer()
            print(f"[DroneStream] WebRTC offer created: {offer.sdp}")
            await self.peer_connection.setLocalDescription(offer)
            self.send_message({'type': 'offer', 'sdp': offer.sdp})
        except Exception as e:
            print(f"[DroneStream] Error in createOffer(): {e}")

    def create_peer_connection(self):
        """Create and configure the RTCPeerConnection."""
        try:
            self.peer_connection = RTCPeerConnection(configuration=ice_configuration)

            @self.peer_connection.on("icecandidate")
            async def on_ice_candidate(event):
                if event.candidate:
                    self.send_message({
                        'type': 'candidate',
                        'candidate': event.candidate.to_sdp(),
                    })
                else:
                    print("[DroneStream] End of ICE candidates")

            @self.peer_connection.on("track")
            def on_track(track):
                print(f"[DroneStream] Received track: {track.kind}")
                # Record incoming media
                self.recorder = MediaRecorder(f'{self.drone_socket_id}_output.mp4')
                self.recorder.addTrack(track)
                asyncio.create_task(self.recorder.start())

            @self.peer_connection.on("connectionstatechange")
            async def on_connection_state_change():
                state = self.peer_connection.connectionState
                states = {
                    "new": "Connecting…",
                    "checking": "Checking connection…",
                    "connected": "Online",
                    "disconnected": "Disconnecting…",
                    "closed": "Offline",
                    "failed": "Error",
                }
                print(f"[DroneStream] State: {states.get(state, 'Unknown')}")

            # Add transceivers for video and audio
            self.peer_connection.addTransceiver('video', direction='recvonly')
            self.peer_connection.addTransceiver('audio', direction='recvonly')

            print(f"[DroneStream] Created RTCPeerConnection: {self.peer_connection}")
        except Exception as e:
            print(f"[DroneStream] Failed to create PeerConnection: {e}")
