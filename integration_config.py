"""Read launcher paths without executing the user's shell configuration."""
import os
from pathlib import Path
import shlex


def config_home():
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))


def read_config(path=None):
    """Read plain KEY=VALUE assignments, including shell-quoted path names."""
    config = Path(path) if path else config_home() / 'wallpaper-engine/config.sh'
    values = {}
    try:
        lines = config.read_text().splitlines()
    except FileNotFoundError:
        return values
    for line in lines:
        name, separator, value = line.partition('=')
        name = name.strip()
        if not separator or not name.isidentifier():
            continue
        try:
            words = shlex.split(value, comments=True)
        except ValueError:
            continue
        if len(words) == 1:
            values[name] = words[0]
    return values


def backend_path(explicit=None):
    """Resolve the real renderer, with command line and environment overrides."""
    value = explicit or os.environ.get('LWE_BACKEND') or read_config().get('BINARY')
    return Path(value or '/opt/linux-wallpaperengine/linux-wallpaperengine').expanduser().resolve()
