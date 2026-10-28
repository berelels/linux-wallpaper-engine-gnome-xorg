#!/usr/bin/env python3
"""Install the optional native full-browser integration into the current user account."""
import argparse
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from integration_config import backend_path, config_home, read_config

SOURCE = Path(__file__).resolve().parent


def quote_exec(value):
    value = str(value).replace('%', '%%').replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$')
    return '"' + value + '"'


def desktop_entry(name, command, icon='linux-wallpaper-engine', autostart=False):
    lines = ['[Desktop Entry]', 'Type=Application', 'Name=' + name, 'Exec=' + command,
             'Icon=' + icon, 'Terminal=false']
    if autostart:
        lines += ['NoDisplay=true', 'X-GNOME-Autostart-enabled=true']
    else:
        lines += ['Comment=Browse, download and apply animated wallpapers', 'Categories=Utility;']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', help='Path to the real compiled renderer')
    parser.add_argument('--browser', help='Path to the separately installed native full browser')
    parser.add_argument('--no-desktop-shortcut', action='store_true')
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error('Run as your desktop user, without sudo')
    if os.environ.get('XDG_SESSION_TYPE') != 'x11':
        parser.error('This integration requires a GNOME X11 desktop session')
    for command in ('xrandr', 'xprop', 'wmctrl', 'stdbuf', 'gsettings'):
        if not shutil.which(command): parser.error('Missing dependency: ' + command)
    try:
        import PIL
    except ImportError:
        parser.error('Install python3-pil before running this installer')
    renderer = backend_path(args.backend)
    if not renderer.is_file() or not os.access(renderer, os.X_OK):
        parser.error('The real renderer is not executable; pass --backend /path/to/linux-wallpaperengine')
    config = read_config()
    browser = args.browser or config.get('BROWSER') or shutil.which('linux-wallpaper-engine')
    if not browser or not Path(browser).is_file() or not os.access(browser, os.X_OK):
        parser.error('Install the native full browser first, or pass --browser /path/to/linux-wallpaper-engine')
    browser = Path(browser).expanduser().resolve()
    data = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
    target = data / 'wallpaper-engine-gnome'
    target.mkdir(parents=True, exist_ok=True)
    files = ['wallpaper-position.py', 'wallpaper_content.py', 'gnome-backend.py',
             'capture_x11.py', 'integration_config.py', 'background_state.py',
             'sync-overview-background.py', 'keep-desktop-icons.py',
             'browser-launcher.py', 'restore-browser-wallpapers.py',
             'uninstall-browser-integration.py']
    for name in files:
        shutil.copy2(SOURCE / name, target / name)
    (target / 'uninstall-browser-integration.py').chmod(0o755)
    (target / 'bin').mkdir(exist_ok=True)
    shutil.copy2(SOURCE / 'browser-bin/linux-wallpaperengine', target / 'bin/linux-wallpaperengine')
    (target / 'bin/linux-wallpaperengine').chmod(0o755)
    config.update(BINARY=str(renderer), BROWSER=str(browser))
    config_path = config_home() / 'wallpaper-engine/config.sh'
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        shutil.copy2(config_path, config_path.with_suffix('.sh.before-browser-integration'))
    config_path.write_text(''.join(key + '=' + shlex.quote(value) + '\n' for key, value in config.items()))
    command = quote_exec(sys.executable) + ' ' + quote_exec(target / 'browser-launcher.py')
    position_command = quote_exec(sys.executable) + ' ' + quote_exec(target / 'wallpaper-position.py')
    entry = desktop_entry('Linux Wallpaper Engine', command)
    entry += 'Actions=Position;\n\n[Desktop Action Position]\nName=Adjust wallpaper position\nExec=' + position_command + '\n'
    applications = data / 'applications'
    applications.mkdir(parents=True, exist_ok=True)
    (applications / 'linux-wallpaper-engine.desktop').write_text(entry)
    (applications / 'wallpaper-position.desktop').write_text(desktop_entry('Wallpaper Position', position_command))
    if not args.no_desktop_shortcut:
        try:
            desktop = Path(subprocess.check_output(['xdg-user-dir', 'DESKTOP'], text=True).strip())
        except (OSError, subprocess.SubprocessError):
            desktop = Path.home() / 'Desktop'
        if desktop.is_dir():
            shortcut = desktop / 'Linux Wallpaper Engine.desktop'
            shortcut.write_text(entry); shortcut.chmod(0o755)
            if shutil.which('gio'):
                subprocess.run(['gio', 'set', str(shortcut), 'metadata::trusted', 'true'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    autostart = config_home() / 'autostart'
    autostart.mkdir(parents=True, exist_ok=True)
    for name, script in [('wallpaper-overview-sync', 'sync-overview-background.py'), ('wallpaper-icon-stacking', 'keep-desktop-icons.py'), ('wallpaper-browser-restore', 'restore-browser-wallpapers.py')]:
        launch = quote_exec(sys.executable) + ' ' + quote_exec(target / script)
        (autostart / (name + '.desktop')).write_text(desktop_entry(name, launch, autostart=True))
    legacy = autostart / 'wallpaper-engine.desktop'
    if legacy.exists() and 'start-wallpaper.sh' in legacy.read_text():
        shutil.copy2(legacy, legacy.with_suffix('.desktop.before-browser-integration'))
        lines = [line for line in legacy.read_text().splitlines() if not line.startswith('Hidden=')]
        legacy.write_text('\n'.join(lines) + '\nHidden=true\n')
    print('Installed. Open Linux Wallpaper Engine from your desktop or app menu.')
    print('The browser and renderer remain installed separately.')


if __name__ == '__main__':
    main()
