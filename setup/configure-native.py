"""Connect the downloaded native browser to the GNOME integration."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

repo, app, player, browser = map(Path, sys.argv[1:])
home = Path.home()
config = Path(os.environ.get('XDG_CONFIG_HOME', home / '.config'))
data = Path(os.environ.get('XDG_DATA_HOME', home / '.local/share'))
steam_home = home / '.var/app/com.valvesoftware.Steam'
subprocess.run([sys.executable, str(repo / 'patch-browser-session.py'), str(browser / 'resources/app.asar')], check=True)
# Keep the host XDG profile, while allowing Steamworks to locate Flatpak Steam.
launch = app / 'native-browser'
launch.write_text('#!/bin/sh\n' + '\n'.join('export ' + key + '=' + shlex.quote(str(value)) for key, value in {
    'HOME': steam_home, 'XDG_CONFIG_HOME': config, 'XDG_DATA_HOME': data}.items()) +
    '\nexec ' + shlex.quote(str(browser / 'linux-wallpaper-engine')) + ' "$@"\n')
launch.chmod(0o755)
settings = config / 'Linux Wallpaper Engine/settings.json'
settings.parent.mkdir(parents=True, exist_ok=True)
values = json.loads(settings.read_text()) if settings.exists() else {}
values.update(enableSystemTray=True, minimizeOnClose=True, minimizeOnStartup=False)
settings.write_text(json.dumps(values, indent=2))
subprocess.run([sys.executable, str(repo / 'install-browser-integration.py'),
    '--backend', str(player / 'linux-wallpaperengine'), '--browser', str(launch)], check=True)
# Existing suite launchers now reach the same native app/profile.
old = app / 'open-browser'
old.write_text('#!/bin/sh\nexec ' + shlex.quote(sys.executable) + ' ' + shlex.quote(str(data / 'wallpaper-engine-gnome/browser-launcher.py')) + ' "$@"\n')
old.chmod(0o755)
legacy = data / 'applications/linux-wallpaper-engine-steam.desktop'
if legacy.exists():
    lines = [line for line in legacy.read_text().splitlines() if not line.startswith('Hidden=')]
    legacy.write_text('\n'.join(lines) + '\nHidden=true\n')
print('Keep Steam running. In browser setup, choose Steam at ' + str(steam_home / '.local/share/Steam'))
