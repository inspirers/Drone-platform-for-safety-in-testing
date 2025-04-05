package com.dji.sdk.sample;

import android.util.Log;

import androidx.annotation.Nullable;

import java.io.IOException;
import java.net.URI;
import java.util.concurrent.Semaphore;

import dev.gustavoavila.websocketclient.WebSocketClient;

/**
 * Handles a websocket connection by implementing the library.
 * The class remembers two things, the last bytes, and the last string it received. These are
 * accessible through the methods getLastBytesReceived() and getLastStringReceived(). There is
 * also a semaphore which can be used to to read when a new string is used.
 * TODO: Write a better way of implementing the notification, probably based on the
 * different types of messages.
 */
public class WebsocketClientHandler {
    private static WebsocketClientHandler clientHandler = null;
    private URI uri = null;
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

    /**
     * Check if an instance has been created
     * @return True if an instance has been created, false if nor
     */
    public static boolean isInstanceCreated(){
        return clientHandler != null;
    }

    /**
     * Create an instance of the class. Overwrites the current instance if one exists.
     * @param uri The URI of the server
     * @return The instance of WebsocketClient
     */
    public static WebsocketClientHandler createInstance(URI uri){
        clientHandler = new WebsocketClientHandler(uri);
        return clientHandler;
    }

    private WebsocketClientHandler(URI uri){
        this.uri = uri;
        //Use the webSocketClient implementation in TODO: Link
        //These methods are called by the package, rather than by our code.
        webSocketClient = new WebSocketClient(uri) {
            @Override
            public void onOpen() {
                Log.d(TAG, "New connection opened on URI" + getUri());
                connected = true;
                startPositionSending();
                WebsocketClientHandler.status_update.release();
            }

            @Override
            public void onTextReceived(String message) {
                Log.d(TAG, "Received: " + message);
                lastStringReceived = message;
                new_string.release();
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
                if (e.getClass() == IOException.class){
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
        //As the client will send more than it will receive, it will stay open for an hour
        webSocketClient.setReadTimeout(30000);
        webSocketClient.enableAutomaticReconnection(1000);
    }

    /**
     * @return The URI of the server
     */
    public URI getUri() {
        return uri;
    }

    /**
     * Creates a new WebsocketHandler with the specified URI.
     * If a connection is open on the old URI, it is closed.
     * Note that all received data is lost.
     * @param uri The URI for the new Client
     */
    public static WebsocketClientHandler resetClientHandler(URI uri) {
        clientHandler = new WebsocketClientHandler(uri);
        return clientHandler;
    }

    /**
     * Check whether the websocket is connected or not.
     * @return True if the socket is connected, false if not
     */
    public boolean isConnected() {
        return connected;
    }

    /**
     * Send a String message to the server.
     * @param message The string to send to the client
     * @return True if sent, false if the client is not connected
     */
    public boolean send(String message){
        Log.w(TAG, "Sending...");
        if (isConnected()){
            webSocketClient.send(message);
            return true;
        } else{
            return false;
        }
    }

    /**
     * Send a byte[] of data to the server.
     * @param data The data to send to the client
     * @return True if sent, false if the client is not connected
     */
    public boolean send(byte[] data){
        if (isConnected()){
            webSocketClient.send(data);
            return true;
        } else{
            return false;
        }
    }

    /**
     *
     * @return The last bytes that were received by the client
     */
    public byte[] getLastBytesReceived() {
        return lastBytesReceived;
    }

    /**
     *
     * @return The last String that were received by the client
     */
    public String getLastStringReceived() {
        return lastStringReceived;
    }

    /**
     * Close the websocket connection.
     */
    public void closeConnection(){
        if (isConnected()){
            webSocketClient.close(1, 1001, "Connection closed by app");
            connected = false;
        }
    }

    /**
     *
     * @return True if the client was not connected but existed, otherwise false
     */
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

