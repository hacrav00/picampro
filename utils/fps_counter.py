"""
fps_counter.py — Real-time FPS Measurement
==========================================
Uses a rolling window of frame timestamps to compute smooth FPS.
"""

import time
from collections import deque


class FPSCounter:
    """
    Tracks frames per second using a sliding-window average.

    Usage:
        counter = FPSCounter(window=30)
        ...
        counter.tick()           # call once per frame
        fps = counter.get_fps()  # read current average FPS
    """

    def __init__(self, window: int = 60):
        """
        Args:
            window: Number of recent frame timestamps to keep.
                    Larger → smoother but slower to react to changes.
        """
        self._times: deque = deque(maxlen=window)

    def tick(self) -> None:
        """Record a frame timestamp. Call this once per captured frame."""
        self._times.append(time.monotonic())

    def get_fps(self) -> float:
        """Return the current rolling average FPS (0.0 if insufficient data)."""
        if len(self._times) < 2:
            return 0.0
        elapsed = self._times[-1] - self._times[0]
        if elapsed <= 0:
            return 0.0
        return (len(self._times) - 1) / elapsed

    def reset(self) -> None:
        self._times.clear()

    @property
    def frame_count(self) -> int:
        return len(self._times)
