"""Offline regression tests; no desktop settings or live wallpaper are changed."""

import importlib.util
from contextlib import nullcontext
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image


SPEC = importlib.util.spec_from_file_location(
    'overview', Path(__file__).resolve().parent / 'sync-overview-background.py')
overview = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(overview)


class OverviewTests(unittest.TestCase):
    def setUp(self):
        self.bounds = {'left': (-2, 1, 2, 3), 'main': (0, 0, 4, 2)}
        self.active = {'left': {'backgroundId': '/wallpapers/portrait'},
                       'main': {'backgroundId': '/wallpapers/landscape'}}
        self.windows = {'left': '0x10', 'main': '0x20'}

    def test_monitor_layout_accepts_negative_origins_rotation_and_primary(self):
        layout = ('DP-1 connected 1080x1920-1080+60 left (normal)\n'
                  'HDMI-1 connected primary 3840x2160+0-200 (normal)\n'
                  'DP-2 connected (normal)\nDP-3 disconnected\n')
        with patch.object(overview.subprocess, 'check_output', return_value=layout):
            self.assertEqual(overview.monitors(), {
                'DP-1': (-1080, 60, 1080, 1920), 'HDMI-1': (0, -200, 3840, 2160)})

    def test_composition_preserves_monitor_pixels_and_empty_desktop_regions(self):
        frames = {'left': Image.new('RGB', (2, 3), 'red'),
                  'main': Image.new('RGB', (4, 2), 'blue')}
        canvas = overview.compose(self.bounds, frames)
        self.assertEqual(canvas.size, (6, 4))
        self.assertEqual(canvas.getpixel((0, 0)), (0, 0, 0))
        self.assertEqual(canvas.getpixel((0, 3)), (255, 0, 0))
        self.assertEqual(canvas.getpixel((5, 0)), (0, 0, 255))
        self.assertEqual(canvas.getpixel((5, 3)), (0, 0, 0))

    def test_composition_rejects_window_that_is_still_resizing(self):
        with self.assertRaises(RuntimeError):
            overview.compose(self.bounds, {'left': Image.new('RGB', (3, 2))})

    def test_backend_explicit_and_environment_override_config(self):
        with patch.dict(os.environ, {'LWE_BACKEND': '/environment/renderer'}):
            self.assertEqual(overview.backend_path('/chosen/renderer'), Path('/chosen/renderer'))
            self.assertEqual(overview.backend_path(), Path('/environment/renderer'))

    def test_renderer_must_be_this_users_exact_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backend, other = root / 'renderer', root / 'other-app'
            backend.touch()
            other.touch()
            proc = root / '123'
            proc.mkdir()
            (proc / 'exe').symlink_to(backend)
            argv = [str(backend), '--window', '0x0x4x2', '--bg', '/chosen']
            (proc / 'cmdline').write_bytes(b'\0'.join(word.encode() for word in argv))
            self.assertEqual(overview.renderer_arguments('123', backend, root), argv)
            self.assertIsNone(overview.renderer_arguments('123', other, root))
            with patch.object(overview.os, 'getuid', return_value=os.getuid() + 1):
                self.assertIsNone(overview.renderer_arguments('123', backend, root))

    def test_matching_requires_background_option_geometry_size_and_renderer(self):
        rows = ('0x10 -1 100 -4 2 2 3 host wallpaperengine\n'
                '0x20 -1 200 0 0 4 2 host wallpaperengine\n'
                '0x30 -1 300 0 0 4 2 host other-app\n'
                '0x40 -1 400 0 0 4 2 host stale-wallpaper\n'
                '0x50 -1 500 0 0 4 2 host wrong-geometry\n'
                '0x60 -1 600 0 0 3 2 host resizing\n')
        argv = {
            '100': ['/renderer', '--window=-2x1x2x3', '--bg=/wallpapers/portrait'],
            '200': ['/renderer', '--window', '0x0x4x2', '--bg', '/wallpapers/landscape'],
            '300': None,
            # A matching string used as an assets argument is not the selection.
            '400': ['/renderer', '--window', '0x0x4x2', '--bg', '/wallpapers/landscape-old',
                    '--assets-dir', '/wallpapers/landscape'],
            '500': ['/renderer', '--window', '1x0x4x2', '--bg', '/wallpapers/landscape'],
            '600': ['/renderer', '--window', '0x0x4x2', '--bg', '/wallpapers/landscape'],
        }
        with patch.object(overview.subprocess, 'check_output', return_value=rows), \
                patch.object(overview, 'renderer_arguments', side_effect=lambda pid, _: argv[pid]):
            self.assertEqual(overview.matching_windows(self.active, self.bounds, '/renderer'),
                             self.windows)

    def test_waits_for_every_active_monitor_before_any_capture_or_publish(self):
        with patch.object(overview, 'matching_windows', return_value={'main': '0x20'}), \
                patch.object(overview, 'capture_window') as capture, \
                patch.object(overview, 'publish') as publish:
            self.assertFalse(overview.update(self.active, self.bounds, '/renderer'))
            capture.assert_not_called()
            publish.assert_not_called()

    def capture(self, window, expected_geometry):
        self.assertEqual(expected_geometry, self.bounds['left' if window == 0x10 else 'main'])
        return Image.new('RGB', expected_geometry[2:], 'red' if window == 0x10 else 'blue')

    def run_update(self, current=True, layout=None, matches=None):
        with patch.object(overview, 'matching_windows', side_effect=matches or [self.windows] * 2), \
                patch.object(overview, 'capture_window', side_effect=self.capture), \
                patch.object(overview, 'monitors', return_value=layout or self.bounds), \
                patch.object(overview, 'publish') as publish:
            changed = overview.update(self.active, self.bounds, '/renderer', lambda: current)
            return changed, publish

    def test_only_verified_renderer_pixels_are_published_after_complete_capture(self):
        changed, publish = self.run_update()
        self.assertTrue(changed)
        canvas = publish.call_args.args[0]
        self.assertEqual(canvas.getpixel((0, 3)), (255, 0, 0))
        self.assertEqual(canvas.getpixel((5, 0)), (0, 0, 255))

    def test_selection_changed_during_capture_does_not_publish(self):
        changed, publish = self.run_update(current=False)
        self.assertFalse(changed)
        publish.assert_not_called()

    def test_display_geometry_changed_during_capture_does_not_publish(self):
        changed, publish = self.run_update(layout={'main': (0, 0, 4, 2)})
        self.assertFalse(changed)
        publish.assert_not_called()

    def test_renderer_replaced_during_capture_does_not_publish(self):
        changed, publish = self.run_update(matches=[self.windows, {'left': '0x11', 'main': '0x20'}])
        self.assertFalse(changed)
        publish.assert_not_called()

    def test_stopped_playback_restores_original_background(self):
        with patch.object(overview, 'capture_window') as capture, \
                patch.object(overview, 'publish') as publish, \
                patch.object(overview, 'restore_original') as restore:
            self.assertTrue(overview.update({}, self.bounds, '/renderer'))
            capture.assert_not_called()
            publish.assert_not_called()
            restore.assert_called_once_with()

    def test_partial_monitor_selection_keeps_original_background(self):
        active = {'main': self.active['main'], 'unplugged': {'backgroundId': '/old'}}
        with patch.object(overview, 'matching_windows') as matching, \
                patch.object(overview, 'capture_window') as capture, \
                patch.object(overview, 'publish') as publish, \
                patch.object(overview, 'restore_original') as restore:
            self.assertTrue(overview.update(active, self.bounds, '/renderer'))
            matching.assert_not_called()
            capture.assert_not_called()
            publish.assert_not_called()
            restore.assert_called_once_with()

    def test_state_mtime_detects_reapplying_same_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'active.json'
            state.write_text(json.dumps({'activeWallpapers': self.active}))
            active, first = overview.state_snapshot(state)
            stamp = state.stat()
            os.utime(state, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 10_000_000))
            again, second = overview.state_snapshot(state)
            self.assertEqual(active, again)
            self.assertNotEqual(first, second)

    def test_invalid_active_state_cannot_be_used_to_capture_an_unselected_window(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'active.json'
            for active in ({'main': {}}, {'main': {'backgroundId': 123}}, []):
                state.write_text(json.dumps({'activeWallpapers': active}))
                with self.assertRaises(ValueError):
                    overview.state_snapshot(state)

    def test_publication_alternates_filenames_and_updates_both_gnome_uris(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            current = ''
            selected = []

            def settings_run(command, check):
                nonlocal current
                if command[-2] == 'picture-uri':
                    current = command[-1]
                    selected.append(current)

            with patch.object(overview.subprocess, 'check_output',
                              side_effect=lambda *a, **kw: repr(current) + '\n'), \
                    patch.object(overview.subprocess, 'run', side_effect=settings_run) as run, \
                    patch.object(overview, 'save_original') as save:
                for _ in range(3):
                    overview.publish(Image.new('RGB', (2, 2), 'blue'), output)
            self.assertEqual(save.call_count, 3)
            self.assertEqual(selected, [(output / f'overview-{slot}.png').as_uri()
                                        for slot in (0, 1, 0)])
            self.assertEqual(sum(call.args[0][-2] == 'picture-uri-dark'
                                 for call in run.call_args_list), 3)
            self.assertEqual(sorted(path.name for path in output.iterdir()),
                             ['overview-0.png', 'overview-1.png'])

    def test_selection_changed_during_png_encoding_does_not_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with patch.object(overview.subprocess, 'check_output', return_value="''\n"), \
                    patch.object(overview.subprocess, 'run') as settings:
                self.assertFalse(overview.publish(Image.new('RGB', (2, 2)), output,
                                                  still_current=lambda: False))
                settings.assert_not_called()
            self.assertEqual(list(output.iterdir()), [])

    def test_watcher_refreshes_after_renderer_restart_without_a_selection_change(self):
        with patch.object(overview, 'single_instance', side_effect=nullcontext), \
                patch.object(overview, 'backend_path', return_value=Path('/renderer')), \
                patch.object(overview, 'state_snapshot', return_value=(self.active, 'same-version')), \
                patch.object(overview, 'monitors', return_value=self.bounds), \
                patch.object(overview, 'matching_windows', side_effect=[
                    self.windows, self.windows, {'main': '0x30'}, {'main': '0x30'}]), \
                patch.object(overview.time, 'monotonic', side_effect=[0, 0, 4, 5, 5, 9]), \
                patch.object(overview.time, 'sleep', side_effect=[None, None, None, KeyboardInterrupt]), \
                patch.object(overview, 'update', return_value=True) as update, \
                patch('sys.argv', ['sync-overview-background.py']):
            with self.assertRaises(KeyboardInterrupt):
                overview.main()
        self.assertEqual(update.call_count, 2)


if __name__ == '__main__':
    unittest.main()
