#!/usr/bin/env python3
"""
FFT (Frequency Domain) Analysis for gait data.

Computes and plots the Fast Fourier Transform of acceleration and gyroscopic data
to identify characteristic frequencies of different gait patterns.

Usage:
    python plot_fft_analysis.py --sample 1              # FFT of specific sample
    python plot_fft_analysis.py --stats                 # Average FFT across all samples
    python plot_fft_analysis.py --sample 1 --compare    # Compare with stats
"""

import argparse
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import numpy as np
from scipy.signal.windows import hann


def load_gait_data(filepath):
    """Load gait data from CSV file."""
    return pd.read_csv(filepath, comment="#")


def compute_fft(data, sampling_rate=100):
    """
    Compute FFT and return frequencies and power spectrum.

    Args:
        data: 1D array of sensor values
        sampling_rate: Sampling frequency in Hz (default 100Hz for MPU6050)

    Returns:
        frequencies: Array of frequencies (Hz)
        power: Power spectrum (magnitude squared)
    """
    # Remove DC component
    data_centered = data - np.mean(data)

    # Apply Hann window to reduce spectral leakage
    windowed = data_centered * hann(len(data_centered))

    # Compute FFT
    fft_vals = np.fft.fft(windowed)
    power = np.abs(fft_vals) ** 2

    # Get only positive frequencies
    freqs = np.fft.fftfreq(len(data_centered), 1/sampling_rate)
    positive_idx = freqs > 0

    return freqs[positive_idx], power[positive_idx]


def plot_single_sample_fft(filepath, sample_num, save=False):
    """Plot FFT for a single fog sample."""
    df = load_gait_data(filepath)

    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    fig.suptitle(f"FFT Analysis - fog Walking (Sample {sample_num})",
                 fontsize=14, fontweight="bold")

    # Compute FFT for each axis
    freq_ax, power_ax = compute_fft(df["ax"].values)
    freq_ay, power_ay = compute_fft(df["ay"].values)
    freq_az, power_az = compute_fft(df["az"].values)
    freq_gx, power_gx = compute_fft(df["gx"].values)
    freq_gy, power_gy = compute_fft(df["gy"].values)
    freq_gz, power_gz = compute_fft(df["gz"].values)

    # Acceleration plots
    axes[0, 0].semilogy(freq_ax, power_ax, color="tab:red", linewidth=1.5)
    axes[0, 0].set_title("Acceleration X-axis")
    axes[0, 0].set_ylabel("Power (g²)")
    axes[0, 0].grid(True, alpha=0.3, which="both")
    axes[0, 0].set_xlim([0, 20])

    axes[0, 1].semilogy(freq_ay, power_ay, color="tab:green", linewidth=1.5)
    axes[0, 1].set_title("Acceleration Y-axis")
    axes[0, 1].set_ylabel("Power (g²)")
    axes[0, 1].grid(True, alpha=0.3, which="both")
    axes[0, 1].set_xlim([0, 20])

    axes[0, 2].semilogy(freq_az, power_az, color="tab:blue", linewidth=1.5)
    axes[0, 2].set_title("Acceleration Z-axis")
    axes[0, 2].set_ylabel("Power (g²)")
    axes[0, 2].grid(True, alpha=0.3, which="both")
    axes[0, 2].set_xlim([0, 20])

    # Gyroscope plots
    axes[1, 0].semilogy(freq_gx, power_gx, color="tab:red", linewidth=1.5)
    axes[1, 0].set_title("Gyroscope X-axis")
    axes[1, 0].set_xlabel("Frequency (Hz)")
    axes[1, 0].set_ylabel("Power (deg²/s²)")
    axes[1, 0].grid(True, alpha=0.3, which="both")
    axes[1, 0].set_xlim([0, 20])

    axes[1, 1].semilogy(freq_gy, power_gy, color="tab:green", linewidth=1.5)
    axes[1, 1].set_title("Gyroscope Y-axis")
    axes[1, 1].set_xlabel("Frequency (Hz)")
    axes[1, 1].set_ylabel("Power (deg²/s²)")
    axes[1, 1].grid(True, alpha=0.3, which="both")
    axes[1, 1].set_xlim([0, 20])

    axes[1, 2].semilogy(freq_gz, power_gz, color="tab:blue", linewidth=1.5)
    axes[1, 2].set_title("Gyroscope Z-axis")
    axes[1, 2].set_xlabel("Frequency (Hz)")
    axes[1, 2].set_ylabel("Power (deg²/s²)")
    axes[1, 2].grid(True, alpha=0.3, which="both")
    axes[1, 2].set_xlim([0, 20])

    # Add frequency band annotations
    for ax in axes.flat:
        ax.axvspan(0.5, 3, alpha=0.1, color="green", label="Normal walk (0.5-3 Hz)")
        ax.axvspan(3, 10, alpha=0.1, color="red", label="FoG tremor (3-10 Hz)")
        ax.legend(fontsize=8)

    plt.tight_layout()

    if save:
        filename = f"fog_sample_{sample_num:02d}_fft.png"
        plt.savefig(filename, dpi=150, bbox_inches="tight")
        print(f"Plot saved to: {filename}")
    else:
        plt.show()


