"""Browser launcher tests use temporary homes only."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    'browser_wrapper', Path(__file__).with_name('setup') / 'browser_wrapper.py')
wrapper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wrapper)


class BrowserWrapperTests(unittest.TestCase):
    def test_detects_flatpak_before_native_and_none(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            self.assertIsNone(wrapper.detect_steam(home))
            (home / '.local/share/Steam').mkdir(parents=True)
            self.assertEqual(wrapper.detect_steam(home), ('native', (home / '.local/share/Steam').resolve()))
            flatpak = home / '.var/app/com.valvesoftware.Steam/.local/share/Steam'
            flatpak.mkdir(parents=True)
            self.assertEqual(wrapper.detect_steam(home), ('flatpak', flatpak))

    def test_native_steam_keeps_home_and_flatpak_overrides_it(self):
        with tempfile.TemporaryDirectory(prefix='browser home ') as temp:
            home = Path(temp)
            browser = home / 'fake browser'
            browser.write_text('#!/bin/sh\necho "HOME=$HOME CONFIG=$XDG_CONFIG_HOME"\n')
            browser.chmod(0o755)
            for kind, expected_home in (('native', home), ('flatpak', home / '.var/app/com.valvesoftware.Steam')):
                launch = wrapper.write_browser_wrapper(home / ('launch-' + kind), browser, kind, home=home,
                                                       config=home / 'cfg', data=home / 'data')
                out = subprocess.run([str(launch)], check=True, stdout=subprocess.PIPE, text=True,
                                     env={'HOME': str(home), 'PATH': '/usr/bin:/bin'}).stdout.strip()
                self.assertEqual(out, f'HOME={expected_home} CONFIG={home / "cfg"}')

    def test_settings_keep_existing_values(self):
        with tempfile.TemporaryDirectory() as temp:
            settings = Path(temp) / 'Linux Wallpaper Engine/settings.json'
            settings.parent.mkdir(parents=True)
            settings.write_text(json.dumps({'assetsDir': '/steam/assets', 'minimizeOnClose': False}))
            wrapper.update_browser_settings(temp)
            values = json.loads(settings.read_text())
            self.assertEqual(values['assetsDir'], '/steam/assets')
            self.assertTrue(values['minimizeOnClose'] and values['enableSystemTray'])


if __name__ == '__main__':
    unittest.main()
