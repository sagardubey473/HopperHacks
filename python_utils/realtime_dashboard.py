#!/usr/bin/env python3
"""
Real-Time CSI Dashboard — Live visualization with human presence detection.

Shows:
  - Top panel:    CSI amplitude over time for selected subcarriers
  - Middle panel: Amplitude variance over time with detection threshold line
  - Bottom panel: Detection status bar (green=empty, red=human detected)

Controls:
  - Press 'c' to start/stop calibration
  - Press 'q' to quit

Also saves data to CSV simultaneously.

Usage:
    python realtime_dashboard.py --port /dev/tty.usbserial-XXX
    python realtime_dashboard.py --port /dev/ttyUSB0 --baud 921600
"""

import argparse
import collections
import os
import sys
import threading
import time

# Ensure sibling modules are importable regardless of working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np

from csi_processing import parse_csi_line, iq_to_amplitude, get_active_subcarriers, SlidingWindow, open_serial
from presence_detector import PresenceDetector


# --- Configuration ---
PLOT_HISTORY = 500          # Number of frames to show in rolling plots
RENDER_INTERVAL_MS = 200    # Milliseconds between plot updates
SUBCARRIERS_TO_PLOT = [10, 20, 30, 40, 50]  # Subcarrier indices to plot in top panel

# Adaptive sliding window — sized to hold ~3 seconds of CSI data
TARGET_WINDOW_DURATION_SEC = 3.0
DEFAULT_WINDOW_SIZE = 300   # Default for 100 pkt/s (3s * 100)
MIN_WINDOW_SIZE = 15
MAX_WINDOW_SIZE = 1000

CSV_HEADER = "type,role,mac,rssi,rate,sig_mode,mcs,bandwidth,smoothing,not_sounding,aggregation,stbc,fec_coding,sgi,noise_floor,ampdu_cnt,channel,secondary_channel,local_timestamp,ant,sig_len,rx_state,real_time_set,real_timestamp,len,CSI_DATA,pc_timestamp\n"


class DashboardState:
    """Thread-safe shared state between serial reader and plot renderer."""

    def __init__(self):
        self.lock = threading.Lock()

        # Rolling amplitude history per subcarrier: {subcarrier_idx: deque}
        self.amp_history = {sc: collections.deque(maxlen=PLOT_HISTORY) for sc in SUBCARRIERS_TO_PLOT}

        # Variance and detection history
        self.variance_history = collections.deque(maxlen=PLOT_HISTORY)
        self.threshold_history = collections.deque(maxlen=PLOT_HISTORY)
        self.detection_history = collections.deque(maxlen=PLOT_HISTORY)

        # Current status
        self.status_text = "Waiting for data..."
        self.packets_per_sec = 0
        self.total_packets = 0
        self.is_calibrating = False
        self.calibrated = False

        # Detector and window (adaptive — resized once packet rate is measured)
        self.detector = PresenceDetector(threshold_multiplier=3.0, smoothing_window=50)
        self.window = SlidingWindow(window_size=DEFAULT_WINDOW_SIZE)
        self.effective_window_size = DEFAULT_WINDOW_SIZE
        self.calibration_variances = []

        # Adaptive rate measurement
        self.rate_history = []           # Per-second rate samples for adaptive sizing
        self.window_resized = False      # True once window has been auto-sized

        # MAC filtering — lock onto the most frequent source
        self.target_mac = None           # Set via --mac or auto-detected
        self.mac_counts = {}             # {mac: count} for auto-detection
        self.mac_locked = False          # True once we've chosen a MAC


def serial_reader_thread(state, port, baud, csv_file):
    """Background thread: read serial, parse CSI, update shared state, write CSV."""
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

                # Auto-detect MAC: count packets per MAC, lock onto most common
                if not state.mac_locked:
                    state.mac_counts[mac] = state.mac_counts.get(mac, 0) + 1
                    # Lock after seeing 30 packets
                    if state.total_packets >= 30 and not state.target_mac:
                        state.target_mac = max(state.mac_counts, key=state.mac_counts.get)
                        state.mac_locked = True
                        print(f"Locked onto MAC: {state.target_mac} "
                              f"({state.mac_counts[state.target_mac]}/{state.total_packets} packets)")

                # Filter: skip packets from other MACs
                if state.mac_locked and mac != state.target_mac:
                    continue

            amplitudes = iq_to_amplitude(iq)

            with state.lock:
                # Update per-subcarrier amplitude history
                for sc in SUBCARRIERS_TO_PLOT:
                    if sc < len(amplitudes):
                        state.amp_history[sc].append(amplitudes[sc])

                # Sliding window features
                state.window.add(amplitudes)
                features = state.window.compute_features()

                # Only use features once window is >= 50% full for stable variance
                if features is not None and state.window.count() >= state.effective_window_size // 2:
                    variance = features['mean_variance']

                    if state.is_calibrating:
                        # Only record calibration data after window is full
                        # (skip warm-up period with unstable variance)
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
                    else:
                        state.variance_history.append(variance)
                        state.threshold_history.append(0)
                        state.detection_history.append(0)

                # Update packets/sec
                now = time.time()
                if now - interval_start >= 1.0:
                    state.packets_per_sec = packet_count

                    # Adaptive window resizing: measure rate for 3 seconds, then resize
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


