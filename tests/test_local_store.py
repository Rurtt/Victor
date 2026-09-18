from pathlib import Path
import tempfile
import unittest
from local_store import LocalStore, StorageError


class StorageTests(unittest.TestCase):
    def test_key_round_trip_is_encrypted_and_settings_are_separate(self):
        with tempfile.TemporaryDirectory() as d:
            store = LocalStore(Path(d))
            secret = "test-jarvis-key-not-a-real-credential"
            store.save_key(secret)
            self.assertNotIn(secret.encode(), store.key_path.read_bytes())
            self.assertEqual(store.read_key(), secret)
            store.save_settings("gemini-3.8-flash")
            self.assertNotIn(secret, store.settings_path.read_text())
            self.assertEqual(store.read_settings()["language"], "th")
            store.forget_key()
            self.assertEqual(store.read_key(), "")

    def test_corrupt_secret_does_not_load(self):
        with tempfile.TemporaryDirectory() as d:
            store = LocalStore(Path(d))
            store.directory.mkdir()
            store.key_path.write_bytes(b"not-a-dpapi-blob")
            with self.assertRaises(StorageError):
                store.read_key()
