#!/usr/bin/env python3
"""Adapt linux-wallpaperengine screen output to GNOME X11 windows.

Usage: gnome-backend.py BACKEND [linux-wallpaperengine arguments...]
Requires wmctrl, xprop, and xrandr on PATH. Does not change the Workshop browser.
"""
import collections
import ctypes
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from wallpaper_content import prepare_arguments


def renderer_lifetime(libc):
    # The browser uses SIGKILL on Stop. Linux must also terminate its renderer
    # children when this supervisor disappears (SIGKILL cannot be trapped).
    # SIGTERM cannot terminate a renderer suspended by the game-pause service.
    # Runs between fork and exec while relay threads exist, so libc is loaded
    # beforehand and nothing here imports or loads a library.
    parent = os.getppid()
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'prctl(PR_SET_PDEATHSIG) failed')
    if parent == 1 or os.getppid() != parent:
        os._exit(1)


class Relay:
    """Pass renderer output on to TARGET without ever blocking the renderer.

    The Workshop browser opens stderr as a pipe but stops reading it for
    wallpapers it has already rated. Once that pipe filled, every renderer
    froze in the middle of a log write and GNOME reported it as not responding.
    Output waits here while nobody reads, and the oldest chunks are dropped.
    """

    def __init__(self, target, limit=256):
        self.target = target
        self.chunks = collections.deque(maxlen=limit)
        self.ready = threading.Condition()
        self.readers, self.writing = [], False
        threading.Thread(target=self._write, daemon=True).start()

    def attach(self, stream):
        reader = threading.Thread(target=self._read, args=(stream,), daemon=True)
        reader.start()
        self.readers.append(reader)

    def drain(self, timeout=2):
        """Briefly wait for the last output; the browser rates wallpapers by their exit errors."""
        deadline = time.monotonic() + timeout
        for reader in self.readers:
            reader.join(max(0, deadline - time.monotonic()))
        with self.ready:
            while (self.chunks or self.writing) and time.monotonic() < deadline:
                self.ready.wait(0.05)

    def _read(self, stream):
        with stream:
            for chunk in iter(lambda: stream.read1(4096), b''):
                with self.ready:
                    self.chunks.append(chunk)
                    self.ready.notify()

    def _write(self):
        while True:
            with self.ready:
                while not self.chunks:
                    self.ready.wait()
                chunk = self.chunks.popleft()
                self.writing = True
            try:
                os.write(self.target, chunk)
            except OSError:
                pass  # Reader gone: keep draining so the renderers keep running.
            with self.ready:
                self.writing = False
                self.ready.notify_all()


def monitors():
    # --current reads the layout GNOME already applied; --query makes the X
    # server probe every output again and reread each monitor's EDID.
    output = subprocess.check_output(['xrandr', '--current'], text=True)
    found = {}
    for line in output.splitlines():
        match = re.match(r'(\S+) connected (?:primary )?(\d+)x(\d+)([+-]\d+)([+-]\d+)', line)
        if match:
            name, w, h, x, y = match.groups()
            found[name] = (str(int(x)), str(int(y)), w, h)
    return found


def lower_desktop(window):
    """Request bottom stacking within GNOME's desktop layer."""
    class Data(ctypes.Union):
        _fields_ = [('bytes', ctypes.c_char * 20), ('longs', ctypes.c_long * 5)]
    class Client(ctypes.Structure):
        _fields_ = [('type', ctypes.c_int), ('serial', ctypes.c_ulong),
                    ('send_event', ctypes.c_int), ('display', ctypes.c_void_p),
                    ('window', ctypes.c_ulong), ('message_type', ctypes.c_ulong),
                    ('format', ctypes.c_int), ('data', Data)]
    class Event(ctypes.Union):
        _fields_ = [('client', Client), ('pad', ctypes.c_long * 24)]
    x11 = ctypes.CDLL('libX11.so.6')
    signatures = [
        ('XOpenDisplay', ctypes.c_void_p, [ctypes.c_char_p]),
        ('XDefaultRootWindow', ctypes.c_ulong, [ctypes.c_void_p]),
        ('XInternAtom', ctypes.c_ulong, [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]),
        ('XSendEvent', ctypes.c_int, [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int,
                                    ctypes.c_long, ctypes.POINTER(Event)]),
        ('XSync', ctypes.c_int, [ctypes.c_void_p, ctypes.c_int]),
        ('XCloseDisplay', ctypes.c_int, [ctypes.c_void_p]),
    ]
    for name, result, args in signatures:
        function = getattr(x11, name)
        function.restype, function.argtypes = result, args
    display = x11.XOpenDisplay(None)
    if not display:
        raise RuntimeError('Cannot open X11 display to lower wallpaper')
    try:
        event = Event()
        event.client.type = 33  # ClientMessage
        event.client.display = display
        event.client.window = int(window, 0)
        event.client.message_type = x11.XInternAtom(display, b'_NET_RESTACK_WINDOW', 0)
        event.client.format = 32
        event.client.data.longs[0] = 2  # pager source
        event.client.data.longs[1] = 0  # no sibling: bottom of the layer
        event.client.data.longs[2] = 1  # Below
        x11.XSendEvent(display, x11.XDefaultRootWindow(display), 0,
                      (1 << 20) | (1 << 19), ctypes.byref(event))
        x11.XSync(display, 0)
    finally:
        x11.XCloseDisplay(display)


