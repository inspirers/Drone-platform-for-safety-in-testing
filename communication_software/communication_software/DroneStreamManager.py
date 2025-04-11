import asyncio
import json
import threading
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer, MediaRecorder

# Configuration for ICE servers
ice_configuration = {
    'iceServers': [
        {
            'urls': 'stun:stun.l.google.com:19302'
        }
    ]
}

class KeyError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.name = "KeyError"

class DroneStreamManager:
    ongoing_streams = {}
    socket = None

    @staticmethod
    def get_stream_by_drone_id(drone_id):
        """Returns the handle to the drone stream, but will throw an exception if the droneID is invalid."""
        if drone_id in DroneStreamManager.ongoing_streams:
            return DroneStreamManager.ongoing_streams[drone_id]
        else:
            raise KeyError(f"DroneID ('{drone_id}') not found in dictionary of ongoing streams")

    @staticmethod
    def setup_socket_event(socket):
        """Sets up the socket event for incoming messages."""
        DroneStreamManager.socket = socket
        socket.on('webrtc_msg', lambda drone_id, message: DroneStreamManager.handle_incoming_webrtc_msg(drone_id, message))

    @staticmethod
    def handle_incoming_webrtc_msg(drone_id, message):
        """Handles incoming WebRTC messages."""
        drone_stream = DroneStreamManager.get_stream_by_drone_id(drone_id)
        drone_stream.handle_incoming_socket_msg(message)
        print(f"Found drone {drone_stream} that is receiving a webrtc_msg ({drone_id})")

    @staticmethod
    def create_drone_stream(drone_id, video_tag_id):
        """Creates a new drone stream."""
        stream = DroneStream(drone_id, video_tag_id)
        DroneStreamManager.ongoing_streams[drone_id] = stream
        return stream

    @staticmethod
    def close_drone_stream(drone_id):
        """Closes the drone stream."""
        print(f"Closing drone stream for {drone_id}")
        stream = DroneStreamManager.get_stream_by_drone_id(drone_id)
        stream.peer_connection.close()
        del DroneStreamManager.ongoing_streams[drone_id]
        stream.peer_connection = None
        stream = None


class DroneStream:
    def __init__(self, drone_socket_id, src_id):
        """Initializes the drone stream with the socket ID and the video tag ID."""
        self.drone_socket_id = drone_socket_id
        self.stream_obj = src_id  # This can be a reference to a video element, adjusted for Python usage
        self.create_peer_connection()

    def send_message(self, message):
        """Sends a message to the drone."""
        print(f'Client sending message: {message} to drone ID: {self.drone_socket_id}')
        if DroneStreamManager.socket:
            DroneStreamManager.socket.emit("webrtc_msg", self.drone_socket_id, message)

    def handle_incoming_socket_msg(self, message):
        """Handles incoming socket messages."""
        print(f'Client received message: {message}')
        if message['type'] == 'answer':
            self.peer_connection.set_remote_description(RTCSessionDescription(sdp=message['sdp'], type=message['type']))
        elif message['type'] == 'candidate':
            candidate = message
            self.peer_connection.add_ice_candidate(candidate)

    def start_drone_stream(self):
        """Starts the drone stream."""
        try:
            offer = self.peer_connection.create_offer()
            print(f"WebRTC offer created: {offer}")
            self.peer_connection.set_local_description(offer)
            self.send_message({'type': 'offer', 'sdp': offer.sdp})
        except Exception as e:
            print(f'createOffer() error: {e}')

    def handle_on_track(self, event):
        """Handles the 'ontrack' event."""
        self.stream_obj.src_object = event.streams[0]  # Adapt this for Python video handling if necessary
        return False

    def handle_on_connection_state_change(self, event):
        """Handles changes in the connection state."""
        state = self.peer_connection.connection_state
        states = {
            "new": "Connecting…",
            "checking": "Connecting…",
            "connected": "Online",
            "disconnected": "Disconnecting…",
            "closed": "Offline",
            "failed": "Error"
        }
        print(states.get(state, "Unknown"))

    def create_peer_connection(self):
        """Creates the WebRTC peer connection."""
        try:
            self.peer_connection = RTCPeerConnection(configuration=ice_configuration)  # Using aiortc's RTCPeerConnection
            self.peer_connection.on_ice_candidate = self.on_ice_candidate
            self.peer_connection.on_ice_candidate_error = self.on_ice_candidate_error
            self.peer_connection.on_track = self.handle_on_track
            self.peer_connection.on_connection_state_change = self.handle_on_connection_state_change
            self.peer_connection.add_transceiver('video', {'direction': 'recvonly'})
            self.peer_connection.add_transceiver('audio', {'direction': 'recvonly'})
            print(f"Created RTCPeerConnection: {self.peer_connection}")
        except Exception as e:
            print(f'Failed to create PeerConnection, exception: {e}')

    def on_ice_candidate(self, event):
        """Handles ICE candidates."""
        if event.candidate:
            self.send_message({
                'type': 'candidate',
                'label': event.candidate.sdp_mline_index,
                'id': event.candidate.sdp_mid,
                'candidate': event.candidate.candidate
            })
        else:
            print('End of candidates.')

    def on_ice_candidate_error(self, event):
        """Handles ICE candidate errors."""
        raise Exception("[WebRTC](OnIceCandidateError) something went wrong with ice candidates")

# Example of how the WebSocket server and WebRTC signaling might be wired up (you'll need actual WebSocket server code):
async def handle_socket_message(message):
    # Handle incoming messages, such as "offer", "answer", or "candidate"
    pass
