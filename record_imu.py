#!/usr/bin/env python3
"""
IMU Data Recorder for Gait Analysis.

Records MPU6050 acceleration and gyroscopic data from ESP32 to labeled .txt files.
Collects 10 seconds of gait data per recording.
Press ENTER to start recording each gait sample.

Usage:
    python record_imu.py                        # auto-detects port
    python record_imu.py --port /dev/tty.usbserial-11130
    python record_imu.py --port /dev/tty.usbserial-11130 --baud 115200

Sensor Placement:
    Recommended: Ankle-worn or wrist-worn (document placement in collected data)

Collection Tips:
    - Healthy: Natural walking pace, multiple trials
    - Shuffling: Short, rapid steps with reduced amplitude
    - FoG (Freezing of Gait): Sudden loss of movement, often at turns
"""

import argparse
import re
import sys
import time
from pathlib import Path

import serial
import serial.tools.list_ports

# ── Configuration ────────────────────────────────────────────────────────────
BAUD_RATE = 115200
RECORD_DURATION = 10  # seconds per movement

# Regex to parse ESP_LOGI output
LINE_RE = re.compile(
    r"AX:(?P<ax>[-\d.]+)\s+AY:(?P<ay>[-\d.]+)\s+AZ:(?P<az>[-\d.]+)"
    r"\s*\|\s*"
    r"GX:(?P<gx>[-\d.]+)\s+GY:(?P<gy>[-\d.]+)\s+GZ:(?P<gz>[-\d.]+)"
    r"\s*\|\s*"
    r"T:(?P<t>[-\d.]+)"
)

# Output directory
OUTPUT_DIR = Path("dataset")
OUTPUT_DIR.mkdir(exist_ok=True)

GAIT_CONDITIONS = ["healthy", "shuffling", "fog"]

# Repetitions per gait condition (can be customized per condition)
REPS_PER_CONDITION = {
    "healthy": 0,      # Multiple samples to capture natural variability
    "shuffling": 20,    # Gait shuffling samples
    "fog": 0,          # Freezing of Gait episodes (harder to collect)
}


def find_port() -> str:
    """Auto-detect the first USB-serial port."""
    ports = serial.tools.list_ports.comports()
    usb = [p for p in ports if "usb" in p.device.lower() or "usbserial" in p.device.lower()]
    if usb:
        return usb[0].device
    if ports:
        return ports[0].device
    print("[ERROR] No serial ports found. Plug in your ESP32 or specify --port.", file=sys.stderr)
    sys.exit(1)


def parse_line(line: str):
    """Parse IMU data line. Returns (ax, ay, az, gx, gy, gz, temp) or None."""
    m = LINE_RE.search(line)
    if m:
        return tuple(float(m.group(k)) for k in ("ax", "ay", "az", "gx", "gy", "gz", "t"))
    return None


def get_output_filepath(gesture_name: str, idx: int) -> Path:
    """Get the output file path like up_01.txt, up_02.txt, etc."""
    return OUTPUT_DIR / f"{gesture_name}_{idx:02d}.txt"


def write_header(filepath: Path):
    """Write CSV header to file."""
    with open(filepath, "w") as f:
        f.write("# Gait Analysis Data - MPU6050 IMU\n")
        f.write(f"# Duration: {RECORD_DURATION} seconds\n")
        f.write("# Format: timestamp(s),ax(g),ay(g),az(g),gx(deg/s),gy(deg/s),gz(deg/s),temp(C)\n")
        f.write("# Note: Document sensor placement (ankle/wrist) separately\n")
        f.write("timestamp,ax,ay,az,gx,gy,gz,temp\n")


