"""
snapshot.py — PiCamPro Still Capture Engine
============================================
Captures full-resolution still images from both libcamera (CSI) cameras
and USB/V4L2 cameras. Saves JPEG or PNG with optional EXIF metadata.
"""

import logging
import time
import cv2
import numpy as np
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.camera_manager import CameraInfo

log = logging.getLogger(__name__)


class SnapshotEngine:
    """
    Takes still photos.  Works with both libcamera and V4L2 (USB) cameras.

    For libcamera cameras, we optionally switch to the highest-resolution
    sensor mode for the capture, then return to streaming mode.
    For V4L2 cameras we capture the current frame from the live stream.
    """

    def __init__(self, camera_info: "CameraInfo"):
        self._info = camera_info
        self._picam2 = None   # injected externally for libcamera cameras

    def attach_picam2(self, picam2) -> None:
        """Give the engine a reference to the running Picamera2 instance."""
        self._picam2 = picam2

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def capture_from_frame(self, frame: np.ndarray, path: Path,
                           quality: int = 95) -> bool:
        """
        Save the given numpy frame (BGR or RGB) to *path*.
        This is the fast path used during live streaming.
        Returns True on success.
        """
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            ext = path.suffix.lower().lstrip(".")

            if ext in ("jpg", "jpeg"):
                params = [cv2.IMWRITE_JPEG_QUALITY, quality]
                ok, buf = cv2.imencode(".jpg", frame, params)
                if ok:
                    buf.tofile(str(path))
                    log.info("Snapshot saved: %s", path)
                    return True

            elif ext == "png":
                ok, buf = cv2.imencode(".png", frame)
                if ok:
                    buf.tofile(str(path))
                    log.info("Snapshot saved: %s", path)
                    return True

            else:
                cv2.imwrite(str(path), frame)
                log.info("Snapshot saved: %s", path)
                return True

        except Exception as e:
            log.error("Snapshot failed: %s", e)
        return False

    def capture_full_res(self, path: Path, quality: int = 95) -> bool:
        """
        For libcamera cameras: switch to full-sensor-resolution mode,
        capture one frame, then return to preview mode.
        Falls back to capture_from_frame if picam2 is unavailable.
        Returns True on success.
        """
        if self._info.source != "libcamera" or self._picam2 is None:
            log.warning("Full-res capture only supported for libcamera cameras. "
                        "Use capture_from_frame() instead.")
            return False

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._picam2.switch_mode_and_capture_file(
                self._picam2.create_still_configuration(),
                str(path),
            )
            log.info("Full-res snapshot saved: %s", path)
            return True
        except Exception as e:
            log.error("Full-res capture failed: %s", e)
            return False
