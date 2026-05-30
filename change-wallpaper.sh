#!/bin/bash
# ╔══════════════════════════════════════════════════════════════╗
# ║       Linux Wallpaper Engine — GNOME + X11 GUI               ║
# ║       Compatible with Zorin OS, Ubuntu, and GNOME + X11      ║
# ╚══════════════════════════════════════════════════════════════╝

CONFIG_DIR="$HOME/.config/wallpaper-engine"
CONFIG_FILE="$CONFIG_DIR/config.sh"
AUTOSTART="$HOME/.local/bin/start-wallpaper.sh"

mkdir -p "$CONFIG_DIR"
mkdir -p "$HOME/.local/bin"

# ─── Check dependencies ────────────────────────────────────────────────────────

MISSING=()
for cmd in zenity xrandr xdotool wmctrl python3; do
  command -v "$cmd" &>/dev/null || MISSING+=("$cmd")
done

if [ ${#MISSING[@]} -gt 0 ]; then
  zenity --error --title="Missing dependencies" \
    --text="Please install the required packages:\n\nsudo apt install ${MISSING[*]}"
  exit 1
fi

# ─── Auto-detection functions ──────────────────────────────────────────────────

detect_steam() {
  for p in \
    "$HOME/.local/share/Steam" \
    "$HOME/.steam/steam" \
    "$HOME/.steam/root" \
    "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam"
  do
    [ -d "$p/steamapps" ] && echo "$p" && return
  done
}

detect_binary() {
  for p in \
    "$HOME/linux-wallpaperengine/build/output/linux-wallpaperengine" \
    "/usr/local/bin/linux-wallpaperengine" \
    "/usr/bin/linux-wallpaperengine"
  do
    [ -x "$p" ] && echo "$p" && return
  done
  command -v linux-wallpaperengine 2>/dev/null
}

get_monitors() {
  # Returns: NAME|EngineGeometry|DisplayLabel
  # xrandr example: "DisplayPort-0 connected 1920x1080+1440+0"
  # Engine expects: --window XxYxWxH (e.g. 1440x0x1920x1080)
  xrandr --query | awk '/ connected/ {
    name = $1
    for (i = 1; i <= NF; i++) {
      if ($i ~ /^[0-9]+x[0-9]+\+[0-9]+\+[0-9]+$/) {
        split($i, a, /[x+]/)
        w=a[1]; h=a[2]; x=a[3]; y=a[4]
        geom = x "x" y "x" w "x" h
        label = w "x" h " (position " x "," y ")"
        print name "|" geom "|" label
      }
    }
  }'
}

# ─── Setup wizard (first run or reconfiguration) ──────────────────────────────

setup_wizard() {
  zenity --info \
    --title="Wallpaper Engine — Initial Setup" \
    --text="Welcome! Let's configure the required paths.\nThis only happens once." \
    --width=420 --ok-label="Continue"

  # Binary
  local bin_default
  bin_default=$(detect_binary)

  BINARY=$(zenity --file-selection \
    --title="Select the linux-wallpaperengine binary" \
    --filename="${bin_default:-$HOME/}")

  [ -z "$BINARY" ] && exit 0

  if [ ! -x "$BINARY" ]; then
    zenity --error --title="Error" \
      --text="File not found or not executable:\n$BINARY"
    exit 1
  fi

  # Steam root folder
  local steam_default
  steam_default=$(detect_steam)

  STEAM_PATH=$(zenity --file-selection \
    --title="Select your Steam root folder (the one that contains 'steamapps')" \
    --directory \
    --filename="${steam_default:-$HOME/.local/share/Steam}")

  [ -z "$STEAM_PATH" ] && exit 0

  local ASSETS="$STEAM_PATH/steamapps/common/wallpaper_engine/assets"
  local WORKSHOP="$STEAM_PATH/steamapps/workshop/content/431960"

  if [ ! -d "$ASSETS" ]; then
    zenity --error --title="Assets folder not found" \
      --text="Could not find the assets folder at:\n$ASSETS\n\nMake sure Wallpaper Engine is installed via Steam with Proton enabled."
    exit 1
  fi

  if [ ! -d "$WORKSHOP" ]; then
    zenity --error --title="Workshop folder not found" \
      --text="No wallpapers found at:\n$WORKSHOP\n\nSubscribe to wallpapers on the Steam Workshop first."
    exit 1
  fi

  # Save config
  cat > "$CONFIG_FILE" << EOF
BINARY="$BINARY"
STEAM_PATH="$STEAM_PATH"
ASSETS="$ASSETS"
WORKSHOP="$WORKSHOP"
EOF

  zenity --info --title="Setup complete!" \
    --text="✓ All set!\n\nBinary:\n$BINARY\n\nAssets:\n$ASSETS\n\nWorkshop:\n$WORKSHOP" \
    --width=500
}

# ─── Load or create config ────────────────────────────────────────────────────

# Pass --setup to force reconfiguration
if [ "$1" = "--setup" ] || [ ! -f "$CONFIG_FILE" ]; then
  setup_wizard
fi

if [ ! -f "$CONFIG_FILE" ]; then
  zenity --error --title="Error" --text="Configuration not found. Please run the script again."
  exit 1
fi

# shellcheck source=/dev/null
source "$CONFIG_FILE"

# ─── Select monitors ──────────────────────────────────────────────────────────

MONITORS=$(get_monitors)

if [ -z "$MONITORS" ]; then
  zenity --error --title="No monitors detected" \
    --text="xrandr found no active monitors.\nCheck your video connection."
  exit 1
fi

declare -A MON_GEOM
MON_ARGS=()

while IFS='|' read -r name geom label; do
  MON_GEOM["$name"]="$geom"
  MON_ARGS+=("TRUE" "$name" "$label")
done <<< "$MONITORS"

SELECTED_NAMES=$(zenity --list --checklist \
  --title="Select Monitors" \
  --text="Choose which monitors to apply the wallpaper to:" \
  --column="✓" --column="Monitor" --column="Resolution / Position" \
  --print-column=2 --separator="|" \
  --width=520 --height=280 \
  "${MON_ARGS[@]}")

[ -z "$SELECTED_NAMES" ] && exit 0

# ─── Select wallpaper ─────────────────────────────────────────────────────────

WP_ARGS=()
while IFS= read -r dir; do
  wid=$(basename "$dir")
  title=$(python3 -c "
import json, sys
try:
    with open('$dir/project.json') as f:
        d = json.load(f)
    t = d.get('title', '$wid')
    print(t[:60])
except:
    print('$wid')
" 2>/dev/null)
  WP_ARGS+=("$wid" "$title")
done < <(find "$WORKSHOP" -mindepth 1 -maxdepth 1 -type d | sort)

if [ ${#WP_ARGS[@]} -eq 0 ]; then
  zenity --error --title="No wallpapers found" \
    --text="No wallpapers found at:\n$WORKSHOP\n\nSubscribe to wallpapers on the Steam Workshop."
  exit 1
fi

ID=$(zenity --list \
  --title="Select Wallpaper" \
  --text="Choose a wallpaper to apply:" \
  --column="ID" --column="Name" \
  --print-column=1 \
  --width=620 --height=420 \
  "${WP_ARGS[@]}")

[ -z "$ID" ] && exit 0

# ─── Wallpaper boolean properties ────────────────────────────────────────────

PROJ="$WORKSHOP/$ID/project.json"
PROP_FLAGS=()

BOOL_PROPS=$(python3 - "$PROJ" << 'PYEOF'
import json, sys
try:
    with open(sys.argv[1]) as f:
        data = json.load(f)
    props = data.get('general', {}).get('properties', {})
    for key, val in sorted(props.items()):
        if val.get('type') == 'bool':
            text = val.get('text', key)
            # Bilingual wallpapers use "/" as separator — use the English part
            if '/' in text:
                text = text.split('/')[-1].strip()
            text = text[:70]
            value = '1' if val.get('value', False) else '0'
            print(f'{key}|{text}|{value}')
except Exception as e:
    pass
PYEOF
)

if [ -n "$BOOL_PROPS" ]; then
  CHECKLIST_ARGS=()
  while IFS='|' read -r key text value; do
    [ "$value" = "1" ] && checked="TRUE" || checked="FALSE"
    CHECKLIST_ARGS+=("$checked" "$key" "$text")
  done <<< "$BOOL_PROPS"

  SELECTED_PROPS=$(zenity --list --checklist \
    --title="Wallpaper Properties" \
    --text="Enable or disable wallpaper properties:" \
    --column="✓" --column="Key" --column="Description" \
    --print-column=2 --separator="|" \
    --width=640 --height=460 \
    "${CHECKLIST_ARGS[@]}" 2>/dev/null)

  # If the user cancels the properties dialog, apply with defaults
  if [ $? -eq 0 ]; then
    while IFS='|' read -r key text value; do
      if echo "|${SELECTED_PROPS}|" | grep -q "|${key}|"; then
        PROP_FLAGS+=(--set-property "${key}=1")
      else
        PROP_FLAGS+=(--set-property "${key}=0")
      fi
    done <<< "$BOOL_PROPS"
  fi
fi

# ─── Apply wallpaper ──────────────────────────────────────────────────────────

pkill -9 -f linux-wallpaperengine 2>/dev/null
sleep 1

AUTOSTART_BODY=""
FIRST=true

IFS='|' read -ra SELECTED_ARR <<< "$SELECTED_NAMES"
for name in "${SELECTED_ARR[@]}"; do
  [ -z "$name" ] && continue
  geom="${MON_GEOM[$name]}"
  [ -z "$geom" ] && continue

  CMD=("$BINARY" --window "$geom" --disable-mouse --disable-parallax
       --fps 60 --scaling fill --assets-dir "$ASSETS"
       "${PROP_FLAGS[@]}" "$ID")

  "${CMD[@]}" &

  CMD_STR="\"$BINARY\" --window \"$geom\" --disable-mouse --disable-parallax --fps 60 --scaling fill --assets-dir \"$ASSETS\""
  for f in "${PROP_FLAGS[@]}"; do
    CMD_STR+=" \"$f\""
  done
  CMD_STR+=" \"$ID\" &"
  AUTOSTART_BODY+="$CMD_STR\n"

  if [ "$FIRST" = true ]; then
    FIRST=false
    AUTOSTART_BODY+="\nsleep 4\n\n"
    sleep 4
  fi
done

sleep 3

for wid in $(xdotool search --name "wallpaperengine" 2>/dev/null); do
  wmctrl -i -r "$wid" -b add,below,sticky         2>/dev/null
  wmctrl -i -r "$wid" -b add,skip_taskbar,skip_pager 2>/dev/null
done

# ─── Save autostart ───────────────────────────────────────────────────────────

cat > "$AUTOSTART" << STARTEOF
#!/bin/bash
# Auto-generated by change-wallpaper.sh — do not edit manually
sleep 5
pkill -9 -f linux-wallpaperengine 2>/dev/null
sleep 1

$(echo -e "$AUTOSTART_BODY")
sleep 3

for wid in \$(xdotool search --name "wallpaperengine" 2>/dev/null); do
  wmctrl -i -r "\$wid" -b add,below,sticky         2>/dev/null
  wmctrl -i -r "\$wid" -b add,skip_taskbar,skip_pager 2>/dev/null
done
STARTEOF

chmod +x "$AUTOSTART"

zenity --info \
  --title="Wallpaper Engine" \
  --text="✓ Wallpaper applied successfully!\n\nSaved to autostart — it will launch automatically on login." \
  --width=400
