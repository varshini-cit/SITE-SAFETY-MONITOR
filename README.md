# Site Safety Monitor

**Real-time PPE Compliance Detection for Construction Sites using YOLOv8**

Machine Learning PBL project: detects construction workers on video, checks
whether each worker is wearing the required PPE (helmet/hardhat and safety
vest), and raises a confirmed violation only after it persists for 8
consecutive frames — producing timestamped alerts, snapshots, a JSON log, and
a processed output video.

---

## 1. Project Overview

| Item | Value |
|---|---|
| Dataset | Roboflow "Construction Site Safety" — 2,801 images (2,605 train / 114 valid / 82 test), 10 classes |
| Main PPE focus | helmets/hardhats, safety vests |
| Prototype input | pre-recorded video file (no live camera yet) |
| Inference device | CPU |
| Model | YOLOv8n (nano) trained from `yolov8n.pt` |
| Key tuning rules | ~5% PPE-box overlap association threshold, 8-consecutive-frame persistence — both configurable in `src/config.py` |

## 2. Problem Statement

Construction sites report large numbers of preventable head and torso
injuries every year, and manual supervision of Personal Protective Equipment
(PPE) compliance does not scale. This project automates that check: given a
site video, the system detects each worker, determines whether the required
PPE (helmet and safety vest) is actually worn *by that worker*, and only
raises an alert when a violation persists long enough to rule out flicker or
occlusion noise.

## 3. Architecture / Pipeline

```
VIDEO INPUT
   -> FRAME PREPROCESSING          (frame-by-frame reads via OpenCV)
   -> YOLOv8 DETECTION             (model.predict on each processed frame)
   -> PERSON/PPE ASSOCIATION       (overlap-fraction rule, src/violation_logic.py)
   -> VIOLATION DETECTION          (missing helmet / missing vest per person)
   -> 8-CONSECUTIVE-FRAME PERSISTENCE   (per tracked person, ViolationStateTracker)
   -> CONFIRMED VIOLATION
   -> TIMESTAMPED ALERT            (AlertManager)
   -> SNAPSHOT + JSON LOG          (outputs/snapshots/, outputs/alerts/)
   -> PROCESSED VIDEO              (outputs/videos/)
```

## 4. Folder Structure

```
SITE SAFETY MONITOR/
├── data/
│   ├── raw/                      # <-- put the real Roboflow dataset here
│   ├── processed/                # for any preprocessed/augmented dataset copies
│   └── dataset.example.yaml      # template; copy to data/dataset.yaml
├── models/                       # trained weights (models/ppe_model.pt) go here
├── src/
│   ├── __init__.py
│   ├── config.py                 # ALL tunable values live here
│   ├── train.py                  # opt-in training script (never auto-runs)
│   ├── detect.py                 # video pipeline
│   ├── violation_logic.py        # PPE association + 8-frame persistence
│   ├── tracker.py                # simple centroid tracker (prototype)
│   ├── alert_manager.py          # snapshots + JSON alert log
│   └── utils.py                  # geometry, drawing, timestamps
├── outputs/
│   ├── alerts/                   # violations_log.json
│   ├── snapshots/                # PNG snapshot per confirmed violation
│   └── videos/                   # annotated processed video
├── tests/
│   ├── __init__.py
│   ├── test_violation_logic.py   # persistence + association unit tests
│   └── test_utils.py             # overlap/timestamp unit tests
├── requirements.txt
├── README.md
└── run_detection.py              # beginner-friendly entry point
```

## 5. Python Environment Setup

You already have a `.venv` (Python 3.10). From the project root in PowerShell:

```powershell
.venv\Scripts\activate            # or use the full path as shown below
```

All commands below also work without activation by calling the venv python
directly: `.venv\Scripts\python`.

## 6. Dependency Installation

```powershell
.venv\Scripts\python -m pip install -r requirements.txt
```

This installs `ultralytics` (YOLOv8, which pulls in PyTorch CPU wheels),
`opencv-python`, `numpy`, `pandas`, `matplotlib`, `pytest`, and `PyYAML`.

## 7. Dataset Placement (real dataset required)

This repository does **not** include the dataset and never fabricates one.

1. Download the Roboflow **Construction Site Safety** dataset (2,801 images;
   2,605 train / 114 valid / 82 test; 10 classes) in **YOLOv8** export format.
2. Unpack it under `data/raw/`, e.g.:

```
data/raw/construction-site-safety/
├── train/   (2,605 images + labels)
├── valid/     (114 images + labels)
└── test/       (82 images + labels)
```

3. Open the dataset's own `data.yaml` (inside your download) to confirm the
   real class names and count.

## 8. Dataset YAML Configuration

Copy the template and edit it with the REAL values from your download:

```powershell
copy data\dataset.example.yaml data\dataset.yaml
```

Then set `path`, `train`, `val`, `test`, `nc`, and `names` in
`data/dataset.yaml` to match the dataset you downloaded. The template leaves
class names as placeholders on purpose — never train against the template.

## 9. Training Command (runs only when you execute it)

8-epoch smoke test (as in the report):

```powershell
.venv\Scripts\python -m src.train --data data/dataset.yaml --epochs 8 --batch 8 --device cpu
```

Planned full run (report targets 50–100 epochs):

