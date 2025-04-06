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

    private Context context;
    private CapturerObserver capturerObserver;

    public DJIVideoCapturer() {
        // No need for droneDisplayName anymore
    }

    private void setupVideoListener() {
        if (codecManager != null)
            return;

        // Pass SurfaceTexture as null to force the Yuv callback - width and height for the surface texture does not matter
        codecManager = new DJICodecManager(context, (SurfaceTexture) null, 0, 0);
        codecManager.enabledYuvData(true);
        codecManager.setYuvDataCallback(new DJICodecManager.YuvDataCallback() {
            @Override
            public void onYuvDataReceived(MediaFormat mediaFormat, ByteBuffer videoBuffer, int dataSize, int width, int height) {
                if (videoBuffer != null) {
                    try {
                        // We need to check which color format they are using by doing a lookup in our MediaFormat
                        long timestampNS = TimeUnit.MILLISECONDS.toNanos(SystemClock.elapsedRealtime());
                        NV12Buffer buffer = new NV12Buffer(width,
                                height,
                                mediaFormat.getInteger(MediaFormat.KEY_STRIDE),
                                mediaFormat.getInteger(MediaFormat.KEY_SLICE_HEIGHT),
                                videoBuffer,
                                null);
                        VideoFrame videoFrame = new VideoFrame(buffer, 0, timestampNS);

                        // Feed the video frame to all observers
                        for (CapturerObserver obs : observers) {
                            obs.onFrameCaptured(videoFrame);
                        }
                        videoFrame.release();
                    } catch (Exception e) {
                        e.printStackTrace();
                    }
                }
            }
        });

        // Generalized handling for video feed listener
        VideoFeeder.VideoDataListener videoDataListener = new VideoFeeder.VideoDataListener() {
            @Override
            public void onReceive(byte[] bytes, int dataSize) {
                // Pass the encoded data along to obtain the YUV-color data
                if (codecManager != null) {
                    codecManager.sendDataToDecoder(bytes, dataSize);
                }
            }
        };

        // Add the video data listener to the primary video feed (this works for most DJI drones)
        VideoFeeder.getInstance().getPrimaryVideoFeed().addVideoDataListener(videoDataListener);
    }

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
        // Empty on purpose, but you could implement dynamic format changes if needed
    }

    @Override
    public void dispose() {
        // Stop receiving frames on the callback from the decoder
        if (observers.contains(capturerObserver)) {
            observers.remove(capturerObserver);
        }
    }

    @Override
    public boolean isScreencast() {
        return false;
    }
}
