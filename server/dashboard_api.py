"""
Read-only FastAPI layer for the Site Safety Monitor dashboard.

Serves REAL project data only:
  - outputs/alerts/violations_log.json   (confirmed violation events)
  - outputs/snapshots/*.png              (violation snapshots)
  - outputs/videos/*.mp4                 (processed videos)
  - runs/detect/ppe_smoke/results.csv    (real per-epoch training metrics)
  - runs/detect/ppe_smoke/args.yaml      (actual training configuration)
  - train_smoke.log                      (final per-class validation table)
  - data/dataset.yaml                    (real dataset configuration)

No detection/violation logic is modified or re-implemented here: this module
only READS files the existing pipeline produced. All endpoints are GET-only.
"""

from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import threading
from pathlib import Path
from typing import Dict, List

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from server import live_session
from src.config import MODEL_PATH, PROJECT_ROOT

app = FastAPI(title="Site Safety Monitor API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

RUNS_DIR = PROJECT_ROOT / "runs" / "detect"
TRAIN_RUN = RUNS_DIR / "ppe_smoke"
TEST_EVAL = RUNS_DIR / "test_eval"
LOG_PATH = PROJECT_ROOT / "outputs" / "alerts" / "violations_log.json"
SNAPSHOTS_DIR = PROJECT_ROOT / "outputs" / "snapshots"
VIDEOS_DIR = PROJECT_ROOT / "outputs" / "videos"
PROCESSED_VIDEO = VIDEOS_DIR / "processed_site_video.mp4"
# Browser-compatible H.264 copy created lazily next to the original (below).
WEB_VIDEO = VIDEOS_DIR / "processed_site_video_web.mp4"
TRAIN_LOG = PROJECT_ROOT / "train_smoke.log"
DATASET_YAML = PROJECT_ROOT / "data" / "dataset.yaml"

CLASS_NAMES = ["Hardhat", "Mask", "NO-Hardhat", "NO-Mask", "NO-Safety Vest",
               "Person", "Safety Cone", "Safety Vest", "machinery", "vehicle"]


# ---------------------------------------------------------------------------
# Helpers (all read-only)
# ---------------------------------------------------------------------------
def _load_events() -> List[Dict]:
    if not LOG_PATH.exists():
        return []
    try:
        data = json.loads(LOG_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _read_results_csv() -> List[Dict]:
    csv_path = TRAIN_RUN / "results.csv"
    if not csv_path.exists():
        return []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    parsed = []
    for r in rows:
        parsed.append({
            "epoch": int(r["epoch"]),
            "time": float(r["time"]),
            "precision": float(r["metrics/precision(B)"]),
            "recall": float(r["metrics/recall(B)"]),
            "map50": float(r["metrics/mAP50(B)"]),
            "map50_95": float(r["metrics/mAP50-95(B)"]),
            "box_loss": float(r["train/box_loss"]),
            "cls_loss": float(r["train/cls_loss"]),
            "val_box_loss": float(r["val/box_loss"]),
            "val_cls_loss": float(r["val/cls_loss"]),
        })
    return parsed


def _parse_log_tables() -> Dict:
    """Parse the REAL per-class validation table + duration from train_smoke.log."""
    out = {"per_class": [], "overall": {}, "duration_hours": None}
    if not TRAIN_LOG.exists():
        return out
    text = TRAIN_LOG.read_text(encoding="utf-8", errors="ignore")

    m = re.search(r"(\d+) epochs completed in ([0-9.]+) hours", text)
    if m:
        out["epochs_declared"] = int(m.group(1))
        out["duration_hours"] = float(m.group(2))

    for line in text.splitlines():
        mm = re.match(
            r"^\s{10,}(\S.*?)\s+(\d+)\s+(\d+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s*$",
            line,
        )
        if not mm:
            continue
        name = mm.group(1).strip()
        row = {
            "class": name,
            "images": int(mm.group(2)),
            "instances": int(mm.group(3)),
            "precision": float(mm.group(4)),
            "recall": float(mm.group(5)),
            "map50": float(mm.group(6)),
            "map50_95": float(mm.group(7)),
        }
        if name == "all":
            out["overall"] = row
        else:
            out["per_class"].append(row)
    return out


def _parse_args_yaml() -> Dict:
    path = TRAIN_RUN / "args.yaml"
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except OSError:
        return {}


def _dataset_info() -> Dict:
    info = {"yaml_exists": DATASET_YAML.exists(), "classes": CLASS_NAMES, "nc": 10,
            "splits": {}}
    if DATASET_YAML.exists():
        try:
            cfg = yaml.safe_load(DATASET_YAML.read_text(encoding="utf-8")) or {}
            info["nc"] = cfg.get("nc", 10)
            info["classes"] = list(cfg.get("names", CLASS_NAMES))
            root = Path(cfg.get("path", ""))
            for split in ("train", "val", "test"):
                sub = cfg.get(split, "")
                images_dir = root / sub
                count = len(list(images_dir.glob("*.jpg"))) if images_dir.is_dir() else 0
                info["splits"][split] = {"path": str(images_dir), "images": count}
        except (OSError, yaml.YAMLError):
            pass
    return info


# ---------------------------------------------------------------------------
# Endpoints (GET only)
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health() -> Dict:
    events = _load_events()
    return {
        "status": "ok",
        "model_present": MODEL_PATH.exists(),
        "model_path": str(MODEL_PATH),
        "violations_logged": len(events),
        "snapshots": len(list(SNAPSHOTS_DIR.glob("*.png"))) if SNAPSHOTS_DIR.exists() else 0,
        "processed_video_present": PROCESSED_VIDEO.exists(),
        "train_run_present": (TRAIN_RUN / "results.csv").exists(),
        "test_eval_present": TEST_EVAL.exists(),
    }


@app.get("/api/summary")
def summary() -> Dict:
    events = _load_events()
    helmet_missing = sum(1 for e in events if "helmet" in (e.get("missing") or []))
    vest_missing = sum(1 for e in events if "safety vest" in (e.get("missing") or []))
    log_rows = _read_results_csv()
    tables = _parse_log_tables()

    latest = events[-1] if events else None
    return {
        "model_present": MODEL_PATH.exists(),
        "violations_confirmed": len(events),
        "alerts_generated": len(events),
        "helmet_violations": helmet_missing,
        "vest_violations": vest_missing,
        "persons_detected_latest": 1 if latest else 0,
        "latest_event": latest,
        "snapshot_count": len(list(SNAPSHOTS_DIR.glob("*.png"))) if SNAPSHOTS_DIR.exists() else 0,
        "processed_video_present": PROCESSED_VIDEO.exists(),
        "processed_video_size": PROCESSED_VIDEO.stat().st_size if PROCESSED_VIDEO.exists() else 0,
        "training": {
            "run_name": "ppe_smoke",
            "epochs_completed": len(log_rows),
            "duration_hours": tables.get("duration_hours"),
            "final": log_rows[-1] if log_rows else None,
            "best_map50_epoch": max(log_rows, key=lambda r: r["map50"]) if log_rows else None,
            "overall_valid": tables.get("overall"),
        },
    }


@app.get("/api/events")
def events() -> List[Dict]:
    return list(reversed(_load_events()))  # newest first


@app.get("/api/snapshots")
def snapshots() -> List[Dict]:
    if not SNAPSHOTS_DIR.exists():
        return []
    out = []
    for p in sorted(SNAPSHOTS_DIR.glob("*.png"), key=lambda x: x.stat().st_mtime, reverse=True):
        st = p.stat()
        out.append({"filename": p.name, "size_bytes": st.st_size,
                    "modified": st.st_mtime, "url": f"/api/snapshots/{p.name}"})
    return out


@app.get("/api/snapshots/{name}")
def snapshot_file(name: str) -> FileResponse:
    p = SNAPSHOTS_DIR / name
    if not p.exists() or p.parent != SNAPSHOTS_DIR:
        raise HTTPException(status_code=404, detail="snapshot not found")
    return FileResponse(p, media_type="image/png")


# ---------------------------------------------------------------------------
# Browser-compatible video copy (additive; pipeline output is never modified)
# ---------------------------------------------------------------------------
# detect.py writes MP4 with OpenCV's "mp4v" fourcc (MPEG-4 Part 2), which
# Chromium/Firefox cannot demux. To make playback work in the dashboard we
# lazily create an H.264 copy alongside the original (..._web.mp4). The
# original processed_site_video.mp4 is left byte-identical; if transcoding is
# unavailable the endpoint falls back to serving the original bytes.
_web_video_lock = threading.Lock()


def _ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _ensure_web_video() -> bool:
    """Create outputs/videos/processed_site_video_web.mp4 (H.264) if needed."""
    if not PROCESSED_VIDEO.exists():
        return False
    with _web_video_lock:
        if (WEB_VIDEO.exists()
                and WEB_VIDEO.stat().st_mtime >= PROCESSED_VIDEO.stat().st_mtime):
            return True
        exe = _ffmpeg_exe()
        if exe is None:
            return False
        tmp = WEB_VIDEO.with_suffix(".mp4.tmp")
        cmd = [
            exe, "-y", "-i", str(PROCESSED_VIDEO),
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-an",
            "-f", "mp4",  # .tmp suffix hides the container from ffmpeg
            str(tmp),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=300)
            if tmp.exists() and tmp.stat().st_size > 0:
                os.replace(tmp, WEB_VIDEO)
                return True
        except Exception:
            pass
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
        return False


@app.get("/api/videos")
def videos() -> List[Dict]:
    if not VIDEOS_DIR.exists():
        return []
    out = []
    for p in sorted(VIDEOS_DIR.glob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.name == WEB_VIDEO.name:  # internal browser copy; don't double-list
            continue
        out.append({"filename": p.name, "size_bytes": p.stat().st_size,
                    "url": f"/api/videos/{p.name}"})
    return out


@app.get("/api/videos/{name}")
def video_file(name: str) -> FileResponse:
    p = VIDEOS_DIR / name
    if not p.exists() or p.parent != VIDEOS_DIR:
        raise HTTPException(status_code=404, detail="video not found")
    # Transparently serve the H.264 web copy for the processed video so it
    # plays in the browser; the original file on disk is never touched.
    if name == PROCESSED_VIDEO.name and _ensure_web_video():
        return FileResponse(WEB_VIDEO, media_type="video/mp4",
                            filename=PROCESSED_VIDEO.name)
    return FileResponse(p, media_type="video/mp4")


@app.get("/api/training")
def training() -> Dict:
    rows = _read_results_csv()
    tables = _parse_log_tables()
    return {
        "run_name": "ppe_smoke",
        "epochs": rows,
        "epochs_completed": len(rows),
        "duration_hours": tables.get("duration_hours"),
        "overall_valid": tables.get("overall"),
        "per_class_valid": tables.get("per_class"),
        "args": _parse_args_yaml(),
        "artifacts": {
            "results_csv": (TRAIN_RUN / "results.csv").exists(),
            "results_png": (TRAIN_RUN / "results.png").exists(),
            "confusion_matrix": (TRAIN_RUN / "confusion_matrix.png").exists(),
        },
    }


@app.get("/api/dataset")
def dataset() -> Dict:
    return _dataset_info()


@app.get("/api/test-eval")
def test_eval() -> Dict:
    """Test-split artifacts are the PR/F1/confusion PNGs; metrics were not
    persisted to disk by the evaluation run, so none are served here."""
    return {
        "exists": TEST_EVAL.exists(),
        "artifacts": sorted(p.name for p in TEST_EVAL.glob("*.png")) if TEST_EVAL.exists() else [],
        "note": "Metrics printed by the eval run were not persisted; see runs/detect/test_eval/ plots.",
    }


# ---------------------------------------------------------------------------
# LIVE CAMERA — PROTOTYPE (additive; isolated outputs/live_camera/ area)
# ---------------------------------------------------------------------------
# Laptop webcam frames (JPEG from the browser) -> EXISTING model + EXISTING
# detect.process_detections() (tracking, PPE association, 8-frame persistence)
# -> EXISTING AlertManager pointed at the ISOLATED live output area. The
# prerecorded-video pipeline and outputs/alerts + outputs/snapshots are never
# touched here. Webcam is a PROTOTYPE source only; no CCTV/RTSP is claimed.


@app.post("/api/live/start")
async def live_start() -> Dict:
    try:
        return await run_in_threadpool(live_session.get_session().start)
    except Exception as exc:  # e.g. friendly ModelMissingError from detect.load_model
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/live/stop")
async def live_stop() -> Dict:
    return await run_in_threadpool(live_session.get_session().stop)


@app.post("/api/live/frame")
async def live_frame(request: Request) -> Dict:
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="empty JPEG body")
    # Inference runs in the threadpool so /api/health etc. stay responsive;
    # the session lock ensures a single concurrent inference (skip-if-busy).
    return await run_in_threadpool(live_session.get_session().process_frame, body)


@app.get("/api/live/status")
def live_status() -> Dict:
    return live_session.get_session().status()


@app.get("/api/live/events")
def live_events() -> List[Dict]:
    """Events from the ISOLATED live log only (outputs/live_camera/)."""
    return live_session.read_live_events()


@app.get("/api/live/snapshots/{name}")
def live_snapshot_file(name: str) -> FileResponse:
    p = live_session.LIVE_SNAPSHOTS_DIR / name
    if not p.exists() or p.parent != live_session.LIVE_SNAPSHOTS_DIR:
        raise HTTPException(status_code=404, detail="live snapshot not found")
    return FileResponse(p, media_type="image/png")
