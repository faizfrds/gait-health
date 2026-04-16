#!/usr/bin/env python3
"""
Real-time 3D IMU Trace — tracks sensor position by integrating acceleration.

Shows a live 3D path of the sensor, a 2D top-down (XY) trace, and current
orientation from gyroscope data. Press 'r' in the terminal to reset the trace.

Usage:
    python trace_imu.py                        # auto-detects port
    python trace_imu.py --port /dev/tty.usbserial-11130
    python trace_imu.py --port /dev/tty.usbserial-11130 --trail 500
"""

import argparse
import re
import sys
import threading
import time
from collections import deque

import matplotlib
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import matplotlib.gridspec as gridspec
from matplotlib.animation import FuncAnimation
import numpy as np
import serial
import serial.tools.list_ports

# ── Configuration ────────────────────────────────────────────────────────────
BAUD_RATE = 115200
SAMPLE_HZ = 100
TRAIL_LEN = 500          # max trail points to display
GRAVITY = 9.81            # m/s^2
ALPHA = 0.3               # high-pass filter coefficient (removes drift)

# Matches: I (4200) mpu6050 stream: AX:0.873 AY:0.030 AZ:-0.514 | GX:-1.908 GY:2.916 GZ:-0.840 | T:31.97 C
LINE_RE = re.compile(
    r"AX:(?P<ax>[-\d.]+)\s+AY:(?P<ay>[-\d.]+)\s+AZ:(?P<az>[-\d.]+)"
    r"\s*\|\s*"
    r"GX:(?P<gx>[-\d.]+)\s+GY:(?P<gy>[-\d.]+)\s+GZ:(?P<gz>[-\d.]+)"
    r"\s*\|\s*"
    r"T:(?P<t>[-\d.]+)"
)

# ESP-IDF log output includes ANSI colour codes — strip them before parsing
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[mK]")

# ── Colours ──────────────────────────────────────────────────────────────────
C = {
    "bg":       "#0f1117",
    "panel":    "#1a1d27",
    "grid":     "#2a2d3a",
    "trail":    "#4fc3f7",
    "trail2d":  "#81d4fa",
    "head":     "#ff5252",
    "arrow":    "#ffcc02",
    "text":     "#e0e0e0",
    "title":    "#ffffff",
    "ax_color": "#4fc3f7",
    "ay_color": "#81d4fa",
    "az_color": "#b3e5fc",
    "gx_color": "#f48fb1",
    "gy_color": "#f06292",
    "gz_color": "#e91e63",
}


def find_port() -> str:
    ports = serial.tools.list_ports.comports()
    usb = [p for p in ports if "usb" in p.device.lower() or "usbserial" in p.device.lower()]
    if usb:
        return usb[0].device
    if ports:
        return ports[0].device
    print("[ERROR] No serial ports found.", file=sys.stderr)
    sys.exit(1)


def parse_line(line: str):
    line = ANSI_RE.sub("", line)   # strip ESP-IDF colour codes
    m = LINE_RE.search(line)
    if m:
        return tuple(float(m.group(k)) for k in ("ax", "ay", "az", "gx", "gy", "gz", "t"))
    return None



