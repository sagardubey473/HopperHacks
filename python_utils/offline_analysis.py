#!/usr/bin/env python3
"""
Offline CSI Analysis — Analyze previously collected CSV files for human presence detection.

Generates:
  - Amplitude over time plot
  - Variance over time plot with threshold line
  - Detection timeline
  - Summary statistics (% time human detected, event timestamps)
  - JSON results file

Usage:
    python offline_analysis.py data/csi_2026-02-21_14-30-00.csv
    python offline_analysis.py data/csi_file.csv --calibration data/calibration.json
    python offline_analysis.py data/csi_file.csv --auto-calibrate 30
"""

import argparse
import json
import os
import sys

# Ensure sibling modules are importable regardless of working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import matplotlib.pyplot as plt
import numpy as np

from csi_processing import parse_csi_line, iq_to_amplitude, get_active_subcarriers, SlidingWindow
from presence_detector import PresenceDetector


def load_csv(filepath):
    """Load all CSI_DATA lines from a CSV file. Returns list of (metadata, amplitudes)."""
    records = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if "CSI_DATA" not in line or line.startswith("type,"):
                continue
            metadata, iq = parse_csi_line(line)
            if metadata is None:
                continue
            amplitudes = iq_to_amplitude(iq)
            records.append((metadata, amplitudes))
    return records


def run_analysis(records, detector, window_size=100):
    """
    Run presence detection over all records.

    Returns list of result dicts, one per window step.
    """
    window = SlidingWindow(window_size=window_size)
    results = []

    for i, (metadata, amplitudes) in enumerate(records):
        window.add(amplitudes)
        features = window.compute_features()
        if features is None:
            continue

        result = detector.detect(features)
        if result is None:
            continue

        result['packet_index'] = i
        result['rssi'] = metadata.get('rssi', 0)
        result['pc_timestamp'] = metadata.get('pc_timestamp', i)
        results.append(result)

    return results


