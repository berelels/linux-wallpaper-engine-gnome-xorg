import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
spec = importlib.util.spec_from_file_location('session_patch', Path(__file__).with_name('patch-browser-session.py'))
patcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)

class SessionPatchTests(unittest.TestCase):
    def archive(self, directory, version='0.4.11'):
        package = json.dumps({'version': version, 'main': '.vite/build/main.js'}).encode()
        raw = json.dumps({'files': {'package.json': {'size': len(package), 'offset': '0'}, 'sentinel': {'size': 8, 'offset': str(len(package))}}}).encode()
        payload = struct.pack('<I', len(raw)) + raw + b'\0' * (-len(raw) % 4)
        header = struct.pack('<I', len(payload)) + payload
        path = Path(directory)/'app.asar'
        path.write_bytes(struct.pack('<II', 4, len(header)) + header + package + b'original')
        return path

    def test_preserves_payload_backup_and_idempotence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.archive(directory); original = path.read_bytes()
            self.assertTrue(patcher.patch_archive(path))
            self.assertEqual(path.with_name('app.asar.before-persistent-session').read_bytes(), original)
            header, offset = patcher.read_archive(path); content = path.read_bytes()
            entry = header['files']['sentinel']; start = offset + int(entry['offset'])
            self.assertEqual(content[start:start+entry['size']], b'original')
            entry = header['files']['package.json']; start = offset + int(entry['offset'])
            self.assertEqual(json.loads(content[start:start+entry['size']])['main'], 'session-main.cjs')
            self.assertFalse(patcher.patch_archive(path))
            self.assertEqual(content, path.read_bytes())

    def test_rejects_unsupported_version_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.archive(directory, '999'); original = path.read_bytes()
            with self.assertRaises(ValueError): patcher.patch_archive(path)
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse(path.with_name('app.asar.before-persistent-session').exists())

    def test_rejects_truncated_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'app.asar'; path.write_bytes(b'bad')
            with self.assertRaises(ValueError): patcher.patch_archive(path)

if __name__ == '__main__': unittest.main()
