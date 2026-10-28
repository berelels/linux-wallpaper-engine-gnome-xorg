"""Connect the downloaded native browser to the GNOME integration."""
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
sys.path.insert(0, str(Path(__file__).resolve().parent))
from browser_wrapper import update_browser_settings, write_browser_wrapper
# run.sh installs Flatpak Steam, so Steamworks needs the Flatpak HOME.
launch = write_browser_wrapper(app / 'native-browser', browser / 'linux-wallpaper-engine', 'flatpak',
                               home=home, config=config, data=data)
update_browser_settings(config)
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
