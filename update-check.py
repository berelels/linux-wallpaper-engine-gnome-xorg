#!/usr/bin/env python3
"""Tell the user when a newer AppImage release is out. Checks at most once a day.

Only asks GitHub for this project's latest release; nothing about the computer
is sent. Set UPDATE_CHECK=no in ~/.config/wallpaper-engine/config.sh to stop it.
"""
import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request
from integration_config import read_config

PROJECT = 'berelels/linux-wallpaper-engine-gnome-xorg'
API = f'https://api.github.com/repos/{PROJECT}/releases/latest'
DOWNLOAD = f'https://github.com/{PROJECT}/releases/latest'
DAY = 24 * 3600
HERE = Path(__file__).resolve().parent


def parse(version):
    try:
        return tuple(int(part) for part in str(version).strip().lstrip('v').split('.'))
    except ValueError:
        return None


def installed_version(base=HERE):
    """Version of an AppImage install; None for run.sh installs, which update from git."""
    try:
        return (base / 'runtime/current').read_text().strip() or None
    except FileNotFoundError:
        return None


def latest_release(opener=urllib.request.urlopen):
    request = urllib.request.Request(API, headers={
        'Accept': 'application/vnd.github+json', 'User-Agent': 'linux-wallpaper-engine-gnome'})
    with opener(request, timeout=20) as response:
        data = json.load(response)
    if data.get('draft') or data.get('prerelease'):
        return None
    return str(data.get('tag_name', '')).lstrip('v') or None


def check(state_path, current, fetch=latest_release, notify=None, now=None):
    """Return a newer version to announce, at most once a day and once per version."""
    now = time.time() if now is None else now
    try:
        state = json.loads(Path(state_path).read_text())
    except (OSError, ValueError):
        state = {}
    last = state.get('checked')
    if isinstance(last, (int, float)) and 0 <= now - last < DAY:  # a clock set back checks again
        return None
    latest = fetch()  # Offline: raises, and the next hourly attempt tries again.
    state['checked'] = now
    announce = None
    if (parse(latest) and parse(current) and parse(latest) > parse(current)
            and state.get('notified') != latest):
        announce = state['notified'] = latest
        if notify:
            notify(current, latest)
    temporary = Path(state_path).with_name(Path(state_path).name + '.tmp')
    temporary.write_text(json.dumps(state) + '\n')
    temporary.replace(state_path)
    return announce


def show_notification(current, latest):
    """Wait for the notification in a separate process so the checker keeps running."""
    subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--notify', current, latest],
                     stdin=subprocess.DEVNULL, start_new_session=True)


def notify(current, latest):
    if not shutil.which('notify-send'):
        return
    title = f'Linux Wallpaper Engine {latest} is available'
    body = (f'You have {current}. Download the new AppImage and open it to update. '
            'Gear Lever can also update it for you.')
    common = ['notify-send', '--app-name=Linux Wallpaper Engine', '--icon=linux-wallpaper-engine']
    result = subprocess.run([*common, '--action=open=Download', '--wait', title, body],
                            capture_output=True, text=True)
    if result.returncode != 0:  # libnotify without actions
        subprocess.run([*common, title, body + ' ' + DOWNLOAD])
    elif result.stdout.strip() == 'open' and shutil.which('xdg-open'):
        subprocess.run(['xdg-open', DOWNLOAD])


def disabled(config=None):
    config = read_config() if config is None else config
    return config.get('UPDATE_CHECK', 'yes').lower() in ('no', '0', 'false', 'off')


@contextmanager
def single_instance():
    runtime = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
    with (runtime / 'wallpaper-update-check.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit(0)
        yield


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--notify', nargs=2, metavar=('CURRENT', 'LATEST'), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.notify:
        notify(*args.notify)
        return
    if not installed_version() or disabled():
        return
    with single_instance():
        while True:
            try:
                # Reread each time: an update replaces the installed version.
                current = installed_version()
                if current:
                    check(HERE / 'update-check.json', current, notify=show_notification)
            except (OSError, ValueError) as exc:
                print('Update check: ' + str(exc), flush=True)
            # Hourly wake-ups make the daily check survive suspend and long sessions.
            time.sleep(3600)


if __name__ == '__main__':
    main()
