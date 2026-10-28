#!/bin/bash
# Launch one renderer and place only its window on the requested monitor.
set -u
if [ "$#" -lt 3 ]; then
  echo "Usage: $0 XxYxWxH BACKEND [backend arguments...]" >&2
  exit 2
fi
geometry=$1
shift
IFS=x read -r x y width height <<< "$geometry"
if ! [[ $geometry =~ ^[0-9]+x[0-9]+x[0-9]+x[0-9]+$ ]]; then
  echo "Invalid monitor geometry: $geometry" >&2
  exit 2
fi
"$@" &
player_pid=$!
trap 'kill "$player_pid" 2>/dev/null || true' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
window=''
# Loading large scenes can take longer than the old fixed three-second wait.
for ((attempt=0; attempt<120; attempt++)); do
  kill -0 "$player_pid" 2>/dev/null || { wait "$player_pid"; exit $?; }
  window=$(wmctrl -lp | awk -v pid="$player_pid" '$3 == pid {print $1; exit}')
  [ -n "$window" ] && break
  sleep 0.5
done
if [ -z "$window" ]; then
  echo "Wallpaper window did not appear within 60 seconds." >&2
  exit 1
fi
xprop -id "$window" -f _NET_WM_WINDOW_TYPE 32a -set _NET_WM_WINDOW_TYPE _NET_WM_WINDOW_TYPE_DESKTOP
wmctrl -i -r "$window" -b remove,above,below
wmctrl -i -r "$window" -b remove,maximized_vert,maximized_horz
wmctrl -i -r "$window" -b add,sticky
wmctrl -i -r "$window" -b add,skip_taskbar,skip_pager
wmctrl -i -r "$window" -t -1
# GNOME can override the initial GLFW position; place it after it is mapped.
wmctrl -i -r "$window" -e "0,$x,$y,$width,$height"
python3 "$(dirname "$0")/gnome-backend.py" --lower-window "$window"
wait "$player_pid"
