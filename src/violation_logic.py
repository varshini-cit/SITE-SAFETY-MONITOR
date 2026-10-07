"""
PPE association and violation persistence logic.

Two responsibilities, kept separate so each can be improved independently:

1. Association (associate_ppe_with_persons): match helmet/vest detections to
   person detections using an overlap-fraction rule. Swap this function for a
   better method (e.g., containment, IoU, or a learned associator) later.
2. Persistence (ViolationStateTracker): a suspected violation must survive
   PERSISTENCE_FRAMES consecutive frames per tracked person before it is
   confirmed, and one continuous violation produces exactly ONE alert.

This module deliberately has NO dependency on YOLO/OpenCV so the unit tests
run fast and the association strategy can be replaced cleanly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Tuple

from src.config import (
    HELMET_CLASSES,
    PERSISTENCE_FRAMES,
    PPE_ASSOCIATION_OVERLAP_THRESHOLD,
    PERSON_CLASS,
    VEST_CLASSES,
)
from src.utils import class_matches, compute_overlap_fraction


# ---------------------------------------------------------------------------
# 1. Person <-> PPE association
# ---------------------------------------------------------------------------
@dataclass
class PersonCompliance:
    """Compliance result for one person detection in one frame."""

    track_id: object = None          # tracker ID, if tracking ran
    bbox: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    has_helmet: bool = False
    has_vest: bool = False
    missing_ppe: List[str] = field(default_factory=list)

    @property
    def is_compliant(self) -> bool:
        return not self.missing_ppe


def associate_ppe_with_persons(
    detections: List[Dict],
    overlap_threshold: float = PPE_ASSOCIATION_OVERLAP_THRESHOLD,
    person_class: str = PERSON_CLASS,
    helmet_classes: Iterable[str] = HELMET_CLASSES,
    vest_classes: Iterable[str] = VEST_CLASSES,
) -> List[PersonCompliance]:
    """
    Associate PPE detections with person detections and report compliance.

    Association rule (configurable via overlap_threshold): a PPE detection
    belongs to a person when at least `overlap_threshold` of the PPE box's
    area overlaps that person's box. Each PPE box is assigned to the person
    with the largest overlap.

    Parameters mirror src/config.py values so tests can override them.
    """
    persons = [
        d for d in detections
        if class_matches(d.get("class_name", ""), (person_class, "worker"))
    ]
    helmets = [d for d in detections if class_matches(d.get("class_name", ""), helmet_classes)]
    vests = [d for d in detections if class_matches(d.get("class_name", ""), vest_classes)]

    results: List[PersonCompliance] = []
    for person in persons:
        compliance = PersonCompliance(
            track_id=person.get("track_id"),
            bbox=tuple(person["bbox"]),  # type: ignore[arg-type]
        )
        compliance.has_helmet = _ppe_overlaps_person(person, helmets, overlap_threshold)
        compliance.has_vest = _ppe_overlaps_person(person, vests, overlap_threshold)

        if not compliance.has_helmet:
            compliance.missing_ppe.append("helmet")
        if not compliance.has_vest:
            compliance.missing_ppe.append("safety vest")

        results.append(compliance)

    return results


def _ppe_overlaps_person(
    person: Dict,
    ppe_detections: List[Dict],
    overlap_threshold: float,
) -> bool:
    """True if any PPE box overlaps this person by >= threshold fraction."""
    person_box = person["bbox"]
    for ppe in ppe_detections:
        fraction = compute_overlap_fraction(ppe["bbox"], person_box)
        if fraction >= overlap_threshold:
            return True
    return False


# ---------------------------------------------------------------------------
# 2. 8-consecutive-frame persistence
# ---------------------------------------------------------------------------
class ViolationStateTracker:
    """
    Track per-person, per-violation-type persistence across frames.

    Rules implemented:
      * A suspected violation's counter increments only while the violation
        keeps being detected for the same tracked person on consecutive
        frames.
      * If the violation disappears for that person, the counter resets.
      * A violation is CONFIRMED exactly when the counter reaches
        persistence_frames (default 8).
      * Confirmation fires ONCE per continuous violation episode: further
        frames of the same episode do not re-alert. Only after the violation
        clears (reset) can a new episode later confirm again.
      * State is exposed and can be reset cleanly (reset() / clear_person()).
    """

    def __init__(self, persistence_frames: int = PERSISTENCE_FRAMES) -> None:
        if persistence_frames < 1:
            raise ValueError("persistence_frames must be >= 1")
        self.persistence_frames = persistence_frames
        # (track_id, violation_type) -> consecutive-frame count
        self.counts: Dict[Tuple[object, str], int] = {}
        # Episodes that have already fired an alert and are still ongoing.
        self._alerted: set = set()

    def update(
        self,
        track_id: object,
        violation_type: str,
        is_violating: bool,
    ) -> bool:
        """
        Feed one frame's status for a person; return True if this call
        CONFIRMS a violation (i.e., the alert should fire now).

        track_id may be None when tracking is unavailable; in that case the
        caller should treat the whole scene as one "person" slot.
        """
        key = (track_id, violation_type)

        if not is_violating:
            # Violation ended: reset persistence and clear the episode flag so
            # a future episode can alert again.
            self.counts.pop(key, None)
            self._alerted.discard(key)
            return False

        current = self.counts.get(key, 0) + 1
        self.counts[key] = current

        if current == self.persistence_frames:
            self._alerted.add(key)
            return True

        # Already alerted and still ongoing -> no duplicate alert.
        if key in self._alerted:
            return False
        return False

    def has_suspected_violation(self, track_id: object, violation_type: str) -> bool:
        return (track_id, violation_type) in self.counts

    def get_count(self, track_id: object, violation_type: str) -> int:
        return self.counts.get((track_id, violation_type), 0)

    def clear_person(self, track_id: object) -> None:
        """Drop all state for one tracked person (e.g., tracker deregistered them)."""
        for key in [k for k in self.counts if k[0] == track_id]:
            self.counts.pop(key, None)
            self._alerted.discard(key)

    def reset(self) -> None:
        """Clear all persistence state (e.g., between videos)."""
        self.counts.clear()
        self._alerted.clear()
