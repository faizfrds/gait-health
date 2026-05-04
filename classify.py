#!/usr/bin/env python3
"""Classify a single gait recording file as healthy / shuffling / fog.

Usage:
    python classify.py dataset/fog_05.txt
    python classify.py dataset/healthy_03.txt --model gait_model.pkl --verbose
"""

import argparse
import pickle
from collections import Counter
from pathlib import Path

import numpy as np

from gait_classifier.data import load_file
from gait_classifier.features import extract_features
from gait_classifier.windows import make_windows


def predict_file(model_path: Path, recording_path: Path, verbose: bool = False):
    with model_path.open("rb") as f:
        bundle = pickle.load(f)
    model = bundle["model"]
    feat_names = bundle["feature_names"]

    df = load_file(recording_path)
    windows = make_windows(df)
    if len(windows) == 0:
        raise ValueError(f"recording too short to window: {recording_path}")

    X = np.array(
        [[extract_features(w)[n] for n in feat_names] for w in windows],
        dtype=np.float64,
    )
    preds = model.predict(X)
    probs = model.predict_proba(X)
    counts = Counter(str(p) for p in preds)
    final, n = counts.most_common(1)[0]
    confidence = n / len(preds)
    avg_proba = dict(zip(model.classes_, probs.mean(axis=0)))

    if verbose:
        print(f"\nWindow-by-window predictions for {recording_path.name}:")
        for i, (p, row) in enumerate(zip(preds, probs)):
            probs_str = " ".join(f"{c}={pp:.2f}" for c, pp in zip(model.classes_, row))
            print(f"  win {i:2d}: {p:10s}  [{probs_str}]")

    return {
        "file": recording_path.name,
        "prediction": final,
        "confidence": confidence,
        "n_windows": len(preds),
        "window_votes": dict(counts),
        "avg_probabilities": avg_proba,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("recording", type=Path)
    parser.add_argument("--model", type=Path, default=Path("gait_model.pkl"))
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    result = predict_file(args.model, args.recording, verbose=args.verbose)
    print(f"\nfile:        {result['file']}")
    print(f"prediction:  {result['prediction']}")
    print(f"confidence:  {result['confidence']:.2f} "
          f"({result['window_votes']} of {result['n_windows']} windows)")
    print("avg per-window probabilities:")
    for label, p in sorted(result["avg_probabilities"].items(), key=lambda kv: -kv[1]):
        print(f"  {label:10s}  {p:.3f}")


if __name__ == "__main__":
    main()
