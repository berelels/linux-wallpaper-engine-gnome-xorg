"""Background save/restore tests do not change live desktop settings."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    'background_state', Path(__file__).with_name('background_state.py'))
background = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(background)


class BackgroundStateTests(unittest.TestCase):
    def test_saves_once_and_restores_every_setting(self):
        values = {
            'picture-uri': "'file:///original-light.jpg'",
            'picture-uri-dark': "'file:///original-dark.jpg'",
            'picture-options': "'zoom'",
        }
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'original.json'
            with patch.object(background, 'setting', side_effect=values.get):
                self.assertTrue(background.save_original(state, Path(directory) / 'output'))
                self.assertFalse(background.save_original(state, Path(directory) / 'output'))
            self.assertEqual(json.loads(state.read_text()), values)
            with patch.object(background.subprocess, 'run') as run:
                self.assertTrue(background.restore_original(state))
            self.assertFalse(state.exists())
            self.assertEqual(
                [(call.args[0][-2], call.args[0][-1]) for call in run.call_args_list],
                list(values.items()))

    def test_does_not_overwrite_saved_original(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'original.json'
            state.write_text(json.dumps({key: "'saved'" for key in background.KEYS}))
            with patch.object(background, 'setting') as setting:
                self.assertFalse(background.save_original(state))
            setting.assert_not_called()

    def test_refuses_to_save_its_own_generated_image(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'output'
            values = iter([(output / 'overview-0.png').as_uri(),
                           "'file:///dark.jpg'", "'zoom'"])
            with patch.object(background, 'setting', side_effect=values):
                with self.assertRaises(RuntimeError):
                    background.save_original(Path(directory) / 'state.json', output)

    def test_failed_restore_keeps_recovery_state(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'original.json'
            state.write_text(json.dumps({key: "'saved'" for key in background.KEYS}))
            with patch.object(background.subprocess, 'run', side_effect=OSError('failed')):
                with self.assertRaises(OSError):
                    background.restore_original(state)
            self.assertTrue(state.exists())


if __name__ == '__main__':
    unittest.main()
