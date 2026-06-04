"""
control_panel.py — PiCamPro Right Sidebar Controls
===================================================
Contains all user-facing camera controls in a scrollable dark-themed sidebar:
  • Camera selector (with refresh button)
  • Resolution dropdown
  • Frame rate slider
  • Digital zoom slider
  • Record / Snapshot buttons
  • Timelapse controls
  • Storage info
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
from typing import Callable, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from core.camera_manager import CameraInfo

log = logging.getLogger(__name__)

# ── Palette ──────────────────────────────────────────────────────────────────
C_BG        = "#0d1117"
C_PANEL     = "#161b22"
C_BORDER    = "#21262d"
C_TEXT      = "#e6edf3"
C_MUTED     = "#8b949e"
C_ACCENT    = "#00d4aa"
C_ACCENT_DK = "#009e7f"
C_RED       = "#f85149"
C_RED_DK    = "#b91c1c"
C_BTN       = "#21262d"
C_BTN_HV    = "#30363d"
C_YELLOW    = "#f0b429"
C_SECTION   = "#1c2128"

FONT_LABEL  = ("Segoe UI", 9)
FONT_VALUE  = ("Segoe UI", 10, "bold")
FONT_BTN    = ("Segoe UI", 10, "bold")
FONT_TITLE  = ("Segoe UI", 8)
FONT_HEAD   = ("Segoe UI", 9, "bold")


def _make_button(parent, text, command, bg=C_BTN, fg=C_TEXT,
                 hover_bg=C_BTN_HV, **kw) -> tk.Button:
    btn = tk.Button(
        parent, text=text, command=command,
        bg=bg, fg=fg, activebackground=hover_bg, activeforeground=fg,
        relief=tk.FLAT, bd=0, padx=12, pady=6,
        font=FONT_BTN, cursor="hand2", **kw
    )
    btn.bind("<Enter>", lambda e: btn.config(bg=hover_bg))
    btn.bind("<Leave>", lambda e: btn.config(bg=bg))
    return btn


def _section_label(parent, text: str) -> tk.Label:
    lbl = tk.Label(
        parent, text=text.upper(),
        bg=C_PANEL, fg=C_MUTED,
        font=FONT_TITLE, anchor="w"
    )
    return lbl


def _separator(parent) -> tk.Frame:
    return tk.Frame(parent, bg=C_BORDER, height=1)


class ControlPanel(tk.Frame):
    """
    Sidebar widget.  Callbacks are injected by the parent window so this
    module stays decoupled from the rest of the app.
    """

    def __init__(self, parent,
                 on_camera_change: Callable[["CameraInfo"], None],
                 on_resolution_change: Callable[[Tuple[int, int]], None],
                 on_fps_change: Callable[[int], None],
                 on_zoom_change: Callable[[float], None],
                 on_record_toggle: Callable[[], None],
                 on_snapshot: Callable[[], None],
                 on_timelapse_toggle: Callable[[], None],
                 on_timelapse_interval_change: Callable[[float], None],
                 on_refresh_cameras: Callable[[], None],
                 **kwargs):
        super().__init__(parent, bg=C_PANEL, width=290, **kwargs)
        self.pack_propagate(False)

        # Store callbacks
        self._on_camera_change      = on_camera_change
        self._on_resolution_change  = on_resolution_change
        self._on_fps_change         = on_fps_change
        self._on_zoom_change        = on_zoom_change
        self._on_record_toggle      = on_record_toggle
        self._on_snapshot           = on_snapshot
        self._on_timelapse_toggle   = on_timelapse_toggle
        self._on_interval_change    = on_timelapse_interval_change
        self._on_refresh            = on_refresh_cameras

        # State
        self._cameras: List["CameraInfo"] = []
        self._selected_camera: Optional["CameraInfo"] = None
        self._is_recording = False
        self._is_timelapse = False

        # Internal tk variables
        self._cam_var     = tk.StringVar()
        self._res_var     = tk.StringVar()
        self._fps_var     = tk.IntVar(value=30)
        self._zoom_var    = tk.DoubleVar(value=1.0)
        self._tl_interval = tk.DoubleVar(value=5.0)

        self._build_ui()

    # ──────────────────────────────────────────────────────────────────
    # UI Construction
    # ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        pad = dict(padx=14, pady=4)

        # ── Header ──
        hdr = tk.Frame(self, bg="#0d1117", height=50)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(
            hdr, text="🎥  PiCamPro", bg="#0d1117", fg=C_ACCENT,
            font=("Segoe UI", 13, "bold"), anchor="w"
        ).pack(side=tk.LEFT, padx=14, pady=12)

        # Left border accent
        tk.Frame(self, bg=C_BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y)

        # Scrollable inner area
        canvas = tk.Canvas(self, bg=C_PANEL, highlightthickness=0)
        scroll = tk.Scrollbar(self, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._inner = tk.Frame(canvas, bg=C_PANEL)
        self._inner_id = canvas.create_window((0, 0), window=self._inner,
                                               anchor="nw")
        self._inner.bind("<Configure>",
                         lambda e: canvas.configure(
                             scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(
                        self._inner_id, width=e.width))

        inner = self._inner

        # ── Camera Section ──
        self._build_section(inner, "Camera")
        # Dropdown
        self._cam_combo = ttk.Combobox(
            inner, textvariable=self._cam_var,
            state="readonly", font=FONT_LABEL
        )
        self._cam_combo.pack(fill=tk.X, **pad)
        self._cam_combo.bind("<<ComboboxSelected>>", self._on_cam_selected)

        # Refresh button
        _make_button(
            inner, "⟳  Refresh Cameras", self._on_refresh,
            bg=C_BTN, fg=C_MUTED
        ).pack(fill=tk.X, padx=14, pady=(0, 8))

        _separator(inner).pack(fill=tk.X, padx=14, pady=6)

        # ── Resolution Section ──
        self._build_section(inner, "Resolution")
        self._res_combo = ttk.Combobox(
            inner, textvariable=self._res_var,
            state="readonly", font=FONT_LABEL
        )
        self._res_combo.pack(fill=tk.X, **pad)
        self._res_combo.bind("<<ComboboxSelected>>", self._on_res_selected)
        self._caps_lbl = tk.Label(
            inner, text="Hardware max: --",
            bg=C_PANEL, fg=C_MUTED, font=("Segoe UI", 8), anchor="w"
        )
        self._caps_lbl.pack(fill=tk.X, padx=14)

        _separator(inner).pack(fill=tk.X, padx=14, pady=6)

        # ── Frame Rate ──
        self._build_section(inner, "Frame Rate")
        fps_row = tk.Frame(inner, bg=C_PANEL)
        fps_row.pack(fill=tk.X, padx=14)
        self._fps_slider = tk.Scale(
            fps_row, from_=1, to=120, orient=tk.HORIZONTAL,
            variable=self._fps_var,
            bg=C_PANEL, fg=C_TEXT, troughcolor=C_BTN,
            highlightthickness=0, activebackground=C_ACCENT,
            font=FONT_LABEL, showvalue=False,
            command=self._on_fps_moved
        )
        self._fps_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._fps_val_lbl = tk.Label(
            fps_row, text="30 fps",
            bg=C_PANEL, fg=C_ACCENT, font=FONT_VALUE, width=7
        )
        self._fps_val_lbl.pack(side=tk.LEFT)

        _separator(inner).pack(fill=tk.X, padx=14, pady=6)

        # ── Zoom ──
        self._build_section(inner, "Digital Zoom")
        zoom_row = tk.Frame(inner, bg=C_PANEL)
        zoom_row.pack(fill=tk.X, padx=14)
        self._zoom_slider = tk.Scale(
            zoom_row, from_=1.0, to=8.0, resolution=0.1,
            orient=tk.HORIZONTAL, variable=self._zoom_var,
            bg=C_PANEL, fg=C_TEXT, troughcolor=C_BTN,
            highlightthickness=0, activebackground=C_ACCENT,
            font=FONT_LABEL, showvalue=False,
            command=self._on_zoom_moved
        )
        self._zoom_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._zoom_val_lbl = tk.Label(
            zoom_row, text="1.0×",
            bg=C_PANEL, fg=C_ACCENT, font=FONT_VALUE, width=5
        )
        self._zoom_val_lbl.pack(side=tk.LEFT)

        _separator(inner).pack(fill=tk.X, padx=14, pady=6)

        # ── Record / Snapshot ──
        self._build_section(inner, "Capture")

        self._rec_btn = _make_button(
            inner, "⏺  Start Recording", self._toggle_record,
            bg="#1a0a0a", fg="#ff6b6b",
            hover_bg="#2a0f0f"
        )
        self._rec_btn.pack(fill=tk.X, padx=14, pady=(4, 3))

        _make_button(
            inner, "📷  Take Snapshot", self._on_snapshot,
            bg=C_BTN, fg=C_TEXT
        ).pack(fill=tk.X, padx=14, pady=3)

        _separator(inner).pack(fill=tk.X, padx=14, pady=6)

        # ── Timelapse ──
        self._build_section(inner, "Timelapse")

        self._tl_btn = _make_button(
            inner, "▶  Start Timelapse", self._toggle_timelapse,
            bg=C_BTN, fg=C_TEXT
        )
        self._tl_btn.pack(fill=tk.X, padx=14, pady=(4, 3))

        tl_row = tk.Frame(inner, bg=C_PANEL)
        tl_row.pack(fill=tk.X, padx=14, pady=3)
        tk.Label(tl_row, text="Interval:", bg=C_PANEL, fg=C_MUTED,
                 font=FONT_LABEL).pack(side=tk.LEFT)
        self._tl_spin = tk.Spinbox(
            tl_row, from_=1, to=3600, increment=1,
            textvariable=self._tl_interval,
            width=6, font=FONT_LABEL,
            bg=C_BTN, fg=C_TEXT, insertbackground=C_TEXT,
            buttonbackground=C_BTN, relief=tk.FLAT,
            command=self._on_interval_spin
        )
        self._tl_spin.pack(side=tk.LEFT, padx=6)
        tk.Label(tl_row, text="sec", bg=C_PANEL, fg=C_MUTED,
                 font=FONT_LABEL).pack(side=tk.LEFT)

        self._tl_count_lbl = tk.Label(
            inner, text="Frames captured: 0",
            bg=C_PANEL, fg=C_MUTED, font=("Segoe UI", 8), anchor="w"
        )
        self._tl_count_lbl.pack(fill=tk.X, padx=14)

        _separator(inner).pack(fill=tk.X, padx=14, pady=6)

        # ── Storage ──
        self._build_section(inner, "Storage")
        self._storage_lbl = tk.Label(
            inner, text="Used: --  /  Total: --",
            bg=C_PANEL, fg=C_MUTED, font=("Segoe UI", 8), anchor="w"
        )
        self._storage_lbl.pack(fill=tk.X, padx=14)
        self._disk_bar_canvas = tk.Canvas(
            inner, bg=C_BTN, height=6, highlightthickness=0
        )
        self._disk_bar_canvas.pack(fill=tk.X, padx=14, pady=4)
        self._file_count_lbl = tk.Label(
            inner, text="Photos: 0  Videos: 0  TL: 0",
            bg=C_PANEL, fg=C_MUTED, font=("Segoe UI", 8), anchor="w"
        )
        self._file_count_lbl.pack(fill=tk.X, padx=14, pady=(0, 16))

    def _build_section(self, parent, title: str):
        lbl = tk.Label(
            parent, text=f"  {title.upper()}",
            bg=C_SECTION, fg=C_MUTED,
            font=FONT_TITLE, anchor="w", pady=5
        )
        lbl.pack(fill=tk.X, pady=(8, 2))

    # ──────────────────────────────────────────────────────────────────
    # Public update methods
    # ──────────────────────────────────────────────────────────────────

    def update_cameras(self, cameras: List["CameraInfo"]) -> None:
        self._cameras = cameras
        labels = [c.label for c in cameras]
        self._cam_combo["values"] = labels
        if cameras:
            self._cam_combo.current(0)
            self._select_camera(cameras[0])

    def set_recording(self, recording: bool) -> None:
        self._is_recording = recording
        if recording:
            self._rec_btn.config(
                text="⏹  Stop Recording",
                bg="#2a0000", fg=C_RED,
                activebackground="#3a0000"
            )
        else:
            self._rec_btn.config(
                text="⏺  Start Recording",
                bg="#1a0a0a", fg="#ff6b6b",
                activebackground="#2a0f0f"
            )

    def set_timelapse(self, running: bool) -> None:
        self._is_timelapse = running
        if running:
            self._tl_btn.config(
                text="⏹  Stop Timelapse",
                bg=C_ACCENT_DK, fg="#fff",
                activebackground=C_ACCENT
            )
        else:
            self._tl_btn.config(
                text="▶  Start Timelapse",
                bg=C_BTN, fg=C_TEXT,
                activebackground=C_BTN_HV
            )

    def update_timelapse_count(self, count: int) -> None:
        self._tl_count_lbl.config(text=f"Frames captured: {count}")

    def update_storage_display(self, used_str: str, total_str: str,
                                pct: float,
                                photos: int, videos: int, tl: int) -> None:
        self._storage_lbl.config(
            text=f"Used: {used_str}  /  Total: {total_str}"
        )
        self._file_count_lbl.config(
            text=f"Photos: {photos}  Videos: {videos}  TL: {tl}"
        )
        # Draw usage bar
        w = self._disk_bar_canvas.winfo_width()
        if w > 0:
            self._disk_bar_canvas.delete("all")
            fill_w = int(w * pct / 100)
            colour = C_RED if pct > 85 else (C_YELLOW if pct > 65 else C_ACCENT)
            self._disk_bar_canvas.create_rectangle(
                0, 0, fill_w, 6, fill=colour, outline=""
            )

    # ──────────────────────────────────────────────────────────────────
    # Internal event handlers
    # ──────────────────────────────────────────────────────────────────

    def _on_cam_selected(self, _event=None):
        idx = self._cam_combo.current()
        if 0 <= idx < len(self._cameras):
            self._select_camera(self._cameras[idx])

    def _select_camera(self, cam: "CameraInfo"):
        self._selected_camera = cam
        # Populate resolution dropdown
        resolutions = cam.resolutions_for_ui()
        res_labels = [f"{w}×{h}" for w, h in resolutions]
        self._res_combo["values"] = res_labels
        if res_labels:
            self._res_combo.current(0)
        # Update caps label
        self._caps_lbl.config(
            text=f"Hardware max: {cam.max_width}×{cam.max_height}  @{cam.max_fps:.0f}fps"
        )
        # Cap FPS slider to camera max
        self._fps_slider.config(to=max(1, int(cam.max_fps)))
        cur_fps = min(self._fps_var.get(), int(cam.max_fps))
        self._fps_var.set(cur_fps)
        self._fps_val_lbl.config(text=f"{cur_fps} fps")
        # Fire callback
        self._on_camera_change(cam)

    def _on_res_selected(self, _event=None):
        val = self._res_var.get()
        try:
            w, h = (int(x) for x in val.split("×"))
            self._on_resolution_change((w, h))
        except Exception:
            pass

    def _on_fps_moved(self, val):
        fps = int(float(val))
        self._fps_val_lbl.config(text=f"{fps} fps")
        self._on_fps_change(fps)

    def _on_zoom_moved(self, val):
        z = round(float(val), 1)
        self._zoom_val_lbl.config(text=f"{z:.1f}×")
        self._on_zoom_change(z)

    def _toggle_record(self):
        self._on_record_toggle()

    def _toggle_timelapse(self):
        self._on_timelapse_toggle()

    def _on_interval_spin(self):
        try:
            v = float(self._tl_interval.get())
            self._on_interval_change(v)
        except Exception:
            pass
