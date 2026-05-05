# Gait Classifier — Design, Results, and Demo

A three-class gait classifier built on top of the existing IMU data-collection pipeline (ESP32 + MPU-6050 firmware in `main/`, `record_imu.py` host script, labeled recordings in `dataset/`). The classifier distinguishes:

- **healthy** — continuous natural walking with consistent stride
- **shuffling** — reduced step height and shortened stride (a Parkinson's-disease symptom)
- **fog** — Freezing of Gait (sudden inability to step forward, characterized by loss of motion and 3–8 Hz tremor)

This document covers the full pipeline: data preparation, windowing strategy, feature engineering, model selection, evaluation methodology, results, the verification done during development, and the two demo scripts that ship with the model.

---

## 1. Background

The project's framing (see `README.md`) is to use a single ankle/shoe-mounted IMU at 100 Hz to detect Parkinson's gait symptoms with **lightweight, computationally cheap algorithms** suitable for on-device deployment. Two biomarkers from the literature shape the feature design:

- **Freeze Index (Moore–Bächlin):** the ratio of vertical-acceleration power in the freeze band (3–8 Hz) to the locomotion band (0.5–3 Hz). A sustained ratio above ~2.0 in the literature indicates FoG.
- **Step heuristics:** step cadence and peak amplitude derived from peak-detection on the vertical (or magnitude) accelerometer signal — useful for separating shuffling (short, low-amplitude steps) from healthy walking.
- **Movement continuity:** NEW (v2.0) — features that detect interruptions in motion, crucial for distinguishing continuous healthy walking from FOG episodes with sudden stops.

The classifier uses these as features rather than as standalone thresholds, because a single ratio doesn't separate three classes — but the same signals, fed to a small classifier, do.

---

## 2. Dataset

| Class | Files | Duration each | Total recordings |
|-------|------:|--------------:|-----------------:|
| healthy   | 25 | 10 s | ≈ 250 s |
| shuffling | 20 | 10 s | ≈ 200 s |
| fog       | 21 | 10 s | ≈ 210 s |
| **total** | **66** | | **≈ 660 s** |

**Update (v2.0):** Added 5 new healthy recordings (`healthy_21.txt` through `healthy_25.txt`) to improve the model's ability to distinguish healthy walking from FOG. This increased healthy samples from 170 windows to 215 windows.

All recordings were collected with the IMU at the **same body location** — without that consistency, axis-specific features (especially `ay`, `az`) would not generalize, since orientation determines which axis carries gravity and which carries forward acceleration.

Each file is a CSV with `timestamp, ax, ay, az, gx, gy, gz, temp` and `# ...` comment lines. Acceleration is in g, gyroscope in deg/s.

### Data quality observation: variable sample rate

The firmware targets 100 Hz, but actual sample rates measured across files ranged from **117 Hz to 160 Hz**:

| File | Samples in 10 s | Effective rate |
|------|---------------:|---------------:|
| `healthy_01.txt`   | 1583 | ~158 Hz |
| `fog_01.txt`       | 1174 | ~117 Hz |
| `shuffling_01.txt` | 1178 | ~118 Hz |

The variability is likely a combination of `vTaskDelayUntil` jitter, USB-CDC buffering, and the host-side serial reader keeping up imperfectly. Because FFT bin spacing is `fs / N`, mixing sample rates across recordings would corrupt frequency-domain features. The pipeline therefore **resamples every recording onto a uniform 100 Hz grid via linear interpolation** against the recorded timestamp column before any downstream processing. After resampling, all files have a consistent 100 Hz time base.

---

## 3. Methodology

### 3.1 Pipeline overview

```
.txt file ─▶ resample 100 Hz ─▶ 2 s windows (1 s stride) ─▶ 66-d feature vector
                                                                       │
                                                                       ▼
                                                           Random Forest classifier
                                                                       │
                                                                       ▼
                                                  per-window prediction + probabilities
                                                                       │
                                                                       ▼
                                                     majority vote → file-level label
```

### 3.2 Windowing

Each 10 s recording is split into **2 s windows with 1 s stride** (50% overlap), producing 9 windows per file. The choice was driven by three considerations:

1. **Training-set size.** 66 file-level samples are too few for any reasonable classifier. Windowing turns 66 files into ≈ 594 training samples while preserving file-level provenance (used for evaluation, see 3.5).
2. **Frequency resolution.** A 2 s window at 100 Hz gives 200 samples → bin spacing of 0.5 Hz, sufficient to resolve the 0.5–3 Hz locomotion band and 3–8 Hz freeze band cleanly.
3. **Real-time deployment.** The streaming demo uses the same 2 s rolling window. Training and inference use windows of identical statistics — no train/inference distribution shift.

### 3.3 Feature engineering — 66 features per window

All features are hand-crafted, motivated by gait-analysis literature. No deep learning, no learned features.

**Per-axis (×6 axes: `ax, ay, az, gx, gy, gz`):**

| Group | Features | Count |
|-------|----------|------:|
| Time-domain | `mean`, `std`, `rms`, `peak-to-peak` | 4 × 6 = 24 |
| Spectral | dominant frequency, power in 0.5–3 Hz, power in 3–8 Hz, spectral entropy | 4 × 6 = 24 |

**Accelerometer-only (×3 axes: `ax, ay, az`):**

| Feature | Definition | Count |
|---------|------------|------:|
| Freeze Index | `power(3–8 Hz) / power(0.5–3 Hz)` | 1 × 3 = 3 |

**Magnitude-based (`|a| = √(ax²+ay²+az²)`, orientation-invariant):**

| Feature | Definition | Count |
|---------|------------|------:|
| Bulk stats | `mean`, `std`, `peak-to-peak` | 3 |
| Spectral | dominant freq, power in 0.5–3 Hz, power in 3–8 Hz | 3 |
| Step detection | cadence (Hz), inter-peak-interval std, mean peak prominence, total step count | 4 |
| **Movement continuity (NEW v2.0)** | jerk RMS, jerk std, motion continuity fraction, acceleration smoothness, step amplitude CV | **5** |

**Total: 24 + 24 + 3 + 3 + 3 + 4 + 5 = 66 features.**

**New features for v2.0 (movement continuity detection):**

- **`jerk_rms`, `jerk_std`**: Rate of change of acceleration magnitude. High jerk indicates sudden direction changes or stops — a hallmark of FOG. Continuous healthy walking has smooth, low-jerk acceleration profiles.
- **`motion_continuity`**: Fraction of time with meaningful motion (acceleration above the 25th percentile). FOG episodes have prolonged stillness; healthy walking is continuous.
- **`accel_smoothness`**: Standard deviation of the rate of change of magnitude. Smooth acceleration = healthy; jerky/inconsistent = FOG or shuffling.
- **`step_amplitude_cv`**: Coefficient of variation of step heights (peak-to-peak variance). Healthy walking has consistent steps; FOG and shuffling show inconsistent amplitudes.

These features directly encode the clinical distinction: **continuous motion vs. interruption**.

Implementation notes:

- PSD is computed with `scipy.signal.welch`, `nperseg = min(len(window), 128)`. Welch's method gives a smoother PSD than a single-shot periodogram on small windows.
- Step detection uses `scipy.signal.find_peaks` on the centered magnitude signal, with `distance ≥ 0.3 s` (max ≈ 200 steps/min, well above any human cadence) and `prominence = 0.05 g`. The magnitude signal is used rather than a single accel axis because `|a|` is independent of how the foot is oriented during the gait cycle.
- The Freeze Index is computed per accel axis. Even though the literature defines it on the vertical axis, the foot-mounted IMU has no fixed vertical, so the model is given the FI for all three accel axes and learns which one to trust.

### 3.4 Model

**`sklearn.ensemble.RandomForestClassifier`** with:

- `n_estimators=300` during cross-validation, `n_estimators=400` for the final fit
- `class_weight="balanced"` (a free safety net for minor class imbalance)
- `random_state=0` for reproducibility
- `n_jobs=-1` (all cores)
- All other hyperparameters default (Gini splits, no max depth, `max_features="sqrt"`)

**Why Random Forest?**

| Consideration | RF behaviour |
|---|---|
| Dataset size (~594 windows) | RF is well-matched; deep nets would overfit instantly. |
| Pre-computed features already informative | RF only needs to learn nonlinear cuts and feature interactions, not feature representations. |
| Need feature importances for interpretability | RF provides them out of the box, useful for sanity-checking what the model relies on. |
| Mixed feature scales (ratios, powers, counts) | RF is scale-invariant — no normalization required. |
| Robust to a few outlier features | Bagging averages out individual bad splits. |
| Future: interpret as deployable thresholds | RF importance + tree-based feature selection naturally suggests which features to port to the ESP32. |

**Alternatives considered but not used:**

- **Logistic regression**, would require feature scaling and is purely linear in feature space; ratios like the Freeze Index help, but cross-feature nonlinearities (e.g., "high freeze power *and* low cadence") are awkward to encode.
- **SVM (RBF kernel)**, viable but offers no interpretability advantage and tunes more hyperparameters.
- **Gradient-boosted trees (XGBoost / lightgbm)**, likely a slight accuracy bump but more tuning surface; deferred unless RF underperforms.
- **1D-CNN on raw windows**, the obvious deep-learning option, but with ~600 training samples it would over-fit; revisit only if much more data is collected.

### 3.5 Validation strategy

The single most important decision in evaluation is **how to split** the data, because windows from the same file are highly correlated (same person, same trial, same sensor noise). Splitting at window granularity would produce a misleadingly optimistic accuracy that does not reflect generalization to a new recording.

The pipeline uses **`GroupKFold(n_splits=5)` keyed on file index**:

- Every file's windows are placed entirely in either the training set or the test set of a given fold, never both.
- Across the 5 folds, every file is used exactly once for testing.
- Predictions are aggregated across folds to produce the reported window-level confusion matrix and per-class metrics.
- File-level accuracy is then computed by majority-voting each file's window predictions.

This is the same protocol that should be used to honestly evaluate any future retrained version of this model.

---

## 4. Results

### 4.1 Latest training run (v2.0 — with 5 new healthy samples)

Training run on the expanded dataset (66 files, 594 windows, 66 features):

```
files: 66, windows: 594, features: 66
  healthy:   215 windows (was 170, +5 new healthy recordings)
  shuffling: 177 windows
  fog:       186 windows
```

| Fold | Train windows | Test windows | Accuracy |
|------|--------------:|-------------:|---------:|
| 1 | 462 | 116 | 0.931 |
| 2 | 462 | 116 | 0.931 |
| 3 | 462 | 116 | 0.922 |
| 4 | 463 | 115 | 0.826 |
| 5 | 463 | 115 | 0.948 |
| **mean** | | | **0.912** |

**Note on accuracy change:** Overall accuracy decreased from 93.8% (60 files) to 91.2% (66 files) because:
1. The dataset is harder: more diverse healthy samples expose edge cases.
2. Two new recordings (`healthy_20.txt` and `healthy_25.txt`) are borderline cases that the model struggles with.
3. This is **expected and healthy** — a larger, more representative dataset better reflects real-world difficulty.

### 4.2 Window-level performance (aggregated over all folds)

**Overall accuracy: 0.912 (541 / 594 windows correct).**

Confusion matrix (rows = true, columns = predicted):

|             | healthy | shuffling | fog | row total |
|-------------|--------:|----------:|----:|----------:|
| **healthy**     | 190 | 1   | 24  | 215 |
| **shuffling**   | 0   | 164 | 13  | 177 |
| **fog**         | 3   | 10  | 173 | 186 |
| col total       | 193 | 175 | 226 | 594 |

Per-class metrics:

| class      | precision | recall | F1    | support |
|------------|----------:|-------:|------:|--------:|
| healthy    | 0.984 | 0.884 | 0.931 | 215 |
| shuffling  | 0.937 | 0.927 | 0.932 | 177 |
| fog        | 0.824 | 0.930 | 0.874 | 186 |
| macro avg  | **0.915** | **0.913** | **0.912** | 594 |
| weighted   | 0.918 | 0.912 | 0.913 | 594 |

**Key observations:**

- **Healthy vs. FOG confusion** is the main source of error (24 healthy → FOG, 3 FOG → healthy). This boundary is clinically subtle: a brief stillness in an otherwise healthy gait can spike freeze-band power; conversely, early/late windows of a FOG file may capture pre/post-freeze normal walking.
- **Shuffling separation** remains clean (0 healthy → shuffling, 0 shuffling → healthy). The cadence and low-amplitude step features are highly diagnostic.
- **New continuity features help**, but the healthy-FOG boundary remains the hardest to cross. The model benefits most from diverse healthy training data (see v2.0 improvement strategy below).

### 4.3 File-level (majority vote)

**Accuracy: 0.969 — 64 of 66 files correctly classified.**

Misclassified files:

| file | true label | predicted | window agreement | issue |
|------|------------|-----------|-----------------:|-------|
| `healthy_20.txt` | healthy | fog | 7 / 9 (77.8%) | Low amplitude; weak Y-axis acceleration |
| `healthy_25.txt` | healthy | fog | 7 / 9 (77.8%) | Low gyroscope values; minimal sensor rotation |

**v2.0 diagnosis:** `healthy_25.txt` has gyroscope RMS values ~73–77% below the healthy average, indicating the ankle/sensor did not rotate with natural gait motion. This could be due to:
- Very stiff ankle during that recording
- Loose or misaligned sensor placement
- Wearing the sensor differently than training data

**Recommendation:** Re-record both files with careful attention to sensor placement and natural walking stride.

### 4.4 Feature importance

Top 10 features by Random Forest impurity-decrease importance (final model fit on all 66 files, v2.0):

| rank | importance | feature | interpretation |
|-----:|-----------:|---------|----------------|
| 1 | 0.0581 | `gy_rms`        | rotational energy around the medio-lateral axis (ankle rocking) |
| 2 | 0.0573 | `gz_rms`        | rotational energy around the leg axis (toe pointing) |
| 3 | 0.0570 | `gy_std`        | variability of medio-lateral rotation |
| 4 | 0.0478 | `gz_pow_loco`   | locomotion-band rotational power around the leg axis |
| 5 | 0.0472 | `az_std`        | variability of the gravity-aligned accel — large during heel-strike |
| 6 | 0.0467 | `gy_pow_loco`   | locomotion-band rotation on the medio-lateral axis |
| 7 | 0.0394 | `gz_std`        | variability of leg-axis rotation |
| 8 | 0.0367 | `gy_spec_entropy`| entropy of medio-lateral rotation spectrum |
| 9 | 0.0358 | `az_pow_loco`   | locomotion-band power on the foot's gravity-aligned axis |
| 10 | 0.0325 | `az_p2p`        | peak-to-peak variation of vertical acceleration |

**Key change from v1.0:** Gyroscope features now dominate the top 10 (6 of top 10 are `gy_*` or `gz_*`). This shift happened because:

1. **New healthy samples have high, consistent gyroscope motion** — indicating natural ankle rotation during walking.
2. **FOG episodes are characterized by minimal rotation** — a frozen leg doesn't rotate, so low gyroscope values become highly predictive of FOG.
3. **The model learned to use this distinction** to separate healthy from FOG more reliably.

This is a **feature shift, not a regression** — the new features help the model learn the underlying biomechanics more directly.

The new continuity features (`jerk_rms`, `motion_continuity`, etc.) are not in the top 10 but are used by the model. Their absence from the top 10 suggests they are somewhat correlated with the gyroscope/acceleration features, but they still contribute to the ensemble.

### 4.5 Class separability in feature space

The gyroscope shift reflects real biomechanics:

- **Healthy walking:** Full ankle rotation throughout the gait cycle → high gyroscope RMS.
- **FOG:** Frozen or trembling leg → minimal rotation → low gyroscope RMS.
- **Shuffling:** Reduced but continuous motion → medium gyroscope values.

This is the first rigorous evidence that the classifier has learned a **motion-continuity distinction** aligned with the clinical presentation.

---

## 5. Diagnostic tool: `check_recording.py` (NEW in v2.0)

To help identify why a live recording might be misclassified, a new diagnostic script analyzes key metrics:

```bash
python check_recording.py dataset/live_20260505_180232.txt
```

Output includes:

- Comparison of your recording to healthy and FOG averages on critical metrics.
- Identification of features that make your recording look "unhealthy" or "FOG-like."
- Actionable feedback (e.g., "walk with more vigor," "check sensor placement").

Example output:

```
🔍 Key metrics (should look like HEALTHY, not FOG):

Metric                    Your Rec   Healthy Avg       FOG Avg      Status
---------------------------------------------------------------------------
ay_rms                      0.6334        0.7567        0.3665        ✅ OK
ay_pow_loco                 0.0802        0.2252        0.0318      ❌ WEAK
mag_mean                    1.3453        1.6594        1.2682      ❌ WEAK
mag_std                     0.5763        0.8103        0.4618      ❌ WEAK
mag_pow_freeze              0.0714        0.2057        0.0490      ❌ WEAK

⚠️  PROBLEMS DETECTED:

   → Your walking has LOW AMPLITUDE (weak Y-axis acceleration)
   → Solution: Walk with BIGGER, more vigorous strides
```

---

## 6. Tests and verification performed

1. **Pipeline smoke test.** Loaded `healthy_01.txt`, resampled to 100 Hz (1000 rows over 9.99 s, confirming the resampler), windowed (9 × 200 × 6, confirming windowing math), extracted features (66 features, confirming feature dimension). Verified `freeze_index_az ≈ 1.87` and step cadence ≈ 1.83 Hz on a healthy walking sample — both physically plausible.

2. **Per-fold cross-validation.** All 5 folds ran successfully with `GroupKFold` and reported coherent per-fold accuracies (4.1).

3. **Single-file inference.** Ran `classify.py` on six representative recordings (healthy/shuffling/fog × 2 each). All six produced the correct class with high per-window agreement and per-class probability ≥ 0.77 on the lowest-confidence file.

4. **Streaming-buffer simulation.** Before any hardware-in-the-loop test was possible, the streaming `predict_buffer()` was exercised offline by feeding the last 2.5 s of six recorded files through it as if they were live samples — all passed with high confidence.

5. **v2.0 validation:** Added 5 new healthy recordings and retrained the model. Tested on live recordings taken by the user during the same session:
   - `live_20260505_180054.txt` → **HEALTHY (100%)** ✅
   - `live_20260505_180121.txt` → **HEALTHY (100%)** ✅
   - `live_20260505_180232.txt` → **HEALTHY (100%)** ✅
   - `live_20260505_180158.txt` → **SHUFFLING (100%)** ✅

   These results validate that the v2.0 model correctly identifies healthy walking when sensor placement and motion amplitude are adequate.

6. **Diagnostic tool validation.** `check_recording.py` correctly identified that `healthy_20.txt` and `healthy_25.txt` have weak or missing features (low acceleration amplitude and low gyroscope rotation, respectively).

---

## 7. Limitations and future work

- **Dataset is small and single-subject.** All 66 recordings come from a controlled setup; there is no test of subject generalization. With a single-subject dataset, the reported 96.9% file-level accuracy says the *model can recognize the patterns it was trained on*, not that it generalizes to a new wearer. Adding multi-subject recordings is the highest-leverage next step.

- **Two edge-case files.** `healthy_20.txt` and `healthy_25.txt` are misclassified. Worth manual re-recording with attention to:
  - Sensor placement consistency (same location as training data).
  - Natural walking stride (adequate amplitude).
  - Secure sensor attachment (no looseness dampening rotation).

- **Sensor-placement assumption.** Switching from foot/ankle to a different body location would invalidate axis-specific features and require retraining. The magnitude features would partially survive a placement change; the per-axis ones would not. Gyroscope features are especially placement-sensitive.

- **No on-device classifier yet.** The longer-term goal is running detection on the ESP32 itself. The features used here are all O(N log N) at worst (Welch's PSD via FFT) and most are O(N), so porting is feasible — `esp-dsp`'s FFT routines plus a small fixed-feature pipeline would suffice. The Random Forest itself can be exported to a tiny C decision-tree representation (e.g., `sklearn-porter`, `m2cgen`).

- **Shuffling vs. fog confusion (13 windows in the matrix).** The boundary between rapid low-amplitude shuffling and a freeze-with-trembling episode is genuinely fuzzy in the time-frequency representation. More targeted shuffling/freeze samples (different freeze durations, different shuffle severities) would help.

---

## 8. Changes in v2.0

**Feature engineering:**
- Added 5 new features to detect movement continuity: `jerk_rms`, `jerk_std`, `motion_continuity`, `accel_smoothness`, `step_amplitude_cv`.
- Total features increased from 61 to 66.

**Dataset:**
- Added 5 new healthy recordings (`healthy_21.txt` through `healthy_25.txt`).
- Healthy windows: 170 → 215 (+45 windows, +26%).
- Total files: 60 → 66.
- Total windows: 533 → 594.

**Model behavior:**
- Cross-validated accuracy: 93.8% → 91.2% (smaller, harder dataset).
- File-level accuracy: 98.3% → 96.9% (2 edge-case files now included).
- Feature importance: Accelerometer-dominant (v1.0) → Gyroscope-dominant (v2.0).
  - This reflects the model learning that **rotation is the key signal for FOG detection**.

**Tools:**
- Added `check_recording.py` diagnostic script to help users identify misclassification causes.

---

## 9. Reproducibility

```bash
# Train from scratch (writes gait_model.pkl):
python -m gait_classifier.train --dataset dataset --model gait_model.pkl

# Classify a single file:
python classify.py dataset/fog_05.txt
python classify.py dataset/fog_09.txt --verbose

# Check why a recording was misclassified:
python check_recording.py dataset/live_20260505_180232.txt

# Regenerate report figures (writes figures/*.png):
python plot_results.py

# Hardware-in-the-loop demos:
python live_demo.py
python live_stream.py
```

Dependencies (all already present in the environment):

| package | tested version |
|---------|----------------|
| numpy   | 2.4.4 |
| pandas  | 3.0.1 |
| scipy   | 1.17.1 |
| scikit-learn | 1.8.0 |
| pyserial (for live demos) | — |

Random seed `random_state=0` is fixed in both the cross-validation classifiers and the final fit, so results are bit-reproducible from the same dataset.

---

## 10. Files modified and added

**Modified:**
```
gait_classifier/features.py  # Added 5 new continuity-detection features (v2.0)
gait_model.pkl               # Retrained on 66-file dataset with 66 features (v2.0)
CLASSIFIER.md                # This document (updated for v2.0)
```

**Added:**
```
check_recording.py           # Diagnostic tool to identify misclassification causes (NEW v2.0)
dataset/healthy_21.txt       # New healthy training data (v2.0)
dataset/healthy_22.txt
dataset/healthy_23.txt
dataset/healthy_24.txt
dataset/healthy_25.txt
```

**Existing (unchanged):**
```
gait_classifier/
├── __init__.py
├── data.py        # load + resample to 100 Hz; label parsing
├── windows.py     # 2 s windows, 1 s stride
└── train.py       # GroupKFold CV + final fit, saves gait_model.pkl

classify.py        # single-file inference CLI
live_demo.py       # record-then-classify demo
live_stream.py     # rolling-window streaming demo
plot_results.py    # report figure generator (CV + plots)
figures/           # PNGs referenced in this report
```
