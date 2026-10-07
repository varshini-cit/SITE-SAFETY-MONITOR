"""
Simple centroid tracker for the current prototype.

Assigns persistent IDs to person detections and keeps identity across nearby
frames using centroid distance. This is deliberately NOT ByteTrack and is not
claimed to be one; the Tracker interface (update() -> list of detections with
track_id) is designed so ByteTrack or another tracker can replace this module
later without touching the violation logic.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np


class CentroidTracker:
    """
    Match detections frame-to-frame by nearest centroid.

    Parameters
    ----------
    max_disappeared : int
        Frames a track may go unseen before being deregistered.
    max_distance : float
        Maximum centroid distance (px) for a new detection to match an
        existing track. Larger values tolerate faster motion / bigger videos.
    """

    def __init__(self, max_disappeared: int = 15, max_distance: float = 80.0) -> None:
        self.next_object_id = 0
        # object_id -> centroid (x, y)
        self.centroids: Dict[int, tuple] = {}
        # object_id -> consecutive frames without a match
        self.disappeared: Dict[int, int] = {}
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance

    def update(self, detections: List[Dict]) -> List[Dict]:
        """
        Update tracks with the current frame's detections.

        Only detections whose class is "person" (case-insensitive) participate
        in tracking; other detections pass through untouched. Each returned
        person detection gets a "track_id" key.
        """
        persons = [d for d in detections if d.get("class_name", "").strip().lower() in ("person", "worker")]

        input_centroids = np.array(
            [_centroid(d["bbox"]) for d in persons], dtype="float32"
        ).reshape(-1, 2)

        if not self.centroids:
            for det, centroid in zip(persons, input_centroids):
                self._register(det, centroid)
            return persons

        object_ids = list(self.centroids.keys())
        existing = np.array([self.centroids[oid] for oid in object_ids], dtype="float32")

        if len(persons) == 0:
            self._mark_all_disappeared()
            return persons

        # Greedy nearest-centroid matching: for each detection, pick the
        # closest existing track within max_distance. Good enough for the
        # prototype's mostly-static camera scenes.
        used_objects = set()
        for det, centroid in zip(persons, input_centroids):
            distances = np.linalg.norm(existing - centroid, axis=1)
            order = np.argsort(distances)
            matched = False
            for idx in order:
                oid = object_ids[idx]
                if oid in used_objects:
                    continue
                if distances[idx] <= self.max_distance:
                    self.centroids[oid] = tuple(float(v) for v in centroid)
                    self.disappeared[oid] = 0
                    det["track_id"] = oid
                    used_objects.add(oid)
                    matched = True
                    break
            if not matched:
                self._register(det, centroid)

        for oid in object_ids:
            if oid not in used_objects:
                self.disappeared[oid] += 1
                if self.disappeared[oid] > self.max_disappeared:
                    self._deregister(oid)

        return persons

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _register(self, det: Dict, centroid: np.ndarray) -> None:
        self.centroids[self.next_object_id] = tuple(float(v) for v in centroid)
        self.disappeared[self.next_object_id] = 0
        det["track_id"] = self.next_object_id
        self.next_object_id += 1

    def _deregister(self, object_id: int) -> None:
        self.centroids.pop(object_id, None)
        self.disappeared.pop(object_id, None)

    def _mark_all_disappeared(self) -> None:
        for oid in list(self.centroids.keys()):
            self.disappeared[oid] = self.disappeared.get(oid, 0) + 1
            if self.disappeared[oid] > self.max_disappeared:
                self._deregister(oid)


def _centroid(bbox) -> tuple:
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
