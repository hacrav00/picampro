"""
app_window.py — PiCamPro Main Application Window
=================================================
Orchestrates:
  • Camera detection & switching
  • Live preview rendering
  • Recording, snapshots, timelapse
  • Periodic UI updates (FPS, storage, timelapse count)
  • Clean shutdown
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
import logging
import time
import cv2
import numpy as np
from pathlib import Path
from typing import Optional, List, Tuple

from core.camera_manager import detect_all_cameras, CameraInfo
from core.recorder        import Recorder
from core.snapshot        import SnapshotEngine
from core.timelapse       import TimelapseCapturer
from core.storage         import (
    ensure_dirs, get_photo_path, get_video_path,
    get_timelapse_path, get_disk_usage, human_size, count_files,
    PHOTO_DIR, VIDEO_DIR, TIMELAPSE_DIR, LOG_DIR
)
from gui.preview_canvas   import PreviewCanvas
from gui.control_panel    import ControlPanel
from gui.status_bar       import StatusBar
from gui.settings_dialog  import SettingsDialog

log = logging.getLogger(__name__)

# ── Theme colours ────────────────────────────────────────────────────────────
C_BG     = "#0d1117"
C_PANEL  = "#161b22"
C_BORDER = "#21262d"
C_TEXT   = "#e6edf3"
C_ACCENT = "#00d4aa"

# How often (ms) the main thread updates status displays
_STATUS_INTERVAL_MS = 1500


class AppWindow:
    """
    Top-level application controller.  Creates and wires together all GUI
    components, manages the camera capture thread, and handles all user events.
    """

    def __init__(self, root: tk.Tk):
        self._root = root
        self._root.title("PiCamPro — Universal Raspberry Pi Camera Viewer")
        self._root.configure(bg=C_BG)
        self._root.minsize(900, 560)
        self._root.geometry("1280x720")

        # Apply dark ttk theme
        self._apply_theme()

        # Ensure storage directories exist
        ensure_dirs()

        # State
        self._cameras: List[CameraInfo]      = []
        self._active_cam: Optional[CameraInfo] = None
        self._picam2                          = None   # Picamera2 instance
        self._cap: Optional[cv2.VideoCapture] = None  # V4L2 capture
        self._capture_thread: Optional[threading.Thread] = None
        self._capture_running = False
        self._current_res: Tuple[int, int]   = (1280, 720)
        self._target_fps: int                = 30
        self._snap_format: str               = "jpg"

        # Engines
        self._recorder:  Optional[Recorder]          = None
        self._snapshooter: Optional[SnapshotEngine]  = None
        self._timelapse:  TimelapseCapturer           = TimelapseCapturer(
            self._on_timelapse_tick
        )

        # Build UI
        self._build_layout()

        # Bind window events
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._root.bind("<Configure>", self._on_resize)

        # Start scanning for cameras asynchronously
        self._root.after(200, self._async_scan_cameras)

        # Periodic status refresh
        self._root.after(_STATUS_INTERVAL_MS, self._refresh_status)

    # ──────────────────────────────────────────────────────────────────
    # Layout
    # ──────────────────────────────────────────────────────────────────

    def _build_layout(self):
        """Build the three-panel layout: preview | sidebar | status bar."""

        # Menu bar
        menubar = tk.Menu(self._root, bg=C_PANEL, fg=C_TEXT,
                          activebackground=C_ACCENT, activeforeground="#000",
                          relief=tk.FLAT)
        file_menu = tk.Menu(menubar, tearoff=0, bg=C_PANEL, fg=C_TEXT,
                            activebackground=C_ACCENT, activeforeground="#000")
        file_menu.add_command(label="Open Storage Folder",
                              command=self._open_storage_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Settings…", command=self._open_settings)
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        cam_menu = tk.Menu(menubar, tearoff=0, bg=C_PANEL, fg=C_TEXT,
                           activebackground=C_ACCENT, activeforeground="#000")
        cam_menu.add_command(label="Refresh Cameras",
                             command=self._async_scan_cameras)
        menubar.add_cascade(label="Camera", menu=cam_menu)

        help_menu = tk.Menu(menubar, tearoff=0, bg=C_PANEL, fg=C_TEXT,
                            activebackground=C_ACCENT, activeforeground="#000")
        help_menu.add_command(label="About PiCamPro", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        self._root.configure(menu=menubar)

        # Main container
        main = tk.Frame(self._root, bg=C_BG)
        main.pack(fill=tk.BOTH, expand=True)

        # ── Preview (left, fills space) ──
        self._preview = PreviewCanvas(main, bg_colour=C_BG)
        self._preview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Vertical separator
        tk.Frame(main, bg=C_BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y)

        # ── Control panel (right sidebar) ──
        self._panel = ControlPanel(
            main,
            on_camera_change             = self._on_camera_change,
            on_resolution_change         = self._on_resolution_change,
            on_fps_change                = self._on_fps_change,
            on_zoom_change               = self._on_zoom_change,
            on_record_toggle             = self._on_record_toggle,
            on_snapshot                  = self._on_snapshot,
            on_timelapse_toggle          = self._on_timelapse_toggle,
            on_timelapse_interval_change = self._on_interval_change,
            on_refresh_cameras           = self._async_scan_cameras,
        )
        self._panel.pack(side=tk.RIGHT, fill=tk.Y)

        # ── Status bar (bottom) ──
        self._status = StatusBar(self._root)
        self._status.pack(side=tk.BOTTOM, fill=tk.X)

    # ──────────────────────────────────────────────────────────────────
    # Camera detection & switching
    # ──────────────────────────────────────────────────────────────────

    def _async_scan_cameras(self):
        """Scan in background thread so the UI stays responsive."""
        def _scan():
            cameras = detect_all_cameras()
            self._root.after(0, lambda: self._on_cameras_detected(cameras))

        t = threading.Thread(target=_scan, daemon=True, name="cam-scan")
        t.start()
        self._status.update_camera("Scanning for cameras…")

    def _on_cameras_detected(self, cameras: List[CameraInfo]):
        self._cameras = cameras
        self._panel.update_cameras(cameras)
        if cameras:
            self._status.update_camera(cameras[0].name)
        else:
            self._preview.set_no_signal()
            self._status.update_camera("No cameras found")
            messagebox.showwarning(
                "No Cameras",
                "No cameras detected.\n\n"
                "• For CSI cameras: check ribbon cable connection\n"
                "• For USB cameras: check USB connection\n"
                "• Run 'rpicam-hello --list-cameras' to diagnose\n\n"
                "Press  Camera → Refresh Cameras  to try again."
            )

    def _on_camera_change(self, cam: CameraInfo):
        """Called when user selects a different camera."""
        if self._active_cam is cam:
            return
        log.info("Switching to camera: %s", cam.label)
        self._stop_capture()
        self._active_cam = cam
        self._recorder   = Recorder(cam)
        self._snapshooter = SnapshotEngine(cam)

        # Pick default resolution (highest available, capped to 1920×1080
        # for smooth preview performance; full-res stills use switch_mode)
        modes = cam.sorted_modes()
        default_res = (cam.max_width, cam.max_height)
        for m in modes:
            if m.width <= 1920:
                default_res = (m.width, m.height)
                break
        self._current_res = default_res

        self._status.update_camera(cam.name)
        self._status.update_resolution(*default_res)
        self._start_capture()

    def _on_resolution_change(self, res: Tuple[int, int]):
        self._current_res = res
        self._status.update_resolution(*res)
        if self._active_cam:
            log.info("Resolution changed to %dx%d", *res)
            self._stop_capture()
            self._start_capture()

    def _on_fps_change(self, fps: int):
        self._target_fps = fps
        self._preview.set_target_fps(fps)

    def _on_zoom_change(self, zoom: float):
        self._preview.set_zoom(zoom)

    # ──────────────────────────────────────────────────────────────────
    # Capture thread
    # ──────────────────────────────────────────────────────────────────

    def _start_capture(self):
        if self._active_cam is None:
            return
        self._capture_running = True
        self._preview.set_no_signal()

        if self._active_cam.source == "libcamera":
            self._capture_thread = threading.Thread(
                target=self._libcamera_loop, daemon=True, name="capture-lc"
            )
        else:
            self._capture_thread = threading.Thread(
                target=self._v4l2_loop, daemon=True, name="capture-v4l2"
            )
        self._capture_thread.start()

    def _stop_capture(self):
        self._capture_running = False
        # Stop libcamera if running
        if self._picam2 is not None:
            try:
                self._picam2.stop()
                self._picam2.close()
            except Exception:
                pass
            self._picam2 = None
        # Release V4L2 capture
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
        # Wait for thread
        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=3.0)
        self._capture_thread = None

    def _libcamera_loop(self):
        """Background thread: read frames from Picamera2."""
        try:
            from picamera2 import Picamera2
        except ImportError:
            log.error("picamera2 not installed. Falling back to V4L2.")
            self._root.after(0, self._v4l2_fallback)
            return

        try:
            picam2 = Picamera2(self._active_cam.index)
            w, h   = self._current_res
            config = picam2.create_video_configuration(
                main={"size": (w, h), "format": "RGB888"},
                controls={"FrameRate": float(self._target_fps)},
            )
            picam2.configure(config)
            picam2.start()
            self._picam2 = picam2

            # Inject into recorder & snapshooter
            if self._recorder:
                self._recorder.attach_picam2(picam2)
            if self._snapshooter:
                self._snapshooter.attach_picam2(picam2)

            log.info("libcamera stream started  %dx%d @%dfps", w, h, self._target_fps)

            while self._capture_running:
                frame_rgb = picam2.capture_array("main")
                # Convert RGB → BGR for OpenCV pipeline
                frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                self._preview.push_frame(frame_bgr)
                if self._recorder and self._recorder.is_recording:
                    self._recorder.write_frame(frame_bgr)

        except Exception as e:
            log.error("libcamera loop error: %s", e)
            self._root.after(0, lambda: messagebox.showerror(
                "Camera Error", f"libcamera error:\n{e}"
            ))
        finally:
            if self._picam2 is not None:
                try:
                    self._picam2.stop()
                    self._picam2.close()
                except Exception:
                    pass
                self._picam2 = None

    def _v4l2_loop(self):
        """Background thread: read frames from a V4L2 / USB camera."""
        cam = self._active_cam
        if cam is None:
            return

        cap = cv2.VideoCapture(cam.device_path)
        if not cap.isOpened():
            log.error("Cannot open %s", cam.device_path)
            self._root.after(0, lambda: messagebox.showerror(
                "Camera Error",
                f"Cannot open camera:\n{cam.device_path}\n\n"
                "Check connection and permissions."
            ))
            return

        w, h = self._current_res
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        cap.set(cv2.CAP_PROP_FPS, self._target_fps)
        self._cap = cap

        log.info("V4L2 stream started  %dx%d  device=%s", w, h, cam.device_path)

        while self._capture_running:
            ret, frame = cap.read()
            if not ret:
                log.warning("V4L2 read failed, retrying…")
                time.sleep(0.05)
                continue
            self._preview.push_frame(frame)
            if self._recorder and self._recorder.is_recording:
                self._recorder.write_frame(frame)

        cap.release()
        self._cap = None

    def _v4l2_fallback(self):
        """Switch to V4L2 mode when libcamera is unavailable."""
        if self._active_cam:
            self._active_cam.source = "v4l2"
            self._start_capture()

    # ──────────────────────────────────────────────────────────────────
    # Recording
    # ──────────────────────────────────────────────────────────────────

    def _on_record_toggle(self):
        if self._recorder is None:
            messagebox.showwarning("No Camera", "Select a camera first.")
            return

        if self._recorder.is_recording:
            # Stop
            out = self._recorder.stop_recording()
            self._panel.set_recording(False)
            self._preview.set_recording(False)
            self._status.stop_recording_indicator()
            if out:
                log.info("Recording saved: %s", out)
                messagebox.showinfo("Recording Saved",
                                    f"Video saved to:\n{out}")
        else:
            # Start
            cam_name = self._active_cam.name if self._active_cam else "cam"
            w, h = self._current_res
            path = get_video_path(camera_name=cam_name)

            if self._active_cam and self._active_cam.source == "libcamera":
                ok = self._recorder.start_recording_libcamera(path)
            else:
                ok = self._recorder.start_recording_v4l2(
                    path, w, h, float(self._target_fps)
                )

            if ok:
                self._panel.set_recording(True)
                self._preview.set_recording(True)
                self._status.start_recording_indicator()
            else:
                messagebox.showerror("Recording Error",
                                     "Failed to start recording.")

    # ──────────────────────────────────────────────────────────────────
    # Snapshot
    # ──────────────────────────────────────────────────────────────────

    def _on_snapshot(self):
        if self._snapshooter is None:
            messagebox.showwarning("No Camera", "Select a camera first.")
            return

        cam_name = self._active_cam.name if self._active_cam else "cam"
        path = get_photo_path(ext=self._snap_format, camera_name=cam_name)

        # Try to grab latest frame from the preview
        # (for V4L2 and libcamera streaming mode, capture_from_frame is used)
        frame = self._get_last_frame()
        if frame is not None:
            ok = self._snapshooter.capture_from_frame(frame, path)
        else:
            ok = self._snapshooter.capture_full_res(path)

        if ok:
            messagebox.showinfo("Snapshot Saved",
                                f"Photo saved to:\n{path}")
        else:
            messagebox.showerror("Snapshot Failed",
                                 "Could not capture photo.")

    def _get_last_frame(self) -> Optional[np.ndarray]:
        """Grab one frame from the current capture source (non-blocking)."""
        try:
            if self._cap is not None and self._cap.isOpened():
                ret, frame = self._cap.read()
                return frame if ret else None
            if self._picam2 is not None:
                rgb = self._picam2.capture_array("main")
                return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        except Exception as e:
            log.warning("get_last_frame error: %s", e)
        return None

    # ──────────────────────────────────────────────────────────────────
    # Timelapse
    # ──────────────────────────────────────────────────────────────────

    def _on_timelapse_toggle(self):
        if self._timelapse.is_running:
            self._timelapse.stop()
            self._panel.set_timelapse(False)
        else:
            if self._active_cam is None:
                messagebox.showwarning("No Camera", "Select a camera first.")
                return
            interval = 5.0
            self._timelapse.start(interval_secs=interval)
            self._panel.set_timelapse(True)

    def _on_interval_change(self, interval: float):
        self._timelapse.set_interval(interval)

    def _on_timelapse_tick(self, frame_idx: int, session_id: str):
        """Called from the timelapse thread — capture one frame."""
        if self._snapshooter is None or self._active_cam is None:
            return
        cam_name = self._active_cam.name
        path = get_timelapse_path(session_id, frame_idx,
                                  ext=self._snap_format,
                                  camera_name=cam_name)
        frame = self._get_last_frame()
        if frame is not None:
            self._snapshooter.capture_from_frame(frame, path)
        # Update count on UI thread
        self._root.after(0,
            lambda c=frame_idx: self._panel.update_timelapse_count(c))

    # ──────────────────────────────────────────────────────────────────
    # Periodic status refresh
    # ──────────────────────────────────────────────────────────────────

    def _refresh_status(self):
        try:
            fps = self._preview.get_display_fps()
            self._status.update_fps(fps)

            used, total, pct = get_disk_usage()
            photos, videos, tl = count_files()
            self._panel.update_storage_display(
                human_size(used), human_size(total), pct,
                photos, videos, tl
            )
            self._status.update_storage(human_size(used), pct)
        except Exception as e:
            log.debug("Status refresh error: %s", e)
        finally:
            self._root.after(_STATUS_INTERVAL_MS, self._refresh_status)

    # ──────────────────────────────────────────────────────────────────
    # Menu actions
    # ──────────────────────────────────────────────────────────────────

    def _open_settings(self):
        from core.storage import BASE_DIR
        dlg = SettingsDialog(
            self._root,
            current_storage_path=str(BASE_DIR),
            current_snap_format=self._snap_format,
        )
        self._root.wait_window(dlg)
        if dlg.accepted:
            self._snap_format = dlg.snap_format.get()
            log.info("Settings updated: fmt=%s  path=%s",
                     self._snap_format, dlg.storage_path)

    def _open_storage_folder(self):
        import subprocess, platform
        folder = str(LOG_DIR.parent)
        try:
            if platform.system() == "Linux":
                subprocess.Popen(["xdg-open", folder])
            elif platform.system() == "Windows":
                subprocess.Popen(["explorer", folder])
        except Exception as e:
            log.warning("Could not open folder: %s", e)
            messagebox.showinfo("Storage Location", f"Files are stored at:\n{folder}")

    def _show_about(self):
        messagebox.showinfo(
            "About PiCamPro",
            "PiCamPro  v1.0.0\n\n"
            "Universal Raspberry Pi Camera Viewer\n"
            "Supports all RPi versions, CSI cameras, and\n"
            "USB webcams from any manufacturer.\n\n"
            "Built with Picamera2 + libcamera + OpenCV"
        )

    # ──────────────────────────────────────────────────────────────────
    # Window lifecycle
    # ──────────────────────────────────────────────────────────────────

    def _on_resize(self, _event=None):
        pass  # Canvas handles its own scaling

    def _on_close(self):
        log.info("Shutting down PiCamPro…")
        if self._recorder and self._recorder.is_recording:
            if messagebox.askyesno("Recording Active",
                                   "A recording is in progress.\n"
                                   "Stop recording and quit?"):
                self._recorder.stop_recording()
            else:
                return
        if self._timelapse.is_running:
            self._timelapse.stop()
        self._stop_capture()
        self._root.destroy()

    # ──────────────────────────────────────────────────────────────────
    # Theme
    # ──────────────────────────────────────────────────────────────────

    def _apply_theme(self):
        style = ttk.Style(self._root)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(".", background=C_BG, foreground=C_TEXT,
                         fieldbackground=C_PANEL, troughcolor=C_PANEL,
                         selectbackground=C_ACCENT, selectforeground="#000",
                         insertcolor=C_TEXT, font=("Segoe UI", 10))

        style.configure("TCombobox",
                         fieldbackground=C_PANEL, background=C_PANEL,
                         foreground=C_TEXT, selectbackground=C_ACCENT,
                         arrowcolor=C_TEXT)
        style.map("TCombobox",
                  fieldbackground=[("readonly", C_PANEL)],
                  foreground=[("readonly", C_TEXT)],
                  selectbackground=[("readonly", C_ACCENT)])

        style.configure("TScrollbar",
                         background=C_PANEL, troughcolor=C_BG,
                         arrowcolor=C_TEXT, borderwidth=0)
