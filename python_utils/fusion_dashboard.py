#!/usr/bin/env python3
"""
Fusion Dashboard — Unified CSI + Camera pose detection dashboard.

Combines WiFi CSI presence detection with MediaPipe Pose estimation.
When a person is visible to the camera, pose landmarks are displayed.
When they move behind a wall, CSI detects continued presence.

Layout:
  [Camera + Pose Overlay]  [CSI Amplitude]
  [    Variance + Threshold (full width) ]
  [  Fused Detection Bar (full width)    ]

States:
  VISIBLE  (green):  Person detected by camera
  OCCLUDED (orange): Person behind wall, detected by CSI only
  ABSENT   (gray):   No detection from either source

Controls:
  'c' — Start/stop calibration (keep area empty during calibration)
  'q' — Quit

Usage:
    python fusion_dashboard.py --port /dev/tty.usbserial-XXX
    python fusion_dashboard.py --port /dev/ttyUSB0 --camera 0
    python fusion_dashboard.py --port /dev/ttyUSB0 --no-camera
"""

import argparse
import collections
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.gridspec as gridspec
import numpy as np

from csi_processing import parse_csi_line, iq_to_amplitude, SlidingWindow, open_serial
from presence_detector import PresenceDetector
from fusion_state import FusionDetector, FusionState

# --- Configuration ---
PLOT_HISTORY = 500
RENDER_INTERVAL_MS = 200
SUBCARRIERS_TO_PLOT = [10, 20, 30, 40, 50]

TARGET_WINDOW_DURATION_SEC = 3.0
DEFAULT_WINDOW_SIZE = 300
MIN_WINDOW_SIZE = 15
MAX_WINDOW_SIZE = 1000

STATE_COLORS = {
    FusionState.ABSENT: '#95a5a6',
    FusionState.VISIBLE: '#2ecc71',
    FusionState.OCCLUDED: '#f39c12',
}

CSV_HEADER = "type,role,mac,rssi,rate,sig_mode,mcs,bandwidth,smoothing,not_sounding,aggregation,stbc,fec_coding,sgi,noise_floor,ampdu_cnt,channel,secondary_channel,local_timestamp,ant,sig_len,rx_state,real_time_set,real_timestamp,len,CSI_DATA,pc_timestamp\n"


class DashboardState:
    """Thread-safe shared state for CSI data."""

    def __init__(self):
        self.lock = threading.Lock()

        self.amp_history = {sc: collections.deque(maxlen=PLOT_HISTORY) for sc in SUBCARRIERS_TO_PLOT}
        self.variance_history = collections.deque(maxlen=PLOT_HISTORY)
        self.threshold_history = collections.deque(maxlen=PLOT_HISTORY)
        self.detection_history = collections.deque(maxlen=PLOT_HISTORY)
        # Fusion state history for the 3-color bar
        self.fusion_state_history = collections.deque(maxlen=PLOT_HISTORY)

        self.status_text = "Waiting for data..."
        self.packets_per_sec = 0
        self.total_packets = 0
        self.is_calibrating = False
        self.calibrated = False

        self.detector = PresenceDetector(threshold_multiplier=3.0, smoothing_window=50)
        self.window = SlidingWindow(window_size=DEFAULT_WINDOW_SIZE)
        self.effective_window_size = DEFAULT_WINDOW_SIZE
        self.calibration_variances = []

        self.rate_history = []
        self.window_resized = False

        self.target_mac = None
        self.mac_counts = {}
        self.mac_locked = False


