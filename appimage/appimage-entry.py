#!/usr/bin/env python3
"""AppImage entry point: install or update the per-user copy, then open the app.

The AppImage is only a carrier. Everything that runs at login or from the menu
lives in ~/.local/share/wallpaper-engine-gnome, so the AppImage can be moved or
deleted after the first run. Open it again to update or uninstall.
"""
import argparse
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import time

APP = Path(__file__).resolve().parent.parent          # usr/lib/lwe/app
LWE = APP.parent                                      # usr/lib/lwe
PAYLOAD = ('browser', 'renderer', 'python', 'tools', 'VERSION')
TITLE = 'Linux Wallpaper Engine'
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP / 'setup'))


def data_home():
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))


def target():
    return data_home() / 'wallpaper-engine-gnome'


def version(root=None):
    try:
        return (Path(root or LWE) / 'VERSION').read_text().strip()
    except FileNotFoundError:
        return None


def installed_version(base=None):
    """Version whose runtime is complete and referenced by the integration."""
    base = Path(base or target())
    try:
        value = (base / 'runtime/current').read_text().strip()
    except FileNotFoundError:
        return None
    if (base / 'runtime' / value / '.complete').exists() and (base / 'run').exists():
        return value
    return None


# ---------- messages ----------
def tell(text, error=False):
    print(text, file=sys.stderr if error else sys.stdout)
    if shutil.which('zenity') and os.environ.get('DISPLAY') and not sys.stdin.isatty():
        subprocess.run(['zenity', '--error' if error else '--info', '--title=' + TITLE,
                        '--width=420', '--text=' + text], stderr=subprocess.DEVNULL)


def ask(text):
    if sys.stdin.isatty():
        return input(text + ' [y/N] ').strip().lower() in ('y', 'yes', 's', 'sim')
    if shutil.which('zenity') and os.environ.get('DISPLAY'):
        return subprocess.run(['zenity', '--question', '--title=' + TITLE, '--width=460',
                               '--text=' + text], stderr=subprocess.DEVNULL).returncode == 0
    return False


# ---------- checks ----------
def platform_problem(env=os.environ, machine=None):
    if (machine or platform.machine()) != 'x86_64':
        return 'This AppImage supports x86_64 only.'
    if os.geteuid() == 0:
        return 'Run it as your desktop user, not as root.'
    if env.get('XDG_SESSION_TYPE') != 'x11' or 'gnome' not in env.get('XDG_CURRENT_DESKTOP', '').lower():
        return 'Log in to a GNOME (or Zorin) session on X11. Wayland is not supported.'
    if not env.get('DISPLAY'):
        return 'Run it inside your graphical desktop session.'
    return None


# ---------- install ----------
def copy_payload(dest, source=None):
    """Copy into a temporary folder and rename, so a failed copy never looks installed."""
    dest, source = Path(dest), Path(source or LWE)
    if (dest / '.complete').exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    temporary = dest.with_name(f'.{dest.name}.{os.getpid()}')
    shutil.rmtree(temporary, ignore_errors=True)
    temporary.mkdir()
    try:
        for name in PAYLOAD:
            item = source / name
            if item.is_dir():
                shutil.copytree(item, temporary / name, symlinks=True)
            else:
                shutil.copy2(item, temporary / name)
        (temporary / '.complete').write_text('')
        shutil.rmtree(dest, ignore_errors=True)
        temporary.rename(dest)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)
    return dest


def install_icon(source=None):
    source = Path(source or LWE / 'icon.png')
    if not source.exists():
        return
    icon = data_home() / 'icons/hicolor/256x256/apps/linux-wallpaper-engine.png'
    icon.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, icon)


