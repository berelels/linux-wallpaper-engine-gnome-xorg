"""Write per-user wrappers without embedding the maintainer's machine paths."""
import json
import os
from pathlib import Path
import shlex
import shutil
import sys
import sysconfig


def shell(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('#!/bin/sh\nset -e\n' + text)
    path.chmod(0o755)


def desktop_exec(path):
    return '"' + str(path).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%') + '"'


def configure(repo, app, player, browser):
    q = shlex.quote
    app.mkdir(parents=True, exist_ok=True)
    tools = app / 'tools'
    tools.mkdir(exist_ok=True)
    for name in ['wmctrl', 'xrandr', 'xprop', 'xwininfo', 'xdotool']:
        shutil.copy2(shutil.which(name), tools / name)
    python = app / 'python'
    (python / 'bin').mkdir(parents=True, exist_ok=True)
    shutil.copy2(sys.executable, python / 'bin/python3')
    stdlib = Path(sysconfig.get_path('stdlib'))
    shutil.copytree(stdlib, python / 'lib' / stdlib.name, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', 'test', 'tests', 'site-packages', 'dist-packages'))
    for name in ['gnome-backend.py', 'change-wallpaper.sh', 'run-wallpaper.sh']:
        shutil.copy2(repo / name, app / name)
    for name in ['launch-browser.py', 'runtime.py']:
        shutil.copy2(repo / 'setup' / name, app / name)
    (app / 'install.json').write_text(json.dumps({'player': str(player), 'browser': str(browser)}, indent=2))
    (player / 'deps').mkdir(exist_ok=True)
    shell(app / 'bin/linux-wallpaperengine.real',
          f'export LD_LIBRARY_PATH={q(str(player / "deps") + ":" + str(player))}${{LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}}\n'
          f'cd {q(str(player))}\nexec ./linux-wallpaperengine "$@"\n')
    shell(app / 'bin/linux-wallpaperengine',
          f'export PATH={q(str(tools))}:"$PATH"\n'
          f'export LD_LIBRARY_PATH={q(str(player / "deps"))}${{LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}}\n'
          f'export PYTHONHOME={q(str(python))}\n'
          f'exec {q(str(python / "bin/python3"))} {q(str(app / "gnome-backend.py"))} '
          f'{q(str(app / "bin/linux-wallpaperengine.real"))} "$@"\n')
    shell(app / 'open-browser', f'exec /usr/bin/python3 {q(str(app / "launch-browser.py"))} "$@"\n')
    # The separate launcher is still useful when Steam is offline.
    local = Path.home() / '.local/bin'
    local.mkdir(parents=True, exist_ok=True)
    for name in ['change-wallpaper.sh', 'run-wallpaper.sh', 'gnome-backend.py']:
        target = local / name
        if target.exists():
            shutil.copy2(target, target.with_suffix(target.suffix + '.before-setup'))
        shutil.copy2(repo / name, target)
        target.chmod(0o755)
    applications = Path.home() / '.local/share/applications'
    applications.mkdir(parents=True, exist_ok=True)
    entries = [('linux-wallpaper-engine-steam.desktop', 'Linux Wallpaper Engine', app / 'open-browser'),
               ('wallpaper-engine.desktop', 'Change Animated Wallpaper', local / 'change-wallpaper.sh')]
    for filename, name, executable in entries:
        target = applications / filename
        if target.exists(): shutil.copy2(target, target.with_suffix('.desktop.before-setup'))
        target.write_text(f'[Desktop Entry]\nType=Application\nName={name}\nExec={desktop_exec(executable)}\n'
                          'Icon=preferences-desktop-wallpaper\nTerminal=false\nCategories=Utility;Graphics;\n')
    startup = Path.home() / '.config/autostart/wallpaper-engine.desktop'
    startup.parent.mkdir(parents=True, exist_ok=True)
    # Preserve an existing startup preference. New installs restore once the selector saves a choice.
    if not startup.exists():
        startup.write_text('[Desktop Entry]\nType=Application\nName=Wallpaper Engine Autostart\n'
                           f'Exec={desktop_exec(local / "start-wallpaper.sh")}\n'
                           f'TryExec={local / "start-wallpaper.sh"}\nX-GNOME-Autostart-enabled=true\n')


if __name__ == '__main__':
    configure(*map(Path, sys.argv[1:]))
