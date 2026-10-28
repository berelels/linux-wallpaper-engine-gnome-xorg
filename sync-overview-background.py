#!/usr/bin/env python3
"""Keep GNOME's overview background in sync with the selected live wallpapers.

Capture only verified renderer window backing pixmaps, never the desktop or
screen: open apps, taskbars and desktop icons must not enter the still image.
Requires Xorg with a compositor, Pillow, xrandr, wmctrl and gsettings.
"""

import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import time

from PIL import Image

from background_state import restore_original, save_original
from capture_x11 import capture_window
from integration_config import backend_path
from wallpaper_content import resolve_background


CONFIG_HOME = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
DATA_HOME = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
STATE = CONFIG_HOME / 'Linux Wallpaper Engine/active-wallpapers.json'
OUTPUT = DATA_HOME / 'backgrounds/wallpaper-engine'


def monitors():
    result = {}
    output = subprocess.check_output(['xrandr', '--query'], text=True)
    for line in output.splitlines():
        match = re.match(
            r'(\S+) connected (?:primary )?(\d+)x(\d+)([+-]\d+)([+-]\d+)', line)
        if match:
            name, width, height, x, y = match.groups()
            geometry = tuple(map(int, (x, y, width, height)))
            if geometry[2] > 0 and geometry[3] > 0:
                result[name] = geometry
    return result


def state_snapshot(path=STATE):
    """Return active selections and a version; reject a write in progress."""
    path = Path(path)
    before = path.stat()
    data = json.loads(path.read_text())
    after = path.stat()
    stamp = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
    if stamp(before) != stamp(after):
        raise RuntimeError('Wallpaper selection changed while reading it')
    if not isinstance(data, dict):
        raise ValueError('Wallpaper state must be an object')
    active = data.get('activeWallpapers', {})
    if not isinstance(active, dict):
        raise ValueError('activeWallpapers must be an object')
    if any(not isinstance(name, str) or not isinstance(options, dict)
           or not isinstance(options.get('backgroundId'), str)
           or not options['backgroundId'] for name, options in active.items()):
        raise ValueError('Active wallpaper entries require a backgroundId')
    # mtime catches applying the same wallpaper again with new renderer options.
    return active, (stamp(after), json.dumps(active, sort_keys=True))


def option(argv, name):
    """Read either --option value or --option=value, without substring matches."""
    for index, item in enumerate(argv):
        if item == name:
            return argv[index + 1] if index + 1 < len(argv) else None
        if item.startswith(name + '='):
            return item[len(name) + 1:]
    return None


def renderer_arguments(pid, backend, proc_root=Path('/proc')):
    """Return argv only for this user's exact configured renderer executable."""
    if not str(pid).isdigit() or int(pid) <= 0:
        return None
    proc = Path(proc_root) / str(pid)
    if proc.stat().st_uid != os.getuid():
        return None
    if (proc / 'exe').resolve(strict=True) != Path(backend).resolve():
        return None
    return [word.decode() for word in (proc / 'cmdline').read_bytes().split(b'\0') if word]


def matching_windows(active, bounds, backend):
    """Match the renderer's selection and requested geometry, then window size."""
    result = {}
    for line in subprocess.check_output(['wmctrl', '-lpG'], text=True).splitlines():
        fields = line.split(None, 8)
        if len(fields) < 8:
            continue
        window, _desktop, pid, x, y, width, height, _host, *_title = fields
        try:
            argv = renderer_arguments(pid, backend)
            if not argv:
                continue
            geometry = tuple(map(int, (option(argv, '--window') or '').split('x')))
            actual_size = tuple(map(int, (width, height)))
            background = option(argv, '--bg')
            for screen, settings in active.items():
                if (screen in bounds and background == resolve_background(settings['backgroundId'])[0]
                        and geometry == bounds[screen] and actual_size == bounds[screen][2:]):
                    result[screen] = window
        except (OSError, ValueError, UnicodeError, RuntimeError):
            # Renderers may exit between wmctrl enumeration and /proc reads.
            continue
    return result


