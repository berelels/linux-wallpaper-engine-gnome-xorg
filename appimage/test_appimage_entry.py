"""AppImage entry tests use temporary folders only; nothing is installed or started."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('entry', Path(__file__).with_name('appimage-entry.py'))
entry = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(entry)


def payload(root, version):
    root = Path(root)
    for name in ('browser', 'renderer', 'python', 'tools'):
        (root / name).mkdir(parents=True)
        (root / name / 'file').write_text(name)
    (root / 'renderer/link').symlink_to('file')
    (root / 'VERSION').write_text(version + '\n')
    return root


class EntryTests(unittest.TestCase):
    def test_platform_check(self):
        good = {'XDG_SESSION_TYPE': 'x11', 'XDG_CURRENT_DESKTOP': 'zorin:GNOME', 'DISPLAY': ':0'}
        with patch.object(entry.os, 'geteuid', return_value=1000):
            self.assertIsNone(entry.platform_problem(good, 'x86_64'))
            self.assertIn('x86_64', entry.platform_problem(good, 'aarch64'))
            self.assertIn('Wayland', entry.platform_problem({**good, 'XDG_SESSION_TYPE': 'wayland'}, 'x86_64'))
            self.assertIn('GNOME', entry.platform_problem({**good, 'XDG_CURRENT_DESKTOP': 'KDE'}, 'x86_64'))

    def test_copy_is_complete_keeps_symlinks_and_is_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            source = payload(Path(temp) / 'src', '1.0.0')
            dest = Path(temp) / 'install/runtime/1.0.0'
            entry.copy_payload(dest, source)
            self.assertTrue((dest / '.complete').exists())
            self.assertTrue((dest / 'renderer/link').is_symlink())
            self.assertEqual((dest / 'VERSION').read_text().strip(), '1.0.0')
            (dest / 'renderer/file').write_text('kept')
            entry.copy_payload(dest, source)          # already complete: not copied again
            self.assertEqual((dest / 'renderer/file').read_text(), 'kept')
            self.assertEqual([p.name for p in dest.parent.iterdir()], ['1.0.0'])

    def test_failed_copy_leaves_nothing_that_looks_installed(self):
        with tempfile.TemporaryDirectory() as temp:
            source = payload(Path(temp) / 'src', '1.0.0')
            (source / 'tools').rename(source / 'gone')
            dest = Path(temp) / 'install/runtime/1.0.0'
            with self.assertRaises(OSError):
                entry.copy_payload(dest, source)
            self.assertFalse(dest.exists())
            self.assertEqual(list(dest.parent.iterdir()), [])

    def test_installed_version_needs_complete_runtime_and_wrapper(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            self.assertIsNone(entry.installed_version(base))
            (base / 'runtime/1.0.0').mkdir(parents=True)
            (base / 'runtime/current').write_text('1.0.0\n')
            self.assertIsNone(entry.installed_version(base))
            (base / 'runtime/1.0.0/.complete').write_text('')
            (base / 'run').write_text('')
            self.assertEqual(entry.installed_version(base), '1.0.0')

    def test_update_replaces_old_runtime_after_integration(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / 'install'
            old = base / 'runtime/0.9.0'
            old.mkdir(parents=True); (old / '.complete').write_text('')
            (base / 'runtime/current').write_text('0.9.0\n'); (base / 'run').write_text('')
            source = payload(Path(temp) / 'src', '1.0.0')
            with patch.object(entry, 'LWE', source), \
                    patch.object(entry, 'stop_helpers', return_value=True) as stop, \
                    patch.object(entry, 'integrate') as integrate, \
                    patch.object(entry, 'install_icon'):
                self.assertEqual(entry.install(base), '0.9.0')
            stop.assert_called_once()
            integrate.assert_called_once_with(base / 'runtime/1.0.0')
            self.assertEqual(sorted(p.name for p in (base / 'runtime').iterdir()), ['1.0.0', 'current'])
            self.assertEqual(entry.installed_version(base), '1.0.0')

    def test_update_stops_when_app_cannot_be_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / 'install'
            (base / 'runtime/0.9.0').mkdir(parents=True); (base / 'runtime/0.9.0/.complete').write_text('')
            (base / 'runtime/current').write_text('0.9.0\n'); (base / 'run').write_text('')
            source = payload(Path(temp) / 'src', '1.0.0')
            with patch.object(entry, 'LWE', source), patch.object(entry, 'stop_helpers', return_value=False), \
                    patch.object(entry, 'integrate') as integrate:
                with self.assertRaises(RuntimeError):
                    entry.install(base)
            integrate.assert_not_called()
            self.assertTrue((base / 'runtime/0.9.0').exists())


if __name__ == '__main__':
    unittest.main()
