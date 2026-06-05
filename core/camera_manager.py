"""
camera_manager.py — PiCamPro Camera Detection & Capabilities
=============================================================
Detects all connected cameras (CSI/MIPI via libcamera AND USB via V4L2),
queries their hardware-supported resolutions, frame rates, and formats.
Works on every Raspberry Pi version and with cameras from any manufacturer.
"""

import subprocess
import re
import os
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SensorMode:
    """A single resolution / framerate / format mode for a camera."""
    width: int
    height: int
    fps_max: float
    fps_min: float = 1.0
    format: str = "SRGGB10"          # pixel format string

    @property
    def label(self) -> str:
        return f"{self.width}×{self.height}  @{self.fps_max:.0f}fps"

    @property
    def resolution_tuple(self) -> Tuple[int, int]:
        return (self.width, self.height)


@dataclass
class CameraInfo:
    """Full description of one camera device."""
    index: int                        # v4l2 /dev/videoN index or libcamera index
    name: str                         # human-readable name
    source: str                       # "libcamera" | "v4l2"
    device_path: str                  # e.g. /dev/video0
    modes: List[SensorMode] = field(default_factory=list)
    max_width: int = 0
    max_height: int = 0
    max_fps: float = 30.0
    supports_raw: bool = False

    @property
    def label(self) -> str:
        return f"[{self.source.upper()}] {self.name}  (max {self.max_width}×{self.max_height})"

    @property
    def max_resolution(self) -> Tuple[int, int]:
        return (self.max_width, self.max_height)

    def sorted_modes(self) -> List[SensorMode]:
        """Sorted highest resolution first."""
        return sorted(self.modes, key=lambda m: m.width * m.height, reverse=True)

    def resolutions_for_ui(self) -> List[Tuple[int, int]]:
        """Deduplicated resolution list for dropdown, highest first."""
        seen = set()
        result = []
        for m in self.sorted_modes():
            key = (m.width, m.height)
            if key not in seen:
                seen.add(key)
                result.append(key)
        return result


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def _run(cmd: List[str], timeout: int = 10) -> str:
    """Run a shell command, return stdout. Returns '' on error."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout
    except Exception as e:
        log.debug("Command %s failed: %s", cmd, e)
        return ""


def _detect_libcamera_cameras() -> List[CameraInfo]:
    """
    Parse `rpicam-hello --list-cameras` (or libcamera-hello on older OS).
    Returns CameraInfo objects for all CSI / MIPI cameras found.
    """
    cameras: List[CameraInfo] = []

    # Try rpicam-hello first (Bookworm+), fall back to libcamera-hello (Bullseye)
    for cmd_prefix in ["rpicam-hello", "libcamera-hello"]:
        raw = _run([cmd_prefix, "--list-cameras"])
        if raw.strip():
            break
    else:
        log.info("No libcamera cameras detected (rpicam-hello / libcamera-hello unavailable).")
        return cameras

    # -----------------------------------------------------------------------
    # Example output:
    #   Available cameras
    #   -----------------
    #   0 : imx708 [4608x2592 10-bit RGGB] (/base/axi/pcie@120000/rp1/i2c@88000/imx708@1a)
    #       Modes: 'SRGGB10_CSI2P' : 1536x864 [120.13 fps] ...
    # -----------------------------------------------------------------------
    current_cam: Optional[CameraInfo] = None
    current_fmt = "UNKNOWN"

    for line in raw.splitlines():
        # Camera header line: "0 : imx708 [4608x2592 ...]"
        cam_header = re.match(r"^\s*(\d+)\s*:\s*(.+?)\s*\[(\d+)x(\d+)", line)
        if cam_header:
            idx   = int(cam_header.group(1))
            name  = cam_header.group(2).strip()
            w_max = int(cam_header.group(3))
            h_max = int(cam_header.group(4))
            current_cam = CameraInfo(
                index=idx,
                name=name,
                source="libcamera",
                device_path=f"/dev/video{idx}",
                max_width=w_max,
                max_height=h_max,
            )
            cameras.append(current_cam)
            current_fmt = "UNKNOWN"
            continue

        if current_cam:
            # Check for a line starting a new format group:
            # e.g., "    Modes: 'SRGGB10_CSI2P' : 1536x864 [120.13 fps]"
            mode_format_match = re.search(
                r"'([^']+)'\s*:\s*(\d+)x(\d+)\s*\[([0-9.]+)\s*fps\s*(?:-\s*([0-9.]+)\s*fps)?",
                line,
            )
            if mode_format_match:
                current_fmt = mode_format_match.group(1)
                mw       = int(mode_format_match.group(2))
                mh       = int(mode_format_match.group(3))
                fps_max  = float(mode_format_match.group(4))
                fps_min  = float(mode_format_match.group(5)) if mode_format_match.group(5) else 1.0
                current_cam.modes.append(SensorMode(mw, mh, fps_max, fps_min, current_fmt))
                current_cam.max_fps = max(current_cam.max_fps, fps_max)
                if "RAW" in current_fmt.upper() or "DNG" in current_fmt.upper():
                    current_cam.supports_raw = True
                continue

            # Check for a line continuing the current format group:
            # e.g., "                             1536x864 [120.13 fps]"
            mode_continue_match = re.search(
                r"^\s*(\d+)x(\d+)\s*\[([0-9.]+)\s*fps\s*(?:-\s*([0-9.]+)\s*fps)?",
                line,
            )
            if mode_continue_match:
                mw       = int(mode_continue_match.group(1))
                mh       = int(mode_continue_match.group(2))
                fps_max  = float(mode_continue_match.group(3))
                fps_min  = float(mode_continue_match.group(4)) if mode_continue_match.group(4) else 1.0
                current_cam.modes.append(SensorMode(mw, mh, fps_max, fps_min, current_fmt))
                current_cam.max_fps = max(current_cam.max_fps, fps_max)

    # Ensure each camera has at least its max resolution as a mode
    for cam in cameras:
        if not cam.modes:
            cam.modes.append(SensorMode(cam.max_width, cam.max_height, cam.max_fps))

    return cameras


def _v4l2_list_devices() -> Dict[str, str]:
    """
    Run `v4l2-ctl --list-devices`, return {device_name: /dev/videoX} map.
    """
    raw = _run(["v4l2-ctl", "--list-devices"])
    devices: Dict[str, str] = {}
    current_name = None
    for line in raw.splitlines():
        line = line.rstrip()
        if not line:
            current_name = None
            continue
        if not line.startswith("\t") and not line.startswith("    "):
            current_name = line.rstrip(":").strip()
        else:
            path = line.strip()
            if re.match(r"^/dev/video\d+$", path) and current_name:
                devices.setdefault(current_name, path)
    return devices


def _v4l2_framesizes(device: str) -> List[SensorMode]:
    """
    Query supported frame sizes via `v4l2-ctl --list-formats-ext` for a device.
    Handles MJPEG and YUYV (and any other format the camera exposes).
    """
    raw = _run(["v4l2-ctl", "--device", device, "--list-formats-ext"])
    modes: List[SensorMode] = []

    current_fmt = "UNKNOWN"
    for line in raw.splitlines():
        # "[0]: 'MJPG' (Motion-JPEG)"
        fmt_match = re.search(r"'\s*([A-Z0-9]+)\s*'", line)
        if fmt_match and "Pixel Format" not in line and "[" in line:
            current_fmt = fmt_match.group(1)

        # "Size: Discrete 3840x2160"
        sz_match = re.match(r"\s+Size: Discrete (\d+)x(\d+)", line)
        if sz_match:
            w = int(sz_match.group(1))
            h = int(sz_match.group(2))
            # We'll fill fps on the next lines; add placeholder
            modes.append(SensorMode(w, h, 30.0, 1.0, current_fmt))
            continue

        # "Interval: Discrete 0.033s (30.000 fps)"
        fps_match = re.search(r"\(([0-9.]+)\s*fps\)", line)
        if fps_match and modes:
            fps = float(fps_match.group(1))
            modes[-1].fps_max = max(modes[-1].fps_max, fps)

    # Remove duplicates (keep highest fps per resolution)
    dedup: Dict[Tuple[int, int], SensorMode] = {}
    for m in modes:
        key = (m.width, m.height)
        if key not in dedup or m.fps_max > dedup[key].fps_max:
            dedup[key] = m
    return list(dedup.values())


def _detect_v4l2_cameras(skip_paths: set) -> List[CameraInfo]:
    """
    Enumerate USB / V4L2 cameras that weren't already found via libcamera.
    Works with any brand (Logitech, Sony, Canon, Insta360, etc.).
    """
    cameras: List[CameraInfo] = []
    device_map = _v4l2_list_devices()

    # Also scan /dev/video* directly in case v4l2-ctl --list-devices fails
    video_nodes = sorted(f for f in os.listdir("/dev") if re.match(r"video\d+$", f))

    processed = set()
    for node in video_nodes:
        dev_path = f"/dev/{node}"
        if dev_path in skip_paths:
            continue
        if dev_path in processed:
            continue
        processed.add(dev_path)

        # Get camera name via v4l2-ctl --info
        info_raw = _run(["v4l2-ctl", "--device", dev_path, "--info"])
        if not info_raw:
            continue

        # Filter out non-capture devices (metadata nodes, etc.)
        if "Device Caps" not in info_raw and "Driver name" not in info_raw:
            continue
        if "Video Capture" not in info_raw:
            continue

        cam_name = dev_path
        name_match = re.search(r"Card type\s*:\s*(.+)", info_raw)
        if name_match:
            cam_name = name_match.group(1).strip()

        # Detect from device_map for better names
        for mapped_name, mapped_path in device_map.items():
            if mapped_path == dev_path:
                cam_name = mapped_name
                break

        idx = int(re.search(r"\d+$", node).group())
        modes = _v4l2_framesizes(dev_path)

        if not modes:
            # Minimum capability: assume 640x480 @ 30fps
            modes = [SensorMode(640, 480, 30.0)]

        max_mode = max(modes, key=lambda m: m.width * m.height)
        cam = CameraInfo(
            index=idx,
            name=cam_name,
            source="v4l2",
            device_path=dev_path,
            modes=modes,
            max_width=max_mode.width,
            max_height=max_mode.height,
            max_fps=max(m.fps_max for m in modes),
        )
        cameras.append(cam)
        log.info("V4L2 camera detected: %s at %s  max=%dx%d",
                 cam_name, dev_path, cam.max_width, cam.max_height)

    return cameras


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_all_cameras() -> List[CameraInfo]:
    """
    Main entry point. Detect every camera on the system:
      1. CSI/MIPI cameras via libcamera (rpicam-hello / libcamera-hello)
      2. USB cameras (any brand) via V4L2

    Returns a list of CameraInfo objects sorted by source then index.
    """
    log.info("Scanning for cameras...")
    lc_cameras = _detect_libcamera_cameras()

    # Collect /dev paths already claimed by libcamera
    claimed = {c.device_path for c in lc_cameras}

    v4l2_cameras = _detect_v4l2_cameras(skip_paths=claimed)

    all_cameras = lc_cameras + v4l2_cameras
    if not all_cameras:
        log.warning("No cameras detected!")
    else:
        for cam in all_cameras:
            log.info("Found: %s", cam.label)

    return all_cameras


def refresh_cameras() -> List[CameraInfo]:
    """Hot-reload camera list (call when user plugs in a new camera)."""
    return detect_all_cameras()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    cams = detect_all_cameras()
    for c in cams:
        print(c.label)
        for m in c.sorted_modes():
            print("  ", m.label)
