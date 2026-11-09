import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from atomic_io import atomic_json, replace_file


class AtomicPublicationTests(unittest.TestCase):
    def test_transient_windows_lock_is_retried(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "progress.json"
            import atomic_io
            original = atomic_io.os.replace
            calls = []
            def locked_once(source, destination):
                calls.append(source)
                if len(calls) == 1: raise PermissionError("sharing violation")
                return original(source, destination)
            with patch("atomic_io.os.replace", side_effect=locked_once), patch("atomic_io.time.sleep"):
                atomic_json(target, {"done": 190})
            self.assertEqual(json.loads(target.read_text()), {"done": 190})
            self.assertEqual(len(calls), 2)
            self.assertEqual(list(Path(d).glob("*.tmp")), [])

    def test_failed_publication_preserves_previous_status_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "progress.json"; target.write_text('{"done": 1}')
            with patch("atomic_io.os.replace", side_effect=PermissionError("locked")), patch("atomic_io.time.sleep"):
                with self.assertRaises(PermissionError): atomic_json(target, {"done": 2})
            self.assertEqual(json.loads(target.read_text()), {"done": 1})
            self.assertEqual(list(Path(d).glob("*.tmp")), [])

    def test_nonsharing_errors_fail_without_retry(self):
        with patch("atomic_io.os.replace", side_effect=FileNotFoundError()) as replace, patch("atomic_io.time.sleep") as sleep:
            with self.assertRaises(FileNotFoundError): replace_file("missing", "destination")
            self.assertEqual(replace.call_count, 1)
            sleep.assert_not_called()
