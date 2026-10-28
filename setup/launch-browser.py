#!/usr/bin/env python3
"""Launch the complete suite inside Steam's existing Flatpak session."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time

from runtime import bundle_runtime, ensure_steam, find_assets


def configure_assets(app, steam_data, assets):
    settings_path = steam_data / 'config/Linux Wallpaper Engine/settings.json'
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings = {}
    if settings_path.exists():
        settings = json.loads(settings_path.read_text())
        backup = settings_path.with_suffix('.json.before-suite-setup')
        if not backup.exists(): shutil.copy2(settings_path, backup)
    # In this upstream version true means direct execution inside Steam's sandbox;
    # it prevents flatpak-spawn --host. It does not relax Flatpak permissions.
    settings.update(assetsDir=str(assets), flatpakBypass=True, windowMode=False)
    temp = settings_path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(settings, indent=2))
    temp.replace(settings_path)
    library = assets.parents[3]
    config = Path.home() / '.config/wallpaper-engine/config.sh'
    config.parent.mkdir(parents=True, exist_ok=True)
    if config.exists() and not config.with_suffix('.sh.before-suite-setup').exists():
        shutil.copy2(config, config.with_suffix('.sh.before-suite-setup'))
    values = {'BINARY': str(app / 'bin/linux-wallpaperengine'), 'STEAM_PATH': str(library),
              'ASSETS': str(assets), 'WORKSHOP': str(library / 'steamapps/workshop/content/431960')}
    config.write_text(''.join(f'{key}={shlex.quote(value)}\n' for key, value in values.items()))


def main():
    app = Path(__file__).resolve().parent
    manifest = json.loads((app / 'install.json').read_text())
    player, browser = Path(manifest['player']), Path(manifest['browser'])
    steam_data = Path.home() / '.var/app/com.valvesoftware.Steam'
    steam = steam_data / '.local/share/Steam'
    setup = '--setup-runtime' in sys.argv[1:]
    instance = ensure_steam()
    if setup:
        bundle_runtime(instance, app, player)
    assets = find_assets(steam)
    if not assets:
        subprocess.Popen(['flatpak', 'run', 'com.valvesoftware.Steam', 'steam://install/431960'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        while not assets:
            result = subprocess.run(['zenity', '--question', '--title=Finish Steam setup',
                '--ok-label=Check installation', '--cancel-label=Finish later', '--width=520',
                '--text=The application components are installed. Steam still needs your account.\n\n'
                       'Sign in to Steam with an account that owns Wallpaper Engine, then install it. '
                       'If Steam does not offer Install, enable Proton Experimental in the game’s '
                       'Properties → Compatibility. Wait for the download to finish.\n\n'
                       'Click Check installation when Steam finishes. No credentials are collected by this launcher.'])
            if result.returncode:
                raise RuntimeError('Steam assets are not ready. Open Linux Wallpaper Engine later to finish setup.')
            assets = find_assets(steam)
    if setup or not (app / 'configured-assets').exists() or (app / 'configured-assets').read_text() != str(assets):
        configure_assets(app, steam_data, assets)
        (app / 'configured-assets').write_text(str(assets))
    if setup:
        print('Runtime libraries and Steam assets verified.')
        return
    environment = {
        'HOME': str(Path.home()), 'DISPLAY': os.environ.get('DISPLAY', ':0'),
        'XAUTHORITY': '/run/flatpak/Xauthority',
        'XDG_RUNTIME_DIR': os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'),
        'XDG_SESSION_TYPE': 'x11', 'XDG_CURRENT_DESKTOP': os.environ.get('XDG_CURRENT_DESKTOP', 'GNOME'),
        'XDG_CACHE_HOME': str(steam_data / 'cache'), 'XDG_CONFIG_HOME': str(steam_data / 'config'),
        'XDG_DATA_HOME': str(steam_data / 'data'),
        'PATH': f'{app}/bin:{app}/tools:/app/bin:/app/utils/bin:/usr/bin:/bin',
    }
    command = ['flatpak', 'enter', instance, 'env',
               *[f'{key}={value}' for key, value in environment.items()],
               str(browser / 'linux-wallpaper-engine'), *sys.argv[1:]]
    os.execvp(command[0], command)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'Wallpaper setup: {error}', file=sys.stderr)
        subprocess.run(['zenity', '--error', '--title=Wallpaper Engine setup', '--text', str(error)])
        sys.exit(1)
