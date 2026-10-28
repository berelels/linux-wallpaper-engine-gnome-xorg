"""Uninstall process matching uses a fake /proc and never signals real processes."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('uninstall', ROOT / 'uninstall-browser-integration.py')
uninstall = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(uninstall)


class HelperProcessTests(unittest.TestCase):
    def test_matches_helpers_and_browser_launcher_only(self):
        with tempfile.TemporaryDirectory() as temp:
            proc, target = Path(temp) / 'proc', Path(temp) / 'install'
            proc.mkdir()
            commands = {
                '10': ['/run/python3', str(target / 'browser-launcher.py')],
                '11': ['/run/python3', str(target / 'sync-overview-background.py')],
                '12': ['/usr/bin/python3', '/elsewhere/browser-launcher.py'],
                '13': ['/usr/bin/bash'],
            }
            for pid, argv in commands.items():
                (proc / pid).mkdir()
                (proc / pid / 'cmdline').write_bytes(b'\0'.join(a.encode() for a in argv))
            (proc / 'self').mkdir()
            found = sorted(uninstall.helper_processes(target, proc))
            self.assertEqual(found, [10, 11])
            self.assertEqual(os.getuid(), (proc / '10').stat().st_uid)


if __name__ == '__main__':
    unittest.main()
