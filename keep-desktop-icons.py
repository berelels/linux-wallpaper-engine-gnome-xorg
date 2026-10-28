#!/usr/bin/env python3
"""Keep Wallpaper Engine below GNOME desktop icons after overview transitions.

Listen for X11 stacking changes instead of repeatedly restacking windows. Only
desktop windows belonging to the current user's configured renderer are moved.
"""

import argparse
import fcntl
import importlib.util
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

from integration_config import backend_path


def lower_desktop(window):
    """Load the companion X11 adapter from the same installation directory."""
    spec = importlib.util.spec_from_file_location(
        "gnome_wallpaper_backend", Path(__file__).resolve().parent / "gnome-backend.py")
    backend = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backend)
    backend.lower_desktop(window)


def process_executable(pid, uid, proc_root=Path("/proc")):
    """Return an executable only for a live process owned by this user."""
    if not pid.isdecimal():
        return None
    proc = proc_root / pid
    try:
        if proc.stat().st_uid != uid:
            return None
        return (proc / "exe").resolve(strict=True)
    except OSError:
        return None


def stacking_order(line):
    return tuple(int(window, 16) for window in re.findall(r"0x[0-9a-fA-F]+", line))


def restore_order(line, renderer, *, lower=None, proc_root=Path("/proc"), uid=None):
    """Lower only renderer desktops stacked above at least one icon surface."""
    order = stacking_order(line)
    if not order:
        return 0
    ranks = {window: index for index, window in enumerate(order)}
    uid = os.getuid() if uid is None else uid
    renderer = Path(renderer).resolve()
    icons, wallpapers = [], []
    rows = subprocess.check_output(["wmctrl", "-lp"], text=True).splitlines()
    for row in rows:
        fields = row.split(None, 4)
        if len(fields) < 5:
            continue
        wid, _, pid, _, title = fields
        try:
            window = int(wid, 16)
            if window not in ranks:
                continue
            executable = process_executable(pid, uid, proc_root)
            if executable == renderer:
                # Workshop compatibility scans also create normal renderer
                # windows. They must never be treated as desktop wallpapers.
                props = subprocess.check_output(
                    ["xprop", "-id", wid, "_NET_WM_WINDOW_TYPE"], text=True,
                    stderr=subprocess.DEVNULL)
                if "_NET_WM_WINDOW_TYPE_DESKTOP" in props:
                    wallpapers.append(window)
            elif (executable is not None and executable.name in ("gjs", "gjs-console")
                  and title.startswith("Desktop Icons")):
                icons.append(window)
        except (OSError, ValueError, subprocess.SubprocessError):
            # A window or process can disappear while the snapshot is read.
            continue
    if not icons:
        return 0
    lowest_icon = min(ranks[window] for window in icons)
    covered = [window for window in wallpapers if ranks[window] > lowest_icon]
    if lower is None:
        lower = lower_desktop
    for window in covered:
        lower(hex(window))
    return len(covered)


def watch(renderer):
    """Block on property events; our own corrected order needs no further work."""
    while True:
        watcher = subprocess.Popen(
            ["stdbuf", "-oL", "xprop", "-root", "-spy", "_NET_CLIENT_LIST_STACKING"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        previous = None
        try:
            for line in watcher.stdout:
                order = stacking_order(line)
                if not order or order == previous:
                    continue
                previous = order
                try:
                    count = restore_order(line, renderer)
                    if count:
                        print(f"Lowered {count} wallpaper window(s) beneath desktop icons", flush=True)
                except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
                    print(f"Icon stacking: {exc}", file=sys.stderr, flush=True)
        finally:
            if watcher.poll() is None:
                watcher.terminate()
            try:
                watcher.wait(timeout=3)
            except subprocess.TimeoutExpired:
                watcher.kill()
                watcher.wait()
            if watcher.stdout is not None:
                watcher.stdout.close()
        # Avoid a busy restart loop if the X server disappears at logout.
        time.sleep(2)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", help="renderer executable (defaults to wallpaper-engine/config.sh)")
    args = parser.parse_args(argv)
    renderer = backend_path(args.backend)
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    lock_fd = os.open(runtime / "wallpaper-icon-stacking.lock", os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(lock_fd, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return

        def stop(signum, frame):
            raise SystemExit(0)

        old_handlers = {sig: signal.signal(sig, stop) for sig in (signal.SIGTERM, signal.SIGINT)}
        try:
            watch(renderer)
        finally:
            for sig, handler in old_handlers.items():
                signal.signal(sig, handler)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"Icon stacking: {exc}", file=sys.stderr)
        sys.exit(1)
