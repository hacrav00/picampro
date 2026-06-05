"""
storage.py — PiCamPro File & Directory Management
==================================================
Manages the on-device directory structure and provides helpers for
naming capture files and querying disk usage.
"""

import os
import time
import shutil
import logging
from pathlib import Path
from typing import Tuple

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Base paths — uses the ACTUAL logged-in user's home directory
# Works for any username (pi, i4mt, ubuntu, etc.)
# ---------------------------------------------------------------------------
BASE_DIR      = Path.home() / "PiCamPro"
PHOTO_DIR     = BASE_DIR / "captures" / "photos"
VIDEO_DIR     = BASE_DIR / "captures" / "videos"
TIMELAPSE_DIR = BASE_DIR / "captures" / "timelapse"
LOG_DIR       = BASE_DIR / "logs"

ALL_DIRS = [PHOTO_DIR, VIDEO_DIR, TIMELAPSE_DIR, LOG_DIR]


def ensure_dirs() -> None:
    """Create all required directories if they do not exist."""
    for d in ALL_DIRS:
        d.mkdir(parents=True, exist_ok=True)
    log.info("Storage directories ready at %s", BASE_DIR)


def _ts() -> str:
    """Return a compact timestamp string suitable for filenames."""
    return time.strftime("%Y%m%d_%H%M%S")


# ---------------------------------------------------------------------------
# Path generators
# ---------------------------------------------------------------------------

def get_photo_path(ext: str = "jpg", camera_name: str = "cam") -> Path:
    safe_name = _safe(camera_name)
    return PHOTO_DIR / f"{safe_name}_{_ts()}.{ext}"


def get_video_path(ext: str = "mp4", camera_name: str = "cam") -> Path:
    safe_name = _safe(camera_name)
    return VIDEO_DIR / f"{safe_name}_{_ts()}.{ext}"


def get_timelapse_path(session_id: str, frame_idx: int,
                       ext: str = "jpg", camera_name: str = "cam") -> Path:
    safe_name = _safe(camera_name)
    session_dir = TIMELAPSE_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir / f"{safe_name}_frame{frame_idx:06d}.{ext}"


def _safe(name: str) -> str:
    """Strip characters unsafe for filenames."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)[:32]


# ---------------------------------------------------------------------------
# Disk usage
# ---------------------------------------------------------------------------

def get_disk_usage() -> Tuple[int, int, float]:
    """
    Returns (used_bytes, total_bytes, percent_used) for the partition
    containing BASE_DIR.
    """
    try:
        stat = shutil.disk_usage(str(BASE_DIR))
        used = stat.used
        total = stat.total
        pct = (used / total * 100) if total > 0 else 0.0
        return used, total, pct
    except Exception as e:
        log.warning("Could not query disk usage: %s", e)
        return 0, 1, 0.0


def human_size(nbytes: int) -> str:
    """Convert bytes to human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes //= 1024
    return f"{nbytes:.1f} PB"


def count_files() -> Tuple[int, int, int]:
    """Returns (photo_count, video_count, timelapse_count)."""
    def _count(d: Path) -> int:
        if not d.exists():
            return 0
        return sum(1 for f in d.rglob("*") if f.is_file())
    return _count(PHOTO_DIR), _count(VIDEO_DIR), _count(TIMELAPSE_DIR)
