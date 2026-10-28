"""Host-side Steam discovery and dependency repair for the private app runtime."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import time


def steam_session():
    result = subprocess.check_output(['flatpak', 'ps', '--columns=instance,application'], text=True)
    for line in result.splitlines():
        columns = line.split()
        if len(columns) < 2 or columns[1] != 'com.valvesoftware.Steam': continue
        found = subprocess.run(['flatpak', 'enter', columns[0], 'sh', '-c', 'pgrep -x steam >/dev/null'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if found.returncode == 0: return columns[0]
    return None


def ensure_steam():
    instance = steam_session()
    if instance: return instance
    subprocess.Popen(['flatpak', 'run', 'com.valvesoftware.Steam'],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(90):
        time.sleep(1)
        instance = steam_session()
        if instance: return instance
    raise RuntimeError('Steam did not start. Open Steam and sign in, then launch Linux Wallpaper Engine again.')


def library_roots(steam):
    roots = [steam]
    vdf = steam / 'steamapps/libraryfolders.vdf'
    if vdf.exists():
        for value in re.findall(r'"path"\s*"((?:\\.|[^"\\])*)"', vdf.read_text()):
            roots.append(Path(value.replace('\\\\', '\\').replace('\\"', '"')))
    return list(dict.fromkeys(roots))


def find_assets(steam):
    for library in library_roots(steam):
        assets = library / 'steamapps/common/wallpaper_engine/assets'
        if assets.is_dir() and any(assets.iterdir()): return assets
    return None


def bundle_runtime(instance, app, player):
    deps = player / 'deps'
    deps.mkdir(exist_ok=True)
    targets = [player / 'linux-wallpaperengine', app / 'python/bin/python3',
               *[app / 'tools' / tool for tool in ['wmctrl', 'xrandr', 'xprop', 'xwininfo', 'xdotool']],
               *list((app / 'python/lib').glob('python*/lib-dynload/_ctypes*.so'))]
    mapping = {}
    for target in targets:
        result = subprocess.run(['ldd', str(target)], capture_output=True, text=True)
        mapping.update(re.findall(r'^\s*(\S+) => (/\S+) ', result.stdout, re.M))
    cache = subprocess.check_output(['/sbin/ldconfig', '-p'], text=True)
    for name, path in re.findall(r'^\s*(\S+) \([^\n]*x86-64[^\n]*\) => (\S+)', cache, re.M):
        mapping.setdefault(name, path)
    # Match ncurses' host version when it is pulled into the bundled dependency graph.
    if 'libtinfo.so.6' in mapping:
        shutil.copy2(mapping['libtinfo.so.6'], deps / 'libtinfo.so.6')
    listing = subprocess.check_output(['flatpak', 'ps', '--columns=instance,application'], text=True)
    instances = {instance}
    for line in listing.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == 'com.valvesoftware.Steam':
            instances.add(parts[0])
    for _ in range(20):
        missing = set()
        for runtime_instance in instances:
            for target in targets:
                result = subprocess.run(['flatpak', 'enter', runtime_instance, 'env',
                    f'LD_LIBRARY_PATH={deps}:{player}', 'ldd', str(target)], capture_output=True, text=True)
                output = result.stdout + result.stderr
                missing.update(re.findall(r'^\s*(\S+) => not found', output, re.M))
                if 'version `' in output or 'version \'' in output:
                    raise RuntimeError(f'Incompatible runtime library for {target}: {output}')
                if result.returncode and not missing:
                    raise RuntimeError(f'Cannot inspect runtime dependencies for {target}: {output}')
        if not missing: break
        for name in missing:
            if name not in mapping: raise RuntimeError(f'No host library available for {name}')
            shutil.copy2(mapping[name], deps / name)
    else: raise RuntimeError('Could not resolve Steam runtime dependencies')
    subprocess.run(['flatpak', 'enter', instance, 'env', f'LD_LIBRARY_PATH={deps}',
                    f'PYTHONHOME={app / "python"}', str(app / 'python/bin/python3'),
                    '-c', 'import ctypes, subprocess; ctypes.CDLL("libX11.so.6")'], check=True)

    # Actually execute the wrapper: ldd alone cannot verify its environment.
    for runtime_instance in instances:
        result = subprocess.run(['flatpak', 'enter', runtime_instance,
                                 str(app / 'bin/linux-wallpaperengine'), '--help'],
                                capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(f'Backend startup check failed: {result.stderr}')
