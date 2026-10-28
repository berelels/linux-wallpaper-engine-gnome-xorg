#!/usr/bin/env python3
"""Copy the shared libraries a directory of ELF files needs into DIR/bundled.

Libraries named in the AppImage excludelist (libc, GL drivers, X11 core...)
stay on the host. Files that use a bundled library get a RUNPATH that finds
it relative to themselves, so no LD_LIBRARY_PATH wrapper is needed and
/proc/<pid>/exe stays the real executable.

Only direct (NEEDED) dependencies are considered: whatever a host library
needs comes from the host together with it.

--check only reports direct dependencies that would still come from the host
without being on the excludelist, and exits non-zero if any exist.
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

BUNDLED = 'bundled'
LDD_LINE = re.compile(r'^\s*(\S+)\s+=>\s+(not found|\S+)')
ALWAYS_HOST = {'linux-vdso.so.1', 'ld-linux-x86-64.so.2'}


def read_excludelist(path):
    names = set(ALWAYS_HOST)
    for line in Path(path).read_text().splitlines():
        line = line.split('#', 1)[0].strip()
        if line:
            names.add(line.split()[0])
    return names


def is_elf(path):
    try:
        with open(path, 'rb') as handle:
            return handle.read(4) == b'\x7fELF'
    except OSError:
        return False


def elf_files(root):
    for path in sorted(Path(root).rglob('*')):
        if path.is_file() and not path.is_symlink() and is_elf(path):
            yield path


def dependencies(path, search):
    """Return {soname: resolved path or None} as the dynamic loader would see it."""
    env = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'LD_LIBRARY_PATH': search, 'LC_ALL': 'C'}
    result = subprocess.run(['ldd', str(path)], env=env, capture_output=True, text=True)
    found = {}
    for line in result.stdout.splitlines():
        match = LDD_LINE.match(line)
        if match:
            name, target = match.groups()
            found[name] = None if target == 'not found' else Path(target)
    return found


def needed(path):
    """Direct dependencies only. Libraries the host's own libraries pull in stay on the host."""
    out = subprocess.run(['readelf', '-d', str(path)], capture_output=True, text=True,
                         env={**os.environ, 'LC_ALL': 'C'}, check=True).stdout
    found = set(re.findall(r'\(NEEDED\)\s+Shared library: \[([^\]]+)\]', out))
    if '(NEEDED)' in out and not found:
        raise RuntimeError(f'Could not parse readelf output for {path}')
    return found


def inside(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def bundle(root, excluded):
    root = Path(root).resolve()
    target = root / BUNDLED
    target.mkdir(exist_ok=True)
    # Directories that hold libraries inside the tree, so local copies win.
    search = ':'.join(sorted({str(p.parent) for p in elf_files(root)}))
    missing, users = set(), set()
    pending = list(elf_files(root))
    seen = set()
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        direct = needed(current)
        for name, resolved in dependencies(current, search).items():
            if name in excluded or name not in direct:
                continue
            if resolved is None:
                missing.add(f'{name} (needed by {current.relative_to(root)})')
                continue
            if inside(resolved, root):
                if inside(resolved, target):
                    users.add(current)
                continue
            copy = target / name
            if not copy.exists():
                shutil.copy2(resolved.resolve(), copy)
                copy.chmod(0o755)
                pending.append(copy)
            users.add(current)
    for path in sorted(users):
        relative = os.path.relpath(target, path.parent)
        wanted = '$ORIGIN' if relative == '.' else '$ORIGIN/' + relative
        current = subprocess.run(['patchelf', '--print-rpath', str(path)],
                                 capture_output=True, text=True, check=True).stdout.strip()
        # Keep only relative entries: absolute ones point into the build machine.
        entries = [entry for entry in current.split(':') if entry.startswith('$ORIGIN')]
        if wanted not in entries:
            subprocess.run(['patchelf', '--set-rpath', ':'.join(['$ORIGIN', wanted] + [
                e for e in entries if e != '$ORIGIN']), str(path)], check=True)
    return missing


def check(root, excluded):
    """Resolve with no extra search path: only RUNPATHs and the host remain."""
    root = Path(root).resolve()
    problems = []
    for path in elf_files(root):
        direct = needed(path)
        for name, resolved in dependencies(path, '').items():
            if name in excluded or name not in direct:
                continue
            if resolved is None or not inside(resolved, root):
                problems.append(f'{path.relative_to(root)}: {name} -> {resolved or "not found"}')
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('root', help='directory with the executables and libraries to make self-contained')
    parser.add_argument('--excludelist', required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    excluded = read_excludelist(args.excludelist)
    if args.check:
        problems = check(args.root, excluded)
        for line in problems:
            print('host dependency:', line)
        sys.exit(1 if problems else 0)
    missing = bundle(args.root, excluded)
    for line in sorted(missing):
        print('not found:', line, file=sys.stderr)
    sys.exit(1 if missing else 0)


if __name__ == '__main__':
    main()
