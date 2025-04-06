package com.dji.sdk.sample;

import android.content.Context;
import android.util.Log;
import android.view.TextureView;

import org.json.JSONException;
import org.json.JSONObject;
import org.webrtc.CapturerObserver;
import org.webrtc.DefaultVideoDecoderFactory;
import org.webrtc.DefaultVideoEncoderFactory;
import org.webrtc.EglBase;
import org.webrtc.IceCandidate;
import org.webrtc.MediaConstraints;
import org.webrtc.MediaStream;
import org.webrtc.PeerConnection;
import org.webrtc.PeerConnectionFactory;
import org.webrtc.SdpObserver;
import org.webrtc.SessionDescription;
import org.webrtc.SurfaceTextureHelper;
import org.webrtc.VideoFrame;
import org.webrtc.VideoSource;
import org.webrtc.VideoTrack;
import org.webrtc.DataChannel;

import java.util.ArrayList;

public class WebRTCSignalingHandler {
    private static final String TAG = WebRTCSignalingHandler.class.getSimpleName();
    private WebsocketClientHandler websocketClientHandler;
    private PeerConnection peerConnection;
    private PeerConnectionFactory peerConnectionFactory;
    private Context context;
    private VideoTrack videoTrack;
    private DJIVideoCapturer djiVideoCapturer;
    private EglBase eglBase;

    private PeerConnectionFactory initializePeerConnectionFactory() {
        // Initialize WebRTC globally
        PeerConnectionFactory.InitializationOptions initializationOptions = PeerConnectionFactory.InitializationOptions.builder(context)
                .createInitializationOptions();
        PeerConnectionFactory.initialize(initializationOptions);

        // Create the PeerConnectionFactory
        return PeerConnectionFactory.builder()
                .setVideoEncoderFactory(new DefaultVideoEncoderFactory(eglBase.getEglBaseContext(), true, true))
                .setVideoDecoderFactory(new DefaultVideoDecoderFactory(eglBase.getEglBaseContext()))
                .createPeerConnectionFactory();
    }

    public WebRTCSignalingHandler(WebsocketClientHandler websocketClientHandler, Context context) {
        this.websocketClientHandler = websocketClientHandler;
        this.context = context;
        this.eglBase = EglBase.create();
        this.peerConnectionFactory = initializePeerConnectionFactory();
        this.djiVideoCapturer = new DJIVideoCapturer();
        initializePeerConnection();
    }

    public void startWebRTCSignaling(TextureView textureView) {
        if (websocketClientHandler != null && websocketClientHandler.isConnected()) {
            createVideoTrack(textureView);
            createSDPOffer();
        } else {
            Log.e(TAG, "No WebSocket connection.");
        }
    }

    private void createVideoTrack(TextureView textureView) {
        try {
            SurfaceTextureHelper textureHelper = SurfaceTextureHelper.create("CaptureThread", eglBase.getEglBaseContext());

            djiVideoCapturer.initialize(textureHelper, context, new CapturerObserver() {
                @Override
                public void onFrameCaptured(VideoFrame videoFrame) {
                    if (videoTrack != null) {
                        videoTrack.addSink(frame -> Log.d(TAG, "Forwarding captured video frame."));
                    }
                }

                @Override
                public void onCapturerStarted(boolean success) {
                    Log.d(TAG, "Video capturer started: " + success);
                }

                @Override
                public void onCapturerStopped() {
                    Log.d(TAG, "Video capturer stopped.");
                }
            });

            djiVideoCapturer.startCapture(640, 480, 30);

            VideoSource videoSource = peerConnectionFactory.createVideoSource(djiVideoCapturer.isScreencast());
            videoTrack = peerConnectionFactory.createVideoTrack("videoTrack", videoSource);

            MediaStream mediaStream = peerConnectionFactory.createLocalMediaStream("localStream");
            mediaStream.addTrack(videoTrack);
            peerConnection.addStream(mediaStream);

            Log.d(TAG, "Video track created and added to peer connection.");
        } catch (Exception e) {
            Log.e(TAG, "Failed to create video track", e);
        }
    }

    private void createSDPOffer() {
        try {
            MediaConstraints mediaConstraints = new MediaConstraints();
            peerConnection.createOffer(new SdpObserver() {
                @Override
                public void onCreateSuccess(SessionDescription desc) {
                    sendSDPOffer(desc.description);
                }

                @Override
                public void onSetSuccess() {}

                @Override
                public void onCreateFailure(String s) {
                    Log.e(TAG, "Failed to create SDP offer: " + s);
                }

                @Override
                public void onSetFailure(String s) {}
            }, mediaConstraints);
        } catch (Exception e) {
            Log.e(TAG, "Failed to create SDP offer", e);
        }
    }

    public void sendSDPOffer(String sdpOffer) {
        if (websocketClientHandler != null && websocketClientHandler.isConnected()) {
            String iceMessage = "ICE/SDP " + sdpOffer;
            websocketClientHandler.send(iceMessage);
            Log.d(TAG, "Sent SDP offer.");
        } else {
            Log.e(TAG, "No WebSocket connection.");
        }
    }

    public void addIceCandidate(IceCandidate candidate) {
        if (peerConnection != null) {
            peerConnection.addIceCandidate(candidate);
            Log.d(TAG, "Added ICE Candidate: " + candidate.sdp);
        }
    }

    private void initializePeerConnection() {
        PeerConnection.Observer observer = new PeerConnection.Observer() {
            @Override
            public void onSignalingChange(PeerConnection.SignalingState signalingState) {
                Log.d(TAG, "Signaling state changed: " + signalingState);
            }

            @Override
            public void onIceConnectionChange(PeerConnection.IceConnectionState iceConnectionState) {
                Log.d(TAG, "ICE connection state changed: " + iceConnectionState);
            }

            @Override
            public void onDataChannel(DataChannel dataChannel) {
                Log.d(TAG, "Data channel is not used.");
            }

            @Override
            public void onIceConnectionReceivingChange(boolean receiving) {
                Log.d(TAG, "ICE connection receiving change: " + receiving);
            }

            @Override
            public void onIceCandidate(IceCandidate candidate) {
                Log.d(TAG, "New ICE candidate: " + candidate.sdp);
                websocketClientHandler.sendIceCandidate(candidate);
            }

            @Override
            public void onIceGatheringChange(PeerConnection.IceGatheringState iceGatheringState) {
                Log.d(TAG, "ICE gathering state changed: " + iceGatheringState);
            }

            @Override
            public void onAddStream(MediaStream mediaStream) {
                Log.d(TAG, "New media stream added.");
            }

            @Override
            public void onRemoveStream(MediaStream mediaStream) {
                Log.d(TAG, "Media stream removed.");
            }

            @Override
            public void onIceCandidatesRemoved(IceCandidate[] candidates) {
                Log.d(TAG, "ICE candidates removed.");
            }

            @Override
            public void onRenegotiationNeeded() {
                Log.d(TAG, "Renegotiation needed.");
            }
        };

        // Initialize PeerConnection with no ICE servers for local network
        PeerConnection.RTCConfiguration rtcConfig = new PeerConnection.RTCConfiguration(new ArrayList<>());
        peerConnection = peerConnectionFactory.createPeerConnection(rtcConfig, observer);
    }
}
