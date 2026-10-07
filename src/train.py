"""
Training script for the Site Safety Monitor (YOLOv8).

IMPORTANT: This script NEVER trains automatically. It only runs when YOU
execute it, e.g.:

    .venv\\Scripts\\python -m src.train --data data/dataset.yaml --epochs 8

That command is the 8-epoch smoke test from the project report. For the full
run the report plans 50-100 epochs; pass --epochs 50 (or more) when ready.

No metrics are invented here: Ultralytics writes real metrics (P, R, mAP50,
mAP50-95) to runs/detect/train*/results.csv after an actual run.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.config import (
    BASE_MODEL,
    TRAIN_BATCH_SIZE,
    TRAIN_EPOCHS,
    TRAIN_IMAGE_SIZE,
    TRAIN_WORKERS,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train YOLOv8 on the PPE dataset (runs only when you invoke it)."
    )
    parser.add_argument(
        "--data",
        type=str,
        required=True,
        help="Path to dataset YAML (e.g., data/dataset.yaml) with REAL paths/classes.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=BASE_MODEL,
        help="Base checkpoint (default: yolov8n.pt; downloaded once by Ultralytics).",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=TRAIN_EPOCHS,
        help=f"Number of epochs (default: {TRAIN_EPOCHS} = smoke test; "
             "use 50-100 for the full planned run).",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=TRAIN_BATCH_SIZE,
        help=f"Batch size (default: {TRAIN_BATCH_SIZE}, CPU-friendly).",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=TRAIN_IMAGE_SIZE,
        help=f"Image size in px (default: {TRAIN_IMAGE_SIZE}).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=TRAIN_WORKERS,
        help="Dataloader workers (default: 2; keep 0-2 on Windows).",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        help="Device: 'cpu' (default) or e.g. '0' for a CUDA GPU.",
    )
    parser.add_argument(
        "--name",
        type=str,
        default="ppe_smoke",
        help="Run name under runs/detect/ (default: ppe_smoke).",
    )
    return parser


def train(
    data: str,
    model: str = BASE_MODEL,
    epochs: int = TRAIN_EPOCHS,
    batch: int = TRAIN_BATCH_SIZE,
    imgsz: int = TRAIN_IMAGE_SIZE,
    workers: int = TRAIN_WORKERS,
    device: str = "cpu",
    name: str = "ppe_smoke",
):
    """
    Launch Ultralytics training. Called ONLY from main() / explicit invocation.
    Returns the Ultralytics results object; metrics land in runs/detect/<name>/.
    """
    data_path = Path(data)
    if not data_path.exists():
        raise FileNotFoundError(
            f"Dataset YAML not found: {data_path}\n"
            "Copy data/dataset.example.yaml -> data/dataset.yaml, then fill in\n"
            "the real train/val/test paths and the dataset's real class names."
        )

    from ultralytics import YOLO  # deferred so --help stays fast

    yolo = YOLO(model)
    return yolo.train(
        data=str(data_path),
        epochs=epochs,
        batch=batch,
        imgsz=imgsz,
        workers=workers,
        device=device,
        name=name,
    )


def main() -> None:
    args = build_parser().parse_args()
    print(
        f"Starting training: model={args.model} epochs={args.epochs} "
        f"batch={args.batch} imgsz={args.imgsz} device={args.device}"
    )
    if args.epochs < 8:
        print("Warning: fewer than 8 epochs is below the report's smoke test; "
              "metrics will be weak.")
    if args.epochs > 8:
        print("Full-length run: expect hours on CPU; the report plans 50-100 "
              "epochs for the final model.")
    train(
        data=args.data,
        model=args.model,
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        workers=args.workers,
        device=args.device,
        name=args.name,
    )


if __name__ == "__main__":
    main()
