"""Resolve Workshop presets without modifying downloaded content."""
import json
from pathlib import Path


def resolve_background(background):
    current = Path(background)
    if not (current / 'project.json').is_file():
        return background, []
    seen, presets = set(), []
    while True:
        resolved = current.resolve()
        if resolved in seen:
            raise ValueError('Wallpaper preset dependency cycle')
        seen.add(resolved)
        project = json.loads((current / 'project.json').read_text())
        if project.get('type') and project.get('file'):
            break
        dependency = str(project.get('dependency', ''))
        if not dependency.isdecimal():
            raise ValueError(f'Wallpaper {current.name} has no playable content or valid dependency')
        presets.append(project.get('preset', {}))
        current = current.parent / dependency
        if not (current / 'project.json').is_file():
            raise ValueError(f'Wallpaper requires Workshop item {dependency}; download it in Steam first')
    values = {}
    for preset in reversed(presets):
        values.update(preset)
    properties = project.get('general', {}).get('properties', {})
    flags = []
    for key, value in values.items():
        if key not in properties or value is None or isinstance(value, (dict, list)):
            continue
        if isinstance(value, bool):
            value = 'true' if value else 'false'
        flags.extend(['--set-property', f'{key}={value}'])
    return str(current), flags


def prepare_arguments(arguments):
    result, properties = list(arguments), []
    for index, arg in enumerate(result[:-1]):
        if arg in ('--bg', '-b'):
            result[index + 1], flags = resolve_background(result[index + 1])
            properties.extend(flags)
    # The backend also accepts a directory as its final positional background.
    if result and Path(result[-1]).is_dir() and (Path(result[-1]) / 'project.json').is_file():
        result[-1], flags = resolve_background(result[-1])
        properties.extend(flags)
    # Explicit user overrides take precedence over preset defaults.
    return properties + result
