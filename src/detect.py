"""
Real-time-ish PPE detection pipeline for pre-recorded video (CPU).

Pipeline per frame:
    read frame -> YOLOv8 detection -> centroid tracking of persons ->
    person/PPE association -> violation detection -> 8-frame persistence ->
    confirmed violation -> snapshot + JSON log -> annotated processed video.

The trained model file is REQUIRED: this script does not fabricate weights
and exits with a clear, beginner-friendly message when it is missing.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np

from src.alert_manager import AlertManager
from src.config import (
    CONFIDENCE_THRESHOLD,
    FRAME_STRIDE,
    IMAGE_SIZE,
    INPUT_VIDEO_PATH,
    IOU_THRESHOLD,
    MODEL_PATH,
    OUTPUT_VIDEO_PATH,
    PERSISTENCE_FRAMES,
    PPE_ASSOCIATION_OVERLAP_THRESHOLD,
    ensure_output_dirs,
)
from src.tracker import CentroidTracker
from src.utils import draw_detections, format_timestamp
from src.violation_logic import (
    ViolationStateTracker,
    associate_ppe_with_persons,
)

__all__ = ["ModelMissingError", "load_model", "run_detection", "main"]


class ModelMissingError(FileNotFoundError):
    """Raised when the trained YOLOv8 weights file does not exist."""


def load_model(model_path):
    """
    Load YOLOv8 weights from disk.

    Raises ModelMissingError with beginner-friendly instructions when the
    weights file is absent -- the pipeline never fabricates a model.
    """
    path = Path(model_path)
    if not path.exists():
        raise ModelMissingError(
            f"Trained model not found at: {path}\n"
            "\n"
            "This project does not ship pre-trained PPE weights.\n"
            "Train your own first (see README, section 'Training'):\n"
            "  1. Download the Roboflow Construction Site Safety dataset and\n"
            "     unpack it under data/raw/<dataset>/.\n"
            "  2. Copy data/dataset.example.yaml to data/dataset.yaml and fill\n"
            "     in the real train/val/test paths and class names.\n"
            "  3. Run a short smoke test:\n"
            "       .venv\\Scripts\\python -m src.train --data data/dataset.yaml --epochs 8\n"
            "  4. Copy the produced best.pt to models/ppe_model.pt, or pass\n"
            "     --model runs/detect/train/weights/best.pt to run_detection.py."
        )
    from ultralytics import YOLO  # deferred: keeps import light when unused

    return YOLO(str(path))


def process_detections(
    detections: List[Dict],
    tracker: CentroidTracker,
    violation_tracker: ViolationStateTracker,
    overlap_threshold: float = PPE_ASSOCIATION_OVERLAP_THRESHOLD,
) -> List[Dict]:
    """
    Take raw YOLO detections for one frame and return person dicts annotated
    with compliance info.

    Steps: tracking (persons only) -> PPE association -> per-person
    persistence update. Person dicts get keys: compliance (PersonCompliance),
    confirmed (bool -> this frame confirmed a violation), missing_ppe (list).
    """
    # 1. Tracking: assign stable IDs to persons (other classes pass through).
    tracker.update(detections)

    # 2. Association: which PPE belongs to which person?
    compliance_list = associate_ppe_with_persons(
        detections,
        overlap_threshold=overlap_threshold,
    )
    compliance_by_id = {}
    for i, compliance in enumerate(compliance_list):
        person = next(
            (d for d in detections
             if d.get("class_name", "").strip().lower() in ("person", "worker")
             and tuple(d["bbox"]) == compliance.bbox),
            None,
        )
        if person is None:
            person = next(
                (d for d in detections
                 if d.get("class_name", "").strip().lower() in ("person", "worker")
                 and d.get("track_id") == compliance.track_id),
                None,
            )
        if person is not None:
            compliance_by_id[id(person)] = (person, compliance)

    # 3. Persistence: confirm violations only after N consecutive frames.
    results = []
    for person, compliance in compliance_by_id.values():
        confirmed_any = False
        for missing in compliance.missing_ppe:
            confirmed = violation_tracker.update(
                track_id=compliance.track_id,
                violation_type=f"missing_{missing.replace(' ', '_')}",
                is_violating=True,
            )
            confirmed_any = confirmed_any or confirmed
        # Violations NOT missing this frame must be fed as "not violating"
        # so their counters reset. We infer the full required-PPE set:
        for violation_type in ("missing_helmet", "missing_safety_vest"):
            missing_name = violation_type.replace("missing_", "").replace("_", " ")
            if missing_name not in compliance.missing_ppe:
                violation_tracker.update(
                    track_id=compliance.track_id,
                    violation_type=violation_type,
                    is_violating=False,
                )

        person["compliance"] = compliance
        person["missing_ppe"] = list(compliance.missing_ppe)
        person["confirmed"] = confirmed_any
        results.append(person)

    return results


def run_detection(
    model_path=MODEL_PATH,
    input_video=INPUT_VIDEO_PATH,
    output_video=OUTPUT_VIDEO_PATH,
    confidence: float = CONFIDENCE_THRESHOLD,
    iou: float = IOU_THRESHOLD,
    image_size: int = IMAGE_SIZE,
    frame_stride: int = FRAME_STRIDE,
    overlap_threshold: float = PPE_ASSOCIATION_OVERLAP_THRESHOLD,
    persistence_frames: int = PERSISTENCE_FRAMES,
    display: bool = False,
) -> Dict:
    """
    Process a video end-to-end and write an annotated output video.

    Returns a summary dict: frames processed, violations confirmed, etc.
    """
    model = load_model(model_path)
    ensure_output_dirs()

    capture = cv2.VideoCapture(str(input_video))
    if not capture.isOpened():
        raise FileNotFoundError(
            f"Could not open input video: {input_video}\n"
            "Place a .mp4/.avi file in data/ and pass --input <path>."
        )

    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    Path(output_video).parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(output_video),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )

    tracker = CentroidTracker()
    violation_tracker = ViolationStateTracker(persistence_frames=persistence_frames)
    alert_manager = AlertManager()

    frame_number = 0
    confirmed_count = 0
    print(f"Processing video: {input_video}")
    print(f"  {width}x{height} @ {fps:.1f} FPS | persistence={persistence_frames} "
          f"| overlap_threshold={overlap_threshold}")

    while True:
        ok, frame = capture.read()
        if not ok:
            break
        frame_number += 1

        if frame_number % max(1, frame_stride) != 0:
            writer.write(frame)
            continue

        # YOLOv8 detection on this frame.
        results = model.predict(
            frame,
            conf=confidence,
            iou=iou,
            imgsz=image_size,
            verbose=False,
        )
        detections = _results_to_detections(results)

        # Tracking + association + persistence.
        persons = process_detections(detections, tracker, violation_tracker,
                                     overlap_threshold=overlap_threshold)

        # Record confirmed violations (snapshot + JSON log).
        video_ts = format_timestamp(frame_number, fps)
        for person in persons:
            if person.get("confirmed"):
                confirmed_count += 1
                alert_manager.record_violation(
                    frame=frame,
                    frame_number=frame_number,
                    violation_type="missing_ppe",
                    track_id=person.get("track_id"),
                    video_timestamp=video_ts,
                    extra={
                        "missing": list(person.get("missing_ppe", [])),
                        "confidence": person.get("confidence"),
                    },
                )

        # Annotate and write.
        annotated = draw_detections(frame, detections)
        if display:
            cv2.imshow("Site Safety Monitor", annotated)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        writer.write(annotated)

        if frame_number % 100 == 0:
            print(f"  frame {frame_number} | confirmed violations so far: {confirmed_count}")

    capture.release()
    writer.release()
    if display:
        cv2.destroyAllWindows()

    summary = {
        "frames_processed": frame_number,
        "confirmed_violations": confirmed_count,
        "output_video": str(output_video),
        "alerts_logged": len(alert_manager.events),
    }
    print("Done:", summary)
    return summary


def _results_to_detections(results) -> List[Dict]:
    """Convert ultralytics Results into plain dicts for the rest of pipeline."""
    detections: List[Dict] = []
    for result in results:
        names = result.names  # class_id -> class name
        boxes = result.boxes
        if boxes is None:
            continue
        for cls_id, conf, xyxy in zip(
            boxes.cls.tolist(), boxes.conf.tolist(), boxes.xyxy.tolist()
        ):
            detections.append({
                "bbox": tuple(float(v) for v in xyxy),
                "class_id": int(cls_id),
                "class_name": str(names[int(cls_id)]),
                "confidence": float(conf),
            })
    return detections


def main() -> None:
    """CLI entry point for run_detection.py."""
    parser = argparse.ArgumentParser(
        description="PPE compliance detection on a video using a trained YOLOv8 model."
    )
    parser.add_argument("--model", default=str(MODEL_PATH),
                        help="Path to trained .pt weights (default: models/ppe_model.pt)")
    parser.add_argument("--input", default=str(INPUT_VIDEO_PATH),
                        help="Input video path (default: data/sample_site_video.mp4)")
    parser.add_argument("--output", default=str(OUTPUT_VIDEO_PATH),
                        help="Output video path (default: outputs/videos/processed_site_video.mp4)")
    parser.add_argument("--conf", type=float, default=CONFIDENCE_THRESHOLD,
                        help="Confidence threshold")
    parser.add_argument("--iou", type=float, default=IOU_THRESHOLD,
                        help="NMS IoU threshold")
    parser.add_argument("--imgsz", type=int, default=IMAGE_SIZE,
                        help="Inference image size")
    parser.add_argument("--frame-stride", type=int, default=FRAME_STRIDE,
                        help="Process every Nth frame (1 = all frames)")
    parser.add_argument("--overlap", type=float, default=PPE_ASSOCIATION_OVERLAP_THRESHOLD,
                        help="PPE/person overlap fraction threshold (e.g., 0.05)")
    parser.add_argument("--persistence", type=int, default=PERSISTENCE_FRAMES,
                        help="Consecutive frames required to confirm a violation")
    parser.add_argument("--display", action="store_true",
                        help="Show annotated frames in a window while processing")
    args = parser.parse_args()

    try:
        run_detection(
            model_path=args.model,
            input_video=args.input,
            output_video=args.output,
            confidence=args.conf,
            iou=args.iou,
            image_size=args.imgsz,
            frame_stride=args.frame_stride,
            overlap_threshold=args.overlap,
            persistence_frames=args.persistence,
            display=args.display,
        )
    except (ModelMissingError, FileNotFoundError) as exc:
        print(f"\nERROR: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
