import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('restore_browser',ROOT/'restore-browser-wallpapers.py')
restore=importlib.util.module_from_spec(spec);spec.loader.exec_module(restore)


class BrowserIntegrationTests(unittest.TestCase):
    def test_installer_is_portable_in_clean_home_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix='wallpaper home ') as temp:
            home=Path(temp);(home/'.config/autostart').mkdir(parents=True)
            legacy=home/'.config/autostart/wallpaper-engine.desktop'
            legacy.write_text('[Desktop Entry]\nExec=/example/start-wallpaper.sh\nHidden=false\n')
            backend=home/'real renderer';backend.write_text('#!/bin/sh\n');backend.chmod(0o755)
            browser=home/'native browser';browser.write_text('#!/bin/sh\n');browser.chmod(0o755)
            env=dict(os.environ,HOME=temp,XDG_CONFIG_HOME=str(home/'.config'),XDG_DATA_HOME=str(home/'.local/share'),XDG_SESSION_TYPE='x11')
            subprocess.run([sys.executable,str(ROOT/'install-browser-integration.py'),'--backend',str(backend),'--browser',str(browser),'--no-desktop-shortcut'],env=env,check=True,stdout=subprocess.PIPE,text=True)
            install=home/'.local/share/wallpaper-engine-gnome'
            self.assertTrue((install/'bin/linux-wallpaperengine').is_file())
            self.assertTrue((install/'capture_x11.py').is_file())
            self.assertTrue((install/'background_state.py').is_file())
            self.assertTrue(os.access(install/'uninstall-browser-integration.py', os.X_OK))
            self.assertIn('"', (home/'.local/share/applications/linux-wallpaper-engine.desktop').read_text())
            self.assertIn('Hidden=true',legacy.read_text())
            self.assertTrue(legacy.with_suffix('.desktop.before-browser-integration').exists())
            self.assertTrue((home/'.config/autostart/wallpaper-browser-restore.desktop').exists())
            config=(home/'.config/wallpaper-engine/config.sh').read_text()
            self.assertIn(str(backend),config)
            self.assertNotIn(str(ROOT.parent),config)

    def test_restore_preserves_background_path_and_monitor_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            bg=Path(temp)/'wallpaper with spaces';bg.mkdir()
            args=restore.restore_args('/renderer','DP-0',{'backgroundId':str(bg),'silent':True,'fps':45},{'assetsDir':'/Steam Library/assets','volume':30},'/adapter.py')
            self.assertEqual(args[args.index('--bg')+1],str(bg))
            self.assertEqual(args[args.index('--screen-root')+1],'DP-0')
            self.assertEqual(args[args.index('--fps')+1],'45')
            self.assertIn('--silent',args)
            self.assertEqual(args[args.index('--assets-dir')+1],'/Steam Library/assets')

    def test_restore_ignores_previews_and_only_skips_occupied_monitor(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);renderer=root/'renderer';renderer.touch()
            proc=root/'123';proc.mkdir();(proc/'exe').symlink_to(renderer)
            active={'left':{'backgroundId':'/wallpaper'},'right':{'backgroundId':'/wallpaper'}}
            bounds={'left':('0','0','1920','1080'),'right':('1920','0','1920','1080')}
            def command(geometry):
                (proc/'cmdline').write_bytes(b'\0'.join([str(renderer).encode(),b'--bg',b'/wallpaper',b'--window',geometry]))
            command(b'100x100x640x360')
            self.assertEqual(restore.active_screens(renderer,active,bounds,root),set())
            command(b'0x0x1920x1080')
            self.assertEqual(restore.active_screens(renderer,active,bounds,root),{'left'})

    def test_missing_wallpaper_is_not_restored(self):
        self.assertIsNone(restore.restore_args('/renderer','DP-0',{'backgroundId':'/missing-wallpaper-for-test'},{},'/adapter.py'))


if __name__=='__main__':unittest.main()
