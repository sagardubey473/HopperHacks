"""
Camera Processor — MediaPipe Pose detection in a background thread.

Captures frames from a USB webcam, runs MediaPipe Pose (33 landmarks),
draws skeleton overlay, and updates the FusionDetector with results.
"""

import threading
import time

import cv2
import mediapipe as mp
import numpy as np


class CameraProcessor:
    """Runs MediaPipe Pose detection on webcam frames in a background thread."""

    def __init__(self, fusion_detector, camera_index=0,
                 min_detection_confidence=0.5, min_tracking_confidence=0.5):
        self.fusion = fusion_detector
        self.camera_index = camera_index
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.running = False
        self._thread = None

        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles

    def start(self):
        """Start the camera processing thread."""
        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """Signal the camera thread to stop."""
        self.running = False

    def _run(self):
        """Main camera loop — runs in background thread."""
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            print(f"[Camera] Error: Could not open camera {self.camera_index}")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        fps_counter = 0
        fps_start = time.time()

        print(f"[Camera] Opened camera {self.camera_index} "
              f"({int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))})")

        with self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            enable_segmentation=False,
            min_detection_confidence=self.min_detection_confidence,
            min_tracking_confidence=self.min_tracking_confidence
        ) as pose:

            while self.running:
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.01)
                    continue

                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = pose.process(rgb_frame)

                detected = False
                confidence = 0.0
                landmarks_array = None

                if results.pose_landmarks:
                    detected = True
                    visibilities = [lm.visibility for lm in results.pose_landmarks.landmark]
                    confidence = sum(visibilities) / len(visibilities)

                    landmarks_array = np.array([
                        [lm.x, lm.y, lm.z, lm.visibility]
                        for lm in results.pose_landmarks.landmark
                    ])

                    self.mp_drawing.draw_landmarks(
                        frame,
                        results.pose_landmarks,
                        self.mp_pose.POSE_CONNECTIONS,
                        landmark_drawing_spec=self.mp_drawing_styles
                            .get_default_pose_landmarks_style()
                    )

                # Draw fusion state overlay on frame
                state_info = self.fusion.get_state()
                state_name = state_info['state'].value
                color_map = {
                    'ABSENT': (128, 128, 128),
                    'VISIBLE': (0, 255, 0),
                    'OCCLUDED': (0, 165, 255),
                }
                color = color_map.get(state_name, (255, 255, 255))
                cv2.putText(frame, f"State: {state_name}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)

                if state_info['csi_detected']:
                    cv2.putText(frame, "CSI: PRESENT", (10, 70),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                else:
                    cv2.putText(frame, "CSI: EMPTY", (10, 70),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                # FPS
                fps_counter += 1
                elapsed = time.time() - fps_start
                if elapsed >= 1.0:
                    with self.fusion.lock:
                        self.fusion.camera_fps = fps_counter / elapsed
                    fps_counter = 0
                    fps_start = time.time()

                self.fusion.update_camera(detected, confidence, landmarks_array, frame)

        cap.release()
        print("[Camera] Camera released.")
