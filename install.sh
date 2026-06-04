#!/usr/bin/env bash
# =============================================================================
#  install.sh — PiCamPro Installer
#  Works on: Raspberry Pi OS Bookworm, Bullseye, Buster (all versions)
#            Pi Zero W, Pi 1, Pi 2, Pi 3, Pi 4, Pi 5
# =============================================================================
set -e

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
CYAN="\033[36m"
RESET="\033[0m"

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STORAGE_DIR="/home/pi/PiCamPro"

echo -e "${CYAN}${BOLD}"
echo "  ╔═══════════════════════════════════════╗"
echo "  ║        PiCamPro  Installer            ║"
echo "  ║  Universal Raspberry Pi Camera Viewer ║"
echo "  ╚═══════════════════════════════════════╝"
echo -e "${RESET}"

# ── Detect OS ────────────────────────────────────────────────────────────────
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_NAME="$NAME"
    OS_VERSION="$VERSION_CODENAME"
else
    OS_NAME="Unknown"
    OS_VERSION="unknown"
fi

echo -e "${GREEN}▶ Detected OS:${RESET} $OS_NAME ($OS_VERSION)"

# ── Detect Pi model ───────────────────────────────────────────────────────────
PI_MODEL="Unknown"
if [ -f /proc/device-tree/model ]; then
    PI_MODEL=$(tr -d '\0' < /proc/device-tree/model)
fi
echo -e "${GREEN}▶ Pi Model:${RESET} $PI_MODEL"
echo ""

# ── Update package lists ──────────────────────────────────────────────────────
echo -e "${BOLD}[1/7] Updating package lists…${RESET}"
sudo apt-get update -qq

# ── Install system packages ───────────────────────────────────────────────────
echo -e "${BOLD}[2/7] Installing system packages…${RESET}"

PACKAGES=(
    python3
    python3-pip
    python3-tk
    python3-pil
    python3-pil.imagetk
    python3-numpy
    v4l-utils
    ffmpeg
    xdg-utils
)

# picamera2 is only available on Bookworm+ via apt
if [[ "$OS_VERSION" == "bookworm" || "$OS_VERSION" == "bullseye" ]]; then
    PACKAGES+=(python3-picamera2)
    echo -e "  ${CYAN}ℹ picamera2 will be installed (CSI camera support enabled)${RESET}"
else
    echo -e "  ${YELLOW}⚠ picamera2 not available for $OS_VERSION — only USB cameras supported${RESET}"
fi

# OpenCV: try apt first (faster), fall back to pip
if apt-cache show python3-opencv &>/dev/null; then
    PACKAGES+=(python3-opencv)
else
    echo -e "  ${YELLOW}⚠ python3-opencv not in apt — will install via pip${RESET}"
    INSTALL_CV2_PIP=1
fi

sudo apt-get install -y "${PACKAGES[@]}" 2>&1 | grep -E "(Installed|already|Error)" || true

# OpenCV via pip if needed
if [ "${INSTALL_CV2_PIP:-0}" = "1" ]; then
    echo -e "${BOLD}[3/7] Installing OpenCV via pip…${RESET}"
    pip3 install --break-system-packages opencv-python-headless 2>/dev/null \
        || pip3 install opencv-python-headless
else
    echo -e "${BOLD}[3/7] OpenCV already installed via apt. ${GREEN}✓${RESET}"
fi

# ── Create storage directories ────────────────────────────────────────────────
echo -e "${BOLD}[4/7] Creating storage directories…${RESET}"
mkdir -p "$STORAGE_DIR/captures/photos"
mkdir -p "$STORAGE_DIR/captures/videos"
mkdir -p "$STORAGE_DIR/captures/timelapse"
mkdir -p "$STORAGE_DIR/logs"
chmod -R 755 "$STORAGE_DIR"
echo -e "  ${GREEN}✓ Storage at $STORAGE_DIR${RESET}"

# ── Create desktop launcher ───────────────────────────────────────────────────
echo -e "${BOLD}[5/7] Creating desktop launcher…${RESET}"

DESKTOP_FILE="$HOME/Desktop/PiCamPro.desktop"
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Name=PiCamPro
Comment=Universal Raspberry Pi Camera Viewer
Exec=python3 $INSTALL_DIR/picampro.py
Icon=$INSTALL_DIR/assets/icon.png
Terminal=false
Type=Application
Categories=Utility;Video;
StartupNotify=true
EOF
chmod +x "$DESKTOP_FILE"
echo -e "  ${GREEN}✓ Desktop shortcut created${RESET}"

# ── Create systemd service (optional) ────────────────────────────────────────
echo -e "${BOLD}[6/7] Creating run script…${RESET}"

RUN_SCRIPT="$INSTALL_DIR/run.sh"
cat > "$RUN_SCRIPT" << EOF
#!/usr/bin/env bash
# Run PiCamPro (auto-detects display)
export DISPLAY=\${DISPLAY:-:0}
cd "$INSTALL_DIR"
python3 picampro.py "\$@"
EOF
chmod +x "$RUN_SCRIPT"
echo -e "  ${GREEN}✓ Run script: $RUN_SCRIPT${RESET}"

# ── Verify install ────────────────────────────────────────────────────────────
echo -e "${BOLD}[7/7] Verifying installation…${RESET}"

ERRORS=0

python3 -c "import tkinter; print('  ✓ tkinter')" 2>/dev/null || { echo "  ✗ tkinter missing"; ERRORS=$((ERRORS+1)); }
python3 -c "import cv2; print(f'  ✓ opencv-python {cv2.__version__}')" 2>/dev/null || { echo "  ✗ opencv missing"; ERRORS=$((ERRORS+1)); }
python3 -c "from PIL import Image; print('  ✓ Pillow')" 2>/dev/null || { echo "  ✗ Pillow missing"; ERRORS=$((ERRORS+1)); }
python3 -c "import picamera2; print(f'  ✓ picamera2 {picamera2.__version__}')" 2>/dev/null || echo "  ℹ picamera2 not available (USB cameras only)"

if [ "$ERRORS" -gt 0 ]; then
    echo -e "\n${RED}${BOLD}⚠ $ERRORS dependency error(s) detected. Check messages above.${RESET}"
else
    echo -e "\n${GREEN}${BOLD}✅ All dependencies satisfied!${RESET}"
fi

echo ""
echo -e "${CYAN}${BOLD}Installation complete!${RESET}"
echo ""
echo -e "  To launch:       ${BOLD}python3 $INSTALL_DIR/picampro.py${RESET}"
echo -e "  Or double-click: ${BOLD}PiCamPro${RESET} on your desktop"
echo -e "  Debug mode:      ${BOLD}python3 $INSTALL_DIR/picampro.py --debug${RESET}"
echo -e "  Fullscreen:      ${BOLD}python3 $INSTALL_DIR/picampro.py --fullscreen${RESET}"
echo ""
echo -e "  Storage location: ${BOLD}$STORAGE_DIR${RESET}"
echo ""
