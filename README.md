# PiCamPro

**Universal Raspberry Pi Camera Viewer & Controller**

A professional, full-featured desktop camera application that works with **any camera** connected to **any Raspberry Pi version**.

---

## ✨ Features

| Feature | Details |
|---|---|
| 🎥 **Live Preview** | Smooth real-time feed at configurable FPS |
| 📐 **Variable Resolution** | Auto-detected from camera hardware — up to 8K for supported cameras |
| ⚡ **Variable Frame Rate** | 1–120 FPS slider (capped to camera hardware max) |
| 🔍 **Digital Zoom** | 1×–8× centre-crop zoom in real time |
| ⏺️ **Video Recording** | Hardware H.264 (CSI cameras) or MP4 (USB cameras) |
| 📸 **Snapshots** | Full-resolution JPEG or PNG capture |
| ⏱️ **Timelapse** | Auto-capture at any interval (1 second – 1 hour) |
| 🔌 **Multi-Camera** | Detect and switch between all connected cameras |
| 💾 **On-Device Storage** | All files saved to `/home/pi/PiCamPro/` |
| 📊 **Disk Monitor** | Live storage usage display with low-space warning |

---

## 📷 Supported Cameras

| Camera Type | Support |
|---|---|
| Raspberry Pi Camera Module 1/2/3 | ✅ Full (via libcamera) |
| Raspberry Pi HQ Camera (IMX477) | ✅ Full (via libcamera) |
| Raspberry Pi HQ Camera (IMX708) | ✅ Full (via libcamera) |
| Any USB Webcam (Logitech, Sony, etc.) | ✅ Full (via V4L2) |
| Any USB camera with 4K/8K support | ✅ Auto-detected resolution |
| Third-party CSI cameras | ✅ If libcamera driver available |

> **Note**: 8K support depends entirely on the connected camera's hardware.
> PiCamPro automatically detects the camera's maximum resolution and offers
> it in the resolution dropdown — it never limits you artificially.

---

## 🖥️ Supported Raspberry Pi Versions

- Raspberry Pi Zero W / Zero 2 W
- Raspberry Pi 1 (Model A/B)
- Raspberry Pi 2, 3 (Model A/B/B+)
- Raspberry Pi 4 (all RAM variants)
- Raspberry Pi 5
- Raspberry Pi Compute Module (any version)

**OS Support**: Raspberry Pi OS Bookworm (recommended), Bullseye, Buster

---

## 🚀 Quick Start

### 1. Install

```bash
cd /path/to/picampro
chmod +x install.sh
./install.sh
```

### 2. Run

```bash
python3 picampro.py
```

Optional flags:
```bash
python3 picampro.py --fullscreen   # start in fullscreen
python3 picampro.py --debug        # verbose logging
```

### 3. Double-click launcher

After installation, a **PiCamPro** shortcut appears on your desktop.

---

## 📁 File Structure

```
/home/pi/PiCamPro/
├── captures/
│   ├── photos/          ← snapshots (JPEG/PNG)
│   ├── videos/          ← recordings (.mp4 / .h264)
│   └── timelapse/       ← timed auto-captures
│       └── TL_20240604_120000/
│           ├── cam_frame000001.jpg
│           └── ...
└── logs/
    └── picampro.log
```

---

## 🎮 Controls

| Control | Action |
|---|---|
| **Camera dropdown** | Switch between detected cameras |
| **⟳ Refresh** | Re-scan for newly connected cameras |
| **Resolution dropdown** | Change stream resolution |
| **FPS slider** | Target frame rate (1–120, capped to camera max) |
| **Zoom slider** | Digital zoom 1×–8× |
| **⏺ Record** | Start/stop video recording |
| **📷 Snapshot** | Capture a still photo immediately |
| **▶ Timelapse** | Start/stop interval auto-capture |
| **Interval** | Seconds between timelapse frames (1–3600) |

---

## 🔧 Manual Dependency Install

If `install.sh` fails, install manually:

```bash
# System packages
sudo apt update
sudo apt install python3-picamera2 python3-opencv python3-pil python3-pil.imagetk \
                 python3-tk v4l-utils ffmpeg

# Check detected cameras
rpicam-hello --list-cameras          # CSI cameras
v4l2-ctl --list-devices              # USB cameras
```

---

## 🐛 Troubleshooting

**No cameras detected?**
- CSI: `rpicam-hello --list-cameras` — check ribbon cable
- USB: `lsusb` and `ls /dev/video*` — check USB connection
- Check camera is enabled: `sudo raspi-config` → Interface Options → Camera

**Low FPS on Pi Zero/Pi 1?**
- Lower the resolution (e.g. 640×480 or 1280×720)
- Reduce FPS slider to 15–24
- Use MJPEG USB cameras (lighter CPU load)

**Recording saves as .h264 not .mp4?**
- Install ffmpeg: `sudo apt install ffmpeg`

---

## 📜 License

MIT License — free to use, modify, and distribute.