def serial_reader_thread(state, fusion, port, baud, csv_file):
    """Background thread: read serial, parse CSI, update shared state and fusion."""
    ser = open_serial(port, baud)
    packet_count = 0
    interval_start = time.time()

    with open(csv_file, 'w') as f:
        f.write(CSV_HEADER)

        while True:
            try:
                raw = ser.readline().decode('utf-8', errors='ignore').strip()
            except Exception:
                continue

            if "CSI_DATA" not in raw:
                continue

            pc_ts = time.time()
            f.write(raw + ',' + str(pc_ts) + '\n')
            f.flush()

            metadata, iq = parse_csi_line(raw)
            if metadata is None:
                continue

            mac = metadata.get('mac', '')

            with state.lock:
                state.total_packets += 1
                packet_count += 1

                if not state.mac_locked:
                    state.mac_counts[mac] = state.mac_counts.get(mac, 0) + 1
                    if state.total_packets >= 30 and not state.target_mac:
                        state.target_mac = max(state.mac_counts, key=state.mac_counts.get)
                        state.mac_locked = True
                        print(f"Locked onto MAC: {state.target_mac} "
                              f"({state.mac_counts[state.target_mac]}/{state.total_packets} packets)")

                if state.mac_locked and mac != state.target_mac:
                    continue

            amplitudes = iq_to_amplitude(iq)

            with state.lock:
                for sc in SUBCARRIERS_TO_PLOT:
                    if sc < len(amplitudes):
                        state.amp_history[sc].append(amplitudes[sc])

                state.window.add(amplitudes)
                features = state.window.compute_features()

                if features is not None and state.window.count() >= state.effective_window_size // 2:
                    variance = features['mean_variance']

                    if state.is_calibrating:
                        if state.window.is_full():
                            state.calibration_variances.append(variance)
                        state.variance_history.append(variance)
                        state.threshold_history.append(0)
                        state.detection_history.append(0)
                    elif state.calibrated:
                        result = state.detector.detect(features)
                        if result:
                            state.variance_history.append(result['variance'])
                            state.threshold_history.append(result['threshold'])
                            state.detection_history.append(1 if result['present'] else 0)
                            # Update fusion with CSI detection
                            fusion.update_csi(
                                detected=result['present'],
                                confidence=result['confidence'],
                                variance=result['variance'],
                                threshold=result['threshold']
                            )
                    else:
                        state.variance_history.append(variance)
                        state.threshold_history.append(0)
                        state.detection_history.append(0)

                # Append current fusion state for the detection bar
                state.fusion_state_history.append(fusion.get_state()['state'])

                # Update packets/sec and adaptive resizing
                now = time.time()
                if now - interval_start >= 1.0:
                    state.packets_per_sec = packet_count

                    if not state.window_resized and packet_count > 0:
                        state.rate_history.append(packet_count)
                        if len(state.rate_history) >= 3:
                            avg_rate = sum(state.rate_history) / len(state.rate_history)
                            new_size = int(avg_rate * TARGET_WINDOW_DURATION_SEC)
                            new_size = max(MIN_WINDOW_SIZE, min(MAX_WINDOW_SIZE, new_size))
                            new_smoothing = max(5, int(avg_rate * 0.5))
                            state.window = SlidingWindow(window_size=new_size)
                            state.detector = PresenceDetector(
                                threshold_multiplier=3.0,
                                smoothing_window=new_smoothing
                            )
                            state.effective_window_size = new_size
                            state.window_resized = True
                            print(f"Adaptive: rate={avg_rate:.0f} pkt/s -> "
                                  f"window_size={new_size}, smoothing={new_smoothing}")

                    packet_count = 0
                    interval_start = now