class IMUTracer(threading.Thread):
    """Background thread: reads serial, integrates accel -> velocity -> position."""

    def __init__(self, port, baud, trail_len):
        super().__init__(daemon=True)
        self.port = port
        self.baud = baud
        self.lock = threading.Lock()

        # Position trail
        self.trail_x = deque(maxlen=trail_len)
        self.trail_y = deque(maxlen=trail_len)
        self.trail_z = deque(maxlen=trail_len)

        # Current state
        self.pos = np.zeros(3)
        self.vel = np.zeros(3)
        self.orientation = np.zeros(3)  # roll, pitch, yaw in degrees

        # Raw values for display
        self.raw_accel = np.zeros(3)
        self.raw_gyro = np.zeros(3)
        self.temp = 0.0

        # Calibration (gravity offset, computed from first N samples)
        self.accel_offset = np.zeros(3)
        self.calibrated = False
        self.cal_buf = []
        self.CAL_SAMPLES = 100

        # High-pass state
        self.prev_accel = np.zeros(3)
        self.filtered_accel = np.zeros(3)

        self.connected = False
        self.status = "Connecting..."
        self.sample_count = 0
        self._reset_flag = False

    def reset(self):
        self._reset_flag = True

    def _do_reset(self):
        with self.lock:
            self.pos[:] = 0
            self.vel[:] = 0
            self.orientation[:] = 0
            self.trail_x.clear()
            self.trail_y.clear()
            self.trail_z.clear()
            self.trail_x.append(0)
            self.trail_y.append(0)
            self.trail_z.append(0)
            self.prev_accel[:] = 0
            self.filtered_accel[:] = 0
            self.calibrated = False
            self.cal_buf.clear()
        self._reset_flag = False

    def run(self):
        self.trail_x.append(0)
        self.trail_y.append(0)
        self.trail_z.append(0)

        while True:
            try:
                with serial.Serial(self.port, self.baud, timeout=1) as ser:
                    self.connected = True
                    self.status = f"Connected — {self.port} @ {self.baud}"
                    prev_time = time.perf_counter()

                    while True:
                        if self._reset_flag:
                            self._do_reset()
                            prev_time = time.perf_counter()

                        raw = ser.readline()
                        try:
                            line = raw.decode("utf-8", errors="replace").strip()
                        except Exception:
                            continue

                        parsed = parse_line(line)
                        if parsed is None:
                            continue

                        ax, ay, az, gx, gy, gz, temp = parsed
                        now = time.perf_counter()
                        dt = now - prev_time
                        prev_time = now

                        if dt > 0.5:
                            dt = 1.0 / SAMPLE_HZ

                        accel = np.array([ax, ay, az]) * GRAVITY  # convert g -> m/s^2
                        gyro = np.array([gx, gy, gz])

                        # Calibration phase: accumulate and average
                        if not self.calibrated:
                            self.cal_buf.append(accel.copy())
                            if len(self.cal_buf) >= self.CAL_SAMPLES:
                                self.accel_offset = np.mean(self.cal_buf, axis=0)
                                self.calibrated = True
                                self.status += "  [Calibrated]"
                            continue

                        # Remove gravity / static offset
                        accel -= self.accel_offset

                        # High-pass filter to reduce drift
                        self.filtered_accel = ALPHA * (self.filtered_accel + accel - self.prev_accel)
                        self.prev_accel = accel.copy()
                        a = self.filtered_accel

                        # Dead-zone: ignore tiny accelerations (noise)
                        threshold = 0.05 * GRAVITY
                        a[np.abs(a) < threshold] = 0

                        with self.lock:
                            # Integrate: accel -> velocity (with damping to fight drift)
                            self.vel = self.vel * 0.95 + a * dt

                            # Integrate: velocity -> position
                            self.pos += self.vel * dt

                            # Gyro -> orientation (simple Euler integration)
                            self.orientation += gyro * dt

                            # Store trail
                            self.trail_x.append(self.pos[0])
                            self.trail_y.append(self.pos[1])
                            self.trail_z.append(self.pos[2])

                            self.raw_accel = np.array([ax, ay, az])
                            self.raw_gyro = gyro
                            self.temp = temp
                            self.sample_count += 1

            except serial.SerialException as e:
                self.connected = False
                self.status = f"Disconnected — {e} (retrying...)"
                time.sleep(2)

    def snapshot(self):
        with self.lock:
            return (
                np.array(self.trail_x), np.array(self.trail_y), np.array(self.trail_z),
                self.pos.copy(), self.vel.copy(), self.orientation.copy(),
                self.raw_accel.copy(), self.raw_gyro.copy(), self.temp,
                self.sample_count, self.calibrated,
            )


