#!/usr/bin/env python3
"""Generate figures for the gait classifier report.

Outputs to figures/ :
    - confusion_matrix.png
    - per_fold_accuracy.png
    - feature_importances.png
    - feature_distributions.png
    - feature_pca.png

Usage:
    python plot_results.py
"""

import pickle
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

from gait_classifier.data import LABELS
from gait_classifier.train import build_dataset

FIGURES_DIR = Path("figures")
DATASET = Path("dataset")
MODEL_PATH = Path("gait_model.pkl")
LABEL_LIST = list(LABELS)
LABEL_COLORS = {"healthy": "#2ca02c", "shuffling": "#ff7f0e", "fog": "#d62728"}


def plot_confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray) -> None:
    cm = confusion_matrix(y_true, y_pred, labels=LABEL_LIST)
    cm_norm = cm.astype(float) / cm.sum(axis=1, keepdims=True)

    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    im = ax.imshow(cm_norm, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(3))
    ax.set_yticks(range(3))
    ax.set_xticklabels(LABEL_LIST)
    ax.set_yticklabels(LABEL_LIST)
    ax.set_xlabel("predicted")
    ax.set_ylabel("true")
    ax.set_title(
        f"Window-level confusion matrix (GroupKFold CV)\n"
        f"overall accuracy = {(y_true == y_pred).mean():.3f}"
    )
    for i in range(3):
        for j in range(3):
            color = "white" if cm_norm[i, j] > 0.5 else "black"
            ax.text(
                j, i, f"{cm[i, j]}\n({cm_norm[i, j]:.1%})",
                ha="center", va="center", color=color, fontsize=11,
            )
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="row-normalized")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "confusion_matrix.png", dpi=150)
    plt.close(fig)


def plot_per_fold_accuracy(fold_accs: list[float]) -> None:
    folds = np.arange(1, len(fold_accs) + 1)
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(folds, fold_accs, color="steelblue", edgecolor="black")
    mean_acc = float(np.mean(fold_accs))
    ax.axhline(mean_acc, color="red", linestyle="--", label=f"mean = {mean_acc:.3f}")
    ax.set_ylim([0.8, 1.0])
    ax.set_xlabel("fold")
    ax.set_ylabel("test accuracy")
    ax.set_title("Per-fold cross-validation accuracy (GroupKFold by file)")
    ax.set_xticks(folds)
    for b, acc in zip(bars, fold_accs):
        ax.text(
            b.get_x() + b.get_width() / 2, acc + 0.005,
            f"{acc:.3f}", ha="center", va="bottom",
        )
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "per_fold_accuracy.png", dpi=150)
    plt.close(fig)


def plot_feature_importances(model, feat_names: list[str], n: int = 15) -> None:
    pairs = sorted(
        zip(feat_names, model.feature_importances_),
        key=lambda kv: kv[1], reverse=True,
    )[:n]
    names = [name for name, _ in pairs][::-1]
    values = [v for _, v in pairs][::-1]
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(names, values, color="steelblue", edgecolor="black")
    ax.set_xlabel("Random Forest impurity-decrease importance")
    ax.set_title(f"Top {n} features by importance")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "feature_importances.png", dpi=150)
    plt.close(fig)


def plot_feature_distributions(
    X: np.ndarray, y: np.ndarray, feat_names: list[str]
) -> None:
    keys = ["az_freeze_index", "step_cadence_hz", "ay_pow_loco", "mag_pow_freeze"]
    titles = [
        "Freeze Index (az axis)\nbiomarker for FoG",
        "Step cadence (Hz)\nbiomarker for shuffling",
        "Locomotion-band power, ay\n(stride strength)",
        "Freeze-band power, |a|\n(orientation-invariant)",
    ]
    df = pd.DataFrame(X, columns=feat_names)
    df["label"] = y

    fig, axes = plt.subplots(1, len(keys), figsize=(16, 4.5))
    for ax, key, title in zip(axes, keys, titles):
        data = [df.loc[df["label"] == lab, key].to_numpy() for lab in LABEL_LIST]
        bp = ax.boxplot(data, patch_artist=True, showfliers=True)
        for patch, lab in zip(bp["boxes"], LABEL_LIST):
            patch.set_facecolor(LABEL_COLORS[lab])
            patch.set_alpha(0.65)
        for med in bp["medians"]:
            med.set_color("black")
        ax.set_xticks(range(1, len(LABEL_LIST) + 1))
        ax.set_xticklabels(LABEL_LIST)
        ax.set_title(title, fontsize=10)
        ax.grid(axis="y", alpha=0.3)
    fig.suptitle("Feature distributions per class (window-level)", fontsize=12)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "feature_distributions.png", dpi=150)
    plt.close(fig)


def plot_pca(X: np.ndarray, y: np.ndarray) -> None:
    X_s = StandardScaler().fit_transform(X)
    pca = PCA(n_components=2, random_state=0)
    X_p = pca.fit_transform(X_s)
    fig, ax = plt.subplots(figsize=(7, 6))
    for lab in LABEL_LIST:
        mask = y == lab
        ax.scatter(
            X_p[mask, 0], X_p[mask, 1],
            label=f"{lab} (n={mask.sum()})",
            c=LABEL_COLORS[lab], alpha=0.65,
            edgecolor="black", linewidth=0.3, s=30,
        )
    ax.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]:.1%} variance)")
    ax.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]:.1%} variance)")
    ax.set_title(
        "PCA of 61-feature space, colored by class\n"
        f"(cumulative variance explained: "
        f"{pca.explained_variance_ratio_.sum():.1%})"
    )
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "feature_pca.png", dpi=150)
    plt.close(fig)


def main() -> None:
    FIGURES_DIR.mkdir(exist_ok=True)

    print("loading dataset and extracting features...")
    X, y, groups, sources, feat_names = build_dataset(DATASET)
    print(f"  {X.shape[0]} windows, {X.shape[1]} features")

    print("running 5-fold GroupKFold CV...")
    fold_accs: list[float] = []
    y_true_all: list[np.ndarray] = []
    y_pred_all: list[np.ndarray] = []
    gkf = GroupKFold(n_splits=5)
    for fold, (train_idx, test_idx) in enumerate(gkf.split(X, y, groups)):
        clf = RandomForestClassifier(
            n_estimators=300, class_weight="balanced",
            random_state=0, n_jobs=-1,
        )
        clf.fit(X[train_idx], y[train_idx])
        y_pred = clf.predict(X[test_idx])
        acc = float((y_pred == y[test_idx]).mean())
        fold_accs.append(acc)
        y_true_all.append(y[test_idx])
        y_pred_all.append(y_pred)
        print(f"  fold {fold + 1} acc = {acc:.3f}")
    y_true = np.concatenate(y_true_all)
    y_pred = np.concatenate(y_pred_all)

    with MODEL_PATH.open("rb") as f:
        bundle = pickle.load(f)
    model = bundle["model"]

    print("rendering figures...")
    plot_confusion_matrix(y_true, y_pred)
    plot_per_fold_accuracy(fold_accs)
    plot_feature_importances(model, feat_names)
    plot_feature_distributions(X, y, feat_names)
    plot_pca(X, y)

    saved = sorted(FIGURES_DIR.glob("*.png"))
    print(f"saved {len(saved)} figures to {FIGURES_DIR}/")
    for p in saved:
        print(f"  {p}")


if __name__ == "__main__":
    main()
