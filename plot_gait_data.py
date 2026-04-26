#!/usr/bin/env python3
"""
Visualization script for gait analysis IMU data.

Plots acceleration and gyroscopic data over time from fog walking samples.

Usage:
    python plot_gait_data.py                    # Plot all fog samples
    python plot_gait_data.py --sample 1         # Plot specific sample (1-indexed)
    python plot_gait_data.py --sample 1 --save  # Save plot to file
"""

import argparse
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import numpy as np


def load_gait_data(filepath):
    """Load gait data from CSV file."""
    return pd.read_csv(filepath, comment="#")


def plot_single_sample(df, sample_num=None, save=False):
    """Plot acceleration and gyro data for a single sample."""
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    fig.suptitle(f"Gait Analysis - fog Walking (Sample {sample_num})", fontsize=14, fontweight="bold")

    time = df["timestamp"].values

    # Acceleration plots (X, Y, Z)
    axes[0, 0].plot(time, df["ax"], label="AX", color="tab:red", linewidth=1.5)
    axes[0, 0].set_title("Acceleration X-axis")
    axes[0, 0].set_ylabel("Acceleration (g)")
    axes[0, 0].grid(True, alpha=0.3)
    axes[0, 0].legend()

    axes[0, 1].plot(time, df["ay"], label="AY", color="tab:green", linewidth=1.5)
    axes[0, 1].set_title("Acceleration Y-axis")
    axes[0, 1].set_ylabel("Acceleration (g)")
    axes[0, 1].grid(True, alpha=0.3)
    axes[0, 1].legend()

    axes[0, 2].plot(time, df["az"], label="AZ", color="tab:blue", linewidth=1.5)
    axes[0, 2].set_title("Acceleration Z-axis")
    axes[0, 2].set_ylabel("Acceleration (g)")
    axes[0, 2].grid(True, alpha=0.3)
    axes[0, 2].legend()

    # Gyroscope plots (X, Y, Z)
    axes[1, 0].plot(time, df["gx"], label="GX", color="tab:red", linewidth=1.5)
    axes[1, 0].set_title("Gyroscope X-axis")
    axes[1, 0].set_xlabel("Time (s)")
    axes[1, 0].set_ylabel("Angular Velocity (deg/s)")
    axes[1, 0].grid(True, alpha=0.3)
    axes[1, 0].legend()

    axes[1, 1].plot(time, df["gy"], label="GY", color="tab:green", linewidth=1.5)
    axes[1, 1].set_title("Gyroscope Y-axis")
    axes[1, 1].set_xlabel("Time (s)")
    axes[1, 1].set_ylabel("Angular Velocity (deg/s)")
    axes[1, 1].grid(True, alpha=0.3)
    axes[1, 1].legend()

    axes[1, 2].plot(time, df["gz"], label="GZ", color="tab:blue", linewidth=1.5)
    axes[1, 2].set_title("Gyroscope Z-axis")
    axes[1, 2].set_xlabel("Time (s)")
    axes[1, 2].set_ylabel("Angular Velocity (deg/s)")
    axes[1, 2].grid(True, alpha=0.3)
    axes[1, 2].legend()

    plt.tight_layout()

    if save:
        filename = f"fog_sample_{sample_num:02d}_plot.png"
        plt.savefig(filename, dpi=150, bbox_inches="tight")
        print(f"Plot saved to: {filename}")
    else:
        plt.show()


def plot_all_samples_overlay(dataset_dir, save=False):
    """Plot all fog samples overlaid for comparison."""
    dataset_path = Path(dataset_dir)
    fog_files = sorted(dataset_path.glob("fog_*.txt"))

    if not fog_files:
        print(f"No fog_*.txt files found in {dataset_path}")
        return

    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    fig.suptitle(f"Gait Analysis - All fog Samples Overlay (n={len(fog_files)})",
                 fontsize=14, fontweight="bold")

    # Plot all samples with transparency
    for filepath in fog_files:
        df = load_gait_data(filepath)
        time = df["timestamp"].values
        alpha = 0.3

        axes[0, 0].plot(time, df["ax"], color="tab:red", alpha=alpha, linewidth=0.8)
        axes[0, 1].plot(time, df["ay"], color="tab:green", alpha=alpha, linewidth=0.8)
        axes[0, 2].plot(time, df["az"], color="tab:blue", alpha=alpha, linewidth=0.8)
        axes[1, 0].plot(time, df["gx"], color="tab:red", alpha=alpha, linewidth=0.8)
        axes[1, 1].plot(time, df["gy"], color="tab:green", alpha=alpha, linewidth=0.8)
        axes[1, 2].plot(time, df["gz"], color="tab:blue", alpha=alpha, linewidth=0.8)

    # Labels
    axes[0, 0].set_title("Acceleration X-axis")
    axes[0, 0].set_ylabel("Acceleration (g)")
    axes[0, 0].grid(True, alpha=0.3)

    axes[0, 1].set_title("Acceleration Y-axis")
    axes[0, 1].set_ylabel("Acceleration (g)")
    axes[0, 1].grid(True, alpha=0.3)

    axes[0, 2].set_title("Acceleration Z-axis")
    axes[0, 2].set_ylabel("Acceleration (g)")
    axes[0, 2].grid(True, alpha=0.3)

    axes[1, 0].set_title("Gyroscope X-axis")
    axes[1, 0].set_xlabel("Time (s)")
    axes[1, 0].set_ylabel("Angular Velocity (deg/s)")
    axes[1, 0].grid(True, alpha=0.3)

    axes[1, 1].set_title("Gyroscope Y-axis")
    axes[1, 1].set_xlabel("Time (s)")
    axes[1, 1].set_ylabel("Angular Velocity (deg/s)")
    axes[1, 1].grid(True, alpha=0.3)

    axes[1, 2].set_title("Gyroscope Z-axis")
    axes[1, 2].set_xlabel("Time (s)")
    axes[1, 2].set_ylabel("Angular Velocity (deg/s)")
    axes[1, 2].grid(True, alpha=0.3)

    plt.tight_layout()

    if save:
        filename = "fog_all_samples_overlay.png"
        plt.savefig(filename, dpi=150, bbox_inches="tight")
        print(f"Plot saved to: {filename}")
    else:
        plt.show()


