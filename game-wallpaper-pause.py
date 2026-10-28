#!/usr/bin/env python3
"""Suspend animated wallpaper renderers while Steam games are running."""
import os
import json
from pathlib import Path
import signal
import time

PROC = Path('/proc')
STATE = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')) / 'wallpaper-paused.json'
RENDERER = b'/hanabi-extension@jeffshee.github.io/renderer/renderer.js'
IGNORE_APPS = {b'0', b'', b'993090', b'431960'}  # Lossless Scaling is a utility.
HELPERS = {'steam.exe', 'services.exe', 'winedevice.exe', 'plugplay.exe',
           'svchost.exe', 'explorer.exe', 'rpcss.exe', 'tabtip.exe',
           'xalia.exe', 'conhost.exe', 'rundll32.exe', 'werfault.exe',
           'winedbg.exe', 'wineboot.exe', 'start.exe'}


def snapshot():
    games, renderers = set(), {}
    for proc in PROC.iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if proc.stat().st_uid != os.getuid():
                continue
            cmd = (proc / 'cmdline').read_bytes()
            comm = (proc / 'comm').read_text().strip()
            args = cmd.split(b'\0')
            executable = os.path.basename(os.fsdecode(args[0]))
            is_wallpaper_engine = (executable == 'linux-wallpaperengine'
                                   and b'--bg' in args)
            if (RENDERER in cmd and comm == 'gjs') or is_wallpaper_engine:
                stat = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
                renderers[int(proc.name)] = stat[19]  # PID start time
                continue
            env = dict(item.split(b'=', 1) for item in
                       (proc / 'environ').read_bytes().split(b'\0') if b'=' in item)
            app = env.get(b'SteamGameId', env.get(b'SteamAppId', b'0'))
            if app in IGNORE_APPS:
                continue
            # Steam's reaper lasts for the game session, for native and Proton games.
            # The executable check also catches games if the wrapper has exited.
            exe_args = [arg.decode(errors='replace').rsplit('/', 1)[-1].lower()
                        for arg in cmd.split(b'\0') if arg.lower().endswith(b'.exe')]
            if comm == 'reaper' or any(arg not in HELPERS for arg in exe_args):
                games.add(app.decode(errors='replace'))
        except (OSError, ValueError, IndexError):
            continue
    return games, renderers


def resume(paused, current):
    for pid, started in list(paused.items()):
        if current.get(pid) == started:
            try:
                os.kill(pid, signal.SIGCONT)
            except ProcessLookupError:
                pass
        paused.pop(pid, None)


def save_paused(paused):
    temporary = STATE.with_suffix('.tmp')
    temporary.write_text(json.dumps(paused))
    temporary.replace(STATE)


def main():
    try:
        paused = {int(pid): started for pid, started in json.loads(STATE.read_text()).items()}
    except (OSError, ValueError, AttributeError):
        paused = {}
    # Recover only processes this service suspended, checking PID start times.
    resume(paused, snapshot()[1])
    save_paused(paused)
    previous = None
    closing = False
    def stop(_signum, _frame):
        nonlocal closing
        closing = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        while not closing:
            games, renderers = snapshot()
            if games != previous:
                print('Games running: ' + ', '.join(sorted(games)) if games
                      else 'No games running; wallpaper resumed', flush=True)
                previous = games
            if games:
                for pid, started in renderers.items():
                    if paused.get(pid) != started:
                        try:
                            paused[pid] = started
                            save_paused(paused)
                            os.kill(pid, signal.SIGSTOP)
                            print(f'Wallpaper paused (PID {pid})', flush=True)
                        except ProcessLookupError:
                            pass
                paused = {pid: started for pid, started in paused.items()
                          if renderers.get(pid) == started}
            else:
                resume(paused, renderers)
            save_paused(paused)
            time.sleep(2)
    finally:
        resume(paused, snapshot()[1])
        save_paused(paused)


if __name__ == '__main__':
    main()