def main():
    parser = argparse.ArgumentParser(description="Real-time 3D IMU Trace")
    parser.add_argument("--port", default=None, help="Serial port")
    parser.add_argument("--baud", default=BAUD_RATE, type=int)
    parser.add_argument("--trail", default=TRAIL_LEN, type=int, help="Trail length in samples")
    args = parser.parse_args()

    port = args.port or find_port()
    print(f"[INFO] Opening {port} at {args.baud} baud ...")
    print("[INFO] Keep sensor still for ~1 second to calibrate.")
    print("[INFO] Press 'r' in the terminal to reset trace.\n")

    tracer = IMUTracer(port, args.baud, args.trail)
    tracer.start()

    # ── Reset listener (non-blocking stdin) ──────────────────────────────────
    def key_listener():
        while True:
            try:
                ch = input()
                if ch.strip().lower() == "r":
                    tracer.reset()
                    print("[RESET] Trace cleared.")
            except EOFError:
                break

    key_thread = threading.Thread(target=key_listener, daemon=True)
    key_thread.start()

    # ── Figure ───────────────────────────────────────────────────────────────
    plt.style.use("dark_background")
    fig = plt.figure(figsize=(16, 9), facecolor=C["bg"])
    fig.canvas.manager.set_window_title("IMU Real-Time Trace")

    gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.35, wspace=0.3,
                           left=0.06, right=0.97, top=0.92, bottom=0.06)

    # 3D trace (large, left side)
    ax3d = fig.add_subplot(gs[:, 0], projection="3d")
    ax3d.set_facecolor(C["panel"])
    ax3d.set_xlabel("X (m)", color=C["text"], fontsize=8)
    ax3d.set_ylabel("Y (m)", color=C["text"], fontsize=8)
    ax3d.set_zlabel("Z (m)", color=C["text"], fontsize=8)
    ax3d.set_title("3D Trace", color=C["title"], fontsize=11, fontweight="bold")
    ax3d.tick_params(colors=C["text"], labelsize=7)

    # Top-down XY view
    ax_xy = fig.add_subplot(gs[0, 1])
    ax_xy.set_facecolor(C["panel"])
    ax_xy.set_xlabel("X (m)", color=C["text"], fontsize=8)
    ax_xy.set_ylabel("Y (m)", color=C["text"], fontsize=8)
    ax_xy.set_title("Top View (XY)", color=C["title"], fontsize=10, fontweight="bold")
    ax_xy.set_aspect("equal", adjustable="datalim")
    ax_xy.grid(True, color=C["grid"], linewidth=0.5, linestyle="--")
    ax_xy.tick_params(colors=C["text"], labelsize=7)

    # Side XZ view
    ax_xz = fig.add_subplot(gs[1, 1])
    ax_xz.set_facecolor(C["panel"])
    ax_xz.set_xlabel("X (m)", color=C["text"], fontsize=8)
    ax_xz.set_ylabel("Z (m)", color=C["text"], fontsize=8)
    ax_xz.set_title("Side View (XZ)", color=C["title"], fontsize=10, fontweight="bold")
    ax_xz.set_aspect("equal", adjustable="datalim")
    ax_xz.grid(True, color=C["grid"], linewidth=0.5, linestyle="--")
    ax_xz.tick_params(colors=C["text"], labelsize=7)

    # Raw sensor readout panel
    ax_info = fig.add_subplot(gs[:, 2])
    ax_info.set_facecolor(C["panel"])
    ax_info.set_xlim(0, 1)
    ax_info.set_ylim(0, 1)
    ax_info.axis("off")
    ax_info.set_title("Sensor Readout", color=C["title"], fontsize=10, fontweight="bold")

    # Pre-create info text
    info_text = ax_info.text(0.05, 0.95, "", transform=ax_info.transAxes,
                             fontfamily="monospace", fontsize=9, color=C["text"],
                             verticalalignment="top", linespacing=1.8)

    suptitle = fig.suptitle("IMU Real-Time Trace", color=C["title"],
                            fontsize=14, fontweight="bold")
    status_txt = fig.text(0.5, 0.005, "Connecting...", ha="center",
                          fontsize=8, color="#888888")

    # ── Animation ────────────────────────────────────────────────────────────
    def update(_):
        tx, ty, tz, pos, vel, orient, raw_a, raw_g, temp, n, cal = tracer.snapshot()

        if len(tx) < 2:
            status_txt.set_text(tracer.status + ("  [Calibrating...]" if not cal else ""))
            return

        # ── 3D trace ─────────────────────────────────────────────────────
        ax3d.cla()
        ax3d.set_facecolor(C["panel"])
        ax3d.set_xlabel("X (m)", color=C["text"], fontsize=8)
        ax3d.set_ylabel("Y (m)", color=C["text"], fontsize=8)
        ax3d.set_zlabel("Z (m)", color=C["text"], fontsize=8)
        ax3d.set_title("3D Trace", color=C["title"], fontsize=11, fontweight="bold")
        ax3d.tick_params(colors=C["text"], labelsize=7)

        # Color trail by recency (fade older points)
        n_pts = len(tx)
        colors = np.zeros((n_pts, 4))
        colors[:, 0] = 0.31  # R
        colors[:, 1] = 0.76  # G
        colors[:, 2] = 0.97  # B
        colors[:, 3] = np.linspace(0.1, 1.0, n_pts)  # alpha

        ax3d.plot(tx, ty, tz, color=C["trail"], linewidth=1.0, alpha=0.6)
        ax3d.scatter([pos[0]], [pos[1]], [pos[2]], color=C["head"], s=60, zorder=5)

        # Origin marker
        ax3d.scatter([0], [0], [0], color="#555555", s=30, marker="x")

        # Auto-scale with padding
        pad = 0.05
        for setter, vals in [(ax3d.set_xlim, tx), (ax3d.set_ylim, ty), (ax3d.set_zlim, tz)]:
            lo, hi = vals.min(), vals.max()
            r = max(hi - lo, 0.1)
            setter(lo - r * pad, hi + r * pad)

        # ── XY top-down ─────────────────────────────────────────────────
        ax_xy.cla()
        ax_xy.set_facecolor(C["panel"])
        ax_xy.set_xlabel("X (m)", color=C["text"], fontsize=8)
        ax_xy.set_ylabel("Y (m)", color=C["text"], fontsize=8)
        ax_xy.set_title("Top View (XY)", color=C["title"], fontsize=10, fontweight="bold")
        ax_xy.grid(True, color=C["grid"], linewidth=0.5, linestyle="--")
        ax_xy.tick_params(colors=C["text"], labelsize=7)

        ax_xy.plot(tx, ty, color=C["trail2d"], linewidth=1.0, alpha=0.7)
        ax_xy.scatter([pos[0]], [pos[1]], color=C["head"], s=50, zorder=5)
        ax_xy.scatter([0], [0], color="#555555", s=25, marker="x")
        ax_xy.set_aspect("equal", adjustable="datalim")

        # ── XZ side view ─────────────────────────────────────────────────
        ax_xz.cla()
        ax_xz.set_facecolor(C["panel"])
        ax_xz.set_xlabel("X (m)", color=C["text"], fontsize=8)
        ax_xz.set_ylabel("Z (m)", color=C["text"], fontsize=8)
        ax_xz.set_title("Side View (XZ)", color=C["title"], fontsize=10, fontweight="bold")
        ax_xz.grid(True, color=C["grid"], linewidth=0.5, linestyle="--")
        ax_xz.tick_params(colors=C["text"], labelsize=7)

        ax_xz.plot(tx, tz, color=C["trail2d"], linewidth=1.0, alpha=0.7)
        ax_xz.scatter([pos[0]], [pos[2]], color=C["head"], s=50, zorder=5)
        ax_xz.scatter([0], [0], color="#555555", s=25, marker="x")
        ax_xz.set_aspect("equal", adjustable="datalim")

        # ── Info readout ─────────────────────────────────────────────────
        speed = np.linalg.norm(vel)
        dist = np.linalg.norm(pos)
        info_text.set_text(
            f"── Acceleration (g) ──\n"
            f"  AX: {raw_a[0]:+8.4f}\n"
            f"  AY: {raw_a[1]:+8.4f}\n"
            f"  AZ: {raw_a[2]:+8.4f}\n"
            f"\n"
            f"── Gyroscope (°/s) ──\n"
            f"  GX: {raw_g[0]:+8.2f}\n"
            f"  GY: {raw_g[1]:+8.2f}\n"
            f"  GZ: {raw_g[2]:+8.2f}\n"
            f"\n"
            f"── Orientation (°) ──\n"
            f"  Roll:  {orient[0]:+8.1f}\n"
            f"  Pitch: {orient[1]:+8.1f}\n"
            f"  Yaw:   {orient[2]:+8.1f}\n"
            f"\n"
            f"── Position (m) ──\n"
            f"  X: {pos[0]:+8.4f}\n"
            f"  Y: {pos[1]:+8.4f}\n"
            f"  Z: {pos[2]:+8.4f}\n"
            f"\n"
            f"  Distance: {dist:.4f} m\n"
            f"  Speed:    {speed:.4f} m/s\n"
            f"  Temp:     {temp:.1f} °C\n"
            f"\n"
            f"  Samples:  {n}\n"
            f"\n"
            f"  [Type 'r' + Enter to reset]"
        )

        status_txt.set_text(tracer.status)

    ani = FuncAnimation(fig, update, interval=50, blit=False, cache_frame_data=False)
    plt.show()


if __name__ == "__main__":
    main()