def generate_plots(records, results, output_prefix):
    """Generate and save analysis plots."""
    subcarriers_to_plot = [10, 20, 30, 40, 50]

    # Build amplitude time series per subcarrier
    amp_series = {sc: [] for sc in subcarriers_to_plot}
    for _, amplitudes in records:
        for sc in subcarriers_to_plot:
            if sc < len(amplitudes):
                amp_series[sc].append(amplitudes[sc])

    fig, (ax_amp, ax_var, ax_det) = plt.subplots(3, 1, figsize=(14, 10),
                                                   gridspec_kw={'height_ratios': [3, 2, 1]})
    fig.suptitle('CSI Offline Analysis — Human Presence Detection', fontsize=14)
    plt.subplots_adjust(hspace=0.35, top=0.93, bottom=0.07)

    # --- Top: Amplitude ---
    colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6']
    for i, sc in enumerate(subcarriers_to_plot):
        data = amp_series[sc]
        if data:
            ax_amp.plot(data, color=colors[i % len(colors)], alpha=0.6,
                       linewidth=0.5, label=f'SC {sc}')
    ax_amp.set_ylabel('Amplitude')
    ax_amp.set_title('CSI Amplitude Over Time')
    ax_amp.legend(loc='upper right', fontsize=8)

    # --- Middle: Variance with threshold ---
    if results:
        indices = [r['packet_index'] for r in results]
        variances = [r['variance'] for r in results]
        thresholds = [r['threshold'] for r in results]
        ax_var.plot(indices, variances, color='#2c3e50', linewidth=0.8, label='Variance')
        ax_var.plot(indices, thresholds, color='#e74c3c', linewidth=1.5,
                   linestyle='--', label='Threshold')
        ax_var.set_ylabel('Variance')
        ax_var.set_title('Mean Amplitude Variance vs Threshold')
        ax_var.legend(loc='upper right', fontsize=8)

    # --- Bottom: Detection timeline ---
    if results:
        det_colors = ['#2ecc71' if not r['present'] else '#e74c3c' for r in results]
        ax_det.bar(indices, [1] * len(results), color=det_colors, width=1.0)
        ax_det.set_ylim(0, 1)
        ax_det.set_yticks([])
        ax_det.set_xlabel('Packet Index')
        ax_det.set_title('Detection Timeline (Green=Empty, Red=Human Detected)')

    plot_path = output_prefix + '_analysis.png'
    fig.savefig(plot_path, dpi=150, bbox_inches='tight')
    print(f"  Plot saved: {plot_path}")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description='Offline CSI presence detection analysis')
    parser.add_argument('csv_file', type=str, help='Path to collected CSV file')
    parser.add_argument('--calibration', '-c', type=str, default=None,
                        help='Path to calibration JSON file')
    parser.add_argument('--auto-calibrate', type=int, default=30,
                        help='Auto-calibrate using first N seconds of data (default: 30)')
    parser.add_argument('--threshold', '-t', type=float, default=3.0,
                        help='Threshold multiplier (default: 3.0)')
    parser.add_argument('--window', '-w', type=int, default=100,
                        help='Sliding window size (default: 100)')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Output prefix for results (default: based on input filename)')
    args = parser.parse_args()

    if not os.path.exists(args.csv_file):
        print(f"Error: File not found: {args.csv_file}", file=sys.stderr)
        sys.exit(1)

    output_prefix = args.output or os.path.splitext(args.csv_file)[0]

    print(f"Loading {args.csv_file}...")
    records = load_csv(args.csv_file)
    print(f"  Loaded {len(records)} CSI packets")

    if len(records) < args.window:
        print(f"Error: Need at least {args.window} packets, got {len(records)}", file=sys.stderr)
        sys.exit(1)

    detector = PresenceDetector(threshold_multiplier=args.threshold)

    if args.calibration and os.path.exists(args.calibration):
        print(f"Loading calibration from {args.calibration}...")
        detector.load_calibration(args.calibration)
    else:
        # Auto-calibrate from first N seconds of data
        print(f"Auto-calibrating from first {args.auto_calibrate}s of data...")

        # Estimate packets per second from timestamps if available
        if 'pc_timestamp' in records[0][0] and 'pc_timestamp' in records[-1][0]:
            total_time = records[-1][0]['pc_timestamp'] - records[0][0]['pc_timestamp']
            if total_time > 0:
                pkt_rate = len(records) / total_time
                cal_packets = int(pkt_rate * args.auto_calibrate)
            else:
                cal_packets = args.auto_calibrate * 100  # assume 100 pkt/s
        else:
            cal_packets = args.auto_calibrate * 100

        cal_packets = min(cal_packets, len(records) // 2)  # Use at most half the data

        # Run sliding window over calibration portion
        cal_window = SlidingWindow(window_size=args.window)
        variance_samples = []
        for metadata, amplitudes in records[:cal_packets]:
            cal_window.add(amplitudes)
            features = cal_window.compute_features()
            if features:
                variance_samples.append(features['mean_variance'])

        if not detector.calibrate(variance_samples):
            print("Error: Auto-calibration failed — not enough variance data", file=sys.stderr)
            sys.exit(1)

        cal_file = output_prefix + '_calibration.json'
        detector.save_calibration(cal_file)
        print(f"  Calibration saved: {cal_file}")

    print(f"  Baseline mean: {detector.baseline_mean:.4f}")
    print(f"  Threshold:     {detector.threshold:.4f}")

    # Run detection
    print("Running detection...")
    results = run_analysis(records, detector, window_size=args.window)

    if not results:
        print("No detection results produced.", file=sys.stderr)
        sys.exit(1)

    # Summary statistics
    total_frames = len(results)
    detected_frames = sum(1 for r in results if r['present'])
    pct_detected = (detected_frames / total_frames * 100) if total_frames > 0 else 0

    # Find detection events (contiguous blocks of 'present')
    events = []
    in_event = False
    for r in results:
        if r['present'] and not in_event:
            in_event = True
            events.append({'start_index': r['packet_index'], 'start_ts': r.get('pc_timestamp')})
        elif not r['present'] and in_event:
            in_event = False
            events[-1]['end_index'] = r['packet_index']
            events[-1]['end_ts'] = r.get('pc_timestamp')
    if in_event:
        events[-1]['end_index'] = results[-1]['packet_index']
        events[-1]['end_ts'] = results[-1].get('pc_timestamp')

    print(f"\n--- Analysis Summary ---")
    print(f"  Total frames analyzed: {total_frames}")
    print(f"  Human detected:       {detected_frames} frames ({pct_detected:.1f}%)")
    print(f"  Detection events:     {len(events)}")
    for i, ev in enumerate(events):
        duration = ''
        if ev.get('start_ts') and ev.get('end_ts'):
            dur = ev['end_ts'] - ev['start_ts']
            duration = f" ({dur:.1f}s)"
        print(f"    Event {i+1}: packets {ev['start_index']}-{ev['end_index']}{duration}")
    print(f"------------------------\n")

    # Save results JSON
    json_path = output_prefix + '_results.json'
    json_data = {
        'source_file': args.csv_file,
        'total_packets': len(records),
        'total_frames': total_frames,
        'detected_frames': detected_frames,
        'detection_percentage': round(pct_detected, 2),
        'threshold': detector.threshold,
        'baseline_mean': detector.baseline_mean,
        'baseline_std': detector.baseline_std,
        'events': events,
    }
    with open(json_path, 'w') as f:
        json.dump(json_data, f, indent=2)
    print(f"  Results saved: {json_path}")

    # Generate plots
    print("Generating plots...")
    generate_plots(records, results, output_prefix)

    print("Done.")


if __name__ == '__main__':
    main()