def plot_average_fft(dataset_dir, save=False):
    """Plot average FFT across all fog samples."""
    dataset_path = Path(dataset_dir)
    fog_files = sorted(dataset_path.glob("fog_*.txt"))

    if not fog_files:
        print(f"No fog_*.txt files found in {dataset_path}")
        return

    # Compute FFT for all samples
    all_power_ax = []
    all_power_ay = []
    all_power_az = []
    all_power_gx = []
    all_power_gy = []
    all_power_gz = []

    for filepath in fog_files:
        df = load_gait_data(filepath)

        freq_ax, power_ax = compute_fft(df["ax"].values)
        freq_ay, power_ay = compute_fft(df["ay"].values)
        freq_az, power_az = compute_fft(df["az"].values)
        freq_gx, power_gx = compute_fft(df["gx"].values)
        freq_gy, power_gy = compute_fft(df["gy"].values)
        freq_gz, power_gz = compute_fft(df["gz"].values)

        all_power_ax.append(power_ax)
        all_power_ay.append(power_ay)
        all_power_az.append(power_az)
        all_power_gx.append(power_gx)
        all_power_gy.append(power_gy)
        all_power_gz.append(power_gz)

    # Compute mean power (truncate to shortest)
    min_len = min(len(p) for p in all_power_ax)
    mean_power_ax = np.mean([p[:min_len] for p in all_power_ax], axis=0)
    mean_power_ay = np.mean([p[:min_len] for p in all_power_ay], axis=0)
    mean_power_az = np.mean([p[:min_len] for p in all_power_az], axis=0)
    mean_power_gx = np.mean([p[:min_len] for p in all_power_gx], axis=0)
    mean_power_gy = np.mean([p[:min_len] for p in all_power_gy], axis=0)
    mean_power_gz = np.mean([p[:min_len] for p in all_power_gz], axis=0)

    freq = freq_ax[:min_len]

    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    fig.suptitle(f"Average FFT Analysis - fog Walking (n={len(fog_files)})",
                 fontsize=14, fontweight="bold")

    # Acceleration plots
    axes[0, 0].semilogy(freq, mean_power_ax, color="tab:red", linewidth=2)
    axes[0, 0].set_title("Acceleration X-axis")
    axes[0, 0].set_ylabel("Power (g²)")
    axes[0, 0].grid(True, alpha=0.3, which="both")
    axes[0, 0].set_xlim([0, 20])

    axes[0, 1].semilogy(freq, mean_power_ay, color="tab:green", linewidth=2)
    axes[0, 1].set_title("Acceleration Y-axis")
    axes[0, 1].set_ylabel("Power (g²)")
    axes[0, 1].grid(True, alpha=0.3, which="both")
    axes[0, 1].set_xlim([0, 20])

    axes[0, 2].semilogy(freq, mean_power_az, color="tab:blue", linewidth=2)
    axes[0, 2].set_title("Acceleration Z-axis")
    axes[0, 2].set_ylabel("Power (g²)")
    axes[0, 2].grid(True, alpha=0.3, which="both")
    axes[0, 2].set_xlim([0, 20])

    # Gyroscope plots
    axes[1, 0].semilogy(freq, mean_power_gx, color="tab:red", linewidth=2)
    axes[1, 0].set_title("Gyroscope X-axis")
    axes[1, 0].set_xlabel("Frequency (Hz)")
    axes[1, 0].set_ylabel("Power (deg²/s²)")
    axes[1, 0].grid(True, alpha=0.3, which="both")
    axes[1, 0].set_xlim([0, 20])

    axes[1, 1].semilogy(freq, mean_power_gy, color="tab:green", linewidth=2)
    axes[1, 1].set_title("Gyroscope Y-axis")
    axes[1, 1].set_xlabel("Frequency (Hz)")
    axes[1, 1].set_ylabel("Power (deg²/s²)")
    axes[1, 1].grid(True, alpha=0.3, which="both")
    axes[1, 1].set_xlim([0, 20])

    axes[1, 2].semilogy(freq, mean_power_gz, color="tab:blue", linewidth=2)
    axes[1, 2].set_title("Gyroscope Z-axis")
    axes[1, 2].set_xlabel("Frequency (Hz)")
    axes[1, 2].set_ylabel("Power (deg²/s²)")
    axes[1, 2].grid(True, alpha=0.3, which="both")
    axes[1, 2].set_xlim([0, 20])

    # Add frequency band annotations
    for ax in axes.flat:
        ax.axvspan(0.5, 3, alpha=0.1, color="green", label="Normal walk (0.5-3 Hz)")
        ax.axvspan(3, 10, alpha=0.1, color="red", label="FoG tremor (3-10 Hz)")
        ax.legend(fontsize=8)

    plt.tight_layout()

    if save:
        filename = "fog_average_fft.png"
        plt.savefig(filename, dpi=150, bbox_inches="tight")
        print(f"Plot saved to: {filename}")
    else:
        plt.show()


