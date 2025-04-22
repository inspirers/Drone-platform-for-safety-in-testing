/* Originally sourced from
* https://chromium.googlesource.com/external/webrtc/+/b6760f9e4442410f2bcb6090b3b89bf709e2fce2/webrtc/api/android/java/src/org/webrtc/CameraVideoCapturer.java
* and rewritten to work for DJI drones.
*  */
package com.dji.sdk.sample;

import org.webrtc.CapturerObserver;
import org.webrtc.NV12Buffer;
import org.webrtc.SurfaceTextureHelper;
import org.webrtc.VideoCapturer;
import org.webrtc.VideoFrame;
import org.webrtc.JavaI420Buffer;  // For creating the I420 buffer
import java.nio.ByteBuffer;       // For handling raw video buffer
import java.util.concurrent.TimeUnit;  // For timestamp calculations



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
            return; // If codecManager is already initialized, return immediately
        }
    
        // Pass SurfaceTexture as null to force the YUV callback - width and height do not matter here
        codecManager = new DJICodecManager(context, (SurfaceTexture) null, 0, 0);
        codecManager.enabledYuvData(true);
        codecManager.setYuvDataCallback(new DJICodecManager.YuvDataCallback() {
            @Override
            public void onYuvDataReceived(MediaFormat mediaFormat, ByteBuffer videoBuffer, int dataSize, int width, int height) {
                if (videoBuffer != null) {
                    try {
                        
                        long timestampNS = TimeUnit.MILLISECONDS.toNanos(SystemClock.elapsedRealtime());
                        
                        // Extract NV12 data from the ByteBuffer
                        byte[] nv12Data = new byte[dataSize];
                        videoBuffer.get(nv12Data); // Get the NV12 data

                        // Allocate an I420 buffer
                        JavaI420Buffer i420Buffer = JavaI420Buffer.allocate(width, height);

                        int ySize = width * height; // Full Y plane size
                        int uvSize = (width / 2) * (height / 2); // Size of U/V chrominance planes

                        // Copy Y plane from NV12 to I420 buffer
                        i420Buffer.getDataY().put(nv12Data, 0, ySize);

                        // Deinterleave NV12 UV plane into separate U and V planes in I420 format
                        ByteBuffer uBuffer = i420Buffer.getDataU();
                        ByteBuffer vBuffer = i420Buffer.getDataV();

                        for (int i = 0; i < uvSize; i++) {
                            uBuffer.put(nv12Data[ySize + 2 * i]);       // U data
                            vBuffer.put(nv12Data[ySize + 2 * i + 1]);   // V data
                        }

                        // Create a WebRTC VideoFrame with the converted I420 buffer
                        VideoFrame videoFrame = new VideoFrame(i420Buffer, 0, timestampNS);

                        // Feed the converted YUV420p frame to all observers
                        for (CapturerObserver obs : observers) {
                            obs.onFrameCaptured(videoFrame);
                        }

                        // Release the frame after processing
                        videoFrame.release();

                    } catch (Exception e) {
                        e.printStackTrace(); // Enhanced error logging can be added
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