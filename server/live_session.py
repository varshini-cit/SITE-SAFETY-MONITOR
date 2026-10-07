"""
Live camera demo session (ADDITIVE prototype feature).

Laptop webcam (browser JPEG frames) -> this session -> the EXISTING pipeline:

    detect.load_model(models/ppe_model.pt)          [EXISTING loader]
    model.predict(...)                              [EXISTING trained model]
    detect._results_to_detections()                 [EXISTING converter]
    detect.process_detections()                     [EXISTING: CentroidTracker +
        person/PPE association + 8-frame ViolationStateTracker persistence]
    AlertManager.record_violation(...)              [EXISTING snapshot+log code]

Nothing in src/ is modified or duplicated. All live-camera output is written
to an ISOLATED area so the prerecorded-video demo data is never touched:

    outputs/live_camera/
    ├── snapshots/          live violation snapshots only
    └── violations_log.json live violation events only

The laptop webcam is a PROTOTYPE camera source only. No CCTV/RTSP support is
implemented or claimed; in deployment this input can be replaced by an IP
CCTV/RTSP stream feeding the same pipeline.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np

from src import detect as detection_pipeline
from src.alert_manager import AlertManager
from src.config import (
    CONFIDENCE_THRESHOLD,
    IMAGE_SIZE,
    IOU_THRESHOLD,
    MODEL_PATH,
    PERSISTENCE_FRAMES,
    PPE_ASSOCIATION_OVERLAP_THRESHOLD,
    PROJECT_ROOT,
)
from src.tracker import CentroidTracker
from src.violation_logic import ViolationStateTracker

# Isolated output area for the live-camera prototype (never the recorded demo data).
LIVE_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "live_camera"
LIVE_SNAPSHOTS_DIR = LIVE_OUTPUT_DIR / "snapshots"
LIVE_LOG_PATH = LIVE_OUTPUT_DIR / "violations_log.json"


class LiveCameraSession:
    """
    One webcam demo session.

    Holds the shared model (lazy-loaded once, kept for fast restarts) and
    per-session tracker/violation/alert state. Only one frame is inferred at
    a time: process_frame() acquires a non-blocking lock and reports
    {"busy": True} when a previous frame is still processing.
    """

    def __init__(
        self,
        model_path=MODEL_PATH,
        snapshots_dir: Path = LIVE_SNAPSHOTS_DIR,
        log_path: Path = LIVE_LOG_PATH,
        persistence_frames: int = PERSISTENCE_FRAMES,
    ) -> None:
        self._model_path = model_path
        self._snapshots_dir = Path(snapshots_dir)
        self._log_path = Path(log_path)
        self._persistence_frames = persistence_frames
        self._lock = threading.Lock()
        self._model = None
        self._reset_state()

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------
    def _reset_state(self) -> None:
        """Fresh per-session state (trackers, counters, isolated alert store)."""
        self.running = False
        self.started_at: Optional[float] = None
        # Per-session pipeline state: EXISTING components, new instances.
        self.tracker = CentroidTracker()
        self.violation_tracker = ViolationStateTracker(persistence_frames=self._persistence_frames)
        self.alert_manager = AlertManager(
            snapshots_dir=self._snapshots_dir, log_path=self._log_path
        )
        # Stats (all derived from real inference; nothing fabricated).
        self.frame_number = 0
        self.processed_frames = 0
        self.session_alerts = 0
        self.last_detections: List[Dict] = []
        self.persons: List[Dict] = []
        self.current_violations = 0
        self.last_alert: Optional[Dict] = None
        self.last_latency_ms: Optional[int] = None
        self.last_error: Optional[str] = None

    def start(self) -> Dict:
        """Start a session (loads the existing model on first use)."""
        with self._lock:
            if self.running:
                return {"running": True, "already_running": True}
            if self._model is None:
                # EXISTING loader + EXISTING weights file. No training here.
                self._model = detection_pipeline.load_model(self._model_path)
            self._reset_state()
            self.running = True
            self.started_at = time.time()
            return {"running": True, "already_running": False}

    def stop(self) -> Dict:
        """Stop the session and release per-session state (model stays cached)."""
        with self._lock:
            was_running = self.running
            self._reset_state()  # running -> False, trackers/counters cleared
            return {"running": False, "was_running": was_running}

    # ------------------------------------------------------------------
    # Per-frame processing (EXISTING pipeline, nothing re-implemented)
    # ------------------------------------------------------------------
    def process_frame(self, jpeg_bytes: bytes) -> Dict:
        if not self.running:
            return {"running": False, "stopped": True}
        if not self._lock.acquire(blocking=False):
            return {"running": True, "busy": True}
        try:
            arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is None:
                self.last_error = "undecodable JPEG frame"
                return {"running": True, "error": self.last_error}

            t0 = time.perf_counter()

            # 1. YOLOv8 detection with the EXISTING trained model.
            results = self._model.predict(
                frame,
                conf=CONFIDENCE_THRESHOLD,
                iou=IOU_THRESHOLD,
                imgsz=IMAGE_SIZE,
                verbose=False,
            )
            # 2. EXISTING conversion to plain detection dicts.
            detections = detection_pipeline._results_to_detections(results)

            # 3. EXISTING tracking + PPE association + 8-frame persistence.
            persons = detection_pipeline.process_detections(
                detections,
                self.tracker,
                self.violation_tracker,
                overlap_threshold=PPE_ASSOCIATION_OVERLAP_THRESHOLD,
            )

            self.frame_number += 1
            self.processed_frames += 1

            # 4. EXISTING alert path for CONFIRMED violations only
            #    (8 consecutive frames; once per episode => no alert flood).
            new_alerts: List[Dict] = []
            for person in persons:
                if person.get("confirmed"):
                    event = self.alert_manager.record_violation(
                        frame=frame,
                        frame_number=self.frame_number,
                        violation_type="missing_ppe",
                        track_id=person.get("track_id"),
                        video_timestamp=None,  # live: wall-clock timestamp is set by AlertManager
                        extra={
                            "missing": list(person.get("missing_ppe", [])),
                            "confidence": person.get("confidence"),
                            "source": "live_camera",
                        },
                    )
                    new_alerts.append(event)
                    self.last_alert = event
            self.session_alerts += len(new_alerts)

            # 5. Real per-frame stats for the dashboard.
            self.last_detections = detections
            self.persons = persons
            self.current_violations = sum(1 for p in persons if p.get("missing_ppe"))
            self.last_latency_ms = int((time.perf_counter() - t0) * 1000)
            self.last_error = None

            return self.status_payload(new_alerts=new_alerts)
        except Exception as exc:  # keep the session alive; surface the error
            self.last_error = str(exc)
            return {"running": True, "error": str(exc)}
        finally:
            self._lock.release()

    # ------------------------------------------------------------------
    # Status / serialization
    # ------------------------------------------------------------------
    def status_payload(self, new_alerts: Optional[List[Dict]] = None) -> Dict:
        detections_payload = [
            {
                "bbox": [float(v) for v in d["bbox"]],
                "class_name": d.get("class_name"),
                "confidence": float(d.get("confidence", 0.0)),
                "track_id": d.get("track_id"),
            }
            for d in self.last_detections
        ]
        persons_payload = [
            {
                "track_id": p.get("track_id"),
                "missing_ppe": list(p.get("missing_ppe", [])),
                "confirmed": bool(p.get("confirmed")),
                "persistence_counts": {
                    "missing_helmet": self.violation_tracker.get_count(
                        p.get("track_id"), "missing_helmet"
                    ),
                    "missing_safety_vest": self.violation_tracker.get_count(
                        p.get("track_id"), "missing_safety_vest"
                    ),
                },
            }
            for p in self.persons
        ]
        violation_active = self.current_violations > 0 and self.session_alerts > 0
        return {
            "running": self.running,
            "frame_number": self.frame_number,
            "processed_frames": self.processed_frames,
            "persons_detected": len(self.persons),
            "ppe_status": (
                "VIOLATION" if self.current_violations > 0
                else ("SAFE" if self.persons else "NO_PERSON")
            ),
            "current_violations": self.current_violations,
            "session_alerts": self.session_alerts,
            "violation_active": violation_active,
            "last_alert": self.last_alert,
            "new_alerts": new_alerts or [],
            "detections": detections_payload,
            "persons": persons_payload,
            "persistence_frames": self._persistence_frames,
            "latency_ms": self.last_latency_ms,
            "last_error": self.last_error,
            "model_path": str(self._model_path),
        }

    def status(self) -> Dict:
        return self.status_payload()


# ---------------------------------------------------------------------------
# Lazy module-level session (created on first /api/live/* request so that
# merely importing the API never creates output directories).
# ---------------------------------------------------------------------------
_session: Optional[LiveCameraSession] = None
_session_lock = threading.Lock()


def get_session() -> LiveCameraSession:
    global _session
    with _session_lock:
        if _session is None:
            _session = LiveCameraSession()
        return _session


def read_live_events() -> List[Dict]:
    """Read the ISOLATED live log (never the prerecorded violations_log.json)."""
    if not LIVE_LOG_PATH.exists():
        return []
    try:
        with open(LIVE_LOG_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []
