"""
CSI Processing Library — Parse raw CSI data and extract features for presence detection.

CSV column layout (from csi_component.h):
  0: type          (CSI_DATA)
  1: role          (AP/STA)
  2: mac
  3: rssi
  4: rate
  5: sig_mode
  6: mcs
  7: bandwidth
  8: smoothing
  9: not_sounding
 10: aggregation
 11: stbc
 12: fec_coding
 13: sgi
 14: noise_floor
 15: ampdu_cnt
 16: channel
 17: secondary_channel
 18: local_timestamp
 19: ant
 20: sig_len
 21: rx_state
 22: real_time_set
 23: real_timestamp
 24: len
 25: CSI_DATA       ([I Q I Q ...])
 26: pc_timestamp   (optional, appended by collector)
"""

import re
import sys

import numpy as np


# CSV column indices
COL_RSSI = 3
COL_NOISE_FLOOR = 14
COL_CHANNEL = 16
COL_LOCAL_TS = 18
COL_REAL_TS = 23
COL_CSI_LEN = 24
COL_CSI_DATA = 25
COL_PC_TIMESTAMP = 26

# First and last few subcarriers are usually null/pilot — skip them.
# For 64 subcarriers (128 I/Q values → 64 pairs), indices 4..59 are typically active.
ACTIVE_SUBCARRIER_START = 5
ACTIVE_SUBCARRIER_END = 59


def parse_csi_line(line):
    """
    Parse a single CSI_DATA CSV line into metadata dict and raw I/Q numpy array.

    Returns (metadata, iq_array) or (None, None) on failure.
    metadata keys: rssi, noise_floor, channel, local_timestamp, real_timestamp, csi_len, pc_timestamp
    iq_array: int8 numpy array of [I, Q, I, Q, ...]
    """
    if "CSI_DATA" not in line:
        return None, None

    try:
        # Extract CSI data bracket contents
        bracket_match = re.search(r"\[(.*?)\]", line)
        if not bracket_match:
            return None, None

        csi_string = bracket_match.group(1)
        iq_raw = np.array([int(x) for x in csi_string.split() if x != ''], dtype=np.int8)

        if len(iq_raw) < 2:
            return None, None

        # Split CSV fields (everything before the bracket)
        fields = line.split(',')

        metadata = {
            'mac': fields[2].strip(),
            'rssi': int(fields[COL_RSSI]),
            'noise_floor': int(fields[COL_NOISE_FLOOR]),
            'channel': int(fields[COL_CHANNEL]),
            'local_timestamp': int(fields[COL_LOCAL_TS]),
            'real_timestamp': float(fields[COL_REAL_TS]),
            'csi_len': int(fields[COL_CSI_LEN]),
        }

        # pc_timestamp is optionally appended after the CSI bracket
        if len(fields) > COL_PC_TIMESTAMP:
            try:
                metadata['pc_timestamp'] = float(fields[COL_PC_TIMESTAMP])
            except (ValueError, IndexError):
                pass

        return metadata, iq_raw

    except (IndexError, ValueError):
        return None, None


def iq_to_amplitude(iq_array):
    """
    Convert raw I/Q array into per-subcarrier amplitude.

    Input:  [I0, Q0, I1, Q1, ...] — length 2N
    Output: [amp0, amp1, ...] — length N
    """
    iq = iq_array.astype(np.float64)
    imaginary = iq[0::2]
    real = iq[1::2]
    return np.sqrt(imaginary ** 2 + real ** 2)


def iq_to_phase(iq_array):
    """
    Convert raw I/Q array into per-subcarrier phase (radians).
    """
    iq = iq_array.astype(np.float64)
    imaginary = iq[0::2]
    real = iq[1::2]
    return np.arctan2(imaginary, real)


def get_active_subcarriers(amplitudes):
    """
    Return only the active subcarrier amplitudes (skip null/pilot at edges).
    """
    end = min(ACTIVE_SUBCARRIER_END, len(amplitudes))
    start = min(ACTIVE_SUBCARRIER_START, end)
    return amplitudes[start:end]


class SlidingWindow:
    """
    Sliding window buffer for CSI amplitude frames.
    Stores a fixed number of recent amplitude arrays and computes features over them.
    """

    def __init__(self, window_size=100):
        """
        Args:
            window_size: Number of CSI frames to keep in the window (default 100 ≈ 1 second at 100 Hz).
        """
        self.window_size = window_size
        self._buffer = []

    def add(self, amplitudes):
        """Add a new amplitude array to the window."""
        active = get_active_subcarriers(amplitudes)
        self._buffer.append(active)
        if len(self._buffer) > self.window_size:
            self._buffer.pop(0)

    def is_full(self):
        return len(self._buffer) >= self.window_size

    def count(self):
        return len(self._buffer)

    def clear(self):
        self._buffer = []

    def compute_features(self):
        """
        Compute features over the current window.

        Returns dict with:
            amplitude_variance: per-subcarrier variance (primary detection signal)
            mean_amplitude: per-subcarrier mean
            overall_std: scalar std across all subcarriers and frames
            mean_variance: scalar mean of per-subcarrier variances
        Returns None if window has fewer than 2 frames.
        """
        if len(self._buffer) < 2:
            return None

        # Stack into 2D array: (num_frames, num_subcarriers)
        try:
            data = np.array(self._buffer)
        except ValueError:
            # Inconsistent subcarrier counts — skip
            return None

        amplitude_variance = np.var(data, axis=0)
        mean_amplitude = np.mean(data, axis=0)
        overall_std = np.std(data)
        mean_variance = np.mean(amplitude_variance)

        return {
            'amplitude_variance': amplitude_variance,
            'mean_amplitude': mean_amplitude,
            'overall_std': float(overall_std),
            'mean_variance': float(mean_variance),
        }


def open_serial(port, baud):
    """
    Open a serial port with helpful error message on failure.
    Lists available ports if the requested one doesn't exist.
    """
    import serial
    import serial.tools.list_ports

    try:
        return serial.Serial(port, baud, timeout=1)
    except serial.SerialException as e:
        print(f"\nError: Could not open port '{port}': {e}", file=sys.stderr)
        ports = serial.tools.list_ports.comports()
        if ports:
            print("\nAvailable serial ports:", file=sys.stderr)
            for p in ports:
                print(f"  {p.device}  —  {p.description}", file=sys.stderr)
            print(f"\nTry: --port {ports[0].device}", file=sys.stderr)
        else:
            print("\nNo serial ports found. Is the ESP32 plugged in via USB?", file=sys.stderr)
        sys.exit(1)
