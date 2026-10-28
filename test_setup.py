import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SETUP = Path(__file__).parent / 'setup'
sys.path.insert(0, str(SETUP))
import runtime
import configure
spec = importlib.util.spec_from_file_location('launcher', SETUP / 'launch-browser.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class SetupTests(unittest.TestCase):
    def test_secondary_steam_library(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            steam, external = root / 'Steam', root / 'Games with spaces'
            (steam / 'steamapps').mkdir(parents=True)
            (steam / 'steamapps/libraryfolders.vdf').write_text(f'"libraryfolders" {{ "1" {{ "path" "{external}" }} }}')
            assets = external / 'steamapps/common/wallpaper_engine/assets'
            assets.mkdir(parents=True)
            (assets / 'asset').write_text('test')
            self.assertEqual(runtime.find_assets(steam), assets)

    def test_empty_assets_not_ready(self):
        with tempfile.TemporaryDirectory() as temp:
            steam = Path(temp)
            (steam / 'steamapps/common/wallpaper_engine/assets').mkdir(parents=True)
            self.assertIsNone(runtime.find_assets(steam))

    def test_settings_preserved_and_config_shell_escaped(self):
        with tempfile.TemporaryDirectory(prefix="wallpaper ' $ test ") as temp:
            home = Path(temp)
            steam_data = home / '.var/app/com.valvesoftware.Steam'
            settings = steam_data / 'config/Linux Wallpaper Engine/settings.json'
            settings.parent.mkdir(parents=True)
            settings.write_text(json.dumps({'volume': 37, 'favorites': ['keep']}))
            assets = home / 'external/steamapps/common/wallpaper_engine/assets'
            app = steam_data / 'data/suite'
            with patch.object(Path, 'home', return_value=home):
                launcher.configure_assets(app, steam_data, assets)
            data = json.loads(settings.read_text())
            self.assertEqual(data['volume'], 37)
            self.assertEqual(data['favorites'], ['keep'])
            self.assertTrue(data['flatpakBypass'])
            config = home / '.config/wallpaper-engine/config.sh'
            actual = subprocess.check_output(['bash', '-c', 'source "$1"; printf "%s" "$ASSETS"', 'test', str(config)], text=True)
            self.assertEqual(actual, str(assets))
            self.assertTrue(settings.with_suffix('.json.before-suite-setup').exists())

    def test_invalid_settings_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            settings = home / 'config/Linux Wallpaper Engine/settings.json'
            settings.parent.mkdir(parents=True)
            settings.write_text('invalid')
            with self.assertRaises(json.JSONDecodeError):
                launcher.configure_assets(home, home, home)
            self.assertEqual(settings.read_text(), 'invalid')

    def test_shell_wrapper_special_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            script = Path(temp) / 'wrapper'
            configure.shell(script, 'printf "%s" "$1"\n')
            actual = subprocess.check_output([str(script), 'spaces " and $literal'], text=True)
            self.assertEqual(actual, 'spaces " and $literal')

    def test_steam_session_skips_nested_runtime(self):
        with patch.object(runtime.subprocess, 'check_output', return_value='1 com.valvesoftware.Steam\n2 com.valvesoftware.Steam\n'), patch.object(runtime.subprocess, 'run', side_effect=[subprocess.CompletedProcess([], 1), subprocess.CompletedProcess([], 0)]):
            self.assertEqual(runtime.steam_session(), '2')

if __name__ == '__main__':
    unittest.main()
