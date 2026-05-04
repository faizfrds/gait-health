#!/usr/bin/env python3
"""Record a live IMU sample over serial, write to a file, classify it.

Loop: ENTER to record N seconds, model predicts, repeat until 'q'.

Usage:
    python live_demo.py
    python live_demo.py --port /dev/tty.usbserial-11130 --duration 10
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import serial

from classify import predict_file
from record_imu import LINE_RE, find_port, parse_line, write_header

DEFAULT_DURATION = 10
DEFAULT_BAUD = 115200
OUTPUT_DIR = Path("dataset")


def record_to_file(ser: serial.Serial, filepath: Path, duration: float) -> int:
    write_header(filepath)
    n = 0
    start = time.time()
    with filepath.open("a") as f:
        while True:
            elapsed = time.time() - start
            if elapsed >= duration:
                break
            raw = ser.readline()
            try:
                line = raw.decode("utf-8", errors="replace").strip()
            except Exception:
                continue
            parsed = parse_line(line)
            if parsed is None:
                continue
            ax, ay, az, gx, gy, gz, temp = parsed
            t = time.time() - start
            f.write(f"{t:.6f},{ax:.6f},{ay:.6f},{az:.6f},"
                    f"{gx:.6f},{gy:.6f},{gz:.6f},{temp:.2f}\n")
            n += 1
            print(f"\r  recording {duration - elapsed:4.1f}s  samples: {n}",
                  end="", flush=True)
    print()
    return n


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default=None)
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION)
    parser.add_argument("--model", type=Path, default=Path("gait_model.pkl"))
    parser.add_argument("--keep", action="store_true",
                        help="keep recording files (default: deletes after classify)")
    args = parser.parse_args()

    if not args.model.exists():
        print(f"[ERROR] model not found: {args.model}. "
              f"Run: python -m gait_classifier.train", file=sys.stderr)
        sys.exit(1)

    OUTPUT_DIR.mkdir(exist_ok=True)
    port = args.port or find_port()
    print(f"[INFO] opening {port} @ {args.baud} baud")
    try:
        ser = serial.Serial(port, args.baud, timeout=1)
    except serial.SerialException as e:
        print(f"[ERROR] could not open port: {e}", file=sys.stderr)
        sys.exit(1)

    print("[INFO] waiting for IMU stream...")
    while True:
        line = ser.readline().decode("utf-8", errors="replace").strip()
        if LINE_RE.search(line):
            break
    print("[INFO] stream detected. Ready.\n")

    try:
        while True:
            ans = input(f"Press ENTER to record {args.duration:g}s "
                        f"(or 'q' to quit): ").strip().lower()
            if ans == "q":
                break
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = OUTPUT_DIR / f"live_{ts}.txt"
            n = record_to_file(ser, filepath, args.duration)
            if n < args.duration * 50:  # arbitrary floor: ~50 Hz minimum
                print(f"[WARN] only {n} samples captured — IMU stream may be slow")

            try:
                result = predict_file(args.model, filepath)
            except ValueError as e:
                print(f"[ERROR] {e}")
                continue

            print(f"\n→ {result['prediction'].upper()} "
                  f"(confidence {result['confidence']:.0%}, "
                  f"{result['n_windows']} windows)")
            for label, p in sorted(result["avg_probabilities"].items(),
                                   key=lambda kv: -kv[1]):
                bar = "█" * int(round(p * 30))
                print(f"  {label:10s} {p:.3f}  {bar}")
            print()

            if not args.keep:
                filepath.unlink()
    finally:
        ser.close()
        print("\n[DONE]")


if __name__ == "__main__":
    main()
