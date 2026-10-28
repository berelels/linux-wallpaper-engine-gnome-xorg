"""Launcher for the native browser and its settings, shared by run.sh and the AppImage."""
import json
import os
from pathlib import Path
import shlex

FLATPAK_HOME = Path('.var/app/com.valvesoftware.Steam')


def detect_steam(home=None):
    """Return ('flatpak' | 'native', Steam folder), or None when Steam is missing."""
    home = Path(home or Path.home())
    flatpak = home / FLATPAK_HOME / '.local/share/Steam'
    if flatpak.is_dir():
        return 'flatpak', flatpak
    for candidate in (home / '.local/share/Steam', home / '.steam/steam', home / '.steam/debian-installation'):
        if candidate.is_dir():
            return 'native', candidate.resolve()
    return None


def write_browser_wrapper(launch, browser, steam_kind, home=None, config=None, data=None):
    """Keep the host XDG profile; Flatpak Steam also needs its HOME for Steamworks."""
    home = Path(home or Path.home())
    config = Path(config or os.environ.get('XDG_CONFIG_HOME', home / '.config'))
    data = Path(data or os.environ.get('XDG_DATA_HOME', home / '.local/share'))
    values = {'XDG_CONFIG_HOME': config, 'XDG_DATA_HOME': data}
    if steam_kind == 'flatpak':
        values = {'HOME': home / FLATPAK_HOME, **values}
    launch = Path(launch)
    launch.write_text('#!/bin/sh\n' + '\n'.join(
        'export ' + key + '=' + shlex.quote(str(value)) for key, value in values.items())
        + '\nexec ' + shlex.quote(str(browser)) + ' "$@"\n')
    launch.chmod(0o755)
    return launch


def update_browser_settings(config=None):
    """Closing hides the window to the tray, so wallpapers keep their owner."""
    config = Path(config or os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    settings = config / 'Linux Wallpaper Engine/settings.json'
    settings.parent.mkdir(parents=True, exist_ok=True)
    values = json.loads(settings.read_text()) if settings.exists() else {}
    values.update(enableSystemTray=True, minimizeOnClose=True, minimizeOnStartup=False)
    settings.write_text(json.dumps(values, indent=2))
    return settings
