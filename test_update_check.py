import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock

spec = importlib.util.spec_from_file_location('update_check', Path(__file__).resolve().parent / 'update-check.py')
update = importlib.util.module_from_spec(spec); spec.loader.exec_module(update)


class UpdateCheckTests(unittest.TestCase):
    def test_announces_a_newer_release_once_and_checks_once_a_day(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp) / 'update-check.json'
            fetch, notify = MagicMock(return_value='1.0.10'), MagicMock()
            self.assertEqual(update.check(state, '1.0.9', fetch, notify, now=1000), '1.0.10')
            notify.assert_called_once_with('1.0.9', '1.0.10')
            self.assertIsNone(update.check(state, '1.0.9', fetch, notify, now=1000 + 3600))
            self.assertEqual(fetch.call_count, 1)  # within the day: GitHub is not asked again
            self.assertIsNone(update.check(state, '1.0.9', fetch, notify, now=1000 + update.DAY))
            self.assertEqual(fetch.call_count, 2)
            notify.assert_called_once()  # same version: no second notification

    def test_same_or_older_release_is_not_announced(self):
        with tempfile.TemporaryDirectory() as temp:
            for latest in ('1.0.2', '1.0.1', None, 'nightly'):
                notify = MagicMock()
                state = Path(temp) / f'{latest}.json'
                self.assertIsNone(update.check(state, '1.0.2', lambda: latest, notify, now=1))
                notify.assert_not_called()

    def test_failed_request_is_retried_instead_of_waiting_a_day(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp) / 'update-check.json'
            with self.assertRaises(OSError):
                update.check(state, '1.0.0', MagicMock(side_effect=OSError('offline')), now=1)
            self.assertFalse(state.exists())
            self.assertEqual(update.check(state, '1.0.0', lambda: '1.1.0', now=2), '1.1.0')
            self.assertEqual(json.loads(state.read_text()), {'checked': 2, 'notified': '1.1.0'})

    def test_reads_the_latest_published_release_tag(self):
        def opener(body):
            response = MagicMock()
            response.__enter__.return_value = io.BytesIO(json.dumps(body).encode())
            return lambda request, timeout: response
        self.assertEqual(update.latest_release(opener({'tag_name': 'v1.2.0'})), '1.2.0')
        self.assertIsNone(update.latest_release(opener({'tag_name': 'v2.0.0', 'prerelease': True})))

    def test_only_appimage_installs_check_and_it_can_be_turned_off(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            self.assertIsNone(update.installed_version(base))  # run.sh install
            (base / 'runtime').mkdir(); (base / 'runtime/current').write_text('1.0.2\n')
            self.assertEqual(update.installed_version(base), '1.0.2')
        self.assertTrue(update.disabled({'UPDATE_CHECK': 'no'}))
        self.assertFalse(update.disabled({}))


if __name__ == '__main__':
    unittest.main()
