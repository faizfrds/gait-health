"""Slice a uniformly-sampled gait dataframe into fixed-length windows."""

import numpy as np
import pandas as pd

from .data import AXES, TARGET_FS


def make_windows(
    df: pd.DataFrame,
    fs: int = TARGET_FS,
    win_sec: float = 2.0,
    stride_sec: float = 1.0,
) -> np.ndarray:
    """Return windows as an array of shape (n_windows, win_len, n_axes)."""
    win_len = int(round(win_sec * fs))
    stride = int(round(stride_sec * fs))
    data = df[list(AXES)].to_numpy()
    n = len(data)
    if n < win_len:
        return np.empty((0, win_len, len(AXES)))
    starts = range(0, n - win_len + 1, stride)
    return np.stack([data[s : s + win_len] for s in starts], axis=0)
