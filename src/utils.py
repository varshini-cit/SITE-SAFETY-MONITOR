"""
Small shared helpers: geometry, class matching, and visualization drawing.

Kept dependency-light (OpenCV + NumPy only) so unit tests can run without a
trained model or the dataset.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

import cv2
import numpy as np

# A detection bounding box in pixels: (x1, y1, x2, y2).
Box = Tuple[float, float, float, float]


def compute_overlap_fraction(box_a: Box, box_b: Box) -> float:
    """
    Return the fraction of box_a's area that overlaps box_b.

    Used for person/PPE association: a PPE box counts as "worn" by a person
    when a configurable fraction of the PPE box lies inside the person box.
    """
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    intersection = inter_w * inter_h

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    if area_a <= 0.0:
        return 0.0
    return intersection / area_a


def class_matches(name: str, candidates: Sequence[str]) -> bool:
    """
    Case-insensitive match between a class name and a tuple of candidates.

    Allows "Hardhat" / "hardhat" / "HELMET" to match the configured class
    lists without sprinkling .lower() calls everywhere.
    """
    return name.strip().lower() in {c.strip().lower() for c in candidates}


def draw_detections(
    frame: np.ndarray,
    detections: List[Dict],
) -> np.ndarray:
    """
    Draw bounding boxes and labels for detections on a copy of the frame.

    Each detection dict must contain: bbox (x1, y1, x2, y2), class_name,
    confidence, and optionally track_id.
    """
    annotated = frame.copy()
    for det in detections:
        x1, y1, x2, y2 = (int(v) for v in det["bbox"])
        label_parts = [det.get("class_name", "?")]
        confidence = det.get("confidence")
        if confidence is not None:
            label_parts.append(f"{confidence:.2f}")
        track_id = det.get("track_id")
        if track_id is not None:
            label_parts.append(f"id{track_id}")
        label = " ".join(label_parts)

        color = _color_for(det.get("class_name", ""), det.get("has_required_ppe"))
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        _draw_label(annotated, label, x1, y1, color)
    return annotated


def _color_for(class_name: str, has_required_ppe: bool | None) -> Tuple[int, int, int]:
    """BGR colors: person red/green by compliance, others orange."""
    lowered = class_name.strip().lower()
    if lowered == "person" or lowered == "worker":
        if has_required_ppe is None:
            return (0, 165, 255)  # orange
        return (0, 200, 0) if has_required_ppe else (0, 0, 230)
    return (0, 165, 255)  # orange for PPE/detritus boxes


def _draw_label(frame: np.ndarray, text: str, x: int, y: int, color: Tuple[int, int, int]) -> None:
    """Draw a small filled label above a box."""
    text = str(text)
    (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    y_top = max(0, y - th - baseline - 4)
    cv2.rectangle(frame, (x, y_top), (x + tw + 4, y_top + th + baseline + 4), color, -1)
    cv2.putText(
        frame,
        text,
        (x + 2, y_top + th + 2),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )


def format_timestamp(frame_number: int, fps: float) -> str:
    """Convert a frame number to HH:MM:SS.mmm given a video FPS."""
    if fps and fps > 0:
        seconds = frame_number / fps
    else:
        seconds = float(frame_number)  # fallback: treat frames as seconds
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
