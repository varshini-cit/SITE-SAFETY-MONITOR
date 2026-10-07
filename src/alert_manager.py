"""
Alert manager: records confirmed violations.

When a violation is confirmed (after the persistence rule fires), this module:
  * generates a wall-clock timestamp and keeps the frame number,
  * records the violation type and tracked-person ID,
  * saves a snapshot image of the offending frame,
  * appends the event to a JSON log.

Telegram/SMS/other notification channels are intentionally NOT implemented
yet; alert_events are only persisted locally.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np

from src.config import ALERTS_DIR, SNAPSHOTS_DIR, VIOLATIONS_LOG_PATH


class AlertManager:
    """Persist confirmed violations as snapshots + a JSON event log."""

    def __init__(
        self,
        snapshots_dir: Path = SNAPSHOTS_DIR,
        log_path: Path = VIOLATIONS_LOG_PATH,
    ) -> None:
        self.snapshots_dir = Path(snapshots_dir)
        self.log_path = Path(log_path)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.events: List[Dict] = []

    def record_violation(
        self,
        frame: np.ndarray,
        frame_number: int,
        violation_type: str,
        track_id: Optional[object] = None,
        video_timestamp: Optional[str] = None,
        extra: Optional[Dict] = None,
    ) -> Dict:
        """
        Record one confirmed violation.

        Returns the event dict that was logged (also appended to JSON file).
        """
        timestamp = datetime.now().isoformat(timespec="seconds")
        snapshot_path = self._save_snapshot(frame, frame_number, violation_type, track_id)

        event = {
            "timestamp": timestamp,
            "video_timestamp": video_timestamp,
            "frame_number": frame_number,
            "violation_type": violation_type,
            "track_id": track_id,
            "snapshot": str(snapshot_path),
        }
        if extra:
            event.update(extra)

        self.events.append(event)
        self._append_to_log(event)
        return event

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _save_snapshot(
        self,
        frame: np.ndarray,
        frame_number: int,
        violation_type: str,
        track_id: Optional[object],
    ) -> Path:
        """Write the offending frame as a PNG and return its path."""
        safe_type = str(violation_type).replace(" ", "_").replace("/", "-")
        track_part = f"id{track_id}" if track_id is not None else "scene"
        name = f"frame{frame_number:06d}_{safe_type}_{track_part}.png"
        path = self.snapshots_dir / name
        cv2.imwrite(str(path), frame)
        return path

    def _append_to_log(self, event: Dict) -> None:
        """
        Append event to the JSON log.

        The log is a JSON list. If the file is missing or unreadable, a new
        list is started; existing valid content is always preserved.
        """
        existing: List[Dict] = []
        if self.log_path.exists():
            try:
                with open(self.log_path, "r", encoding="utf-8") as fh:
                    loaded = json.load(fh)
                if isinstance(loaded, list):
                    existing = loaded
            except (json.JSONDecodeError, OSError):
                # Corrupt/unreadable log: start fresh rather than crash.
                existing = []

        existing.append(event)
        with open(self.log_path, "w", encoding="utf-8") as fh:
            json.dump(existing, fh, indent=2)
