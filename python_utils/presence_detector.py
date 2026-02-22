"""
Presence Detector — Binary human presence detection using CSI amplitude variance thresholding.

Algorithm:
  1. Calibration: Collect ~30s of empty-room CSI → compute baseline variance stats
  2. Detection: For each sliding window, compare current variance to threshold
  3. Temporal smoothing: majority vote over recent decisions to reduce false positives

Usage as standalone (reads from serial):
    python presence_detector.py --port /dev/tty.usbserial-XXX --calibrate 30

Usage as library:
    from presence_detector import PresenceDetector
    detector = PresenceDetector()
    detector.calibrate_from_file('data/calibration.json')
    result = detector.detect(features)
"""

import argparse
import collections
import json
import os
import sys
import time

# Ensure sibling modules are importable regardless of working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

from csi_processing import parse_csi_line, iq_to_amplitude, SlidingWindow, open_serial


class PresenceDetector:
    """
    Threshold-based human presence detection from CSI amplitude variance.
    """

    def __init__(self, threshold_multiplier=3.0, smoothing_window=5):
        """
        Args:
            threshold_multiplier: Detection threshold = baseline_mean + N * baseline_std
            smoothing_window: Number of recent decisions for majority vote
        """
        self.threshold_multiplier = threshold_multiplier
        self.smoothing_window = smoothing_window

        # Calibration state
        self.baseline_mean = None
        self.baseline_std = None
        self.threshold = None
        self.calibrated = False

        # Temporal smoothing buffer
        self._decisions = collections.deque(maxlen=smoothing_window)

    def calibrate(self, variance_samples):
        """
        Calibrate from a list of mean_variance values collected during empty-room period.

        Args:
            variance_samples: list of float — mean_variance from each sliding window during calibration
        """
        if len(variance_samples) < 2:
            return False

        arr = np.array(variance_samples)
        self.baseline_mean = float(np.mean(arr))
        self.baseline_std = float(np.std(arr))
        self.threshold = self.baseline_mean + self.threshold_multiplier * self.baseline_std
        self.calibrated = True
        self._decisions.clear()
        return True

    def save_calibration(self, filepath):
        """Save calibration data to JSON file."""
        if not self.calibrated:
            return False
        data = {
            'baseline_mean': self.baseline_mean,
            'baseline_std': self.baseline_std,
            'threshold': self.threshold,
            'threshold_multiplier': self.threshold_multiplier,
        }
        os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        return True

    def load_calibration(self, filepath):
        """Load calibration data from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        self.baseline_mean = data['baseline_mean']
        self.baseline_std = data['baseline_std']
        self.threshold = data['threshold']
        self.threshold_multiplier = data.get('threshold_multiplier', 3.0)
        self.calibrated = True
        self._decisions.clear()
        return True

    def detect(self, features):
        """
        Run detection on a set of features from SlidingWindow.compute_features().

        Args:
            features: dict with 'mean_variance' key (from SlidingWindow.compute_features())

        Returns dict:
            present: bool — smoothed detection result
            raw_present: bool — unsmoothed detection for this frame
            confidence: float — 0.0 to 1.0, how many recent decisions agree
            variance: float — current mean variance
            threshold: float — current threshold
        Returns None if not calibrated.
        """
        if not self.calibrated or features is None:
            return None

        variance = features['mean_variance']
        raw_present = variance > self.threshold

        self._decisions.append(raw_present)

        # Majority vote over smoothing window
        present_count = sum(self._decisions)
        total = len(self._decisions)
        present = present_count > total / 2
        confidence = present_count / total if present else (total - present_count) / total

        return {
            'present': present,
            'raw_present': raw_present,
            'confidence': confidence,
            'variance': variance,
            'threshold': self.threshold,
        }

    def reset(self):
        """Reset detection state (keeps calibration)."""
        self._decisions.clear()


def main():
    """Standalone mode: read serial, calibrate, then detect."""
    parser = argparse.ArgumentParser(description='CSI-based human presence detection')
    parser.add_argument('--port', '-p', type=str, required=True, help='Serial port')
    parser.add_argument('--baud', '-b', type=int, default=921600, help='Baud rate')
    parser.add_argument('--calibrate', '-c', type=int, default=30,
                        help='Calibration duration in seconds (default: 30)')
    parser.add_argument('--threshold', '-t', type=float, default=3.0,
                        help='Threshold multiplier N (default: 3.0)')
    parser.add_argument('--window', '-w', type=int, default=100,
                        help='Sliding window size in packets (default: 100)')
    parser.add_argument('--calibration-file', type=str, default='data/calibration.json',
                        help='Path to save/load calibration')
    parser.add_argument('--load-calibration', action='store_true',
                        help='Load existing calibration instead of running calibration phase')
    args = parser.parse_args()

    detector = PresenceDetector(threshold_multiplier=args.threshold)
    window = SlidingWindow(window_size=args.window)

    if args.load_calibration:
        print(f"Loading calibration from {args.calibration_file}...")
        detector.load_calibration(args.calibration_file)
        print(f"  Baseline mean: {detector.baseline_mean:.4f}")
        print(f"  Threshold:     {detector.threshold:.4f}")
    else:
        # Calibration phase
        ser = open_serial(args.port, args.baud)
        print(f"Connected to {args.port}.")
        print(f"CALIBRATION PHASE — Keep the area EMPTY for {args.calibrate} seconds")
        print("Waiting for CSI data...")

        variance_samples = []
        cal_start = None

        while True:
            try:
                raw = ser.readline().decode('utf-8', errors='ignore').strip()
            except Exception:
                continue

            if "CSI_DATA" not in raw:
                continue

            if cal_start is None:
                cal_start = time.time()
                print("Calibrating...")

            metadata, iq = parse_csi_line(raw)
            if metadata is None:
                continue

            amplitudes = iq_to_amplitude(iq)
            window.add(amplitudes)

            if window.is_full():
                features = window.compute_features()
                if features:
                    variance_samples.append(features['mean_variance'])

            elapsed = time.time() - cal_start
            remaining = args.calibrate - elapsed
            print(f"  Calibrating... {remaining:.0f}s remaining  ", end='\r')

            if elapsed >= args.calibrate:
                break

        ser.close()

        if not detector.calibrate(variance_samples):
            print("\nCalibration failed — not enough data.", file=sys.stderr)
            sys.exit(1)

        detector.save_calibration(args.calibration_file)
        print(f"\nCalibration complete!")
        print(f"  Samples:       {len(variance_samples)}")
        print(f"  Baseline mean: {detector.baseline_mean:.4f}")
        print(f"  Baseline std:  {detector.baseline_std:.4f}")
        print(f"  Threshold:     {detector.threshold:.4f}")
        print(f"  Saved to:      {args.calibration_file}\n")

    # Detection phase
    ser = open_serial(args.port, args.baud)
    print(f"Connected to {args.port}.")
    print("DETECTION PHASE — monitoring for human presence...")

    window = SlidingWindow(window_size=args.window)

    try:
        while True:
            try:
                raw = ser.readline().decode('utf-8', errors='ignore').strip()
            except Exception:
                continue

            if "CSI_DATA" not in raw:
                continue

            metadata, iq = parse_csi_line(raw)
            if metadata is None:
                continue

            amplitudes = iq_to_amplitude(iq)
            window.add(amplitudes)

            features = window.compute_features()
            if features is None:
                continue

            result = detector.detect(features)
            if result is None:
                continue

            status = "HUMAN DETECTED" if result['present'] else "EMPTY"
            conf = result['confidence']
            var = result['variance']
            thresh = result['threshold']

            print(f"  [{status:>14}]  confidence={conf:.2f}  variance={var:.4f}  threshold={thresh:.4f}  ",
                  end='\r')

    except KeyboardInterrupt:
        pass

    ser.close()
    print("\nStopped.")


if __name__ == '__main__':
    main()
