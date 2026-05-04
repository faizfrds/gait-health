"""Load gait data files and resample to a uniform sample rate."""

from pathlib import Path

import numpy as np
import pandas as pd

LABELS = ("healthy", "shuffling", "fog")
AXES = ("ax", "ay", "az", "gx", "gy", "gz")
TARGET_FS = 100  # Hz


def label_from_path(path: Path) -> str:
    stem = Path(path).stem
    for label in LABELS:
        if stem.startswith(label + "_"):
            return label
    raise ValueError(f"Cannot infer label from filename: {path}")


def load_raw(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, comment="#")


def resample_uniform(df: pd.DataFrame, fs: int = TARGET_FS) -> pd.DataFrame:
    t = df["timestamp"].to_numpy()
    duration = t[-1] - t[0]
    n = int(np.floor(duration * fs))
    new_t = t[0] + np.arange(n) / fs
    out = {"timestamp": new_t}
    for col in AXES:
        out[col] = np.interp(new_t, t, df[col].to_numpy())
    return pd.DataFrame(out)


def load_file(path: Path, fs: int = TARGET_FS) -> pd.DataFrame:
    return resample_uniform(load_raw(path), fs=fs)


def iter_dataset(dataset_dir: Path):
    """Yield (path, dataframe, label) for every labeled file in dataset_dir."""
    dataset_dir = Path(dataset_dir)
    paths = []
    for label in LABELS:
        paths.extend(sorted(dataset_dir.glob(f"{label}_*.txt")))
    for path in paths:
        yield path, load_file(path), label_from_path(path)
