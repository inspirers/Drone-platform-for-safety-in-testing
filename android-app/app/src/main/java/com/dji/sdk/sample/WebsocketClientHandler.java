package com.dji.sdk.sample;

import android.util.Log;
import org.webrtc.IceCandidate; // WebRTC ICE Candidate
import org.json.JSONObject; // JSON handling
import org.json.JSONException; // JSON error handling
import androidx.annotation.Nullable;
import java.io.IOException;
import java.net.URI;
import java.util.concurrent.Semaphore;
import dev.gustavoavila.websocketclient.WebSocketClient;

public class WebsocketClientHandler {
    private static WebsocketClientHandler clientHandler = null;
    private URI uri = null;
    private WebRTCSignalingHandler signalingHandler;
    private final WebSocketClient webSocketClient;
    public static final String TAG = WebsocketClientHandler.class.getName();
    private boolean connected = false;
    private String lastStringReceived = "Nothing received...";
    private byte[] lastBytesReceived = null;
    public static Semaphore new_string = new Semaphore(0);
    public static Semaphore status_update = new Semaphore(0);

    private WSPosition wsPositionRunnable;
    private Thread wsPositionThread;

    /**
     * Get the active instance of the WebsocketClientHandler.
     * @return Returns null if the client hasn't been created, returns
     * the WebsocketClientHandler if it has been instantiated
     */

    @Nullable
    public static WebsocketClientHandler getInstance(){
        return clientHandler;
    }

    public static boolean isInstanceCreated(){
        return clientHandler != null;
    }

    public void sendIceCandidate(IceCandidate candidate) {
        try {
            JSONObject message = new JSONObject();
            message.put("msg_type", "candidate");
            message.put("sdpMid", candidate.sdpMid);
            message.put("sdpMLineIndex", candidate.sdpMLineIndex);
            message.put("candidate", candidate.sdp);
            send(message.toString());
            Log.d(TAG, "Sent ICE candidate: " + message.toString());
        } catch (JSONException e) {
            Log.e(TAG, "Failed to send ICE candidate", e);
        }
    }

    public static WebsocketClientHandler createInstance(URI uri){
        clientHandler = new WebsocketClientHandler(uri);
        return clientHandler;
    }

    private WebsocketClientHandler(URI uri){
        this.uri = uri;
        webSocketClient = new WebSocketClient(uri) {
            @Override
            public void onOpen() {
                Log.d(TAG, "New connection opened on URI " + getUri());
                connected = true;
                startPositionSending();
                WebsocketClientHandler.status_update.release();
            }



            @Override
            public void onTextReceived(String message) {
                try {
                    JSONObject jsonMessage = new JSONObject(message);
                    String type = jsonMessage.getString("msg_type");
                    // FlightManager flightManager = FlightManager.getFlightManager();

                    if (type.equals("Coordinate_request")) {
                        Log.d(TAG, "Received: " + message);
                        lastStringReceived = message;
                        new_string.release();
                    } else if (type.equals("offer") || type.equals("answer") || type.equals("candidate")) {
                        // Forward WebRTC signaling messages to WebRTCSignalingHandler
                        signalingHandler.processMessage(jsonMessage);
                    } else if (type.equals("flight_arm")) {
                        Log.d(TAG, "Attempting to take off");
                    FlightManager flightManager = FlightManager.getFlightManager();
                        flightManager.onArm();
                    } else if (type.equals("flight_take_off")) {
                        Log.d(TAG, "Attempting to take off");
                    FlightManager flightManager = FlightManager.getFlightManager();
                        flightManager.startWaypointMission();
                    } else if (type.equals("flight_return_to_home")) {
                        Log.d(TAG, "Attempting to return to home");
                    FlightManager flightManager = FlightManager.getFlightManager();
                        flightManager.goingHome();
                    } else {
                        Log.w(TAG, "Unhandled message type: " + type);
                    }
                } catch (JSONException e) {
                    Log.e(TAG, "Failed to parse message: " + e.getMessage());
                }
            }

            @Override
            public void onBinaryReceived(byte[] data) {
                Log.d(TAG, "Received bytes");
                lastBytesReceived = data;
            }

            @Override
            public void onPingReceived(byte[] data) {
                Log.d(TAG, "PING");
            }

            @Override
            public void onPongReceived(byte[] data) {
                Log.d(TAG, "PONG");
            }

            @Override
            public void onException(Exception e) {
                Log.e(TAG, e.toString());
                if (e instanceof IOException){
                    closeConnection();
                }
            }

            @Override
            public void onCloseReceived(int reason, String description) {
                Log.d(TAG, String.format("Closed with code %d, %s", reason, description));
                connected = false;
                stopPositionSending();
                WebsocketClientHandler.status_update.release();
            }
        };
        webSocketClient.setConnectTimeout(15000);
        webSocketClient.setReadTimeout(30000);
        webSocketClient.enableAutomaticReconnection(1000);
    }

    public URI getUri() {
        return uri;
    }

    public static WebsocketClientHandler resetClientHandler(URI uri) {
        clientHandler = new WebsocketClientHandler(uri);
        return clientHandler;
    }

    public boolean isConnected() {
        return connected;
    }

    public boolean send(String message){
        Log.w(TAG, "Sending...");
        if (isConnected()){
            webSocketClient.send(message);
            return true;
        } else{
            Log.e(TAG, "WebSocket is not connected.");
            return false;
        }
    }

    public boolean send(byte[] data){
        if (isConnected()){
            webSocketClient.send(data);
            return true;
        } else{
            Log.e(TAG, "WebSocket is not connected.");
            return false;
        }
    }

    public byte[] getLastBytesReceived() {
        return lastBytesReceived;
    }

    public String getLastStringReceived() {
        return lastStringReceived;
    }

    public void closeConnection(){
        if (isConnected()){
            webSocketClient.close(1, 1001, "Connection closed by app");
            connected = false;
        }
    }

    public boolean connect(){
        if (isConnected()){
            return false;
        }
        if (webSocketClient != null){
            webSocketClient.connect();
            WSPosition WSPosition = new WSPosition(webSocketClient);
            Thread thread = new Thread(WSPosition);
            thread.start();
            return true;
        }
        return false;
    }

    private synchronized void startPositionSending() {
        if (wsPositionThread == null || !wsPositionThread.isAlive()) {
            Log.i(TAG, "Starting position sending thread...");
            wsPositionRunnable = new WSPosition(this.webSocketClient); // Pass the client
            wsPositionThread = new Thread(wsPositionRunnable, "WebSocketPositionSender");
            wsPositionThread.start();
        } else {
            Log.w(TAG, "Position sending thread already running.");
        }
    }

    private synchronized void stopPositionSending() {
        if (wsPositionRunnable != null) {
            Log.i(TAG, "Requesting position sending thread to stop...");
            wsPositionRunnable.stopRunning(); // Signal the runnable to stop
        }
        if (wsPositionThread != null && wsPositionThread.isAlive()) {
            Log.i(TAG, "Interrupting position sending thread...");
            wsPositionThread.interrupt(); // Interrupt sleep/wait
            try {
                // Optionally wait a short time for the thread to finish cleanly
                 wsPositionThread.join(500); // Wait max 500ms
                 Log.i(TAG, "Position sending thread joined.");
            } catch (InterruptedException e) {
                Log.w(TAG, "Interrupted while joining position sending thread.");
                Thread.currentThread().interrupt();
            }
        }
        wsPositionRunnable = null; // Clear references
        wsPositionThread = null;
         Log.i(TAG, "Position sending stopped.");
    }
}