def pin(window, geometry):
    # GNOME constrains fullscreen-sized normal windows to their original monitor.
    # Desktop type permits exact placement and keeps them beneath normal apps.
    subprocess.run(['xprop', '-id', window, '-f', '_NET_WM_WINDOW_TYPE', '32a',
                    '-set', '_NET_WM_WINDOW_TYPE', '_NET_WM_WINDOW_TYPE_DESKTOP'], check=True)
    for args in [
        ['-b', 'remove,above,below'],
        ['-b', 'remove,maximized_vert,maximized_horz'],
        ['-b', 'add,sticky'],
        ['-b', 'add,skip_taskbar,skip_pager'],
        ['-t', '-1'],
        ['-e', '0,' + ','.join(geometry)],
    ]:
        subprocess.run(['wmctrl', '-i', '-r', window, *args], check=True)
    lower_desktop(window)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--lower-window':
        lower_desktop(sys.argv[2])
        return
    if len(sys.argv) < 2:
        raise ValueError('Expected backend executable')
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.environ["OMP_NUM_THREADS"] = "1"
    backend, *original = sys.argv[1:]
    original = prepare_arguments(original)
    screens, args = [], []
    i = 0
    while i < len(original):
        if original[i] == '--screen-root':
            if i + 1 >= len(original):
                raise ValueError('--screen-root requires a monitor name')
            screens.append(original[i + 1])
            i += 2
        else:
            args.append(original[i])
            i += 1
    if screens:
        available = monitors()
        inactive = [name for name in screens if name not in available]
        screens = [name for name in screens if name in available]
        for name in inactive:
            print(f'Monitor {name!r} is not active; retaining the saved selection', file=sys.stderr)
        if not screens:
            raise ValueError('None of the selected monitors is active')
    children = []
    libc = ctypes.CDLL(None, use_errno=True)
    relay = Relay(sys.stderr.fileno())
    def terminate(signum, frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    try:
        if not screens:
            # Windowed and compatibility runs: no placement, same output relay.
            child = subprocess.Popen([backend, *original], preexec_fn=lambda: renderer_lifetime(libc),
                                     stderr=subprocess.PIPE)
            children.append(child)
            relay.attach(child.stderr)
            code = child.wait()
            raise SystemExit(128 - code if code < 0 else code)
        for name in dict.fromkeys(screens):
            geometry = available[name]
            environment = dict(os.environ, WE_POSITION_MONITOR=name,
                WE_POSITION_FILE=str(Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "wallpaper-engine/positions.json"))
            child = subprocess.Popen(
                [backend, '--window', 'x'.join(geometry), *args],
                preexec_fn=lambda: renderer_lifetime(libc), env=environment,
                stderr=subprocess.PIPE)
            children.append(child)
            relay.attach(child.stderr)
            deadline = time.monotonic() + 60
            while True:
                if child.poll() is not None:
                    raise RuntimeError(f'Renderer for {name} exited ({child.returncode})')
                lines = subprocess.check_output(['wmctrl', '-lp'], text=True).splitlines()
                window = next((line.split()[0] for line in lines
                               if len(line.split()) >= 3 and line.split()[2] == str(child.pid)), None)
                if window:
                    pin(window, geometry)
                    print(f'Wallpaper positioned on {name}: {geometry}', flush=True)
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError(f'No player window appeared for {name} within 60 seconds')
                time.sleep(0.2)
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        relay.drain()


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(f'GNOME wallpaper: {exc}', file=sys.stderr)
        sys.exit(1)
