#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║    Linux Wallpaper Engine — GNOME + X11                      ║
# ║    Installer                                                  ║
# ╚══════════════════════════════════════════════════════════════╝

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
AUTOSTART_DIR="$HOME/.config/autostart"

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   Linux Wallpaper Engine — GNOME + X11           ║"
echo "║   Installer                                       ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ─── Check session type ───────────────────────────────────────────────────────

if [ "$XDG_SESSION_TYPE" = "wayland" ]; then
  echo "❌  Wayland session detected."
  echo "    This script only supports X11."
  echo "    Log out and choose an X11 session at the login screen."
  exit 1
fi

echo "✓  X11 session detected."

# ─── Install dependencies ─────────────────────────────────────────────────────

echo ""
echo "Checking dependencies..."

MISSING=()
for cmd in zenity xrandr xdotool wmctrl python3; do
  if ! command -v "$cmd" &>/dev/null; then
    MISSING+=("$cmd")
    echo "  ✗ $cmd (missing)"
  else
    echo "  ✓ $cmd"
  fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
  echo ""
  echo "Installing missing packages: ${MISSING[*]}"
  sudo apt install -y "${MISSING[@]}"
  echo "✓  Dependencies installed."
fi

# ─── Check linux-wallpaperengine ─────────────────────────────────────────────

echo ""
echo "Checking for linux-wallpaperengine binary..."

BINARY_FOUND=false
for p in \
  "$HOME/linux-wallpaperengine/build/output/linux-wallpaperengine" \
  "/usr/local/bin/linux-wallpaperengine" \
  "/usr/bin/linux-wallpaperengine"
do
  if [ -x "$p" ]; then
    echo "✓  Binary found at: $p"
    BINARY_FOUND=true
    break
  fi
done

if [ "$BINARY_FOUND" = false ]; then
  echo ""
  echo "⚠️  linux-wallpaperengine binary not found."
  echo ""
  echo "   You need to compile it from source:"
  echo "   https://github.com/Almamu/linux-wallpaperengine"
  echo ""
  echo "   You can still install this script now and point"
  echo "   to the binary during first run."
  echo ""
  read -rp "   Continue installation anyway? [y/N] " choice
  [[ "$choice" =~ ^[Yy]$ ]] || exit 0
fi

# ─── Install script ───────────────────────────────────────────────────────────

echo ""
echo "Installing scripts..."

mkdir -p "$BIN_DIR"
mkdir -p "$APP_DIR"
mkdir -p "$AUTOSTART_DIR"

cp "$SCRIPT_DIR/change-wallpaper.sh" "$BIN_DIR/change-wallpaper.sh"
chmod +x "$BIN_DIR/change-wallpaper.sh"
echo "✓  change-wallpaper.sh → $BIN_DIR"

# ─── Create .desktop for app menu ────────────────────────────────────────────

cat > "$APP_DIR/wallpaper-engine.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Change Animated Wallpaper
Comment=Apply Wallpaper Engine wallpapers on GNOME + X11
Exec=$BIN_DIR/change-wallpaper.sh
Icon=preferences-desktop-wallpaper
Terminal=false
Categories=Settings;DesktopSettings;
EOF

echo "✓  App menu entry created."

# ─── Create autostart placeholder ────────────────────────────────────────────

# The actual start-wallpaper.sh is generated on first wallpaper apply.
# This .desktop just ensures it runs on login once it exists.

cat > "$AUTOSTART_DIR/wallpaper-engine.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Wallpaper Engine Autostart
Exec=bash -c 'if [ -f "$BIN_DIR/start-wallpaper.sh" ]; then "$BIN_DIR/start-wallpaper.sh"; fi'
Hidden=false
NoDisplay=true
X-GNOME-Autostart-enabled=true
EOF

echo "✓  Autostart entry created."

# ─── Done ─────────────────────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   Installation complete!                          ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  Search for 'Change Animated Wallpaper' in your app menu."
echo "  On first launch, you will be guided through the setup."
echo ""
echo "  To reconfigure paths at any time, run:"
echo "  change-wallpaper.sh --setup"
echo ""

read -rp "Run setup wizard now? [Y/n] " choice
if [[ ! "$choice" =~ ^[Nn]$ ]]; then
  "$BIN_DIR/change-wallpaper.sh" --setup
fi
