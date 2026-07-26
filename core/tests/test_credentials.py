from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from simulation_ai.credentials import CredentialVaultError, OpenAICredentialVault
from simulation_ai.engine import SurfaceEngine


TEST_KEY = "sk-proj-test_abcdefghijklmnopqrstuvwxyz0123456789"
TEST_PASSWORD = "correct horse battery staple"


class FakeResponse:
    status = 200

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self, _: int) -> bytes:
        return json.dumps({"object": "list", "data": [{"id": "model-a"}, {"id": "model-b"}]}).encode()


class CapturingOpener:
    def __init__(self) -> None:
        self.authorization = ""

    def __call__(self, request: object, *, timeout: float) -> FakeResponse:
        del timeout
        self.authorization = request.get_header("Authorization")
        return FakeResponse()


class OpenAICredentialVaultTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def vault(self, **kwargs: object) -> OpenAICredentialVault:
        return OpenAICredentialVault(
            self.home,
            scrypt_n=1 << 14,
            minimum_password_characters=4,
            **kwargs,
        )

    def test_save_encrypts_key_and_exposes_redacted_status_only(self) -> None:
        vault = self.vault()
        status = vault.save(TEST_KEY, TEST_PASSWORD)
        self.assertTrue(status.configured)
        self.assertTrue(status.unlocked)
        self.assertEqual(12, len(status.fingerprint))
        file_text = vault.path.read_text(encoding="utf-8")
        self.assertNotIn(TEST_KEY, file_text)
        self.assertNotIn(TEST_PASSWORD, file_text)
        public = status.as_dict()
        self.assertNotIn("api_key", public)
        self.assertFalse(public["secret_exposed"])
        if os.name != "nt":
            self.assertEqual(0o600, vault.path.stat().st_mode & 0o777)

    def test_lock_unlock_and_wrong_password(self) -> None:
        vault = self.vault()
        vault.save(TEST_KEY, TEST_PASSWORD)
        vault.lock()
        self.assertFalse(vault.status().unlocked)
        with self.assertRaisesRegex(CredentialVaultError, "incorrect|modified"):
            vault.unlock("wrong-password")
        status = vault.unlock(TEST_PASSWORD)
        self.assertTrue(status.unlocked)
        key, source = vault.resolve_api_key()
        self.assertEqual(TEST_KEY, key)
        self.assertEqual("encrypted-vault", source)

    def test_import_environment_and_clear_requires_authority(self) -> None:
        vault = self.vault()
        with patch.dict(os.environ, {"OPENAI_API_KEY": TEST_KEY}):
            status = vault.import_environment(TEST_PASSWORD)
        self.assertEqual("environment-import", status.source)
        vault.lock()
        with self.assertRaisesRegex(CredentialVaultError, "Unlock|password"):
            vault.clear()
        status = vault.clear(TEST_PASSWORD)
        self.assertFalse(status.configured)
        self.assertFalse(vault.path.exists())

    def test_connection_uses_bearer_without_returning_key(self) -> None:
        opener = CapturingOpener()
        vault = self.vault(opener=opener)
        vault.save(TEST_KEY, TEST_PASSWORD)
        result = vault.test_connection()
        self.assertTrue(result["ok"])
        self.assertEqual(2, result["model_count"])
        self.assertEqual(f"Bearer {TEST_KEY}", opener.authorization)
        self.assertNotIn(TEST_KEY, json.dumps(result))

    def test_engine_snapshot_and_semantic_store_never_contain_key(self) -> None:
        engine = SurfaceEngine(self.home)
        engine.credential_save(TEST_KEY, TEST_PASSWORD)
        snapshot = engine.snapshot()
        self.assertTrue(snapshot["credentials"]["openai"]["configured"])
        self.assertNotIn(TEST_KEY, json.dumps(snapshot))
        for path in self.home.rglob("*"):
            if not path.is_file() or path == engine.credentials.path:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            self.assertNotIn(TEST_KEY, content, str(path))


if __name__ == "__main__":
    unittest.main()