def record_gait(ser: serial.Serial, condition_name: str, filepath: Path, rep: int, total: int):
    """Record gait data for a specific condition (healthy, shuffling, FoG)."""
    print(f"\n{'='*60}")
    print(f"Gait Condition: {condition_name.upper()}  [{rep}/{total}]")
    print(f"Output file: {filepath}")
    print(f"Press ENTER to start {RECORD_DURATION}-second recording...")
    print(f"{'='*60}")

    input()  # Wait for Enter to start

    # Write header
    write_header(filepath)

    print(f"Recording {condition_name.upper()} for {RECORD_DURATION} seconds...")
    samples = []
    start_time = time.time()

    while True:
        elapsed = time.time() - start_time
        if elapsed >= RECORD_DURATION:
            break

        raw = ser.readline()
        try:
            line = raw.decode("utf-8", errors="replace").strip()
        except Exception:
            continue

        parsed = parse_line(line)
        if parsed is not None:
            ax, ay, az, gx, gy, gz, temp = parsed
            timestamp = time.time() - start_time
            samples.append((timestamp, ax, ay, az, gx, gy, gz, temp))

            with open(filepath, "a") as f:
                f.write(f"{timestamp:.6f},{ax:.6f},{ay:.6f},{az:.6f},{gx:.6f},{gy:.6f},{gz:.6f},{temp:.2f}\n")

        # Print countdown
        remaining = RECORD_DURATION - elapsed
        print(f"\r  Time remaining: {remaining:.1f}s  Samples: {len(samples)}", end="", flush=True)

    print(f"\n\nDone! Recorded {len(samples)} samples in {RECORD_DURATION} seconds")
    print(f"Saved to: {filepath}")


def main():
    parser = argparse.ArgumentParser(description="IMU Gait Analysis Data Recorder")
    parser.add_argument("--port", default=None, help="Serial port (auto-detected if omitted)")
    parser.add_argument("--baud", default=BAUD_RATE, type=int, help=f"Baud rate (default {BAUD_RATE})")
    args = parser.parse_args()

    port = args.port or find_port()
    baud = args.baud

    print(f"[INFO] Opening {port} at {baud} baud ...")
    print(f"[INFO] Data will be saved to: {OUTPUT_DIR.absolute()}")
    print(f"[INFO] Each recording captures {RECORD_DURATION} seconds of gait data")
    print(f"[INFO] Recording plan:")
    for condition in GAIT_CONDITIONS:
        reps = REPS_PER_CONDITION.get(condition, 0)
        if reps > 0:
            print(f"      - {condition}: {reps} samples")
        else:
            print(f"      - {condition}: (not configured yet)")

    # Connect to serial
    try:
        ser = serial.Serial(port, baud, timeout=1)
        print(f"[INFO] Connected to {port}")
    except serial.SerialException as e:
        print(f"[ERROR] Could not open port: {e}")
        sys.exit(1)

    # Wait for data to start flowing
    print("[INFO] Waiting for IMU data...")
    while True:
        line = ser.readline()
        if parse_line(line.decode("utf-8", errors="replace").strip()):
            print("[INFO] IMU data detected!")
            break

    # Record each gait condition
    quit_flag = False
    for condition_name in GAIT_CONDITIONS:
        num_reps = REPS_PER_CONDITION.get(condition_name, 0)
        if num_reps == 0:
            print(f"\n[SKIP] {condition_name}: not configured (set repetitions in REPS_PER_CONDITION)")
            continue

        print(f"\n{'#'*60}")
        print(f"### Starting condition: {condition_name.upper()} ({num_reps} recordings)")
        print(f"{'#'*60}")

        for rep in range(16, num_reps + 1):
            filepath = get_output_filepath(condition_name, rep)
            record_gait(ser, condition_name, filepath, rep, num_reps)

        if condition_name != GAIT_CONDITIONS[-1]:
            cont = input("\nContinue to next condition? (Enter/y to continue, q to quit): ").strip().lower()
            if cont == "q":
                quit_flag = True
                break

    if not quit_flag:
        print("\n" + "="*60)
        print("All gait conditions recorded! Summary:")
        for condition_name in GAIT_CONDITIONS:
            files = sorted(OUTPUT_DIR.glob(f"{condition_name}_*.txt"))
            if files:
                print(f"  {condition_name}: {len(files)} files")
        print("="*60)

    ser.close()
    print("\n[DONE] All recordings complete!")
    print(f"[INFO] Data saved to: {OUTPUT_DIR.absolute()}")


if __name__ == "__main__":
    main()
