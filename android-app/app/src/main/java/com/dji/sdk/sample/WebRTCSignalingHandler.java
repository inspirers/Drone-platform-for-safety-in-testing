package com.dji.sdk.sample;
import android.util.Log;
import com.dji.sdk.sample.WebsocketClientHandler; 
import org.webrtc.MediaConstraints;
import org.webrtc.PeerConnection;
import org.webrtc.PeerConnectionFactory;
import org.webrtc.SdpObserver;
import org.webrtc.SessionDescription;
import android.content.Context;


public class WebRTCSignalingHandler {
    
    private WebsocketClientHandler websocketClientHandler;
    private PeerConnection peerConnection;
    private PeerConnectionFactory peerConnectionFactory;
    private Context context; 

    public WebRTCSignalingHandler(WebsocketClientHandler websocketClientHandler) {
        this.websocketClientHandler = websocketClientHandler;
        this.peerConnectionFactory = initializePeerConnectionFactory();
    }

    public void startWebRTCSignaling() {
        if (websocketClientHandler != null && websocketClientHandler.isConnected()) {
            // Example: send SDP offer automatically when connection is ready
            createSDPOffer();
        } else {
            Log.e("WebRTC", "No WebSocket connection.");
        }
    }

    private void createSDPOffer() {
        MediaConstraints mediaConstraints = new MediaConstraints();  // Set any desired constraints
        peerConnection.createOffer(new SdpObserver() {
            @Override
            public void onCreateSuccess(SessionDescription desc) {
                String sdpOffer = desc.description;  // This is the dynamically created SDP offer
                sendSDPOffer(sdpOffer);  // Send it over WebSocket
            }

            @Override
            public void onSetSuccess() {}

            @Override
            public void onCreateFailure(String s) {}

            @Override
            public void onSetFailure(String s) {}
        }, mediaConstraints);
    }

    public void sendSDPOffer(String sdpOffer) {
        if (websocketClientHandler != null && websocketClientHandler.isConnected()) {
            String iceMessage = "ICE/SDP " + sdpOffer;
            websocketClientHandler.send(iceMessage);
            Log.d("WebRTC", "Sent SDP offer.");
        } else {
            Log.e("WebRTC", "No WebSocket connection.");
        }
    }

    private PeerConnectionFactory initializePeerConnectionFactory() {
        // Initialize WebRTC library with the application's context
        PeerConnectionFactory.InitializationOptions initializationOptions =
            PeerConnectionFactory.InitializationOptions.builder(context)
                .createInitializationOptions();
        PeerConnectionFactory.initialize(initializationOptions);
    
        // Create a default PeerConnectionFactory instance using builder
        return PeerConnectionFactory.builder().createPeerConnectionFactory();
    }
}
