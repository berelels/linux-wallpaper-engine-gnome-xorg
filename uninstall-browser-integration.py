#!/usr/bin/env python3
"""Remove the per-user GNOME integration and restore its saved background."""

import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

from background_state import restore_original
from integration_config import config_home


def helper_processes(target, proc_root=Path('/proc')):
    scripts = {str(target / name) for name in
               ('sync-overview-background.py', 'keep-desktop-icons.py',
                'gnome-backend.py', 'restore-browser-wallpapers.py')}
    for proc in Path(proc_root).iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if proc.stat().st_uid != os.getuid():
                continue
            argv = [part.decode() for part in
                    (proc / 'cmdline').read_bytes().split(b'\0') if part]
            if any(argument in scripts for argument in argv):
                yield int(proc.name)
        except (OSError, UnicodeError):
            continue


def main():
    data = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
    target = data / 'wallpaper-engine-gnome'
    helpers = list(helper_processes(target))
    for pid in helpers:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 3
    while helpers and time.monotonic() < deadline:
        helpers = [pid for pid in helpers if Path(f'/proc/{pid}').exists()]
        if helpers:
            time.sleep(0.05)
    restore_original()
    autostart = config_home() / 'autostart'
    for name in ('wallpaper-overview-sync.desktop',
                 'wallpaper-icon-stacking.desktop',
                 'wallpaper-browser-restore.desktop'):
        (autostart / name).unlink(missing_ok=True)
    for name in ('linux-wallpaper-engine.desktop', 'wallpaper-position.desktop'):
        (data / 'applications' / name).unlink(missing_ok=True)
    try:
        desktop = Path(subprocess.check_output(
            ['xdg-user-dir', 'DESKTOP'], text=True).strip())
        (desktop / 'Linux Wallpaper Engine.desktop').unlink(missing_ok=True)
    except (OSError, subprocess.SubprocessError):
        pass
    if target.is_dir():
        shutil.rmtree(target)
    print('Removed the GNOME integration and restored the saved background.')


if __name__ == '__main__':
    main()
