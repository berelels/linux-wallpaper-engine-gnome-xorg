#!/usr/bin/env python3
"""Start the full browser with its GNOME backend and session integration helpers."""
import os
from pathlib import Path
import shutil
import signal
import time
import subprocess
import sys
from integration_config import config_home, read_config

HERE = Path(__file__).resolve().parent


def main():
    config = read_config()
    browser = os.environ.get('LWE_BROWSER') or config.get('BROWSER') or shutil.which('linux-wallpaper-engine')
    if not browser or not Path(browser).is_file():
        message = 'Install the native Linux Wallpaper Engine browser first, or configure BROWSER in ~/.config/wallpaper-engine/config.sh.'
        if shutil.which('zenity'):
            subprocess.run(['zenity', '--error', '--title=Linux Wallpaper Engine', '--text=' + message])
        raise SystemExit(message)
    logs = config_home() / 'wallpaper-engine'
    logs.mkdir(parents=True, exist_ok=True)
    for script, logfile in [('sync-overview-background.py', 'overview-sync.log'), ('keep-desktop-icons.py', 'icon-stacking.log')]:
        with (logs / logfile).open('a') as output:
            subprocess.Popen([sys.executable, str(HERE / script)], stdin=subprocess.DEVNULL, stdout=output, stderr=output, start_new_session=True)
    environment = dict(os.environ)
    environment['PATH'] = str(HERE / 'bin') + os.pathsep + environment.get('PATH', '')
    # The patched Electron app owns the singleton, even while its window is hidden.
    # Separate process groups keep a secondary launch from stopping the first one.
    child = subprocess.Popen([browser, *sys.argv[1:]], env=environment,
                             start_new_session=True, close_fds=True)
    def stop(signum, _frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        child.wait()
    finally:
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        for _ in range(20):
            try:
                os.killpg(child.pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.1)
        else:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


if __name__ == '__main__':
    main()
