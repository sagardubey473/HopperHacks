"""
Fusion State Machine — Combines MediaPipe Pose detection with CSI presence detection.

States:
    ABSENT:   Neither camera nor CSI detects a person
    VISIBLE:  Camera (MediaPipe) sees pose landmarks
    OCCLUDED: Camera lost person, but CSI variance still elevated (behind wall)

Transitions:
    ABSENT  -> VISIBLE:  Camera detects pose landmarks
    ABSENT  -> OCCLUDED: CSI detects presence without camera
    VISIBLE -> VISIBLE:  Camera still sees person
    VISIBLE -> OCCLUDED: Camera loses person, CSI variance still elevated
    VISIBLE -> ABSENT:   Camera loses person, CSI also quiet
    OCCLUDED -> VISIBLE: Camera re-acquires person
    OCCLUDED -> ABSENT:  CSI variance drops below threshold
"""

import enum
import threading
import time


class FusionState(enum.Enum):
    ABSENT = "ABSENT"
    VISIBLE = "VISIBLE"
    OCCLUDED = "OCCLUDED"


class FusionDetector:
    """Thread-safe fusion state machine combining camera and CSI detection."""

    def __init__(self, camera_timeout=1.0, csi_timeout=2.0):
        """
        Args:
            camera_timeout: Seconds after last camera detection before considering camera as "lost"
            csi_timeout: Seconds after CSI detection drops before transitioning to ABSENT
        """
        self.lock = threading.Lock()
        self.state = FusionState.ABSENT

        # Camera state
        self.camera_detected = False
        self.camera_confidence = 0.0
        self.camera_last_detection_time = 0
        self.camera_landmarks = None   # Latest 33 landmarks as numpy array
        self.latest_frame = None       # Latest annotated camera frame (BGR numpy)
        self.camera_fps = 0

        # CSI state
        self.csi_detected = False
        self.csi_confidence = 0.0
        self.csi_variance = 0.0
        self.csi_threshold = 0.0

        # Timeouts
        self.camera_timeout = camera_timeout
        self.csi_timeout = csi_timeout
        self.csi_last_detection_time = 0

        # Calibration flag — forces ABSENT during calibration
        self.calibrating = False

    def update_camera(self, detected, confidence, landmarks=None, frame=None):
        """Called from camera thread with each frame result."""
        with self.lock:
            self.camera_detected = detected
            self.camera_confidence = confidence
            self.camera_landmarks = landmarks
            if frame is not None:
                self.latest_frame = frame.copy()
            if detected:
                self.camera_last_detection_time = time.time()
            self._update_state()

    def update_csi(self, detected, confidence, variance, threshold):
        """Called from serial reader thread with each CSI detection result."""
        with self.lock:
            self.csi_detected = detected
            self.csi_confidence = confidence
            self.csi_variance = variance
            self.csi_threshold = threshold
            if detected:
                self.csi_last_detection_time = time.time()
            self._update_state()

    def _update_state(self):
        """Compute new fusion state from camera + CSI signals."""
        if self.calibrating:
            self.state = FusionState.ABSENT
            return

        now = time.time()
        camera_active = (self.camera_detected and
                         (now - self.camera_last_detection_time) < self.camera_timeout)
        csi_active = (self.csi_detected and
                      (now - self.csi_last_detection_time) < self.csi_timeout)

        if camera_active:
            self.state = FusionState.VISIBLE
        elif csi_active:
            self.state = FusionState.OCCLUDED
        else:
            self.state = FusionState.ABSENT

    def get_state(self):
        """Thread-safe read of current fusion state."""
        with self.lock:
            return {
                'state': self.state,
                'camera_detected': self.camera_detected,
                'camera_confidence': self.camera_confidence,
                'csi_detected': self.csi_detected,
                'csi_confidence': self.csi_confidence,
                'csi_variance': self.csi_variance,
                'csi_threshold': self.csi_threshold,
            }

    def get_latest_frame(self):
        """Thread-safe read of latest camera frame."""
        with self.lock:
            return self.latest_frame.copy() if self.latest_frame is not None else None
