from __future__ import annotations

import base64
from pathlib import Path
import sqlite3
import tempfile
import unittest

from simulation_ai.encrypted_images import EncryptedImageStore


class FakeCredentialVault:
    def resolve_api_key(self) -> tuple[str, str]:
        return "sk-test-image-key", "test"


PNG_FIXTURE = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class EncryptedImageStoreTests(unittest.TestCase):
    def test_image_and_prompt_are_encrypted_and_materialize_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = EncryptedImageStore(root, FakeCredentialVault())
            record = store.save(PNG_FIXTURE, "type a private desktop instruction")
            self.assertEqual(PNG_FIXTURE, store.materialize(str(record["id"])).read_bytes())
            self.assertEqual(0o700, root.stat().st_mode & 0o777)
            self.assertEqual(0o700, store.cache.stat().st_mode & 0o777)
            self.assertEqual(0o600, store.db_path.stat().st_mode & 0o777)
            with sqlite3.connect(store.db_path) as db:
                row = db.execute("SELECT prompt, prompt_ciphertext FROM images WHERE id = ?", (record["id"],)).fetchone()
            self.assertEqual("", row[0])
            self.assertTrue(row[1])

    def test_non_png_and_oversized_frames_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = EncryptedImageStore(Path(temporary), FakeCredentialVault())
            with self.assertRaisesRegex(ValueError, "PNG"):
                store.save(b"X" * 33, "prompt")
