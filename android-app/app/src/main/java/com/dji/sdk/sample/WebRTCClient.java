package com.dji.sdk.sample;

import static org.webrtc.SessionDescription.Type.OFFER;

import android.content.Context;
import android.util.Log;

import org.json.JSONException;
import org.json.JSONObject;
import org.webrtc.DataChannel;
import org.webrtc.DefaultVideoDecoderFactory;
import org.webrtc.DefaultVideoEncoderFactory;
import org.webrtc.EglBase;
import org.webrtc.IceCandidate;
import org.webrtc.MediaConstraints;
import org.webrtc.MediaStream;
import org.webrtc.PeerConnection;
import org.webrtc.PeerConnectionFactory;
import org.webrtc.RtpReceiver;
import org.webrtc.SessionDescription;
import org.webrtc.VideoCapturer;
import org.webrtc.VideoSource;
import org.webrtc.VideoTrack;

import java.util.ArrayList;

import dev.gustavoavila.websocketclient.WebSocketClient;


public class WebRTCClient {
    private static final String TAG = "WebRTCClient";
    private final Context context;

    // WebRTC related variables
    private PeerConnection peerConnection;
    private VideoTrack videoTrackFromCamera;
    private final WebRTCMediaOptions options;
    private final VideoCapturer videoCapturer;
    private WebsocketClientHandler websocketClientHandler;

    private PeerConnectionChangedListener connectionChangedListener;
    public void setConnectionChangedListener(PeerConnectionChangedListener connectionChangedListener) { this.connectionChangedListener = connectionChangedListener; }

    // Peer variables of the client requesting a stream

    private static PeerConnectionFactory factory;
    private static PeerConnectionFactory getFactory(Context context){
        if (factory == null) {
            initializeFactory(context);
        }
        return factory;
    }

    public WebRTCClient(Context context, VideoCapturer videoCapturer, WebRTCMediaOptions options) {
        this.context = context;
        this.options = options;
        this.videoCapturer = videoCapturer;
    
        if (WebsocketClientHandler.getInstance() == null) {
            Log.e(TAG, "WebsocketClientHandler is null during WebRTCClient initialization.");
        } else {
            this.websocketClientHandler = WebsocketClientHandler.getInstance();
            Log.d(TAG, "WebsocketClientHandler initialized successfully.");
        }
    
        createVideoTrackFromVideoCapturer();
        initializePeerConnection();
        startStreamingVideo();
    }
    

    private static void initializeFactory(Context context){
        // EglBase seems to be used for Hardware-acceleration for our video.
        EglBase rootEglBase = EglBase.create();

        // Initialize the PeerConnectionFactory
        PeerConnectionFactory.InitializationOptions options = PeerConnectionFactory.InitializationOptions.builder(context)
                .setEnableInternalTracer(true)
                .setFieldTrials("WebRTC-H264HighProfile/Enabled/")
                .createInitializationOptions();
        PeerConnectionFactory.initialize(options);

        // Now configure and build the factory
        factory = PeerConnectionFactory
                .builder()
                .setVideoDecoderFactory(new DefaultVideoDecoderFactory(rootEglBase.getEglBaseContext()))
                .setVideoEncoderFactory(new DefaultVideoEncoderFactory(rootEglBase.getEglBaseContext(), true, true))
                .setOptions(new PeerConnectionFactory.Options()).createPeerConnectionFactory();
    }

    public void handleWebRTCMessage(JSONObject message){
        try {
            Log.d(TAG, "connectToSignallingServer: got message " + message);
            if (message.getString("msg_type").equals("offer")) {
                Log.d(TAG, "connectToSignallingServer: received an offer");
                peerConnection.setRemoteDescription(new SimpleSdpObserver(), new SessionDescription(OFFER, message.getString("sdp")));
                answerCall();
            } else if (message.getString("msg_type").equals("candidate")) {
                Log.d(TAG, "connectToSignallingServer: receiving candidates");
                IceCandidate candidate = new IceCandidate(message.getString("id"), message.getInt("label"), message.getString("candidate"));
                peerConnection.addIceCandidate(candidate);
            }
        }
        catch (JSONException e) {
            Log.d(TAG, "Exception with socket : " + e.getMessage());
            e.printStackTrace();
        }
    }

    public void dispose() {
        // Close any WebRTC connections, release resources here
        if (peerConnection != null) {
            peerConnection.close();
        }
        // Additional cleanup if needed
    }

