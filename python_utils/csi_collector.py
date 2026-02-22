#!/usr/bin/env python3
"""
CSI Data Collector — Capture CSI_DATA from ESP32 serial port to timestamped CSV files.

Usage:
    python csi_collector.py --port /dev/tty.usbserial-XXX
    python csi_collector.py --port /dev/ttyUSB0 --baud 921600 --output data/
"""

import argparse
import os
import sys
import time

# Ensure sibling modules are importable regardless of working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import serial

from csi_processing import open_serial


CSV_HEADER = "type,role,mac,rssi,rate,sig_mode,mcs,bandwidth,smoothing,not_sounding,aggregation,stbc,fec_coding,sgi,noise_floor,ampdu_cnt,channel,secondary_channel,local_timestamp,ant,sig_len,rx_state,real_time_set,real_timestamp,len,CSI_DATA,pc_timestamp\n"


def serial_readline(ser):
    """Read a line from serial, ignoring decode errors (matches read_stdin.py pattern)."""
    while True:
        try:
            raw = ser.readline()
            return raw.decode('utf-8', errors='ignore').strip()
        except Exception:
            continue


def find_serial_port():
    """Attempt to auto-detect an ESP32 serial port."""
    import serial.tools.list_ports
    ports = serial.tools.list_ports.comports()
    for p in ports:
        desc = (p.description or '').lower()
        hwid = (p.hwid or '').lower()
        if any(kw in desc or kw in hwid for kw in ['cp210', 'ch340', 'ftdi', 'usb', 'uart', 'silicon labs']):
            return p.device
    # Fall back to first available port
    if ports:
        return ports[0].device
    return None


def collect(port, baud, output_dir):
    """Main collection loop: read serial CSI data, write to CSV."""
    os.makedirs(output_dir, exist_ok=True)

    timestamp_str = time.strftime('%Y-%m-%d_%H-%M-%S')
    filename = os.path.join(output_dir, f'csi_{timestamp_str}.csv')

    ser = open_serial(port, baud)
    print(f"Connected to {port} at {baud} baud. Saving to {filename}")
    print("Waiting for CSI_DATA... (press Ctrl+C to stop)\n")

    packet_count = 0
    total_packets = 0
    start_time = time.time()
    interval_start = time.time()

    try:
        with open(filename, 'w') as f:
            f.write(CSV_HEADER)

            # Skip initial boot/debug lines until first CSI_DATA
            while True:
                line = serial_readline(ser)
                if "CSI_DATA" in line:
                    # Process this first CSI line
                    pc_ts = time.time()
                    f.write(line + ',' + str(pc_ts) + '\n')
                    total_packets += 1
                    packet_count += 1
                    break

            print("Receiving CSI data...")

            while True:
                line = serial_readline(ser)
                if not line:
                    continue

                if "CSI_DATA" in line:
                    pc_ts = time.time()
                    f.write(line + ',' + str(pc_ts) + '\n')
                    total_packets += 1
                    packet_count += 1

                # Print stats every second
                now = time.time()
                if now - interval_start >= 1.0:
                    elapsed = now - start_time
                    print(f"  {packet_count} pkt/s | Total: {total_packets} | Duration: {elapsed:.1f}s",
                          end='\r')
                    packet_count = 0
                    interval_start = now

    except KeyboardInterrupt:
        pass

    ser.close()
    elapsed = time.time() - start_time

    print(f"\n\n--- Collection Summary ---")
    print(f"  File:      {filename}")
    print(f"  Packets:   {total_packets}")
    print(f"  Duration:  {elapsed:.1f} seconds")
    if elapsed > 0:
        print(f"  Avg rate:  {total_packets / elapsed:.1f} packets/sec")
    print(f"--------------------------")


def main():
    parser = argparse.ArgumentParser(description='Collect CSI data from ESP32 serial port')
    parser.add_argument('--port', '-p', type=str, default=None,
                        help='Serial port (e.g. /dev/ttyUSB0). Auto-detected if not specified.')
    parser.add_argument('--baud', '-b', type=int, default=921600,
                        help='Baud rate (default: 921600)')
    parser.add_argument('--output', '-o', type=str, default='data',
                        help='Output directory (default: data/)')
    args = parser.parse_args()

    port = args.port
    if port is None:
        port = find_serial_port()
        if port is None:
            print("Error: No serial port found. Specify one with --port", file=sys.stderr)
            sys.exit(1)
        print(f"Auto-detected serial port: {port}")

    collect(port, args.baud, args.output)


if __name__ == '__main__':
    main()
