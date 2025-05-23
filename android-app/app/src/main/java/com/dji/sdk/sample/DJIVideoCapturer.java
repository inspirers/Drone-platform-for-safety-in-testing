package com.dji.sdk.sample;

import org.webrtc.CapturerObserver;
import org.webrtc.NV12Buffer;
import org.webrtc.SurfaceTextureHelper;
import org.webrtc.VideoCapturer;
import org.webrtc.VideoFrame;


import android.content.Context;
import android.graphics.SurfaceTexture;
import android.media.MediaFormat;
import android.os.SystemClock;

import java.nio.ByteBuffer;
import java.util.ArrayList;
import java.util.concurrent.TimeUnit;

import dji.sdk.camera.VideoFeeder;
import dji.sdk.codec.DJICodecManager;

public class DJIVideoCapturer implements VideoCapturer {
    private final static String TAG = "DJIStreamer";

    private static DJICodecManager codecManager;
    private static final ArrayList<CapturerObserver> observers = new ArrayList<CapturerObserver>();

    private final String droneDisplayName;
    private Context context;
    private CapturerObserver capturerObserver;

    public DJIVideoCapturer(String droneDisplayName){
        this.droneDisplayName = droneDisplayName;
    }

    private void setupVideoListener() {
        if (codecManager != null) {
            return; 
        }
    
   
        codecManager = new DJICodecManager(context, (SurfaceTexture) null, 0, 0);
        codecManager.enabledYuvData(true);
        codecManager.setYuvDataCallback(new DJICodecManager.YuvDataCallback() {
            @Override
            public void onYuvDataReceived(MediaFormat mediaFormat, ByteBuffer videoBuffer, int dataSize, int width, int height) {
                if (videoBuffer != null) {
                    try {
                        //Convert to NV12Buffer and create a VideoFrame
                        long timestampNS = TimeUnit.MILLISECONDS.toNanos(SystemClock.elapsedRealtime());
                        NV12Buffer buffer = new NV12Buffer(
                                width,
                                height,
                                mediaFormat.getInteger(MediaFormat.KEY_STRIDE),
                                mediaFormat.getInteger(MediaFormat.KEY_SLICE_HEIGHT),
                                videoBuffer,
                                null
                        );
                        VideoFrame videoFrame = new VideoFrame(buffer, 0, timestampNS);
    
                        // Feed the video frame to all observers
                        for (CapturerObserver obs : observers) {
                            obs.onFrameCaptured(videoFrame);
                        }
                        videoFrame.release();
                    } catch (Exception e) {
                        e.printStackTrace(); // Improved error logging can be added here
                    }
                }
            }
        });
    
        // Handle video data listener for specific drone models
        addVideoDataListenerForDroneModel(this.droneDisplayName);
    }
    
    private void addVideoDataListenerForDroneModel(String droneModel) {
        switch (droneModel) {
            case "DJI Mavic Enterprise 2":
                // Only add listener once for this drone model to avoid duplication
                if (!isListenerAdded) {
                    VideoFeeder.VideoDataListener videoDataListener = new VideoFeeder.VideoDataListener() {
                        @Override
                        public void onReceive(byte[] bytes, int dataSize) {
                            // Send the encoded data to codec manager for YUV decoding
                            codecManager.sendDataToDecoder(bytes, dataSize);
                        }
                    };
                    VideoFeeder.getInstance().getPrimaryVideoFeed().addVideoDataListener(videoDataListener);
                    isListenerAdded = true; // Flag indicating that listener has been added
                }
                break;
    
            // Add more cases for different drone models as needed
            default:
                // Handle default case or add more models
                break;
        }
    }
    
    // A flag to prevent adding the listener multiple times
    private boolean isListenerAdded = false;
    

    @Override
    public void initialize(SurfaceTextureHelper surfaceTextureHelper, Context applicationContext,
                           CapturerObserver capturerObserver) {
        this.context = applicationContext;
        this.capturerObserver = capturerObserver;

        observers.add(capturerObserver);
    }

    @Override
    public void startCapture(int width, int height, int framerate) {
        // Hook onto the DJI onYuvDataReceived event
        setupVideoListener();
    }

    @Override
    public void stopCapture() throws InterruptedException {
    }

    @Override
    public void changeCaptureFormat(int width, int height, int framerate) {
        // Empty on purpose
    }

    @Override
    public void dispose() {
        // Stop receiving frames on the callback from the decoder
        if (observers.contains(capturerObserver))
            observers.remove(capturerObserver);
    }

    @Override
    public boolean isScreencast() {
        return false;
    }
}