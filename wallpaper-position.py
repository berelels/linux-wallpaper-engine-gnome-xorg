#!/usr/bin/env python3
"""Adjust wallpaper framing live, independently for each monitor."""
import json
import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import re

CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'wallpaper-engine/positions.json'


def load_positions():
    try:
        data = json.loads(CONFIG.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_position(monitor, x, y, zoom):
    data = load_positions()
    data[monitor] = {'x': float(x), 'y': float(y), 'zoom': float(zoom)}
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    temporary = CONFIG.with_name(CONFIG.name + f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(data, indent=2) + '\n')
    temporary.replace(CONFIG)


def main():
    root = tk.Tk(); root.title('Wallpaper Position'); root.resizable(False, False)
    frame = ttk.Frame(root, padding=20); frame.grid()
    try:
        output = subprocess.check_output(['xrandr', '--query'], text=True)
        monitors = re.findall(r'^(\S+) connected (?:primary )?\d+x\d+[+-]\d+[+-]\d+', output, re.M)
    except (OSError, subprocess.SubprocessError) as exc:
        messagebox.showerror('Wallpaper Position', str(exc)); root.destroy(); return
    if not monitors:
        messagebox.showerror('Wallpaper Position', 'No active X11 monitors found.'); root.destroy(); return
    selected = tk.StringVar(value=monitors[0])
    ttk.Label(frame, text='Monitor').grid(row=0, column=0, sticky='w')
    chooser = ttk.Combobox(frame, values=monitors, textvariable=selected, state='readonly', width=24)
    chooser.grid(row=0, column=1, sticky='ew')
    variables = [tk.DoubleVar(value=n) for n in (50, 50, 100)]
    loading = False
    pending = None
    def publish():
        nonlocal pending
        pending = None
        try: save_position(selected.get(), *(v.get() for v in variables))
        except OSError as exc: messagebox.showerror('Cannot save position', str(exc))
    def changed(*_):
        nonlocal pending
        if loading: return
        if pending is not None: root.after_cancel(pending)
        pending = root.after(100, publish)
    def refresh(*_):
        nonlocal loading, pending
        if pending is not None:
            root.after_cancel(pending); pending = None
        loading = True
        settings = load_positions().get(selected.get(), {})
        for v, key, default in zip(variables, ('x','y','zoom'), (50,50,100)):
            v.set(settings.get(key, default))
        loading = False
    chooser.bind('<<ComboboxSelected>>', refresh)
    for row, (label, variable, start, end) in enumerate(zip(
        ('Horizontal framing', 'Vertical framing', 'Zoom (%)'), variables, (0,0,100), (100,100,300)), 1):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky='w')
        tk.Scale(frame, variable=variable, from_=start, to=end, orient='horizontal', length=280,
                 resolution=1, command=changed).grid(row=row, column=1)
    def reset():
        for v, n in zip(variables, (50,50,100)): v.set(n)
        changed()
    ttk.Button(frame, text='Reset to center', command=reset).grid(row=4, column=0, pady=12)
    ttk.Button(frame, text='Done', command=lambda: close()).grid(row=4, column=1, sticky='e')
    ttk.Label(frame, text='Changes apply live and are saved automatically.\nZoom in to allow movement when the image already fits.',
              justify='left').grid(row=5, column=0, columnspan=2, sticky='w')
    def close():
        if pending is not None:
            root.after_cancel(pending); publish()
        root.destroy()
    root.protocol('WM_DELETE_WINDOW', close)
    refresh(); root.mainloop()


if __name__ == '__main__': main()
