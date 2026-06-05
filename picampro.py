#!/usr/bin/env python3
"""
picampro.py — PiCamPro Entry Point
====================================
Universal Raspberry Pi Camera Viewer & Controller

Supports:
  • All Raspberry Pi versions (Zero W, 1, 2, 3, 4, 5)
  • CSI/MIPI cameras via libcamera (rpicam-hello stack)
  • USB webcams from any manufacturer via V4L2
  • Cameras up to the hardware-reported maximum resolution (incl. 8K+ for
    cameras that support it)

Usage:
    python3 picampro.py [--debug]
"""

import sys
import argparse
import logging
import tkinter as tk

# ── Bootstrap logging before any other import ─────────────────────────────────
from pathlib import Path
from utils.logger import setup_logging
from core.storage import LOG_DIR, ensure_dirs

ensure_dirs()
_log_level = logging.DEBUG if "--debug" in sys.argv else logging.INFO
setup_logging(LOG_DIR, level=_log_level)

log = logging.getLogger(__name__)

# ── Import GUI (after logging is set up) ──────────────────────────────────────
from gui.app_window import AppWindow


def _check_platform():
    """Warn (but don't block) if not running on Linux / Raspberry Pi."""
    import platform
    if platform.system() != "Linux":
        log.warning(
            "PiCamPro is designed for Raspberry Pi OS (Linux). "
            "Running on %s — camera capture may not work without "
            "physical Raspberry Pi hardware.", platform.system()
        )


def _check_dependencies() -> bool:
    """
    Verify that critical Python packages are available.
    Returns True if all critical deps are present.
    """
    missing = []

    try:
        import cv2
    except ImportError:
        missing.append("opencv-python  (pip install opencv-python)")

    try:
        from PIL import Image
    except ImportError:
        missing.append("Pillow  (pip install Pillow)")

    if missing:
        log.error("Missing required packages:\n  " + "\n  ".join(missing))
        print("\n❌  PiCamPro cannot start — missing packages:\n")
        for m in missing:
            print(f"    • {m}")
        print("\nRun  install.sh  or install manually and try again.\n")
        return False

    # Picamera2 is optional (falls back to pure V4L2 for USB cameras)
    try:
        import picamera2
        _pc2_ver = getattr(picamera2, "__version__", "installed")
        log.info("picamera2 %s detected — CSI cameras supported.", _pc2_ver)
    except ImportError:
        log.info("picamera2 not available — CSI camera support disabled. "
                 "USB cameras will still work via V4L2.")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="PiCamPro — Universal Raspberry Pi Camera Viewer"
    )
    parser.add_argument("--debug", action="store_true",
                        help="Enable verbose debug logging")
    parser.add_argument("--fullscreen", action="store_true",
                        help="Start in fullscreen mode")
    args = parser.parse_args()

    _check_platform()
    if not _check_dependencies():
        sys.exit(1)

    log.info("=" * 60)
    log.info("  PiCamPro  v1.0.0  starting…")
    log.info("=" * 60)

    # ── Create Tk root ────────────────────────────────────────────────
    root = tk.Tk()
    root.configure(bg="#0d1117")

    # Set window icon if available
    icon_path = Path(__file__).parent / "assets" / "icon.png"
    if icon_path.exists():
        try:
            icon = tk.PhotoImage(file=str(icon_path))
            root.iconphoto(True, icon)
        except Exception:
            pass

    if args.fullscreen:
        root.attributes("-fullscreen", True)
        root.bind("<Escape>", lambda e: root.attributes("-fullscreen", False))

    # ── Launch app ────────────────────────────────────────────────────
    app = AppWindow(root)
    log.info("UI ready.")

    try:
        root.mainloop()
    except KeyboardInterrupt:
        log.info("Interrupted by user.")
    finally:
        log.info("PiCamPro exited.")


if __name__ == "__main__":
    main()