def integrate(dest):
    from browser_wrapper import detect_steam, update_browser_settings, write_browser_wrapper
    steam = detect_steam()
    if steam is None:
        tell('Steam was not found. Install Steam and Wallpaper Engine, then select the Steam folder '
             'in the browser setup.', error=False)
    kind = steam[0] if steam else 'native'
    browser = write_browser_wrapper(dest / 'native-browser', dest / 'browser/linux-wallpaper-engine', kind)
    update_browser_settings()
    python = dest / 'python/bin/python3'
    subprocess.run([str(python), str(APP / 'install-browser-integration.py'),
                    '--backend', str(dest / 'renderer/linux-wallpaperengine'),
                    '--browser', str(browser), '--python', str(python),
                    '--tools-dir', str(dest / 'tools/bin'), '--update-check'], check=True)


def running_helpers(base):
    sys.path.insert(0, str(APP))
    from importlib.util import module_from_spec, spec_from_file_location
    spec = spec_from_file_location('uninstall', APP / 'uninstall-browser-integration.py')
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return list(module.helper_processes(Path(base)))


def stop_helpers(base):
    pids = running_helpers(base)
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 5
    while pids and time.monotonic() < deadline:
        pids = [pid for pid in pids if Path(f'/proc/{pid}').exists()]
        time.sleep(0.1)
    return not pids


def install(base=None):
    base = Path(base or target())
    new = version()
    old = installed_version(base)
    if old and old != new and not stop_helpers(base):
        raise RuntimeError('Close Linux Wallpaper Engine (tray menu → Quit) and try again.')
    dest = copy_payload(base / 'runtime' / new)
    integrate(dest)
    install_icon()
    (base / 'runtime/current').write_text(new + '\n')
    for other in (base / 'runtime').iterdir():
        if other.is_dir() and other.name != new:
            shutil.rmtree(other, ignore_errors=True)
    return old


def open_app(base=None, restore=False):
    base = Path(base or target())
    # The update check normally starts at login; start it now after an install
    # or update (it exits at once when one is already running).
    helpers = ['update-check.py'] + (['restore-browser-wallpapers.py'] if restore else [])
    for script in helpers:
        subprocess.Popen([str(base / 'run'), str(base / script)],
                         start_new_session=True, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.execv(str(base / 'run'), [str(base / 'run'), str(base / 'browser-launcher.py')])


def uninstall(base=None):
    base = Path(base or target())
    script = base / 'uninstall-browser-integration.py'
    if not script.exists():
        tell('Linux Wallpaper Engine is not installed.')
        return
    subprocess.run([str(base / 'run'), str(script)], check=True)
    (data_home() / 'icons/hicolor/256x256/apps/linux-wallpaper-engine.png').unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--install', action='store_true', help='install or update without opening the app')
    group.add_argument('--uninstall', action='store_true', help='remove the app and restore your background')
    group.add_argument('--check', action='store_true', help='check this system without changing anything')
    group.add_argument('--version', action='store_true')
    args = parser.parse_args()
    if args.version:
        print(version()); return
    problem = platform_problem()
    if args.check:
        print(problem or 'Platform supported. No changes made.'); sys.exit(1 if problem else 0)
    if args.uninstall:
        if ask('Remove Linux Wallpaper Engine and restore your original background?'):
            uninstall(); tell('Linux Wallpaper Engine was removed.')
        return
    if problem:
        tell(problem, error=True); sys.exit(1)
    current, new = installed_version(), version()
    if current != new:
        text = (f'Update Linux Wallpaper Engine from {current} to {new}?' if current else
                'Install Linux Wallpaper Engine for your user?\n\n'
                'It copies the app (about 1 GB) to ~/.local/share/wallpaper-engine-gnome and adds it to '
                'your app menu and login. No sudo is needed. You can delete this AppImage afterwards; '
                'open it again to update or uninstall.')
        if not ask(text):
            return
        try:
            install()
        except (OSError, subprocess.SubprocessError, RuntimeError) as error:
            tell(f'Installation failed: {error}', error=True); sys.exit(1)
        if args.install:
            print('Installed', new); return
        open_app(restore=bool(current))
    if args.install:
        print('Already installed:', new); return
    open_app()


if __name__ == '__main__':
    main()
