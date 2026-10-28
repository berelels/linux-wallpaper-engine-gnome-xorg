import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from integration_config import backend_path, open_log, read_config


class ConfigTests(unittest.TestCase):
    def test_helper_log_starts_over_only_past_its_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'helper.log'
            for line in ('first\n', 'second\n'):
                with open_log(path, limit=10) as log:
                    log.write(line)
            self.assertEqual(path.read_text(), 'first\nsecond\n')
            with open_log(path, limit=10) as log:
                log.write('third\n')
            self.assertEqual(path.read_text(), 'third\n')

    def test_quoted_and_escaped_paths_without_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'config.sh'
            path.write_text('BINARY="/opt/Wallpaper Engine/renderer"\nASSETS=/data/Steam\\ Library/assets\nIGNORED=$(touch /tmp/should-not-exist)\n# COMMENT=value\n')
            self.assertEqual(read_config(path), {'BINARY': '/opt/Wallpaper Engine/renderer', 'ASSETS': '/data/Steam Library/assets'})

    def test_backend_override_precedence(self):
        with patch.dict(os.environ, {'LWE_BACKEND': '/environment/renderer'}), patch('integration_config.read_config', return_value={'BINARY': '/configured/renderer'}):
            self.assertEqual(backend_path('/explicit/renderer'), Path('/explicit/renderer'))
            self.assertEqual(backend_path(), Path('/environment/renderer'))
        with patch.dict(os.environ, {}, clear=True), patch('integration_config.read_config', return_value={'BINARY': '/configured/renderer'}):
            self.assertEqual(backend_path(), Path('/configured/renderer'))

    def test_missing_file_is_empty(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(read_config(Path(temp) / 'missing'), {})


if __name__ == '__main__':
    unittest.main()
