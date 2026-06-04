"""
status_bar.py — PiCamPro Bottom Status Bar
==========================================
Displays live FPS, camera info, recording duration, and storage usage.
"""

import tkinter as tk
from tkinter import ttk
import time
import threading
from typing import Optional


# Palette
_BG      = "#0a0e17"
_FG      = "#8b949e"
_ACCENT  = "#00d4aa"
_RED     = "#f85149"
_BORDER  = "#21262d"


class StatusBar(tk.Frame):
    """
    Fixed-height bar along the bottom of the main window.

    Sections (left → right):
      [camera_label] | [fps_label] | [resolution_label] | [rec_timer] | [storage]
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=_BG, height=28, **kwargs)
        self.pack_propagate(False)

        # Top border
        tk.Frame(self, bg=_BORDER, height=1).pack(side=tk.TOP, fill=tk.X)

        # --- Camera name ---
        self._cam_var = tk.StringVar(value="No camera")
        self._cam_lbl = tk.Label(
            self, textvariable=self._cam_var,
            bg=_BG, fg=_ACCENT,
            font=("Courier New", 9), padx=10
        )
        self._cam_lbl.pack(side=tk.LEFT)

        self._sep(side=tk.LEFT)

        # --- Live FPS ---
        self._fps_var = tk.StringVar(value="FPS: --.-")
        tk.Label(
            self, textvariable=self._fps_var,
            bg=_BG, fg=_FG, font=("Courier New", 9), padx=10
        ).pack(side=tk.LEFT)

        self._sep(side=tk.LEFT)

        # --- Resolution ---
        self._res_var = tk.StringVar(value="--×--")
        tk.Label(
            self, textvariable=self._res_var,
            bg=_BG, fg=_FG, font=("Courier New", 9), padx=10
        ).pack(side=tk.LEFT)

        # --- Storage (right-aligned) ---
        self._storage_var = tk.StringVar(value="Storage: --")
        tk.Label(
            self, textvariable=self._storage_var,
            bg=_BG, fg=_FG, font=("Courier New", 9), padx=10
        ).pack(side=tk.RIGHT)

        self._sep(side=tk.RIGHT)

        # --- Recording timer ---
        self._rec_var = tk.StringVar(value="")
        self._rec_lbl = tk.Label(
            self, textvariable=self._rec_var,
            bg=_BG, fg=_RED,
            font=("Courier New", 9, "bold"), padx=10
        )
        self._rec_lbl.pack(side=tk.RIGHT)

        # Blinking rec dot state
        self._rec_blink = False
        self._rec_start: Optional[float] = None
        self._blink_job: Optional[str] = None

    # ------------------------------------------------------------------
    # Public update methods (safe to call from any thread via after_idle)
    # ------------------------------------------------------------------

    def update_camera(self, name: str) -> None:
        self._cam_var.set(f"  {name}")

    def update_fps(self, fps: float) -> None:
        self._fps_var.set(f"FPS: {fps:5.1f}")

    def update_resolution(self, w: int, h: int) -> None:
        self._res_var.set(f"{w}×{h}")

    def update_storage(self, used_str: str, pct: float) -> None:
        bar_filled = int(pct / 10)
        bar = "█" * bar_filled + "░" * (10 - bar_filled)
        colour = _RED if pct > 85 else _FG
        self._storage_var.set(f"{used_str}  [{bar}] {pct:.0f}%")
        self._storage_var.set.__self__   # just to avoid "unused" warning

    def start_recording_indicator(self) -> None:
        self._rec_start = time.monotonic()
        self._blink_rec()

    def stop_recording_indicator(self) -> None:
        if self._blink_job:
            self.after_cancel(self._blink_job)
            self._blink_job = None
        self._rec_var.set("")
        self._rec_start = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _sep(self, side=tk.LEFT) -> None:
        tk.Frame(self, bg=_BORDER, width=1).pack(
            side=side, fill=tk.Y, padx=0, pady=4
        )

    def _blink_rec(self) -> None:
        if self._rec_start is None:
            return
        elapsed = time.monotonic() - self._rec_start
        h = int(elapsed // 3600)
        m = int((elapsed % 3600) // 60)
        s = int(elapsed % 60)
        dot = "●" if self._rec_blink else "○"
        self._rec_blink = not self._rec_blink
        self._rec_var.set(f"{dot} REC  {h:02d}:{m:02d}:{s:02d}")
        self._blink_job = self.after(500, self._blink_rec)
