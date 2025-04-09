package com.dji.sdk.sample;

import android.util.Log;

import java.util.Locale;

import dji.common.battery.BatteryState;
import dji.common.flightcontroller.FlightControllerState;
import dji.common.flightcontroller.LocationCoordinate3D;
import dev.gustavoavila.websocketclient.WebSocketClient;
import dji.sdk.base.BaseProduct;
import dji.sdk.battery.Battery;
import dji.common.battery.BatteryState;
import dji.sdk.products.HandHeld;
import dji.sdk.sdkmanager.DJISDKManager;

class WSPosition implements Runnable {
    private static final String TAG = WSPosition.class.getSimpleName();
    private final WebSocketClient webSocketClient;
    private volatile boolean isRunning = true; // Flag to control the loop

    // Constructor to receive the WebSocketClient instance
    public WSPosition(WebSocketClient client) {
        this.webSocketClient = client;
    }

    @Override
    public void run() {
        Log.i(TAG, "WSPosition thread started.");
        // TODO Check that it is connected
        while (isRunning && webSocketClient != null ) {
            try {
                // Get the FlightManager instance (since it's a singleton)
                // TODO solve when flight manager is unavailable causes error
                FlightManager flightManager = FlightManager.getFlightManager();
                BaseProduct product = DJISDKManager.getInstance().getProduct();
                BatteryState batteryState = flightManager.getBatteryState();
                int batteryPercent = -1;

                if (flightManager != null) {
                    // Get the current state
                    FlightControllerState currentState = flightManager.getState();

                    if (currentState != null) {
                        LocationCoordinate3D location = currentState.getAircraftLocation();

                        // Important: Check if location data is valid (non-zero and not NaN)
                        // DJI SDK often returns 0 or NaN before a valid GPS lock.
                        if (location != null &&
                            !Double.isNaN(location.getLatitude()) &&
                            !Double.isNaN(location.getLongitude()) &&
                            (location.getLatitude() != 0.0 || location.getLongitude() != 0.0))
                        {
                            double latitude = location.getLatitude();
                            double longitude = location.getLongitude();
                            float altitude = location.getAltitude(); // You might want altitude too
                            batteryPercent = batteryState.getChargeRemainingInPercent();
                            // Speed (NED frame: North, East, Down)
                            float velocityX = currentState.getVelocityX(); // Speed towards North (m/s)
                            float velocityY = currentState.getVelocityY(); // Speed towards East (m/s)
                            float verticalSpeed = currentState.getVelocityZ();   // Speed downwards (m/s). Negative value means climbing.
                            double horizontalSpeed = Double.NaN;
                            // Calculate horizontal speed
                            if (!Float.isNaN(velocityX) && !Float.isNaN(velocityY)) {
                                horizontalSpeed = Math.sqrt(velocityX * velocityX + velocityY * velocityY);
                            }
                            // Format the data (e.g., as JSON)
                            String message = String.format(Locale.US,
                                    "{\"msg_type\": \"Position\",\"latitude\": %.8f, \"longitude\": %.8f, \"altitude\": %.2f, \"speed\": %.2f, \"batteryPercent\": %d}",
                                    latitude, longitude, altitude, horizontalSpeed, batteryPercent);

                            // Send the data via WebSocket
                            Log.d(TAG, "Sending position: " + message);
                            webSocketClient.send(message);

                        } else {
                            Log.d(TAG, "Waiting for valid location data...");
                        }
                    } else {
                        Log.d(TAG, "FlightControllerState is null.");
                    }
                } else {
                    Log.e(TAG, "FlightManager instance is null.");
                    // Consider stopping if FlightManager can't be obtained
                    // stopRunning();
                }

                // Wait for 1 second before sending the next update
                Thread.sleep(1000);

            } catch (InterruptedException e) {
                Log.w(TAG, "WSPosition thread interrupted.");
                Thread.currentThread().interrupt(); // Restore interruption status
                isRunning = false; // Stop the loop if interrupted
            } catch (Exception e) {
                // Catch other potential exceptions during data fetching or sending
                Log.e(TAG, "Error in WSPosition loop: " + e.getMessage(), e);
                // Consider adding a small delay before retrying after an error
                try { Thread.sleep(500); } catch (InterruptedException ie) { Thread.currentThread().interrupt(); isRunning = false; }
            }
        }
        Log.i(TAG, "WSPosition thread finished.");
    }

    // Method to signal the thread to stop
    public void stopRunning() {
        isRunning = false;
        Log.i(TAG, "WSPosition stop requested.");
    }
} 
