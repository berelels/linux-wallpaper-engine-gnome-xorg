#!/usr/bin/env bash
# Build dist/Linux_Wallpaper_Engine-<version>-x86_64.AppImage on Zorin 18 / Ubuntu 24.04.
# Needs the same build packages as run.sh (it lists what is missing; it never runs sudo).
set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=appimage/versions.env
source "$ROOT/appimage/versions.env"
CACHE=${XDG_CACHE_HOME:-$HOME/.cache}/lwe-appimage-build
APPDIR=$ROOT/build/AppDir
LWE=$APPDIR/usr/lib/lwe
DIST=$ROOT/dist
OUTPUT=$DIST/Linux_Wallpaper_Engine-$APP_VERSION-x86_64.AppImage
PACKAGES=(build-essential cmake git curl ca-certificates unzip pkg-config patchelf binutils
    wmctrl x11-utils xdotool
    libxrandr-dev libxinerama-dev libxcursor-dev libxi-dev libgl-dev libglew-dev
    freeglut3-dev libsdl2-dev liblz4-dev libavcodec-dev libavformat-dev libavutil-dev
    libswscale-dev libxxf86vm-dev libglm-dev libglfw3-dev libmpv-dev libpulse-dev
    libfftw3-dev libfreetype-dev libdbus-1-dev zlib1g-dev)

missing=()
for package in "${PACKAGES[@]}"; do
    dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q 'install ok installed' || missing+=("$package")