def create_fusion_dashboard(state, fusion, calibration_file, expected_rate=100,
                            use_camera=True):
    """Create and run the unified fusion dashboard."""

    fig = plt.figure(figsize=(16, 10))
    gs = gridspec.GridSpec(3, 2, height_ratios=[4, 2, 1], hspace=0.35, wspace=0.25,
                           top=0.93, bottom=0.05, left=0.06, right=0.98)

    if use_camera:
        ax_camera = fig.add_subplot(gs[0, 0])
        ax_amp = fig.add_subplot(gs[0, 1])
    else:
        ax_camera = None
        ax_amp = fig.add_subplot(gs[0, :])

    ax_var = fig.add_subplot(gs[1, :])
    ax_det = fig.add_subplot(gs[2, :])

    fig.suptitle('ESP32 CSI + Camera Fusion — Human Presence Detection', fontsize=14)

    status_text = fig.text(0.02, 0.97, '', fontsize=10, verticalalignment='top',
                           fontfamily='monospace')
    rate_text = fig.text(0.98, 0.97, '', fontsize=12, verticalalignment='top',
                         horizontalalignment='right', fontfamily='monospace',
                         fontweight='bold')

    # Initialize camera image (updated via set_data for performance)
    cam_img = None
    if ax_camera is not None:
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        cam_img = ax_camera.imshow(blank)
        ax_camera.set_xticks([])
        ax_camera.set_yticks([])
        ax_camera.set_title('Camera — Waiting...')

    def on_key(event):
        if event.key == 'c':
            with state.lock:
                if not state.is_calibrating:
                    state.is_calibrating = True
                    state.calibration_variances = []
                    state.window.clear()
                    state.detector.reset()
                    fusion.calibrating = True
                    state.status_text = "CALIBRATING — keep area empty..."
                else:
                    state.is_calibrating = False
                    fusion.calibrating = False
                    if state.detector.calibrate(state.calibration_variances):
                        state.calibrated = True
                        state.detector.save_calibration(calibration_file)
                        state.status_text = f"Calibrated! Threshold={state.detector.threshold:.4f}"
                    else:
                        state.status_text = "Calibration failed — not enough data"
        elif event.key == 'q':
            plt.close(fig)

    fig.canvas.mpl_connect('key_press_event', on_key)

    def update(frame):
        with state.lock:
            # --- Camera panel ---
            if ax_camera is not None:
                camera_frame = fusion.get_latest_frame()
                if camera_frame is not None:
                    import cv2
                    rgb = cv2.cvtColor(camera_frame, cv2.COLOR_BGR2RGB)
                    cam_img.set_data(rgb)
                    ax_camera.set_title(f'Camera — {fusion.camera_fps:.0f} FPS')
                else:
                    ax_camera.set_title('Camera — No feed')

            # --- CSI Amplitude panel ---
            ax_amp.clear()
            plot_colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6']
            for i, sc in enumerate(SUBCARRIERS_TO_PLOT):
                data = list(state.amp_history[sc])
                if data:
                    ax_amp.plot(data, color=plot_colors[i % len(plot_colors)], alpha=0.7,
                                linewidth=0.8, label=f'SC {sc}')
            ax_amp.set_ylabel('Amplitude')
            ax_amp.set_title('CSI Amplitude (Selected Subcarriers)')
            ax_amp.legend(loc='upper right', fontsize=8, ncol=len(SUBCARRIERS_TO_PLOT))
            ax_amp.set_xlim(0, PLOT_HISTORY)

            # --- Variance panel ---
            ax_var.clear()
            var_data = list(state.variance_history)
            thresh_data = list(state.threshold_history)
            if var_data:
                ax_var.plot(var_data, color='#2c3e50', linewidth=1, label='Variance')
            if thresh_data and any(t > 0 for t in thresh_data):
                ax_var.plot(thresh_data, color='#e74c3c', linewidth=1.5,
                            linestyle='--', label='Threshold')
            ax_var.set_ylabel('Variance')
            ax_var.set_title('Mean Amplitude Variance')
            ax_var.legend(loc='upper right', fontsize=8)
            ax_var.set_xlim(0, PLOT_HISTORY)

            # --- Fused Detection bar (3 colors) ---
            ax_det.clear()
            fusion_data = list(state.fusion_state_history)
            if fusion_data:
                x = np.arange(len(fusion_data))
                bar_colors = [STATE_COLORS.get(s, '#95a5a6') for s in fusion_data]
                ax_det.bar(x, [1] * len(fusion_data), color=bar_colors, width=1.0)
            ax_det.set_xlim(0, PLOT_HISTORY)
            ax_det.set_ylim(0, 1)
            ax_det.set_yticks([])
            ax_det.set_title('Fusion Status (Green=Visible, Orange=Occluded/Behind Wall, Gray=Absent)')

            # --- Status text ---
            fusion_info = fusion.get_state()
            state_name = fusion_info['state'].value

            if state.is_calibrating:
                status = (f"CALIBRATING  |  Samples: {len(state.calibration_variances)}  |  "
                          f"Press 'c' to finish")
            elif state.calibrated:
                last_var = var_data[-1] if var_data else 0
                cam_str = f"Camera: {'ON' if fusion_info['camera_detected'] else 'OFF'}"
                status = (f"{state_name}  |  {cam_str}  |  "
                          f"Variance: {last_var:.4f}  |  "
                          f"Threshold: {state.detector.threshold:.4f}  |  "
                          f"{state.packets_per_sec} pkt/s  |  Total: {state.total_packets}")
            else:
                mac_info = f"MAC: {state.target_mac}" if state.mac_locked else "Detecting MAC..."
                cam_str = f"Camera: {'ON' if use_camera else 'OFF'}"
                status = (f"NOT CALIBRATED — press 'c'  |  {mac_info}  |  {cam_str}  |  "
                          f"{state.packets_per_sec} pkt/s  |  Total: {state.total_packets}")

            status_text.set_text(status)

            # Rate indicator
            rate = state.packets_per_sec
            if expected_rate > 0 and rate >= expected_rate * 0.9:
                rate_color = '#2ecc71'
            elif expected_rate > 0 and rate >= expected_rate * 0.5:
                rate_color = '#f39c12'
            else:
                rate_color = '#e74c3c'
            rate_text.set_text(f'{rate} pkt/s')
            rate_text.set_color(rate_color)

    ani = animation.FuncAnimation(fig, update, interval=RENDER_INTERVAL_MS, cache_frame_data=False)
    plt.show()


