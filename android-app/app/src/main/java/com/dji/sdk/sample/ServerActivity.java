package com.dji.sdk.sample;

import androidx.appcompat.app.AppCompatActivity;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;
import android.view.TextureView;

import com.dji.sdk.sample.databinding.ActivityServerBinding;

import org.w3c.dom.Text;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.Locale;

import dev.gustavoavila.websocketclient.WebSocketClient;
import dji.thirdparty.afinal.core.AsyncTask;

public class ServerActivity extends AppCompatActivity {
    private final String TAG = ServerActivity.class.getName();
    private WebsocketClientHandler websocketClientHandler;
    private WebRTCSignalingHandler signalingHandler;
    EditText ipTextEdit;
    EditText portEdit;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_server);
        ipTextEdit = findViewById(R.id.ip_adress_edit);
        portEdit = findViewById(R.id.portEdit);
    }

    @Override
    protected void onResume() {
        super.onResume();
        updateStatus(); //Start updating the status as soon as the activity is resumed.
    }

    /**
     * Handles the onclick event of the connect button. First, it creates a URI based on
     * the IP and Port fields. Then, it works what webSocketClientHandler to use and stores that.
     * Finally, it connects if the current client isn't already connected.
     */
    public void connectClick(View v) {
        Log.e(TAG, "button clicked!");
        URI newUri;
        try {
            newUri = new URI("ws://" + ipTextEdit.getText() + ":" + portEdit.getText());
        } catch (URISyntaxException e) {
            Toast.makeText(this, "Incorrectly formatted URI", Toast.LENGTH_SHORT).show();
            return;
        }

        // There is a new URI in the field, create a new Client
        if (WebsocketClientHandler.isInstanceCreated() && newUri != websocketClientHandler.getUri()) {
            websocketClientHandler = WebsocketClientHandler.resetClientHandler(newUri);
        } else if (WebsocketClientHandler.isInstanceCreated()) {
            //Otherwise, it's the same socket, just get the new one
            websocketClientHandler = WebsocketClientHandler.getInstance();
        } else {
            // If there is none, create a new one.
            websocketClientHandler = WebsocketClientHandler.createInstance(newUri);
        }

        //Connect only if the client isn't connected
        if (!websocketClientHandler.isConnected()) {
            //This is OK, following block above
            websocketClientHandler.connect();
            toastOnUIThread("Connecting...");
        } else {
            toastOnUIThread("Already connected!");
        }
    }

    public void onWebSocketConnected() {
        // Initialize the WebRTCSignalingHandler
        signalingHandler = new WebRTCSignalingHandler(websocketClientHandler, this); // `this` provides the Activity's Context

        // Find the TextureView from your activity's layout
        TextureView textureView = findViewById(R.id.video_texture_view);

        if (textureView != null) {
            // Start WebRTC signaling (it will create and send SDP offer)
            signalingHandler.startWebRTCSignaling(textureView);
        } else {
            Log.e(TAG, "TextureView not found in the layout.");
            Toast.makeText(this, "Unable to initialize WebRTC signaling: TextureView not found.", Toast.LENGTH_SHORT).show();
        }
    }

    /**
     * Sends a simple websocket message, for debugging.
     */
    public void sendClick(View v) {
        Log.e(TAG, "send clicked!");
        String message = "{\"msg_type\": \"Debug\",\"msg\": \"Hello, from Android!\"}";
        websocketClientHandler.send(message);
    }

    /**
     * A simpler toast method that can be called from Async
     * @param message The message to toast
     */
    private void toastOnUIThread(String message) {
        runOnUiThread(() -> Toast.makeText(ServerActivity.this, message, Toast.LENGTH_SHORT).show());
    }

    /**
     * Continually update the status.
     * Currently only checking for Connection/No connection/No instance
     */
    private void updateStatus() {
        AsyncTask.execute(() -> {
            //This uses busy-wait, which isn't great...
            while (true) {
                try {
                    runOnUiThread(updateRunnable);
                    WebsocketClientHandler.status_update.acquire();
                } catch (InterruptedException e) {
                    Log.e(TAG, "interrupted!");
                }
            }
        });
    }

    private final Runnable updateRunnable = new Runnable() {
        //Factored out into a separate runnable to avoid so many levels of nesting.
        @Override
        public void run() {
            TextView connectionStatusView = findViewById(R.id.banankaka);
            if (WebsocketClientHandler.isInstanceCreated() && websocketClientHandler.isConnected()) {
                connectionStatusView.setText(String.format("Connected to: %s", websocketClientHandler.getUri()));
            } else if (WebsocketClientHandler.isInstanceCreated()) {
                connectionStatusView.setText(String.format("Disconnected from: %s", websocketClientHandler.getUri()));
            } else {
                connectionStatusView.setText("No Client initialized");
            }
        }
    };
}
