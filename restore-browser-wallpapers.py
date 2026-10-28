#!/usr/bin/env python3
"""Restore saved browser monitor selections through the GNOME adapter at login."""
import json
import fcntl
import os
from pathlib import Path
import subprocess
import sys
from integration_config import backend_path, config_home
from wallpaper_content import resolve_background


def restore_args(renderer, screen, options, settings, adapter):
    background = options.get('backgroundId')
    if not isinstance(background, str) or not Path(background).is_dir():
        return None
    args = [sys.executable, str(adapter), str(renderer), '--screen-root', screen, '--bg', background]
    for key, flag, default in [('fps', '--fps', 30), ('volume', '--volume', 0), ('scaling', '--scaling', 'fill')]:
        value = options.get(key, settings.get('defaultScaling' if key == 'scaling' else key, default))
        if value is not None: args.extend([flag, str(value)])
    for key, flag in [('silent', '--silent'), ('disableMouse', '--disable-mouse'), ('disableParallax', '--disable-parallax'), ('disableParticles', '--disable-particles'), ('noAutomute', '--noautomute'), ('noAudioProcessing', '--no-audio-processing'), ('noFullscreenPause', '--no-fullscreen-pause')]:
        if options.get(key, settings.get(key, False)): args.append(flag)
    assets = settings.get('assetsDir')
    if assets: args.extend(['--assets-dir', assets])
    return args


def active_screens(renderer, active, bounds, proc_root=Path('/proc')):
    found = set()
    expected = {screen: resolve_background(options['backgroundId'])[0]
                for screen, options in active.items() if screen in bounds}
    for proc in Path(proc_root).iterdir():
        if not proc.name.isdigit(): continue
        try:
            if proc.stat().st_uid != os.getuid(): continue
            argv = [arg.decode() for arg in (proc/'cmdline').read_bytes().split(b'\0') if arg]
            def option(flag):
                return argv[argv.index(flag)+1] if flag in argv else None
            background = option('--bg')
            if not background: continue
            if (proc/'exe').resolve() == renderer:
                for screen, bg in expected.items():
                    if background == bg and option('--window') == 'x'.join(bounds[screen]): found.add(screen)
            elif any(Path(arg).name == 'gnome-backend.py' for arg in argv):
                if str(renderer) not in argv: continue
                for i, arg in enumerate(argv[:-1]):
                    if arg == '--screen-root' and argv[i+1] in expected:
                        screen = argv[i+1]
                        if resolve_background(background)[0] == expected[screen]: found.add(screen)
        except (OSError, ValueError, IndexError, UnicodeError): continue
    return found


def main():
    runtime = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
    with (runtime/'wallpaper-restore.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        restore()


def restore():
    root = config_home() / 'Linux Wallpaper Engine'
    try:
        settings = json.loads((root / 'settings.json').read_text())
        state = json.loads((root / 'active-wallpapers.json').read_text())
    except (OSError, ValueError): return
    if not settings.get('restoreLastWallpaper', True): return
    renderer = backend_path()
    # Restore each missing screen independently. Preview/compatibility windows
    # and an already-running wallpaper on another monitor must not block it.
    from importlib.util import spec_from_file_location, module_from_spec
    spec = spec_from_file_location('restore_adapter', Path(__file__).with_name('gnome-backend.py'))
    adapter = module_from_spec(spec); spec.loader.exec_module(adapter)
    bounds = adapter.monitors()
    active = state.get('activeWallpapers', {})
    present = active_screens(renderer, active, bounds)
    logdir = config_home() / 'wallpaper-engine'
    logdir.mkdir(parents=True, exist_ok=True)
    with (logdir / 'restore.log').open('a') as output:
        for screen, options in active.items():
            if screen not in bounds or screen in present: continue
            args = restore_args(renderer, screen, options, settings, Path(__file__).resolve().with_name('gnome-backend.py'))
            if args:
                subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=output, stderr=output, start_new_session=True)


if __name__ == '__main__':
    main()
