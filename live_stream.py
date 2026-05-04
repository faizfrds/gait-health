#!/usr/bin/env python3
"""Streaming gait classifier: rolling-window prediction from live IMU serial data.

Maintains the most recent `--window` seconds of samples, re-predicts every
`--stride` seconds, and prints the live label.

Usage:
    python live_stream.py
    python live_stream.py --port /dev/tty.usbserial-11130 --window 2 --stride 1
"""

import argparse
import pickle
import sys
import time
from collections import deque
from pathlib import Path

import numpy as np
import serial

from gait_classifier.data import AXES, TARGET_FS
from gait_classifier.features import extract_features
from record_imu import LINE_RE, find_port, parse_line


def predict_buffer(buf: deque, model, feat_names, fs: int, win_sec: float):
    if len(buf) < 2:
        return None
    arr = np.asarray(buf, dtype=np.float64)
    t = arr[:, 0]
    win_len = int(round(win_sec * fs))
    new_t = t[-1] - np.arange(win_len - 1, -1, -1) / fs
    if t[0] > new_t[0]:
        return None
    window = np.stack(
        [np.interp(new_t, t, arr[:, i + 1]) for i in range(len(AXES))], axis=1
    )
    feats = extract_features(window, fs=fs)
    x = np.array([[feats[n] for n in feat_names]], dtype=np.float64)
    pred = model.predict(x)[0]
    proba = model.predict_proba(x)[0]
    return str(pred), dict(zip(model.classes_, proba))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default=None)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--model", type=Path, default=Path("gait_model.pkl"))
    parser.add_argument("--window", type=float, default=2.0,
                        help="rolling window length in seconds")
    parser.add_argument("--stride", type=float, default=1.0,
                        help="how often to predict, in seconds")
    args = parser.parse_args()

    if not args.model.exists():
        print(f"[ERROR] model not found: {args.model}", file=sys.stderr)
        sys.exit(1)
    with args.model.open("rb") as f:
        bundle = pickle.load(f)
    model = bundle["model"]
    feat_names = bundle["feature_names"]

    port = args.port or find_port()
    print(f"[INFO] opening {port} @ {args.baud} baud")
    try:
        ser = serial.Serial(port, args.baud, timeout=1)
    except serial.SerialException as e:
        print(f"[ERROR] could not open port: {e}", file=sys.stderr)
        sys.exit(1)

    fs = TARGET_FS
    buf_max = int(args.window * 300)  # generous upper bound on raw sample rate
    buf: deque = deque(maxlen=buf_max)

    print(f"[INFO] window={args.window}s stride={args.stride}s — "
          f"streaming predictions (Ctrl+C to stop)\n")
    start = time.time()
    next_predict = start + args.window  # wait until first window is full

    try:
        while True:
            raw = ser.readline()
            try:
                line = raw.decode("utf-8", errors="replace").strip()
            except Exception:
                continue
            parsed = parse_line(line)
            if parsed is not None:
                t = time.time() - start
                buf.append((t,) + parsed[:6])  # drop temperature
                # trim by time as well, not just by maxlen
                cutoff = t - args.window
                while buf and buf[0][0] < cutoff:
                    buf.popleft()

            now = time.time()
            if now >= next_predict:
                result = predict_buffer(buf, model, feat_names, fs, args.window)
                if result is not None:
                    label, proba = result
                    elapsed = now - start
                    bars = " ".join(
                        f"{c}={proba.get(c, 0):.2f}" for c in bundle["labels"]
                    )
                    top = max(proba.values())
                    print(f"[t={elapsed:6.1f}s]  {label:10s} ({top:.0%})   {bars}")
                next_predict = now + args.stride
    except KeyboardInterrupt:
        print("\n[DONE]")
    finally:
        ser.close()


if __name__ == "__main__":
    main()