def plot_fft_comparison(dataset_dir, sample_num, save=False):
    """Plot single sample FFT compared with average."""
    dataset_path = Path(dataset_dir)
    fog_files = sorted(dataset_path.glob("fog_*.txt"))

    if not fog_files:
        print(f"No fog_*.txt files found in {dataset_path}")
        return

    sample_file = dataset_path / f"fog_{sample_num:02d}.txt"
    if not sample_file.exists():
        print(f"Error: File not found: {sample_file}")
        return

    # Load single sample
    df_sample = load_gait_data(sample_file)

    # Compute average across all samples
    all_power_ax = []
    all_power_ay = []
    all_power_az = []
    all_power_gx = []
    all_power_gy = []
    all_power_gz = []

    for filepath in fog_files:
        df = load_gait_data(filepath)

        _, power_ax = compute_fft(df["ax"].values)
        _, power_ay = compute_fft(df["ay"].values)
        _, power_az = compute_fft(df["az"].values)
        _, power_gx = compute_fft(df["gx"].values)
        _, power_gy = compute_fft(df["gy"].values)
        _, power_gz = compute_fft(df["gz"].values)

        all_power_ax.append(power_ax)
        all_power_ay.append(power_ay)
        all_power_az.append(power_az)
        all_power_gx.append(power_gx)
        all_power_gy.append(power_gy)
        all_power_gz.append(power_gz)

    # Compute mean and sample FFTs
    min_len = min(min(len(p) for p in all_power_ax), len(compute_fft(df_sample["ax"].values)[1]))
    mean_power_ax = np.mean([p[:min_len] for p in all_power_ax], axis=0)
    mean_power_ay = np.mean([p[:min_len] for p in all_power_ay], axis=0)
    mean_power_az = np.mean([p[:min_len] for p in all_power_az], axis=0)
    mean_power_gx = np.mean([p[:min_len] for p in all_power_gx], axis=0)
    mean_power_gy = np.mean([p[:min_len] for p in all_power_gy], axis=0)
    mean_power_gz = np.mean([p[:min_len] for p in all_power_gz], axis=0)

    freq_s, power_s_ax = compute_fft(df_sample["ax"].values)
    _, power_s_ay = compute_fft(df_sample["ay"].values)
    _, power_s_az = compute_fft(df_sample["az"].values)
    _, power_s_gx = compute_fft(df_sample["gx"].values)
    _, power_s_gy = compute_fft(df_sample["gy"].values)
    _, power_s_gz = compute_fft(df_sample["gz"].values)

    freq_s = freq_s[:min_len]
    power_s_ax = power_s_ax[:min_len]
    power_s_ay = power_s_ay[:min_len]
    power_s_az = power_s_az[:min_len]
    power_s_gx = power_s_gx[:min_len]
    power_s_gy = power_s_gy[:min_len]
    power_s_gz = power_s_gz[:min_len]

    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    fig.suptitle(f"FFT Comparison - Sample {sample_num} vs Average (n={len(fog_files)})",
                 fontsize=14, fontweight="bold")

    # Acceleration plots
    axes[0, 0].semilogy(freq_s, power_s_ax, color="tab:red", linewidth=1.5, label=f"Sample {sample_num}", alpha=0.7)
    axes[0, 0].semilogy(freq_s, mean_power_ax, color="darkred", linewidth=2.5, label="Average", linestyle="--")
    axes[0, 0].set_title("Acceleration X-axis")
    axes[0, 0].set_ylabel("Power (g²)")
    axes[0, 0].grid(True, alpha=0.3, which="both")
    axes[0, 0].set_xlim([0, 20])
    axes[0, 0].legend()

    axes[0, 1].semilogy(freq_s, power_s_ay, color="tab:green", linewidth=1.5, label=f"Sample {sample_num}", alpha=0.7)
    axes[0, 1].semilogy(freq_s, mean_power_ay, color="darkgreen", linewidth=2.5, label="Average", linestyle="--")
    axes[0, 1].set_title("Acceleration Y-axis")
    axes[0, 1].set_ylabel("Power (g²)")
    axes[0, 1].grid(True, alpha=0.3, which="both")
    axes[0, 1].set_xlim([0, 20])
    axes[0, 1].legend()

    axes[0, 2].semilogy(freq_s, power_s_az, color="tab:blue", linewidth=1.5, label=f"Sample {sample_num}", alpha=0.7)
    axes[0, 2].semilogy(freq_s, mean_power_az, color="darkblue", linewidth=2.5, label="Average", linestyle="--")
    axes[0, 2].set_title("Acceleration Z-axis")
    axes[0, 2].set_ylabel("Power (g²)")
    axes[0, 2].grid(True, alpha=0.3, which="both")
    axes[0, 2].set_xlim([0, 20])
    axes[0, 2].legend()

    # Gyroscope plots
    axes[1, 0].semilogy(freq_s, power_s_gx, color="tab:red", linewidth=1.5, label=f"Sample {sample_num}", alpha=0.7)
    axes[1, 0].semilogy(freq_s, mean_power_gx, color="darkred", linewidth=2.5, label="Average", linestyle="--")
    axes[1, 0].set_title("Gyroscope X-axis")
    axes[1, 0].set_xlabel("Frequency (Hz)")
    axes[1, 0].set_ylabel("Power (deg²/s²)")
    axes[1, 0].grid(True, alpha=0.3, which="both")
    axes[1, 0].set_xlim([0, 20])
    axes[1, 0].legend()

    axes[1, 1].semilogy(freq_s, power_s_gy, color="tab:green", linewidth=1.5, label=f"Sample {sample_num}", alpha=0.7)
    axes[1, 1].semilogy(freq_s, mean_power_gy, color="darkgreen", linewidth=2.5, label="Average", linestyle="--")
    axes[1, 1].set_title("Gyroscope Y-axis")
    axes[1, 1].set_xlabel("Frequency (Hz)")
    axes[1, 1].set_ylabel("Power (deg²/s²)")
    axes[1, 1].grid(True, alpha=0.3, which="both")
    axes[1, 1].set_xlim([0, 20])
    axes[1, 1].legend()

    axes[1, 2].semilogy(freq_s, power_s_gz, color="tab:blue", linewidth=1.5, label=f"Sample {sample_num}", alpha=0.7)
    axes[1, 2].semilogy(freq_s, mean_power_gz, color="darkblue", linewidth=2.5, label="Average", linestyle="--")
    axes[1, 2].set_title("Gyroscope Z-axis")
    axes[1, 2].set_xlabel("Frequency (Hz)")
    axes[1, 2].set_ylabel("Power (deg²/s²)")
    axes[1, 2].grid(True, alpha=0.3, which="both")
    axes[1, 2].set_xlim([0, 20])
    axes[1, 2].legend()

    # Add frequency band annotations
    for ax in axes.flat:
        ax.axvspan(0.5, 3, alpha=0.1, color="green")
        ax.axvspan(3, 10, alpha=0.1, color="red")

    plt.tight_layout()

    if save:
        filename = f"fog_sample_{sample_num:02d}_vs_average_fft.png"
        plt.savefig(filename, dpi=150, bbox_inches="tight")
        print(f"Plot saved to: {filename}")
    else:
        plt.show()


def main():
    parser = argparse.ArgumentParser(description="FFT analysis of gait data")
    parser.add_argument("--dataset", default="dataset", help="Dataset directory (default: dataset)")
    parser.add_argument("--sample", type=int, default=None, help="Analyze specific fog sample (1-indexed)")
    parser.add_argument("--stats", action="store_true", help="Plot average FFT of all fog samples")
    parser.add_argument("--compare", action="store_true", help="Compare sample FFT with average (requires --sample)")
    parser.add_argument("--save", action="store_true", help="Save plots to files instead of displaying")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"Error: Dataset directory '{args.dataset}' not found")
        return

    if args.sample and args.compare:
        plot_fft_comparison(args.dataset, args.sample, save=args.save)
    elif args.sample:
        sample_file = dataset_path / f"fog_{args.sample:02d}.txt"
        if not sample_file.exists():
            print(f"Error: File not found: {sample_file}")
            return
        plot_single_sample_fft(sample_file, args.sample, save=args.save)
    else:
        # Default: plot average FFT
        plot_average_fft(args.dataset, save=args.save)


if __name__ == "__main__":
    main()