def compose(bounds, frames):
    """Place monitor frames on the virtual desktop, including negative origins."""
    if not bounds:
        raise ValueError('No active monitors')
    left = min(rect[0] for rect in bounds.values())
    top = min(rect[1] for rect in bounds.values())
    width = max(rect[0] + rect[2] for rect in bounds.values()) - left
    height = max(rect[1] + rect[3] for rect in bounds.values()) - top
    if not 0 < width <= 32768 or not 0 < height <= 32768:
        raise ValueError('Invalid virtual desktop dimensions')
    canvas = Image.new('RGB', (width, height))
    for screen, frame in frames.items():
        x, y, width, height = bounds[screen]
        if frame.size != (width, height):
            raise RuntimeError(f'Wallpaper window for {screen} is resizing')
        canvas.paste(frame, (x - left, y - top))
    return canvas


def publish(canvas, output=OUTPUT, still_current=lambda: True):
    """Alternate two filenames so GNOME reloads each successful still image."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    current = subprocess.check_output([
        'gsettings', 'get', 'org.gnome.desktop.background', 'picture-uri'], text=True)
    current = shlex.split(current.strip())
    # Always choose the other slot; time parity can repeat the current filename.
    slot = 1 if current == [(output / 'overview-0.png').as_uri()] else 0
    target = output / f'overview-{slot}.png'
    temp = output / f'.overview-{os.getpid()}.png'
    try:
        canvas.save(temp, compress_level=2)
        if not still_current():
            return False
        save_original(output=output)
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)
    subprocess.run(['gsettings', 'set', 'org.gnome.desktop.background',
                    'picture-options', 'spanned'], check=True)
    for key in ('picture-uri', 'picture-uri-dark'):
        subprocess.run(['gsettings', 'set', 'org.gnome.desktop.background',
                        key, target.as_uri()], check=True)
    return True


def update(active, bounds, backend, still_current=lambda: True, output=OUTPUT):
    screens = {name: settings for name, settings in active.items() if name in bounds}
    if set(screens) != set(bounds):
        # Empty playback and partial-monitor selections both use the user's
        # original GNOME background instead of a black composite region.
        restore_original()
        return True
    windows = matching_windows(screens, bounds, backend)
    if set(windows) != set(screens):
        return False  # Never publish a half-updated multi-monitor selection.
    # wmctrl can double root-relative X/Y for unframed desktop windows. Read
    # actual root coordinates through Xlib when capturing instead.
    frames = {screen: capture_window(int(window, 0), expected_geometry=bounds[screen])
              for screen, window in windows.items()}
    canvas = compose(bounds, frames)
    # Selection, monitor layout or renderer processes can change during capture.
    # Leave the previous background in place and retry the new snapshot.
    def unchanged():
        return (still_current() and monitors() == bounds
                and matching_windows(screens, bounds, backend) == windows)

    if not unchanged():
        return False
    if publish(canvas, output, unchanged) is False:
        return False
    print('Updated overview for ' + ', '.join(screens), flush=True)
    return True


@contextmanager
def single_instance():
    runtime = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
    with (runtime / 'wallpaper-overview-sync.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Overview background synchronization is already running')
        yield


def position_version():
    try:
        return (CONFIG_HOME / 'wallpaper-engine/positions.json').stat().st_mtime_ns
    except FileNotFoundError:
        return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true', help='capture once instead of watching')
    parser.add_argument('--backend', help='linux-wallpaperengine renderer executable')
    args = parser.parse_args()
    with single_instance():
        done = pending = None
        changed = 0
        while True:
            try:
                backend = backend_path(args.backend)
                active, version = state_snapshot()
                bounds = monitors()
                windows = matching_windows(active, bounds, backend)
                # A renderer may finish restarting after the state file write,
                # including when reapplying the same item. Refresh its new frame.
                signature = (version, tuple(sorted(bounds.items())), str(backend),
                             tuple(sorted(windows.items())),
                             position_version())
                if signature != pending:
                    pending, changed = signature, time.monotonic()

                def still_current():
                    return state_snapshot()[1] == version

                # Give newly started renderers time to produce a useful frame.
                if args.once or (signature != done and time.monotonic() - changed >= 3):
                    if update(active, bounds, backend, still_current):
                        done = signature
                    elif args.once:
                        raise RuntimeError('Selected wallpaper windows are not ready')
                if args.once:
                    return
            except (OSError, ValueError, subprocess.SubprocessError, RuntimeError) as exc:
                if args.once:
                    raise
                print('Overview sync: ' + str(exc), flush=True)
            time.sleep(2)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError, RuntimeError) as exc:
        raise SystemExit('Overview sync: ' + str(exc))
