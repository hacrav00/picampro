"""
preview_canvas.py — PiCamPro Live Feed Canvas
==============================================
Renders camera frames inside a Tkinter Canvas at a configurable frame rate.
Handles the thread-safe bridge between the camera capture thread and the
Tkinter event loop using a queue and after() scheduling.
Supports digital zoom, FPS overlay, and a stylish NO-SIGNAL placeholder.
"""

import tkinter as tk
import queue
import logging
import cv2
import numpy as np
from PIL import Image, ImageTk, ImageDraw, ImageFont
from typing import Optional

from utils.zoom import apply_zoom
from utils.fps_counter import FPSCounter

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Colour constants (dark neon theme)
# ---------------------------------------------------------------------------
OVERLAY_BG    = (0, 0, 0, 140)       # semi-transparent black (RGBA)
ACCENT_COLOUR = (0, 212, 170)         # teal  (#00d4aa)
WARN_COLOUR   = (248, 81, 73)         # red   (#f85149)
TEXT_COLOUR   = (230, 237, 243)       # near-white


class PreviewCanvas(tk.Frame):
    """
    A Tkinter Frame containing a Canvas that displays live camera frames.

    Public interface:
        push_frame(bgr_frame)     — feed a new OpenCV BGR frame
        set_zoom(level)           — change zoom level (1.0–8.0)
        set_target_fps(fps)       — display refresh rate (not camera FPS)
        set_recording(flag)       — show/hide REC indicator
        set_no_signal()           — show the NO SIGNAL placeholder
    """

    # How often the canvas polls the frame queue (ms)
    _POLL_MS = 16   # ≈ 60 Hz max canvas refresh

    def __init__(self, parent, bg_colour: str = "#0d1117", **kwargs):
        super().__init__(parent, bg=bg_colour, **kwargs)
        self._bg_colour = bg_colour
        self._frame_queue: queue.Queue = queue.Queue(maxsize=4)
        self._current_photo: Optional[ImageTk.PhotoImage] = None
        self._image_id: Optional[int] = None
        self._zoom: float = 1.0
        self._target_fps: int = 30
        self._recording: bool = False
        self._no_signal: bool = True
        self._fps_counter = FPSCounter(window=60)

        # Canvas
        self._canvas = tk.Canvas(
            self, bg=bg_colour, highlightthickness=0, cursor="crosshair"
        )
        self._canvas.pack(fill=tk.BOTH, expand=True)

        # Start the rendering loop
        self._render_loop()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def push_frame(self, bgr_frame: np.ndarray) -> None:
        """
        Thread-safe: put a new BGR frame into the render queue.
        If the queue is full the oldest frame is dropped (live preview
        should always show the most recent frame).
        """
        if self._frame_queue.full():
            try:
                self._frame_queue.get_nowait()
            except queue.Empty:
                pass
        try:
            self._frame_queue.put_nowait(bgr_frame)
        except queue.Full:
            pass

    def set_zoom(self, level: float) -> None:
        self._zoom = max(1.0, min(8.0, level))

    def set_target_fps(self, fps: int) -> None:
        self._target_fps = max(1, min(120, fps))

    def set_recording(self, flag: bool) -> None:
        self._recording = flag

    def set_no_signal(self) -> None:
        self._no_signal = True

    def get_display_fps(self) -> float:
        return self._fps_counter.get_fps()

    # ------------------------------------------------------------------
    # Rendering loop
    # ------------------------------------------------------------------

    def _render_loop(self) -> None:
        """Tkinter after() loop — runs in the main thread."""
        try:
            bgr = self._frame_queue.get_nowait()
            self._no_signal = False
            self._draw_frame(bgr)
        except queue.Empty:
            if self._no_signal:
                self._draw_no_signal()

        # Reschedule based on target FPS
        delay = max(8, int(1000 / max(1, self._target_fps)))
        self.after(delay, self._render_loop)

    def _draw_frame(self, bgr: np.ndarray) -> None:
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if cw < 2 or ch < 2:
            return

        # Apply digital zoom
        if self._zoom > 1.0:
            bgr = apply_zoom(bgr, self._zoom)

        # Convert BGR → RGB and resize to canvas
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        fh, fw = rgb.shape[:2]

        # Letterbox / pillarbox to maintain aspect ratio
        scale = min(cw / fw, ch / fh)
        nw, nh = int(fw * scale), int(fh * scale)
        resized = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_LINEAR)

        # Embed into black background
        canvas_img = np.zeros((ch, cw, 3), dtype=np.uint8)
        ox = (cw - nw) // 2
        oy = (ch - nh) // 2
        canvas_img[oy:oy+nh, ox:ox+nw] = resized

        # Overlay: FPS + zoom + REC badge
        self._draw_overlays(canvas_img)

        self._fps_counter.tick()
        self._update_canvas(canvas_img)

    def _draw_overlays(self, img: np.ndarray) -> None:
        h, w = img.shape[:2]
        fps  = self._fps_counter.get_fps()

        # Top-left: FPS counter
        fps_text = f"FPS: {fps:5.1f}"
        self._put_text(img, fps_text, (10, 28),
                       colour=ACCENT_COLOUR, scale=0.65)

        # Top-left line 2: zoom
        if self._zoom > 1.01:
            self._put_text(img, f"ZOOM {self._zoom:.1f}×", (10, 52),
                           colour=(255, 210, 50), scale=0.60)

        # Top-right: REC indicator
        if self._recording:
            self._put_text(img, "● REC", (w - 90, 28),
                           colour=WARN_COLOUR, scale=0.65, bold=True)

    @staticmethod
    def _put_text(img, text, pos, colour=(255,255,255),
                  scale=0.6, bold=False) -> None:
        thickness = 2 if bold else 1
        # Shadow for readability
        cv2.putText(img, text, (pos[0]+1, pos[1]+1),
                    cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thickness + 1,
                    cv2.LINE_AA)
        cv2.putText(img, text, pos,
                    cv2.FONT_HERSHEY_SIMPLEX, scale, colour, thickness,
                    cv2.LINE_AA)

    def _draw_no_signal(self) -> None:
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if cw < 2 or ch < 2:
            return

        # Dark gradient-like background using numpy
        bg = np.zeros((ch, cw, 3), dtype=np.uint8)
        # Subtle vertical gradient  (#0d1117 → #161b22)
        for y in range(ch):
            v = int(13 + (22 - 13) * y / max(ch, 1))
            bg[y, :] = [v, v + 2, v + 4]

        # Centre cross / icon
        cx, cy = cw // 2, ch // 2
        r = min(cw, ch) // 6
        col = (30, 50, 60)
        cv2.circle(bg, (cx, cy), r, col, 2)
        cv2.line(bg, (cx - r, cy), (cx + r, cy), col, 2)
        cv2.line(bg, (cx, cy - r), (cx, cy + r), col, 2)

        # Text
        self._put_text(bg, "NO SIGNAL", (cx - 68, cy + r + 30),
                       colour=(60, 90, 100), scale=0.75)
        self._put_text(bg, "Connect a camera and press  Refresh",
                       (cx - 130, cy + r + 58),
                       colour=(40, 60, 70), scale=0.45)

        self._update_canvas(bg)

    def _update_canvas(self, rgb_img: np.ndarray) -> None:
        pil_img = Image.fromarray(
            cv2.cvtColor(rgb_img, cv2.COLOR_BGR2RGB)
            if rgb_img.shape[2] == 3 else rgb_img
        )
        photo = ImageTk.PhotoImage(image=pil_img)
        if self._image_id is None:
            self._image_id = self._canvas.create_image(0, 0, anchor=tk.NW, image=photo)
        else:
            self._canvas.itemconfig(self._image_id, image=photo)
        self._current_photo = photo   # keep reference alive
