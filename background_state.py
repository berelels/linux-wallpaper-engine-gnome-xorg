"""Save and restore the GNOME background replaced by overview integration."""

import json
import os
from pathlib import Path
import subprocess


SCHEMA = 'org.gnome.desktop.background'
KEYS = ('picture-uri', 'picture-uri-dark', 'picture-options')
CONFIG_HOME = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
DATA_HOME = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
STATE = CONFIG_HOME / 'wallpaper-engine/original-background.json'
OUTPUT = DATA_HOME / 'backgrounds/wallpaper-engine'


def setting(key):
    """Return a gsettings value in its serialized GVariant form."""
    return subprocess.check_output(
        ['gsettings', 'get', SCHEMA, key], text=True).strip()


def managed_uri(value, output=OUTPUT):
    """Recognize only the two overview images owned by this integration."""
    expected = {(Path(output) / f'overview-{slot}.png').as_uri()
                for slot in (0, 1)}
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        value = value[1:-1]
    return value in expected


def read_state(path=STATE):
    path = Path(path)
    data = json.loads(path.read_text())
    if (not isinstance(data, dict) or set(data) != set(KEYS)
            or any(not isinstance(data[key], str) for key in KEYS)):
        raise ValueError('Invalid saved GNOME background')
    return data


def save_original(path=STATE, output=OUTPUT):
    """Save settings once, before replacing them with a generated image."""
    path = Path(path)
    if path.exists():
        read_state(path)
        return False
    values = {key: setting(key) for key in KEYS}
    if managed_uri(values['picture-uri'], output) or managed_uri(
            values['picture-uri-dark'], output):
        raise RuntimeError(
            'Cannot save an overview image as the original GNOME background')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{path.name}.{os.getpid()}')
    try:
        temporary.write_text(json.dumps(values, indent=2) + '\n')
        temporary.chmod(0o600)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def restore_original(path=STATE, remove=True):
    """Restore all saved settings, retaining state if any write fails."""
    path = Path(path)
    try:
        values = read_state(path)
    except FileNotFoundError:
        return False
    for key in KEYS:
        subprocess.run(
            ['gsettings', 'set', SCHEMA, key, values[key]], check=True)
    if remove:
        path.unlink()
    return True