def create_dashboard(state, calibration_file, expected_rate=100):
    """Create and run the matplotlib dashboard."""

    fig, (ax_amp, ax_var, ax_det) = plt.subplots(3, 1, figsize=(12, 8),
                                                   gridspec_kw={'height_ratios': [3, 2, 1]})
    fig.suptitle('ESP32 CSI — Human Presence Detection Dashboard', fontsize=14)
    plt.subplots_adjust(hspace=0.35, top=0.93, bottom=0.07)

    status_text = fig.text(0.02, 0.97, '', fontsize=10, verticalalignment='top',
                           fontfamily='monospace')
    rate_text = fig.text(0.98, 0.97, '', fontsize=12, verticalalignment='top',
                         horizontalalignment='right', fontfamily='monospace',
                         fontweight='bold')

    # Key press handler for calibration toggle
    def on_key(event):
        if event.key == 'c':
            with state.lock:
                if not state.is_calibrating:
                    # Start calibration — reset window so it fills fresh
                    state.is_calibrating = True
                    state.calibration_variances = []
                    state.window.clear()
                    state.detector.reset()
                    state.status_text = "CALIBRATING — keep area empty..."
                else:
                    # Stop calibration
                    state.is_calibrating = False
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
            # --- Top panel: Amplitude over time ---
            ax_amp.clear()
            colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6']
            for i, sc in enumerate(SUBCARRIERS_TO_PLOT):
                data = list(state.amp_history[sc])
                if data:
                    ax_amp.plot(data, color=colors[i % len(colors)], alpha=0.7,
                               linewidth=0.8, label=f'SC {sc}')
            ax_amp.set_ylabel('Amplitude')
            ax_amp.set_title('CSI Amplitude (Selected Subcarriers)')
            ax_amp.legend(loc='upper right', fontsize=8, ncol=len(SUBCARRIERS_TO_PLOT))
            ax_amp.set_xlim(0, PLOT_HISTORY)

            # --- Middle panel: Variance with threshold ---
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

            # --- Bottom panel: Detection status bar ---
            ax_det.clear()
            det_data = list(state.detection_history)
            if det_data:
                x = np.arange(len(det_data))
                colors_bar = ['#2ecc71' if d == 0 else '#e74c3c' for d in det_data]
                ax_det.bar(x, [1] * len(det_data), color=colors_bar, width=1.0)
            ax_det.set_xlim(0, PLOT_HISTORY)
            ax_det.set_ylim(0, 1)
            ax_det.set_yticks([])
            ax_det.set_title('Detection Status (Green=Empty, Red=Human Detected)')

            # --- Status text ---
            if state.is_calibrating:
                status = f"CALIBRATING  |  Samples: {len(state.calibration_variances)}  |  Press 'c' to finish"
            elif state.calibrated:
                last_det = det_data[-1] if det_data else 0
                label = "HUMAN DETECTED" if last_det else "EMPTY"
                last_var = var_data[-1] if var_data else 0
                status = (f"{label}  |  Variance: {last_var:.4f}  |  "
                         f"Threshold: {state.detector.threshold:.4f}  |  "
                         f"{state.packets_per_sec} pkt/s  |  Total: {state.total_packets}")
            else:
                mac_info = f"MAC: {state.target_mac}  |  " if state.mac_locked else "Detecting MAC...  |  "
                status = f"NOT CALIBRATED — press 'c' to start  |  {mac_info}{state.packets_per_sec} pkt/s  |  Total: {state.total_packets}"

            status_text.set_text(status)

            # Prominent rate indicator (color-coded)
            rate = state.packets_per_sec
            if expected_rate > 0 and rate >= expected_rate * 0.9:
                rate_color = '#2ecc71'  # Green — good
            elif expected_rate > 0 and rate >= expected_rate * 0.5:
                rate_color = '#f39c12'  # Yellow — degraded
            else:
                rate_color = '#e74c3c'  # Red — poor
            rate_text.set_text(f'{rate} pkt/s')
            rate_text.set_color(rate_color)

    ani = animation.FuncAnimation(fig, update, interval=RENDER_INTERVAL_MS, cache_frame_data=False)
    plt.show()


def main():
    parser = argparse.ArgumentParser(description='Real-time CSI presence detection dashboard')
    parser.add_argument('--port', '-p', type=str, required=True, help='Serial port')
    parser.add_argument('--baud', '-b', type=int, default=921600, help='Baud rate')
    parser.add_argument('--output', '-o', type=str, default='data', help='Output directory for CSV')
    parser.add_argument('--calibration-file', type=str, default='data/calibration.json',
                        help='Path to save/load calibration')
    parser.add_argument('--load-calibration', action='store_true',
                        help='Load existing calibration on startup')
    parser.add_argument('--mac', type=str, default=None,
                        help='Filter to this MAC address only (auto-detected if not set)')
    parser.add_argument('--expected-rate', type=int, default=100,
                        help='Expected CSI packet rate in pkt/s (default: 100)')
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    timestamp_str = time.strftime('%Y-%m-%d_%H-%M-%S')
    csv_file = os.path.join(args.output, f'csi_{timestamp_str}.csv')

    state = DashboardState()

    if args.mac:
        state.target_mac = args.mac
        state.mac_locked = True
        print(f"Filtering to MAC: {args.mac}")

    if args.load_calibration and os.path.exists(args.calibration_file):
        state.detector.load_calibration(args.calibration_file)
        state.calibrated = True
        print(f"Loaded calibration from {args.calibration_file}")
        print(f"  Threshold: {state.detector.threshold:.4f}")

    # Start serial reader in background thread
    reader = threading.Thread(target=serial_reader_thread,
                              args=(state, args.port, args.baud, csv_file),
                              daemon=True)
    reader.start()

    print(f"Dashboard started. Saving CSV to {csv_file}")
    print("Press 'c' in the plot window to start/stop calibration")
    print("Press 'q' in the plot window to quit\n")

    create_dashboard(state, args.calibration_file, expected_rate=args.expected_rate)


if __name__ == '__main__':
    main()
