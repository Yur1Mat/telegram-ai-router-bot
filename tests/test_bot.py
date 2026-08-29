import os
import tempfile
import unittest
from pathlib import Path

from cryptography.fernet import Fernet

from bot.app import _chunks
from bot.config import Settings
from bot.storage import Storage


class StorageTests(unittest.TestCase):
    def test_secret_and_history_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Storage(Path(directory) / "test.db", Fernet.generate_key().decode())
            store.set_key(7, "openai", "secret")
            store.save_history(7, [{"role": "user", "content": "hello"}])
            self.assertEqual(store.get_key(7, "openai"), "secret")
            self.assertEqual(store.history(7)[0]["content"], "hello")
            store.close()

    def test_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Storage(Path(directory) / "test.db", Fernet.generate_key().decode())
            self.assertEqual(store.settings(1)["provider"], "openai")
            store.close()


class HelpersTests(unittest.TestCase):
    def test_chunks(self):
        self.assertEqual(_chunks("abcdef", 2), ["ab", "cd", "ef"])


if __name__ == "__main__":
    unittest.main()