def main():
    parser = argparse.ArgumentParser(description='Fusion CSI + Camera presence detection dashboard')
    parser.add_argument('--port', '-p', type=str, required=True, help='Serial port (AP/receiver)')
    parser.add_argument('--baud', '-b', type=int, default=921600, help='Baud rate')
    parser.add_argument('--camera', type=int, default=0, help='Camera index (default: 0)')
    parser.add_argument('--camera-confidence', type=float, default=0.5,
                        help='MediaPipe min detection confidence (default: 0.5)')
    parser.add_argument('--output', '-o', type=str, default='data', help='Output directory for CSV')
    parser.add_argument('--calibration-file', type=str, default='data/calibration.json',
                        help='Path to save/load calibration')
    parser.add_argument('--load-calibration', action='store_true',
                        help='Load existing calibration on startup')
    parser.add_argument('--mac', type=str, default=None,
                        help='Filter to this MAC address only (auto-detected if not set)')
    parser.add_argument('--no-camera', action='store_true',
                        help='Run without camera (CSI-only mode)')
    parser.add_argument('--expected-rate', type=int, default=100,
                        help='Expected CSI packet rate in pkt/s (default: 100)')
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    timestamp_str = time.strftime('%Y-%m-%d_%H-%M-%S')
    csv_file = os.path.join(args.output, f'csi_{timestamp_str}.csv')

    state = DashboardState()
    fusion = FusionDetector()

    if args.mac:
        state.target_mac = args.mac
        state.mac_locked = True
        print(f"Filtering to MAC: {args.mac}")

    if args.load_calibration and os.path.exists(args.calibration_file):
        state.detector.load_calibration(args.calibration_file)
        state.calibrated = True
        print(f"Loaded calibration from {args.calibration_file}")
        print(f"  Threshold: {state.detector.threshold:.4f}")

    # Start serial reader
    reader = threading.Thread(target=serial_reader_thread,
                              args=(state, fusion, args.port, args.baud, csv_file),
                              daemon=True)
    reader.start()

    # Start camera (unless --no-camera)
    use_camera = not args.no_camera
    if use_camera:
        from camera_processor import CameraProcessor
        camera = CameraProcessor(fusion, camera_index=args.camera,
                                 min_detection_confidence=args.camera_confidence)
        camera.start()
        print(f"Camera started (index {args.camera})")
    else:
        print("Running in CSI-only mode (no camera)")

    print(f"Dashboard started. Saving CSV to {csv_file}")
    print("Press 'c' in the plot window to start/stop calibration")
    print("Press 'q' in the plot window to quit\n")

    create_fusion_dashboard(state, fusion, args.calibration_file,
                            expected_rate=args.expected_rate, use_camera=use_camera)

    if use_camera:
        camera.stop()


if __name__ == '__main__':
    main()
