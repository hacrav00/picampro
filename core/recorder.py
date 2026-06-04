"""
recorder.py — PiCamPro Video Recording Engine
=============================================
Handles H.264 / MP4 recording for both:
  - libcamera (CSI) cameras  → Picamera2 H264Encoder (hardware-accelerated)
  - V4L2 / USB cameras       → OpenCV VideoWriter (MJPEG / mp4v)

After stopping, attempts to mux the raw .h264 into .mp4 via ffmpeg.
"""

import logging
import subprocess
import threading
import time
import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from core.camera_manager import CameraInfo

log = logging.getLogger(__name__)

# Prefer mp4v, fall back to XVID for broader codec availability
_FOURCC_PRIORITY = ["mp4v", "avc1", "XVID", "MJPG"]


class Recorder:
    """
    Records video to disk.

    For libcamera cameras: attach a Picamera2 instance via attach_picam2()
    and call start_recording() / stop_recording().

    For V4L2/USB cameras: call write_frame() on every captured frame.
    """

    def __init__(self, camera_info: "CameraInfo"):
        self._info = camera_info
        self._picam2 = None
        self._cv_writer: Optional[cv2.VideoWriter] = None
        self._output_path: Optional[Path] = None
        self._recording = False
        self._lock = threading.Lock()
        self._start_time: float = 0.0
        self._frame_count: int = 0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def elapsed(self) -> float:
        """Seconds elapsed since recording started."""
        if not self._recording:
            return 0.0
        return time.monotonic() - self._start_time

    @property
    def output_path(self) -> Optional[Path]:
        return self._output_path

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def attach_picam2(self, picam2) -> None:
        """Inject a running Picamera2 instance (libcamera cameras only)."""
        self._picam2 = picam2

    # ------------------------------------------------------------------
    # libcamera recording path
    # ------------------------------------------------------------------

    def start_recording_libcamera(self, output_path: Path,
                                  quality: int = 20) -> bool:
        """
        Start hardware H.264 recording via Picamera2.
        *quality*: H264 quantisation parameter (lower = better, ~20 is good).
        """
        if self._recording:
            log.warning("Already recording.")
            return False
        if self._picam2 is None:
            log.error("No Picamera2 instance attached.")
            return False

        try:
            from picamera2.encoders import H264Encoder, Quality
            from picamera2.outputs import FileOutput

            output_path.parent.mkdir(parents=True, exist_ok=True)
            # Record to a .h264 file first; mux to mp4 on stop
            h264_path = output_path.with_suffix(".h264")
            encoder = H264Encoder(bitrate=None, qp=quality)
            self._picam2.start_recording(encoder, str(h264_path))
            self._output_path = h264_path
            self._recording = True
            self._start_time = time.monotonic()
            self._frame_count = 0
            log.info("libcamera recording started → %s", h264_path)
            return True
        except Exception as e:
            log.error("Failed to start libcamera recording: %s", e)
            return False

    def stop_recording_libcamera(self) -> Optional[Path]:
        """Stop libcamera recording and mux to MP4 if possible."""
        if not self._recording or self._picam2 is None:
            return None
        try:
            self._picam2.stop_recording()
            self._recording = False
            log.info("libcamera recording stopped. Duration: %.1fs", self.elapsed)
            return self._mux_to_mp4(self._output_path)
        except Exception as e:
            log.error("Failed to stop libcamera recording: %s", e)
            self._recording = False
            return self._output_path

    # ------------------------------------------------------------------
    # V4L2 / USB recording path
    # ------------------------------------------------------------------

    def start_recording_v4l2(self, output_path: Path,
                              width: int, height: int,
                              fps: float) -> bool:
        """Open an OpenCV VideoWriter for USB camera recording."""
        if self._recording:
            log.warning("Already recording.")
            return False

        output_path.parent.mkdir(parents=True, exist_ok=True)
        mp4_path = output_path.with_suffix(".mp4")

        writer = None
        for cc_str in _FOURCC_PRIORITY:
            fourcc = cv2.VideoWriter_fourcc(*cc_str)
            writer = cv2.VideoWriter(str(mp4_path), fourcc, fps, (width, height))
            if writer.isOpened():
                log.info("VideoWriter opened with codec '%s'", cc_str)
                break
            writer.release()
            writer = None

        if writer is None:
            log.error("Could not open VideoWriter — no working codec found.")
            return False

        self._cv_writer = writer
        self._output_path = mp4_path
        self._recording = True
        self._start_time = time.monotonic()
        self._frame_count = 0
        log.info("V4L2 recording started → %s", mp4_path)
        return True

    def write_frame(self, frame: np.ndarray) -> None:
        """Feed a BGR frame to the OpenCV writer. Call each captured frame."""
        with self._lock:
            if self._recording and self._cv_writer is not None:
                self._cv_writer.write(frame)
                self._frame_count += 1

    def stop_recording_v4l2(self) -> Optional[Path]:
        """Finalise the OpenCV video file."""
        with self._lock:
            if not self._recording:
                return None
            self._recording = False
            if self._cv_writer:
                self._cv_writer.release()
                self._cv_writer = None
            log.info("V4L2 recording stopped. Frames: %d  Duration: %.1fs",
                     self._frame_count, self.elapsed)
            return self._output_path

    # ------------------------------------------------------------------
    # Unified stop (auto-dispatches to correct path)
    # ------------------------------------------------------------------

    def stop_recording(self) -> Optional[Path]:
        if self._info.source == "libcamera":
            return self.stop_recording_libcamera()
        else:
            return self.stop_recording_v4l2()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _mux_to_mp4(self, h264_path: Optional[Path]) -> Optional[Path]:
        """Wrap a raw .h264 file into an .mp4 container using ffmpeg."""
        if h264_path is None or not h264_path.exists():
            return h264_path

        mp4_path = h264_path.with_suffix(".mp4")
        cmd = [
            "ffmpeg", "-y",
            "-i", str(h264_path),
            "-c:v", "copy",
            str(mp4_path),
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=120, check=True)
            h264_path.unlink(missing_ok=True)
            log.info("Muxed to MP4: %s", mp4_path)
            return mp4_path
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            log.warning("ffmpeg mux failed (%s) — keeping .h264", e)
            return h264_path
