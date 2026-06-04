"""
timelapse.py — PiCamPro Interval Auto-Capture
=============================================
Runs a background thread that fires a callback at a user-defined interval.
The callback is responsible for taking the actual snapshot.
"""

import threading
import logging
import time
import uuid
from typing import Callable, Optional

log = logging.getLogger(__name__)


class TimelapseCapturer:
    """
    Fires a user-supplied capture callback every *interval_secs* seconds.

    Usage:
        def on_tick(frame_index: int, session_id: str):
            ...take photo...

        tl = TimelapseCapturer(on_tick)
        tl.start(interval_secs=5)
        ...
        tl.stop()
    """

    def __init__(self, callback: Callable[[int, str], None]):
        """
        Args:
            callback: Called with (frame_index, session_id) on each tick.
        """
        self._callback = callback
        self._interval: float = 5.0
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._frame_index: int = 0
        self._session_id: str = ""
        self._running: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def frame_count(self) -> int:
        return self._frame_index

    @property
    def session_id(self) -> str:
        return self._session_id

    def start(self, interval_secs: float = 5.0) -> None:
        """
        Begin the timelapse.  A new session ID is generated each time.
        Args:
            interval_secs: Seconds between captures (min 1 s, max 3600 s).
        """
        if self._running:
            log.warning("Timelapse already running.")
            return

        self._interval = max(1.0, min(3600.0, interval_secs))
        self._session_id = time.strftime("TL_%Y%m%d_%H%M%S")
        self._frame_index = 0
        self._stop_event.clear()
        self._running = True

        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="timelapse"
        )
        self._thread.start()
        log.info("Timelapse started — session=%s  interval=%.1fs",
                 self._session_id, self._interval)

    def stop(self) -> None:
        """Stop the timelapse after the current tick completes."""
        if not self._running:
            return
        self._stop_event.set()
        self._running = False
        log.info("Timelapse stopped — %d frames captured", self._frame_index)

    def set_interval(self, interval_secs: float) -> None:
        """Change interval while running. Takes effect on next tick."""
        self._interval = max(1.0, min(3600.0, interval_secs))
        log.info("Timelapse interval updated to %.1f s", self._interval)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """Worker thread: sleep → fire callback → repeat."""
        while not self._stop_event.is_set():
            # Wait for the interval (wakes early if stop() is called)
            cancelled = self._stop_event.wait(timeout=self._interval)
            if cancelled:
                break

            self._frame_index += 1
            try:
                self._callback(self._frame_index, self._session_id)
            except Exception as e:
                log.error("Timelapse callback error: %s", e)
