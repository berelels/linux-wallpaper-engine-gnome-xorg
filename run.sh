#!/usr/bin/env bash
# Complete supported-platform setup. Run as your normal desktop user.
set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
BACKEND_REV=b016d7d1fdcf4e5fd2f9c9fa420a8aaa07fee02d
BROWSER_VERSION=0.4.11
BROWSER_SHA=4fd1ef71f5317fca521bff67173b020624cab8fadc0cb1bd685c41d8100fd97f
if [[ ${1:-} == --help ]]; then
    cat <<'EOF'
Usage: ./run.sh [--check]
Installs the browser, builds the renderer, connects GNOME fixes, and opens the app.
Supported: Zorin 18 / Ubuntu 24.04, GNOME X11, x86_64.
Requires internet, several GB of disk space, and sudo for system dependencies.
Steam sign-in, Wallpaper Engine ownership, and Steam install dialogs remain yours.
--check checks the platform without installing or downloading anything.
Build concurrency: set BUILD_JOBS (defaults to 2).
EOF
    exit 0
fi
[[ $# == 0 || ( $# == 1 && $1 == --check ) ]] || { echo 'Unknown option. Use --help.' >&2; exit 2; }
[[ $EUID != 0 ]] || { echo 'Run ./run.sh as your desktop user, not with sudo.' >&2; exit 1; }
[[ $(uname -m) == x86_64 ]] || { echo 'This installer currently supports x86_64 only.' >&2; exit 1; }
# shellcheck source=/etc/os-release
source /etc/os-release
[[ ${UBUNTU_CODENAME:-${VERSION_CODENAME:-}} == noble ]] || { echo 'Supported systems: Zorin 18 / Ubuntu 24.04 (noble).' >&2; exit 1; }
desktop_name=${XDG_CURRENT_DESKTOP:-}
[[ ${XDG_SESSION_TYPE:-} == x11 && ${desktop_name,,} == *gnome* ]] || {
    echo 'Log in to a GNOME/Zorin X11 session, then run this script again.' >&2; exit 1;
}
[[ -n ${DISPLAY:-} ]] || { echo 'Run this inside your graphical desktop session.' >&2; exit 1; }
[[ ${1:-} != --check ]] || { echo 'Platform supported. No changes made.'; exit 0; }
CACHE=${XDG_CACHE_HOME:-$HOME/.cache}/gnome-wallpaper-setup
APP=$HOME/.var/app/com.valvesoftware.Steam/data/gnome-wallpaper-suite
mkdir -p "$CACHE" "$APP"
exec 9>"$CACHE/setup.lock"
flock -n 9 || { echo 'Another setup is running.' >&2; exit 1; }
LOG="$CACHE/setup-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1
trap 'echo "Setup stopped at line $LINENO. Log: $LOG. Fix the reported problem and rerun ./run.sh; downloads/builds are cached." >&2' ERR
printf '\nInstalling Wallpaper Engine tools for GNOME X11.\n'
echo 'The first build can take a while and needs several GB of free space.'
sudo -v
sudo apt-get update
sudo apt-get install -y build-essential cmake git curl ca-certificates unzip pkg-config \
    python3 python3-venv python3-pil python3-tk libxcomposite1 flatpak zenity x11-xserver-utils x11-utils xdotool wmctrl \
    libxrandr-dev libxinerama-dev libxcursor-dev libxi-dev libgl-dev libglew-dev \
    freeglut3-dev libsdl2-dev liblz4-dev libavcodec-dev libavformat-dev libavutil-dev \
    libswscale-dev libxxf86vm-dev libglm-dev libglfw3-dev libmpv-dev mpv libpulse-dev \
    libfftw3-dev libfreetype-dev libdbus-1-dev zlib1g-dev
if ! flatpak info com.valvesoftware.Steam >/dev/null 2>&1; then
    flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
    flatpak install --user -y flathub com.valvesoftware.Steam
fi
ZIP="$CACHE/browser-$BROWSER_VERSION.zip"
if ! echo "$BROWSER_SHA  $ZIP" | sha256sum --check --status 2>/dev/null; then
    curl --fail --location --retry 3 --output "$ZIP.part" \
        "https://github.com/jagrat7/linux-wallpaper-engine/releases/download/v$BROWSER_VERSION/Linux.Wallpaper.Engine-linux-x64-$BROWSER_VERSION.zip"
    echo "$BROWSER_SHA  $ZIP.part" | sha256sum --check
    mv "$ZIP.part" "$ZIP"
fi
SOURCE="$CACHE/backend-$BACKEND_REV"
if [[ ! -d $SOURCE/.git ]]; then
    git clone --no-checkout https://github.com/Almamu/linux-wallpaperengine.git "$SOURCE"
fi
git -C "$SOURCE" checkout --detach "$BACKEND_REV"
if git -C "$SOURCE" apply --check "$ROOT/patches/backend-fixes.patch" 2>/dev/null; then
    git -C "$SOURCE" apply "$ROOT/patches/backend-fixes.patch"
elif ! git -C "$SOURCE" apply --reverse --check "$ROOT/patches/backend-fixes.patch" 2>/dev/null; then
    echo 'Backend checkout has incompatible changes; preserve it and use a fresh setup cache.' >&2
    exit 1
fi
git -C "$SOURCE" submodule update --init --recursive
cmake -S "$SOURCE" -B "$SOURCE/build" -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF
cmake --build "$SOURCE/build" --parallel "${BUILD_JOBS:-2}"
STAGE=$(mktemp -d "$CACHE/browser.XXXXXX")
unzip -q "$ZIP" -d "$STAGE"
# Keep versioned installs so repeating setup cannot overwrite a running executable.
BROWSER="$APP/browser-$BROWSER_VERSION-session-v1"
if [[ ! -f $BROWSER/.installed ]]; then
    mkdir -p "$BROWSER"
    cp -a "$STAGE/Linux Wallpaper Engine-linux-x64/." "$BROWSER/"
    chmod +x "$BROWSER/linux-wallpaper-engine"
    touch "$BROWSER/.installed"
fi
rm -rf -- "$STAGE"
PATCH_ID=$(sha256sum "$ROOT/patches/backend-fixes.patch" | cut -c1-12)
PLAYER="$APP/player-$BACKEND_REV-$PATCH_ID"
if [[ ! -f $PLAYER/.installed ]]; then
    mkdir -p "$PLAYER"
    cp -a "$SOURCE/build/output/." "$PLAYER/"
    cp "$SOURCE/LICENSE" "$PLAYER/LICENSE.backend"
    touch "$PLAYER/.installed"
fi
python3 "$ROOT/setup/configure-native.py" "$ROOT" "$APP" "$PLAYER" "$BROWSER"
echo 'Starting Steam. Sign in if Steam asks you to.'
flatpak run com.valvesoftware.Steam >/dev/null 2>&1 9>&- &
printf '\nSetup complete. Open “Linux Wallpaper Engine” from your applications menu.\nLog: %s\n' "$LOG"
"$APP/open-browser" >/dev/null 2>&1 9>&- &