done
if ((${#missing[@]})); then
    echo "Missing build packages. Install them, then run this again:" >&2
    echo "  sudo apt-get install ${missing[*]}" >&2
    exit 1
fi
[[ ${1:-} != --check-deps ]] || { echo 'Build packages present.'; exit 0; }

mkdir -p "$CACHE" "$DIST"
fetch() {  # url sha256 destination
    if ! echo "$2  $3" | sha256sum --check --status 2>/dev/null; then
        curl --fail --location --retry 3 --output "$3.part" "$1"
        echo "$2  $3.part" | sha256sum --check
        mv "$3.part" "$3"
    fi
}

echo '== Downloads (pinned, checked by SHA-256)'
fetch "https://github.com/jagrat7/linux-wallpaper-engine/releases/download/v$BROWSER_VERSION/Linux.Wallpaper.Engine-linux-x64-$BROWSER_VERSION.zip" \
    "$BROWSER_SHA" "$CACHE/browser-$BROWSER_VERSION.zip"
fetch "$PYTHON_URL" "$PYTHON_SHA" "$CACHE/python.tar.gz"
fetch "$PILLOW_URL" "$PILLOW_SHA" "$CACHE/${PILLOW_URL##*/}"
fetch "$APPIMAGETOOL_URL" "$APPIMAGETOOL_SHA" "$CACHE/appimagetool"
chmod +x "$CACHE/appimagetool"
[[ -s $CACHE/excludelist ]] || curl --fail --location --retry 3 --output "$CACHE/excludelist" "$EXCLUDELIST_URL"

echo '== Renderer (same pinned commit and patch as run.sh)'
SOURCE=$CACHE/backend-$BACKEND_REV
[[ -d $SOURCE/.git ]] || git clone --no-checkout https://github.com/Almamu/linux-wallpaperengine.git "$SOURCE"
git -C "$SOURCE" checkout --detach "$BACKEND_REV"
if git -C "$SOURCE" apply --check "$ROOT/patches/backend-fixes.patch" 2>/dev/null; then
    git -C "$SOURCE" apply "$ROOT/patches/backend-fixes.patch"
elif ! git -C "$SOURCE" apply --reverse --check "$ROOT/patches/backend-fixes.patch" 2>/dev/null; then
    echo 'Renderer checkout has incompatible changes; delete it from the build cache.' >&2; exit 1
fi
git -C "$SOURCE" submodule update --init --recursive
cmake -S "$SOURCE" -B "$SOURCE/build" -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF
cmake --build "$SOURCE/build" --parallel "${BUILD_JOBS:-2}"

echo '== AppDir'
rm -rf "$APPDIR"
mkdir -p "$LWE/renderer" "$LWE/tools/bin" "$LWE/browser"
# Only what the renderer needs at run time (no static libs, headers, tests or benchmarks).
OUT=$SOURCE/build/output
for item in linux-wallpaperengine liblinux-wallpaperengine-lib.so libcef.so libEGL.so libGLESv2.so \
        libvk_swiftshader.so vk_swiftshader_icd.json chrome_100_percent.pak chrome_200_percent.pak \
        resources.pak icudtl.dat v8_context_snapshot.bin chrome-sandbox locales; do
    cp -a "$OUT/$item" "$LWE/renderer/"
done
mkdir -p "$LWE/renderer/lib"
cp -a "$SOURCE"/build/lib/*.so* "$LWE/renderer/lib/"
# The build tree links with absolute RUNPATHs into the build folder; make them relative.
for elf in "$LWE/renderer/linux-wallpaperengine" "$LWE/renderer/liblinux-wallpaperengine-lib.so"; do
    patchelf --set-rpath '$ORIGIN:$ORIGIN/lib' "$elf"
done
cp "$SOURCE/LICENSE" "$LWE/renderer/LICENSE"
find "$LWE/renderer" -type f \( -name '*.so*' -o -name linux-wallpaperengine \) -exec strip --strip-unneeded {} +

unzip -q "$CACHE/browser-$BROWSER_VERSION.zip" -d "$CACHE/browser-stage.$$"
cp -a "$CACHE/browser-stage.$$/Linux Wallpaper Engine-linux-x64/." "$LWE/browser/"
rm -rf "$CACHE/browser-stage.$$"
chmod +x "$LWE/browser/linux-wallpaper-engine"
python3 "$ROOT/patch-browser-session.py" "$LWE/browser/resources/app.asar"
rm -f "$LWE/browser/resources/"*.before-persistent-session

tar -xzf "$CACHE/python.tar.gz" -C "$LWE"           # creates $LWE/python
"$LWE/python/bin/python3" -m pip install --no-index --no-deps --no-cache-dir --disable-pip-version-check \
    "$CACHE/${PILLOW_URL##*/}"
"$LWE/python/bin/python3" -c 'import PIL.Image, tkinter, ctypes, fcntl'
# Deprecated module the helpers never use; it is the only one needing the host libcrypt.
rm -f "$LWE"/python/lib/python3.*/lib-dynload/_crypt.*.so

for tool in wmctrl xprop xdotool xwininfo; do cp "$(command -v "$tool")" "$LWE/tools/bin/"; done

mkdir -p "$LWE/app"
git -C "$ROOT" ls-files -z --cached --others --exclude-standard | while IFS= read -r -d '' file; do
    [[ $file == test_* || $file == test-* ]] && continue
    mkdir -p "$LWE/app/$(dirname "$file")"
    cp -a "$ROOT/$file" "$LWE/app/$file"
done
echo "$APP_VERSION" > "$LWE/VERSION"
cp "$ROOT/appimage/AppRun" "$APPDIR/AppRun"
cp "$ROOT/appimage/linux-wallpaper-engine.desktop" "$APPDIR/"
# The browser's own icon; the largest PNG it ships.
icon=$(find "$LWE/browser" -type f -iname '*.png' -printf '%s %p\n' | sort -rn | awk 'NR==1{print $2}')
[[ -n $icon ]] || { echo 'No icon found in the browser package.' >&2; exit 1; }
cp "$icon" "$APPDIR/linux-wallpaper-engine.png"
cp "$icon" "$LWE/icon.png"
ln -s linux-wallpaper-engine.png "$APPDIR/.DirIcon"

echo '== Bundle and check libraries'
python3 "$ROOT/appimage/bundle-libs.py" "$LWE/renderer" --excludelist "$CACHE/excludelist"
python3 "$ROOT/appimage/bundle-libs.py" "$LWE/tools" --excludelist "$CACHE/excludelist"
for dir in renderer tools python; do
    python3 "$ROOT/appimage/bundle-libs.py" "$LWE/$dir" --excludelist "$CACHE/excludelist" --check
done
env -i PATH=/usr/bin:/bin "$LWE/renderer/linux-wallpaperengine" --help >/dev/null

echo '== AppImage'
ARCH=x86_64 "$CACHE/appimagetool" --appimage-extract-and-run --no-appstream "$APPDIR" "$OUTPUT"
ls -lh "$OUTPUT"