def plot_statistics(dataset_dir, save=False):
    """Plot mean ± std of all fog samples."""
    dataset_path = Path(dataset_dir)
    fog_files = sorted(dataset_path.glob("fog_*.txt"))

    if not fog_files:
        print(f"No fog_*.txt files found in {dataset_path}")
        return

    # Load all samples
    all_data = []
    min_length = float("inf")
    for filepath in fog_files:
        df = load_gait_data(filepath)
        all_data.append(df)
        min_length = min(min_length, len(df))

    # Truncate all to same length for consistent comparison
    all_data = [df.iloc[:min_length] for df in all_data]
    time = all_data[0]["timestamp"].values
    n_samples = len(all_data)

    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    fig.suptitle(f"Gait Analysis - fog Walking Statistics (n={n_samples})",
                 fontsize=14, fontweight="bold")

    # Collect data for each axis
    axes_data = {
        "ax": [df["ax"].values for df in all_data],
        "ay": [df["ay"].values for df in all_data],
        "az": [df["az"].values for df in all_data],
        "gx": [df["gx"].values for df in all_data],
        "gy": [df["gy"].values for df in all_data],
        "gz": [df["gz"].values for df in all_data],
    }

    # Plot mean ± std
    for idx, (axis_name, data_list) in enumerate(axes_data.items()):
        ax_idx = idx // 3
        col_idx = idx % 3
        ax = axes[ax_idx, col_idx]

        # Stack data and compute statistics
        stacked = np.array(data_list)
        mean = np.mean(stacked, axis=0)
        std = np.std(stacked, axis=0)

        ax.plot(time, mean, color="black", linewidth=2, label="Mean")
        ax.fill_between(time, mean - std, mean + std, alpha=0.3, label="± 1 Std Dev")

        if axis_name.startswith("a"):
            ax.set_ylabel("Acceleration (g)")
        else:
            ax.set_ylabel("Angular Velocity (deg/s)")

        if ax_idx == 1:
            ax.set_xlabel("Time (s)")

        ax.grid(True, alpha=0.3)
        ax.legend()
        ax.set_title(f"{axis_name.upper()} - Mean ± Std")

    plt.tight_layout()

    if save:
        filename = "fog_statistics_plot.png"
        plt.savefig(filename, dpi=150, bbox_inches="tight")
        print(f"Plot saved to: {filename}")
    else:
        plt.show()


def main():
    parser = argparse.ArgumentParser(description="Plot gait analysis IMU data")
    parser.add_argument("--dataset", default="dataset", help="Dataset directory (default: dataset)")
    parser.add_argument("--sample", type=int, default=None, help="Plot specific fog sample (1-indexed)")
    parser.add_argument("--all", action="store_true", help="Plot all fog samples overlaid")
    parser.add_argument("--stats", action="store_true", help="Plot mean ± std of all fog samples")
    parser.add_argument("--save", action="store_true", help="Save plots to files instead of displaying")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"Error: Dataset directory '{args.dataset}' not found")
        return

    if args.sample:
        filepath = dataset_path / f"fog_{args.sample:02d}.txt"
        if not filepath.exists():
            print(f"Error: File not found: {filepath}")
            return
        df = load_gait_data(filepath)
        plot_single_sample(df, sample_num=args.sample, save=args.save)
    elif args.stats:
        plot_statistics(args.dataset, save=args.save)
    else:
        # Default: plot all samples overlay
        plot_all_samples_overlay(args.dataset, save=args.save)


if __name__ == "__main__":
    main()