    private void answerCall() {
        peerConnection.createAnswer(new SimpleSdpObserver() {
            @Override
            public void onCreateSuccess(SessionDescription sessionDescription) {
                peerConnection.setLocalDescription(new SimpleSdpObserver(), sessionDescription);
                JSONObject message = new JSONObject();
                try {
                    message.put("msg_type", "answer");
                    message.put("sdp", sessionDescription.description);
                    sendMessage(message);
                } catch (JSONException e) {
                    e.printStackTrace();
                }
            }
        }, new MediaConstraints());
    }

    private void sendMessage(Object message) {
        websocketClientHandler.send(message.toString());
        Log.d(TAG, "Message sent: " + message);
    }

    private void createVideoTrackFromVideoCapturer() {
        VideoSource videoSource = getFactory(context).createVideoSource(false);

        // Instantiate our custom video capturer to get video from our drone
        videoCapturer.initialize(null, context, videoSource.getCapturerObserver());
        videoCapturer.startCapture(options.VIDEO_RESOLUTION_WIDTH, options.VIDEO_RESOLUTION_HEIGHT, options.FPS);

        videoTrackFromCamera = getFactory(context).createVideoTrack(options.VIDEO_SOURCE_ID, videoSource);
        videoTrackFromCamera.setEnabled(true);
    }

    private void initializePeerConnection() {
        peerConnection = createPeerConnection();
    }

    private void startStreamingVideo() {
        MediaStream mediaStream = getFactory(context).createLocalMediaStream(options.MEDIA_STREAM_ID);
        mediaStream.addTrack(videoTrackFromCamera);
        peerConnection.addStream(mediaStream);
    }

    private PeerConnection createPeerConnection() {
        ArrayList<PeerConnection.IceServer> iceServers = new ArrayList<>();
        PeerConnection.IceServer stun =  PeerConnection.IceServer.builder("stun:stun.l.google.com:19302").createIceServer();
        iceServers.add(stun);
        PeerConnection.RTCConfiguration rtcConfig = new PeerConnection.RTCConfiguration(iceServers);
        rtcConfig.sdpSemantics = PeerConnection.SdpSemantics.PLAN_B;


        PeerConnection.Observer pcObserver = new PeerConnection.Observer() {
            @Override
            public void onSignalingChange(PeerConnection.SignalingState signalingState) {
                Log.d(TAG, "onSignalingChange: ");
            }

            @Override
            public void onIceConnectionChange(PeerConnection.IceConnectionState iceConnectionState) {
                switch (iceConnectionState){
                    case DISCONNECTED:
                        Log.d(TAG, "PEER HAS DISCONNECTED");
                        if (connectionChangedListener != null)
                            connectionChangedListener.onDisconnected();
                        // Dispose of the capturer and then the peer connection to clean up properly
                        videoCapturer.dispose();
                        break;
                }
            }

            @Override
            public void onIceConnectionReceivingChange(boolean b) {
                Log.d(TAG, "onIceConnectionReceivingChange: ");
            }

            @Override
            public void onIceGatheringChange(PeerConnection.IceGatheringState iceGatheringState) {
                Log.d(TAG, "onIceGatheringChange: ");
            }

            @Override
            public void onAddTrack(RtpReceiver rtpReceiver, MediaStream[] mediaStreams) {
                // We are not interested in displaying whatever video feed we receive from the other end.
                // Not that we are getting any..
            }

            @Override
            public void onIceCandidate(IceCandidate iceCandidate) {
                Log.d(TAG, "onIceCandidate: ");
                JSONObject message = new JSONObject();

                try {
                    message.put("msg_type", "candidate");
                    message.put("label", iceCandidate.sdpMLineIndex);
                    message.put("id", iceCandidate.sdpMid);
                    message.put("candidate", iceCandidate.sdp);

                    Log.d(TAG, "onIceCandidate: sending candidate " + message);
                    sendMessage(message);
                } catch (JSONException e) {
                    e.printStackTrace();
                }
            }

            @Override
            public void onIceCandidatesRemoved(IceCandidate[] iceCandidates) { Log.d(TAG, "onIceCandidatesRemoved: "); }

            @Override
            public void onAddStream(MediaStream mediaStream) { Log.d(TAG, "onAddStream: "); }

            @Override
            public void onRemoveStream(MediaStream mediaStream) {
                Log.d(TAG, "onRemoveStream: ");
            }

            @Override
            public void onDataChannel(DataChannel dataChannel) {
                Log.d(TAG, "onDataChannel: ");
            }

            @Override
            public void onRenegotiationNeeded() {
                Log.d(TAG, "onRenegotiationNeeded: ");
            }
        };

        return getFactory(context).createPeerConnection(rtcConfig, pcObserver);
    }

    public interface PeerConnectionChangedListener {
        void onDisconnected(); // Is called when our peer disconnects from the call
    }
}