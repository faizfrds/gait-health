"""Train and evaluate a gait classifier over the labeled dataset.

Usage:
    python -m gait_classifier.train --dataset dataset --model gait_model.pkl
"""

import argparse
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import GroupKFold

from .data import LABELS, iter_dataset
from .features import extract_features, feature_names
from .windows import make_windows


def build_dataset(dataset_dir: Path):
    feat_names = feature_names()
    rows, labels, groups, sources = [], [], [], []
    for file_idx, (path, df, label) in enumerate(iter_dataset(dataset_dir)):
        windows = make_windows(df)
        for w in windows:
            feats = extract_features(w)
            rows.append([feats[name] for name in feat_names])
            labels.append(label)
            groups.append(file_idx)
            sources.append(path.name)
    X = np.asarray(rows, dtype=np.float64)
    y = np.asarray(labels)
    groups = np.asarray(groups)
    return X, y, groups, sources, feat_names


def cross_validate(X, y, groups, n_splits=5, seed=0):
    gkf = GroupKFold(n_splits=n_splits)
    y_true_all, y_pred_all, idx_all = [], [], []
    for fold, (train_idx, test_idx) in enumerate(gkf.split(X, y, groups)):
        clf = RandomForestClassifier(
            n_estimators=300, class_weight="balanced", random_state=seed, n_jobs=-1
        )
        clf.fit(X[train_idx], y[train_idx])
        y_pred = clf.predict(X[test_idx])
        y_true_all.append(y[test_idx])
        y_pred_all.append(y_pred)
        idx_all.append(test_idx)
        print(f"fold {fold + 1}: train={len(train_idx)} test={len(test_idx)} "
              f"acc={(y_pred == y[test_idx]).mean():.3f}")
    return (
        np.concatenate(y_true_all),
        np.concatenate(y_pred_all),
        np.concatenate(idx_all),
    )


def majority_vote_per_file(y_true, y_pred, groups, sources):
    df = pd.DataFrame(
        {"group": groups, "source": sources, "true": y_true, "pred": y_pred}
    )
    rows = []
    for grp, sub in df.groupby("group"):
        vote = sub["pred"].mode().iloc[0]
        rows.append({
            "file": sub["source"].iloc[0],
            "true": sub["true"].iloc[0],
            "predicted": vote,
            "n_windows": len(sub),
            "agreement": (sub["pred"] == vote).mean(),
        })
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="dataset")
    parser.add_argument("--model", default="gait_model.pkl")
    parser.add_argument("--folds", type=int, default=5)
    args = parser.parse_args()

    dataset_dir = Path(args.dataset)
    print(f"loading dataset from {dataset_dir.resolve()}")
    X, y, groups, sources, feat_names = build_dataset(dataset_dir)
    n_files = len(set(groups))
    print(f"  files: {n_files}, windows: {len(X)}, features: {X.shape[1]}")
    for label in LABELS:
        n = (y == label).sum()
        print(f"  {label}: {n} windows")

    print("\nGroupKFold cross-validation (split by file):")
    y_true, y_pred, test_idx = cross_validate(X, y, groups, n_splits=args.folds)

    print("\nWindow-level results:")
    print(f"overall accuracy: {(y_true == y_pred).mean():.3f}")
    print("confusion matrix (rows=true, cols=pred), order:", list(LABELS))
    print(confusion_matrix(y_true, y_pred, labels=list(LABELS)))
    print(classification_report(y_true, y_pred, labels=list(LABELS), digits=3))

    sources_arr = np.asarray(sources)
    file_results = majority_vote_per_file(
        y_true, y_pred, groups[test_idx], sources_arr[test_idx]
    )
    file_acc = (file_results["true"] == file_results["predicted"]).mean()
    print(f"\nFile-level (majority vote) accuracy: {file_acc:.3f}")
    misses = file_results[file_results["true"] != file_results["predicted"]]
    if not misses.empty:
        print("misclassified files:")
        print(misses.to_string(index=False))

    print("\nFitting final model on full data...")
    clf = RandomForestClassifier(
        n_estimators=400, class_weight="balanced", random_state=0, n_jobs=-1
    )
    clf.fit(X, y)
    importances = sorted(
        zip(feat_names, clf.feature_importances_), key=lambda kv: kv[1], reverse=True
    )
    print("top 10 features:")
    for name, imp in importances[:10]:
        print(f"  {imp:.4f}  {name}")

    out = Path(args.model)
    with out.open("wb") as f:
        pickle.dump({"model": clf, "feature_names": feat_names, "labels": list(LABELS)}, f)
    print(f"\nSaved model to {out.resolve()}")


if __name__ == "__main__":
    main()