```powershell
.venv\Scripts\python -m src.train --data data/dataset.yaml --epochs 50 --batch 16 --device cpu --name ppe_full
```

After training, Ultralytics writes real metrics to
`runs/detect/<name>/results.csv` (P, R, mAP50, mAP50-95) and weights to
`runs/detect/<name>/weights/best.pt`. Copy the best weights into the models
folder:

```powershell
copy runs\detect\ppe_smoke\weights\best.pt models\ppe_model.pt
```

Nothing in this repo claims any accuracy/mAP number — those come only from
your actual training run.

## 10. Detection Command

```powershell
.venv\Scripts\python run_detection.py
```

With options:

```powershell
.venv\Scripts\python run_detection.py --input data/sample_site_video.mp4 --model models/ppe_model.pt --output outputs/videos/processed_site_video.mp4 --conf 0.25 --overlap 0.05 --persistence 8
```

If `models/ppe_model.pt` does not exist you will get a clear error telling
you to train first — the pipeline refuses to run without a real model.

## 11. Output Locations

| Output | Path |
|---|---|
| Annotated video | `outputs/videos/processed_site_video.mp4` |
| Snapshot per confirmed violation | `outputs/snapshots/frame######_<type>_id<id>.png` |
| JSON alert log | `outputs/alerts/violations_log.json` |
| Training metrics | `runs/detect/<name>/results.csv` |

## 12. How Person/PPE Association Works

Implemented in `src/violation_logic.py::associate_ppe_with_persons`:

1. Detections are split into **person** boxes and **PPE** boxes (helmet /
   hardhat, safety vest), matched case-insensitively against the class-name
   lists in `src/config.py`.
2. For each PPE box, the overlap fraction — intersection area divided by the
   **PPE box's own area** — is computed against every person box
   (`src/utils.py::compute_overlap_fraction`).
3. A PPE item is "worn by" a person if that fraction is at least the
   configurable threshold (`PPE_ASSOCIATION_OVERLAP_THRESHOLD`, default
   `0.05` ≈ the report's ~5% rule).
4. Any person missing a required PPE type is reported as violating
   (`missing_helmet` and/or `missing_safety_vest`).

The association function is intentionally small and dependency-free so it can
be swapped for a smarter rule (containment, IoU matching, or a learned
associator) without touching the rest of the pipeline.

## 13. The 8-Frame Persistence Rule

Implemented in `src/violation_logic.py::ViolationStateTracker`:

* Every processed frame, each tracked person's missing-PPE status is fed to
  the tracker.
* A per-(person, violation-type) counter increments **only while the
  violation continues**; if the violation disappears, the counter resets to
  zero.
* A violation becomes **confirmed exactly when the counter reaches 8
  consecutive frames** (`PERSISTENCE_FRAMES` in `src/config.py`).
* Confirmation fires **once per continuous episode**: while the same
  violation keeps going, no duplicate alerts are emitted. Only after the
  violation clears can a later episode confirm again.
* State is exposed (`get_count`, `has_suspected_violation`) and resettable
  (`reset()`, `clear_person(track_id)`).

This prevents alerts on every frame and suppresses flicker/occlusion noise.

## 14. Feature Status

**Implemented now (code + unit tests):**

* Full video pipeline skeleton: read frames → detect → track → associate →
  persist → alert → annotate → write video
* Centroid tracking of persons with stable IDs (prototype tracker)
* Overlap-based PPE association (~5% configurable threshold)
* 8-consecutive-frame persistence with duplicate-alert prevention
* Snapshot saving + JSON violation log with timestamps and frame numbers
* All thresholds/paths centralized in `src/config.py`; CLI overrides
* Unit tests for persistence, association, and utilities

**Requires the real dataset / trained model / real video (not in repo):**

* Trained YOLOv8 weights (`models/ppe_model.pt`) — produced by you via
  `src/train.py`; the pipeline will not run without it
* Any metrics (precision/recall/mAP) — only from your actual training run
* Detection results/snapshots — only from running `run_detection.py` on a
  real site video placed in `data/`

**Future features (not implemented):**

* ByteTrack or stronger multi-object tracking (the tracker interface is
  designed for a drop-in replacement)
* Telegram/SMS/other notification channels
* Live camera / RTSP input
* GPU acceleration, frame-skipping heuristics, web dashboard

## 15. Limitations

* Centroid tracking is simple: heavy occlusion or fast motion can switch IDs,
  which resets persistence for the affected person.
* The ~5% overlap association can mis-attribute PPE in crowded scenes
  (e.g., a helmet belonging to a background worker behind another worker).
* CPU inference is slow at full resolution/frame rates; use `--frame-stride`
  to trade smoothness for speed.
* The prototype processes a pre-recorded video, so alerts are as "real-time"
  as the file processing allows.
* Class-name matching depends on the dataset's real class names being
  configured correctly in `src/config.py` / `data/dataset.yaml`.

## 16. Future Improvements

* Replace the centroid tracker with ByteTrack via Ultralytics' built-in
  tracking support.
* Upgrade association to containment/IoU matching or per-person crops fed to
  a PPE classifier.
* Tune the overlap threshold and persistence length against labeled video,
  and report precision/recall of *confirmed violations* against ground truth.
* Add notification channels, a dashboard, and site-map analytics.

## 17. Running the Tests

```powershell
.venv\Scripts\python -m pytest tests/ -v
```
