"""
zoom.py — PiCamPro Digital Zoom
================================
Centre-crop the frame to simulate optical zoom, then upscale back
to the original display dimensions using bicubic interpolation.
"""

import cv2
import numpy as np
from typing import Tuple


def apply_zoom(frame: np.ndarray, zoom: float) -> np.ndarray:
    """
    Apply digital zoom to a BGR/RGB numpy frame.

    Args:
        frame: H×W×C numpy array (any dtype).
        zoom:  Zoom level ≥ 1.0.  1.0 = no zoom, 2.0 = 2× zoom, etc.

    Returns:
        Frame cropped and upscaled to the original (H, W) dimensions.
    """
    if zoom <= 1.0:
        return frame

    h, w = frame.shape[:2]

    # Compute crop box
    crop_h = int(h / zoom)
    crop_w = int(w / zoom)
    crop_h = max(crop_h, 2)
    crop_w = max(crop_w, 2)

    y1 = (h - crop_h) // 2
    x1 = (w - crop_w) // 2
    y2 = y1 + crop_h
    x2 = x1 + crop_w

    cropped = frame[y1:y2, x1:x2]
    zoomed  = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_CUBIC)
    return zoomed


def zoom_label(zoom: float) -> str:
    """Return a human-readable zoom label, e.g. '2.0×'."""
    return f"{zoom:.1f}×"


def clamp_zoom(zoom: float, min_zoom: float = 1.0, max_zoom: float = 8.0) -> float:
    return max(min_zoom, min(max_zoom, zoom))


def get_zoom_steps(max_zoom: float = 8.0) -> list:
    """Return a list of discrete zoom presets."""
    steps = [1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0]
    return [z for z in steps if z <= max_zoom]
