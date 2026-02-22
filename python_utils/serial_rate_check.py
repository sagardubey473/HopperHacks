#!/usr/bin/env python3
"""
CSI Packet Rate Checker — Verify that ESP32 CSI packets arrive at the expected rate.

Usage:
    python serial_rate_check.py --port /dev/tty.usbserial-XXX
    python serial_rate_check.py --port /dev/ttyUSB0 --duration 10
    python serial_rate_check.py --port /dev/ttyUSB0 --continuous
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from csi_processing import parse_csi_line, open_serial


def run_summary(ser, duration, expected_rate):
    """Run for a fixed duration and print a summary report."""
    print(f"Measuring CSI packet rate for {duration} seconds...")
    print("Waiting for first CSI_DATA packet...\n")

    per_second_counts = []
    mac_counts = {}
    packet_count = 0
    interval_start = None
    measure_start = None

    while True:
        try:
            raw = ser.readline().decode('utf-8', errors='ignore').strip()
        except Exception:
            continue

        if "CSI_DATA" not in raw:
            continue

        now = time.time()

        if measure_start is None:
            measure_start = now
            interval_start = now
            print("Receiving packets...")

        packet_count += 1

        metadata, _ = parse_csi_line(raw)
        if metadata:
            mac = metadata.get('mac', 'unknown')
            mac_counts[mac] = mac_counts.get(mac, 0) + 1

        if now - interval_start >= 1.0:
            per_second_counts.append(packet_count)
            print(f"  [{len(per_second_counts):>3}s]  {packet_count} pkt/s")
            packet_count = 0
            interval_start = now

        if now - measure_start >= duration:
            # Count any remaining partial second
            if packet_count > 0:
                per_second_counts.append(packet_count)
            break

    total_time = time.time() - measure_start
    total_packets = sum(per_second_counts)

    if not per_second_counts:
        print("\nNo CSI packets received!")
        return

    import numpy as np
    rates = np.array(per_second_counts)
    avg_rate = total_packets / total_time
    min_rate = int(rates.min())
    max_rate = int(rates.max())
    std_rate = float(rates.std())

    print(f"\n{'=' * 40}")
    print(f"  CSI Packet Rate Report")
    print(f"{'=' * 40}")
    print(f"  Duration:      {total_time:.1f} seconds")
    print(f"  Total packets: {total_packets}")
    print(f"  Average rate:  {avg_rate:.1f} pkt/s")
    print(f"  Min (1s):      {min_rate} pkt/s")
    print(f"  Max (1s):      {max_rate} pkt/s")
    print(f"  Std deviation: {std_rate:.1f} pkt/s")

    if mac_counts:
        print(f"\n  Per-MAC breakdown:")
        for mac, count in sorted(mac_counts.items(), key=lambda x: -x[1]):
            mac_rate = count / total_time
            print(f"    {mac} -- {count} packets ({mac_rate:.1f} pkt/s)")

    print(f"{'=' * 40}")
    if avg_rate >= expected_rate * 0.9:
        print(f"  RESULT: {expected_rate} pkt/s target VERIFIED")
    elif avg_rate >= expected_rate * 0.5:
        print(f"  WARNING: {avg_rate:.0f} pkt/s is below target {expected_rate} pkt/s")
    else:
        print(f"  PROBLEM: {avg_rate:.0f} pkt/s is far below target {expected_rate} pkt/s")
        print(f"  Check: baud rate, WiFi connection, serial output bottleneck")
    print(f"{'=' * 40}")


def run_continuous(ser):
    """Print per-second rate indefinitely."""
    print("Continuous rate monitoring (Ctrl+C to stop)...")
    print("Waiting for first CSI_DATA packet...\n")

    packet_count = 0
    total_packets = 0
    total_seconds = 0
    interval_start = None

    try:
        while True:
            try:
                raw = ser.readline().decode('utf-8', errors='ignore').strip()
            except Exception:
                continue

            if "CSI_DATA" not in raw:
                continue

            now = time.time()
            if interval_start is None:
                interval_start = now

            packet_count += 1
            total_packets += 1

            if now - interval_start >= 1.0:
                total_seconds += 1
                avg = total_packets / total_seconds
                print(f"  [{total_seconds:>4}s]  {packet_count} pkt/s  |  avg: {avg:.1f}")
                packet_count = 0
                interval_start = now
    except KeyboardInterrupt:
        print(f"\nStopped. Total: {total_packets} packets in {total_seconds} seconds.")


def main():
    parser = argparse.ArgumentParser(description='CSI packet rate verification tool')
    parser.add_argument('--port', '-p', type=str, required=True, help='Serial port')
    parser.add_argument('--baud', '-b', type=int, default=921600, help='Baud rate')
    parser.add_argument('--duration', '-d', type=int, default=10,
                        help='Measurement duration in seconds (default: 10)')
    parser.add_argument('--expected-rate', type=int, default=100,
                        help='Expected packet rate in pkt/s (default: 100)')
    parser.add_argument('--continuous', '-c', action='store_true',
                        help='Run continuously instead of fixed duration')
    args = parser.parse_args()

    ser = open_serial(args.port, args.baud)
    print(f"Connected to {args.port} at {args.baud} baud\n")

    if args.continuous:
        run_continuous(ser)
    else:
        run_summary(ser, args.duration, args.expected_rate)

    ser.close()


if __name__ == '__main__':
    main()
