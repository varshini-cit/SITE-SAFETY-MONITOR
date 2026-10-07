"""
Centralized configuration for the Site Safety Monitor project.

Every tunable value used anywhere in the pipeline lives here. Other modules
import from this file instead of hard-coding numbers, so behavior
(thresholds, paths, video IO) can be changed in ONE place.

Values marked "CLI-configurable" can be overridden from the command line via
run_detection.py; everything else is edited here.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Project layout (resolved relative to this file's project root)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

MODELS_DIR = PROJECT_ROOT / "models"

OUTPUTS_DIR = PROJECT_ROOT / "outputs"
ALERTS_DIR = OUTPUTS_DIR / "alerts"
SNAPSHOTS_DIR = OUTPUTS_DIR / "snapshots"
VIDEOS_DIR = OUTPUTS_DIR / "videos"

# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------
# Path to the trained YOLOv8 weights file. This file must be produced by
# actually running training (src/train.py). It is NOT shipped with the repo.
MODEL_PATH = MODELS_DIR / "ppe_model.pt"

# Base pretrained checkpoint used as the starting point for training.
# "yolov8n.pt" is downloaded once by Ultralytics at first training run.
BASE_MODEL = "yolov8n.pt"

CONFIDENCE_THRESHOLD = 0.25   # minimum detection confidence to keep
IOU_THRESHOLD = 0.45          # NMS IoU threshold
IMAGE_SIZE = 640              # inference/training image size (px)

# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------
# YAML describing the Roboflow Construction Site Safety dataset. A template
# lives at data/dataset.example.yaml; copy it to data/dataset.yaml and fill
# in the real paths/classes from your downloaded dataset.
DATASET_YAML = DATA_DIR / "dataset.yaml"

# ---------------------------------------------------------------------------
# Video IO
# ---------------------------------------------------------------------------
INPUT_VIDEO_PATH = DATA_DIR / "sample_site_video.mp4"
OUTPUT_VIDEO_PATH = VIDEOS_DIR / "processed_site_video.mp4"

# ---------------------------------------------------------------------------
# Detection pipeline behavior
# ---------------------------------------------------------------------------
# Minimum fraction of a PPE box area that must overlap a person box for the
# PPE to be considered "worn by" that person. The project report describes
# roughly a 5% overlap threshold; keep it configurable so the association
# rule can be tuned without touching pipeline code.
PPE_ASSOCIATION_OVERLAP_THRESHOLD = 0.05

# A suspected violation must persist this many consecutive frames (per
# tracked person, per violation type) before it is confirmed and alerted.
PERSISTENCE_FRAMES = 8

# Person class name used by the model (as named in dataset.yaml).
PERSON_CLASS = "person"

# PPE classes the model is expected to emit for compliance checking.
# These names must match the classes in the REAL Roboflow dataset's
# data.yaml. They are listed here as configuration, not invented.
HELMET_CLASSES = ("hardhat", "helmet")
VEST_CLASSES = ("safety vest", "vest")

# Frames are processed one by one on CPU; set > 1 to skip frames.
FRAME_STRIDE = 1

# After processing, optionally write a JSON log of confirmed violations.
VIOLATIONS_LOG_PATH = ALERTS_DIR / "violations_log.json"

# ---------------------------------------------------------------------------
# Training defaults (src/train.py) -- nothing trains automatically.
# ---------------------------------------------------------------------------
TRAIN_EPOCHS = 8              # report used an 8-epoch smoke test
TRAIN_BATCH_SIZE = 8          # keep small for CPU
TRAIN_WORKERS = 2             # dataloader workers; 0-2 is safest on Windows
TRAIN_IMAGE_SIZE = IMAGE_SIZE
# Planned full training range from the report; expose for reference.
TRAIN_EPOCHS_MIN_RECOMMENDED = 50
TRAIN_EPOCHS_MAX_RECOMMENDED = 100


def ensure_output_dirs() -> None:
    """Create output directories if they are missing."""
    for directory in (ALERTS_DIR, SNAPSHOTS_DIR, VIDEOS_DIR):
        directory.mkdir(parents=True, exist_ok=True)
