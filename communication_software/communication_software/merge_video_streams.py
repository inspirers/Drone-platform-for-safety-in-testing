import cv2
import numpy as np

# Load video files
video1 = cv2.VideoCapture("/home/viggof/drone2/communication_software/communication_software/TEST1_R (1).mp4")
video2 = cv2.VideoCapture("/home/viggof/drone2/communication_software/communication_software/TEST1_R (2).mp4")

# Get video properties
frame_width = int(video1.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_height = int(video1.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = int(video1.get(cv2.CAP_PROP_FPS))

# Define output video writer
out = cv2.VideoWriter('stitched_output.mp4', cv2.VideoWriter_fourcc(*'mp4v'), fps, (frame_width * 2, frame_height))

# Use ORB for feature detection (fast and robust)
orb = cv2.ORB_create(5000)  # 5000 keypoints
bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)  # Allow better matches

while video1.isOpened() and video2.isOpened():
    ret1, frame1 = video1.read()
    ret2, frame2 = video2.read()

    if not ret1 or not ret2:
        break  # Stop if end of either video

    # Convert frames to grayscale
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)

    # Detect keypoints and descriptors
    kp1, des1 = orb.detectAndCompute(gray1, None)
    kp2, des2 = orb.detectAndCompute(gray2, None)

    if des1 is None or des2 is None:
        print("Skipping frame due to lack of features.")
        continue

    # Match descriptors using KNN
    matches = bf.knnMatch(des1, des2, k=2)

    # Apply Lowe's Ratio Test to filter out weak matches
    good_matches = [m for m, n in matches if m.distance < 0.75 * n.distance]

    if len(good_matches) > 10:  # Need at least 10 good matches
        src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

        # Compute homography
        H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)

        if H is not None:
            # Warp first frame
            warped_frame1 = cv2.warpPerspective(frame1, H, (frame_width * 2, frame_height))

            # Place second frame correctly
            warped_frame1[0:frame_height, 0:frame_width] = frame2

            # Feather blending
            blend_mask = np.zeros_like(warped_frame1, dtype=np.uint8)
            blend_mask[0:frame_height, 0:frame_width] = 255
            stitched_frame = cv2.seamlessClone(warped_frame1, frame2, blend_mask, (frame_width // 2, frame_height // 2), cv2.NORMAL_CLONE)

            # Write stitched frame to output video
            out.write(stitched_frame)

            # Show result in real-time
            cv2.imshow("Stitched Video", stitched_frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release resources
video1.release()
video2.release()
out.release()
cv2.destroyAllWindows()
