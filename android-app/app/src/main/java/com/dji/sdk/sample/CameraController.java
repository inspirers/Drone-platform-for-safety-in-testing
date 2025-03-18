package com.dji.sdk.sample;

import android.content.Context;
import android.util.Log;
import android.view.TextureView;
import android.widget.Toast;

import androidx.annotation.NonNull;

import dji.common.error.DJIError;
import dji.common.gimbal.GimbalState;
import dji.common.gimbal.Rotation;
import dji.common.gimbal.RotationMode;
import dji.common.product.Model;
import dji.sdk.base.BaseProduct;
import dji.sdk.camera.VideoFeeder;
import dji.sdk.codec.DJICodecManager;
import dji.sdk.gimbal.Gimbal;
import dji.sdk.sdkmanager.DJISDKManager;

import java.lang.Math;

/**
 * This singleton class is responsible for setting up a VideoDataListener,
 * managing the video feed from the drone, and controlling the gimbal.
 */
public class CameraController {
    private static volatile CameraController instance = null;
    private DJICodecManager codecManager;
    private VideoFeeder.VideoDataListener receivedVideoDataListener;
    private BaseProduct drone;
    private Gimbal gimbal; // Store reference to gimbal
    private boolean isGimbalOverloaded = false;
    public static final String CAM_LOADED_FLAG = "camera_loaded";
    private float yawAngle = 0.0f;

    /**
     * Private constructor to enforce singleton pattern.
     */
    private CameraController() {
        // Set up a VideoDataListener
        receivedVideoDataListener = (videoBuffer, size) -> {
            if (codecManager != null) {
                codecManager.sendDataToDecoder(videoBuffer, size);
            }
        };

        // Get a connection to the connected drone
        drone = DJISDKManager.getInstance().getProduct();
        if (drone != null) {
            gimbal = drone.getGimbal();
            if (gimbal != null) {
                gimbal.setStateCallback(new GimbalState.Callback() {
                    @Override
                    public void onUpdate(@NonNull GimbalState gimbalState) {
                        isGimbalOverloaded = gimbalState.isMotorOverloaded();
                        yawAngle = gimbalState.getYawRelativeToAircraftHeading();
                    }
                });
            } else {
                Log.e("CameraController", "Gimbal is not available.");
            }
        }
    }

    /**
     * Returns the singleton instance of the CameraController.
     * Ensures only one instance exists at a time.
     */
    public static synchronized CameraController getInstance() {
        if (instance == null) {
            synchronized (CameraController.class) {
                if (instance == null) {
                    instance = new CameraController();
                }
            }
        }
        return instance;
    }

    /**
     * Retrieves the DJICodecManager instance.
     * @return The DJICodecManager instance.
     */
    public DJICodecManager getCodecManager() {
        return codecManager;
    }

    /**
     * Initializes the video previewer and sets up the video feed.
     */
    public void initPreviewer(TextureView cameraTextureView,
                              Context callingContext,
                              TextureView.SurfaceTextureListener surfaceTextureListener) {
        if (drone == null || !drone.isConnected()) {
            Toast.makeText(callingContext, R.string.disconnected, Toast.LENGTH_SHORT).show();
        } else {
            if (cameraTextureView != null) {
                cameraTextureView.setSurfaceTextureListener(surfaceTextureListener);
            }
            if (!drone.getModel().equals(Model.UNKNOWN_AIRCRAFT)) {
                VideoFeeder.getInstance().getPrimaryVideoFeed().addVideoDataListener(receivedVideoDataListener);
            } else {
                Toast.makeText(callingContext, "Unknown device connected. Check SDK compatibility.", Toast.LENGTH_SHORT).show();
            }
        }
    }

    /**
     * Rotates the gimbal to an absolute rotation.
     */
    public boolean gimbalAbs(Context callingContext, float roll, float yaw, float pitch) {
        if (isGimbalOverloaded) {
            Toast.makeText(callingContext, "Gimbal overloaded!", Toast.LENGTH_SHORT).show();
            return false;
        }
        if (gimbal == null) {
            Toast.makeText(callingContext, "No gimbal found!", Toast.LENGTH_SHORT).show();
            return false;
        }

        Rotation targetRot = new Rotation.Builder()
                .roll(roll)
                .yaw(yaw)
                .pitch(pitch)
                .time(0.1)
                .mode(RotationMode.ABSOLUTE_ANGLE)
                .build();

        gimbal.rotate(targetRot, djiError -> handleGimbalError(callingContext, djiError));
        return true;
    }

    /**
     * Rotates the gimbal to a relative rotation.
     */
    public boolean gimbalRel(Context callingContext, float roll, float yaw, float pitch) {
        if (Math.abs(yawAngle + yaw) > 90) {
            Log.e("gimbal", "Gimbal max yaw rotation reached");
            return false;
        }
        if (isGimbalOverloaded) {
            return false;
        }
        if (gimbal == null) {
            Toast.makeText(callingContext, "No gimbal found!", Toast.LENGTH_SHORT).show();
            return false;
        }

        Rotation targetRot = new Rotation.Builder()
                .roll(roll)
                .yaw(yaw)
                .pitch(pitch)
                .time(0.1)
                .mode(RotationMode.RELATIVE_ANGLE)
                .build();

        gimbal.rotate(targetRot, djiError -> handleGimbalError(callingContext, djiError));
        return true;
    }

    /**
     * Moves the gimbal to a downward-facing position.
     */
    public boolean gimbalDown(Context callingContext) {
        return gimbalAbs(callingContext, 0, 0, -90);
    }

    /**
     * Rotates the gimbal to the right by a given number of degrees.
     */
    public boolean gimbalRight(Context callingContext, float degrees) {
        return gimbalRel(callingContext, 0, degrees, 0);
    }

    /**
     * Rotates the gimbal to the left by a given number of degrees.
     */
    public boolean gimbalLeft(Context callingContext, float degrees) {
        return gimbalRel(callingContext, 0, -degrees, 0);
    }

    /**
     * Handles gimbal rotation errors.
     */
    private void handleGimbalError(Context context, DJIError djiError) {
        if (djiError != null) {
            Log.e("CameraController", "Gimbal error: " + djiError.getDescription());
            Toast.makeText(context, "Gimbal error: " + djiError.getDescription(), Toast.LENGTH_SHORT).show();
        }
    }

    /**
     * Releases resources when no longer needed.
     */
    public void releaseResources() {
        if (gimbal != null) {
            gimbal.setStateCallback(null);
        }
        if (VideoFeeder.getInstance().getPrimaryVideoFeed() != null) {
            VideoFeeder.getInstance().getPrimaryVideoFeed().removeVideoDataListener(receivedVideoDataListener);
        }
        instance = null;
    }
}