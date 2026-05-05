"""Per-window feature extraction for gait classification."""

import numpy as np
from scipy.signal import find_peaks, welch

from .data import AXES, TARGET_FS

ACCEL_AXES = ("ax", "ay", "az")
LOCO_BAND = (0.5, 3.0)
FREEZE_BAND = (3.0, 8.0)


def _psd(x: np.ndarray, fs: int) -> tuple[np.ndarray, np.ndarray]:
    nperseg = min(len(x), 128)
    return welch(x - np.mean(x), fs=fs, nperseg=nperseg)


def _band_power(f: np.ndarray, pxx: np.ndarray, lo: float, hi: float) -> float:
    mask = (f >= lo) & (f < hi)
    if not mask.any():
        return 0.0
    return float(np.trapezoid(pxx[mask], f[mask]))


def _dominant_freq(f: np.ndarray, pxx: np.ndarray) -> float:
    if len(pxx) == 0:
        return 0.0
    return float(f[int(np.argmax(pxx))])


def _spectral_entropy(pxx: np.ndarray) -> float:
    total = pxx.sum()
    if total <= 0:
        return 0.0
    p = pxx / total
    p = p[p > 0]
    return float(-(p * np.log(p)).sum())


def _axis_features(x: np.ndarray, fs: int, name: str) -> dict[str, float]:
    f, pxx = _psd(x, fs)
    feats = {
        f"{name}_mean": float(np.mean(x)),
        f"{name}_std": float(np.std(x)),
        f"{name}_rms": float(np.sqrt(np.mean(x * x))),
        f"{name}_p2p": float(np.ptp(x)),
        f"{name}_dom_freq": _dominant_freq(f, pxx),
        f"{name}_pow_loco": _band_power(f, pxx, *LOCO_BAND),
        f"{name}_pow_freeze": _band_power(f, pxx, *FREEZE_BAND),
        f"{name}_spec_entropy": _spectral_entropy(pxx),
    }
    if name in ACCEL_AXES:
        loco = feats[f"{name}_pow_loco"]
        freeze = feats[f"{name}_pow_freeze"]
        feats[f"{name}_freeze_index"] = freeze / loco if loco > 1e-12 else 0.0
    return feats


def _magnitude_features(window: np.ndarray, fs: int) -> dict[str, float]:
    accel = window[:, :3]
    mag = np.linalg.norm(accel, axis=1)
    mag_centered = mag - np.mean(mag)
    distance = max(int(0.3 * fs), 1)
    peaks, props = find_peaks(mag_centered, distance=distance, prominence=0.05)
    if len(peaks) >= 2:
        intervals = np.diff(peaks) / fs
        cadence = 1.0 / float(np.mean(intervals))
        ipi_std = float(np.std(intervals))
    else:
        cadence = 0.0
        ipi_std = 0.0
    peak_amp = float(np.mean(props["prominences"])) if len(peaks) else 0.0
    f, pxx = _psd(mag, fs)
    
    # NEW: Features for movement continuity vs freezing
    accel_mag = np.linalg.norm(accel, axis=1)
    
    # Jerk: rate of change of acceleration (high = sudden stops)
    jerk = np.diff(accel_mag)
    jerk_rms = float(np.sqrt(np.mean(jerk**2)))
    jerk_std = float(np.std(jerk))
    
    # Movement continuity: fraction of time with meaningful motion
    motion_threshold = np.percentile(accel_mag, 25)
    motion_continuity = float(np.sum(accel_mag > motion_threshold) / len(accel_mag))
    
    # Acceleration smoothness: variance of rate of change
    accel_rate = np.diff(mag)
    accel_smoothness = float(np.std(accel_rate))
    
    # Step amplitude consistency: low CV = healthy, high CV = FOG/shuffling
    if len(props["prominences"]) > 1:
        amp_cv = float(np.std(props["prominences"]) / (np.mean(props["prominences"]) + 1e-10))
    else:
        amp_cv = 0.0
    
    return {
        "mag_mean": float(np.mean(mag)),
        "mag_std": float(np.std(mag)),
        "mag_p2p": float(np.ptp(mag)),
        "mag_dom_freq": _dominant_freq(f, pxx),
        "mag_pow_loco": _band_power(f, pxx, *LOCO_BAND),
        "mag_pow_freeze": _band_power(f, pxx, *FREEZE_BAND),
        "step_cadence_hz": cadence,
        "step_ipi_std": ipi_std,
        "step_peak_amp": peak_amp,
        "step_count": float(len(peaks)),
        "jerk_rms": jerk_rms,
        "jerk_std": jerk_std,
        "motion_continuity": motion_continuity,
        "accel_smoothness": accel_smoothness,
        "step_amplitude_cv": amp_cv,
    }


def extract_features(window: np.ndarray, fs: int = TARGET_FS) -> dict[str, float]:
    """window: shape (win_len, 6) with column order matching data.AXES."""
    feats: dict[str, float] = {}
    for i, name in enumerate(AXES):
        feats.update(_axis_features(window[:, i], fs, name))
    feats.update(_magnitude_features(window, fs))
    return feats


def feature_names(fs: int = TARGET_FS) -> list[str]:
    dummy = np.zeros((int(2 * fs), len(AXES)))
    return list(extract_features(dummy, fs=fs).keys())
