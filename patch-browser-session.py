#!/usr/bin/env python3
"""Add persistent-session startup to the supported native browser (v0.4.11).

Preserves every existing packed byte and the external app.asar.unpacked tree.
Run while the browser is closed. A backup is retained beside the archive.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile


def read_archive(path):
    with Path(path).open('rb') as source:
        prefix = source.read(16)
        if len(prefix) != 16:
            raise ValueError('Truncated ASAR archive')
        size, header_size, payload_size, length = struct.unpack('<4I', prefix)
        if size != 4 or header_size != payload_size + 4 or length > header_size - 8 or header_size > 64*1024*1024:
            raise ValueError('Unsupported ASAR header')
        header = json.loads(source.read(length))
    return header, 8 + header_size


def patch_archive(path):
    path = Path(path).resolve()
    header, data_start = read_archive(path)
    files = header['files']
    entry = files['package.json']
    if entry.get('unpacked') or 'offset' not in entry:
        raise ValueError('package.json must be packed')
    with path.open('rb') as source:
        source.seek(data_start + int(entry['offset']))
        package = json.loads(source.read(entry['size']))
    bootstrap = Path(__file__).with_name('session-main.cjs').read_bytes()
    if package.get('main') == 'session-main.cjs':
        with path.open('rb') as source:
            source.seek(data_start + int(files['session-main.cjs']['offset']))
            if source.read(files['session-main.cjs']['size']) != bootstrap:
                raise ValueError('Different session patch already installed; restore backup before upgrading')
        return False
    if package.get('version') != '0.4.11' or package.get('main') != '.vite/build/main.js':
        raise ValueError('Supported browser is v0.4.11 with .vite/build/main.js; archive left unchanged')
    package['main'] = 'session-main.cjs'
    additions = [('package.json', json.dumps(package, indent=2).encode()), ('session-main.cjs', bootstrap)]
    offset = path.stat().st_size - data_start
    for name, content in additions:
        digest = hashlib.sha256(content).hexdigest()
        files[name] = {'size': len(content), 'offset': str(offset), 'integrity': {
            'algorithm': 'SHA256', 'hash': digest, 'blockSize': 4194304, 'blocks': [digest]}}
        offset += len(content)
    raw = json.dumps(header, separators=(',', ':')).encode()
    payload = struct.pack('<I', len(raw)) + raw + b'\0' * (-len(raw) % 4)
    encoded_header = struct.pack('<I', len(payload)) + payload
    backup = path.with_name(path.name + '.before-persistent-session')
    if not backup.exists():
        shutil.copy2(path, backup)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(struct.pack('<II', 4, len(encoded_header)))
            output.write(encoded_header)
            with path.open('rb') as source:
                source.seek(data_start)
                shutil.copyfileobj(source, output)
            for _, content in additions:
                output.write(content)
            output.flush()
            os.fsync(output.fileno())
        shutil.copymode(path, temporary)
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path, help='Native browser resources/app.asar')
    args = parser.parse_args()
    try:
        print('Session fix installed.' if patch_archive(args.archive) else 'Session fix already installed.')
    except (ValueError, KeyError, OSError) as error:
        parser.exit(1, str(error) + '\n')
