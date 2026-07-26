from __future__ import annotations

import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from simulation_ai.credentials import OpenAICredentialVault
from simulation_ai.engine import SurfaceEngine
from simulation_ai.server import SurfaceHandler, ThreadingHTTPServer


TEST_KEY = "sk-proj-server_abcdefghijklmnopqrstuvwxyz0123456789"
PASSWORD = "server vault password"
TOKEN = "test-loopback-token"


class FakeResponse:
    status = 200

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self, _: int) -> bytes:
        return b'{"object":"list","data":[{"id":"model-a"}]}'


def fake_open(request: object, *, timeout: float) -> FakeResponse:
    del timeout
    assert request.get_header("Authorization") == f"Bearer {TEST_KEY}"
    return FakeResponse()


class QuietHandler(SurfaceHandler):
    def log_message(self, format: str, *args: object) -> None:
        del format, args


class CredentialServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        home = Path(self.temp.name)
        engine = SurfaceEngine(home)
        engine.credentials = OpenAICredentialVault(
            home,
            scrypt_n=1 << 14,
            minimum_password_characters=4,
            opener=fake_open,
        )
        QuietHandler.engine = engine
        QuietHandler.bearer_token = TOKEN
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, method: str, path: str, payload: dict | None = None, *, authenticated: bool = True) -> dict:
        headers = {"Content-Type": "application/json"}
        if authenticated:
            headers["Authorization"] = f"Bearer {TOKEN}"
        body = None if payload is None else json.dumps(payload).encode()
        with urlopen(Request(self.base + path, data=body, headers=headers, method=method), timeout=3) as response:
            return json.loads(response.read())

    def test_routes_are_authenticated_and_never_return_secret(self) -> None:
        with self.assertRaises(HTTPError) as denied:
            self.request("GET", "/v1/credentials/openai", authenticated=False)
        self.assertEqual(401, denied.exception.code)

        saved = self.request(
            "POST",
            "/v1/credentials/openai/save",
            {"api_key": TEST_KEY, "password": PASSWORD},
        )
        self.assertTrue(saved["credential"]["configured"])
        self.assertNotIn(TEST_KEY, json.dumps(saved))

        locked = self.request("POST", "/v1/credentials/openai/lock", {})
        self.assertFalse(locked["credential"]["unlocked"])

        unlocked = self.request(
            "POST",
            "/v1/credentials/openai/unlock",
            {"password": PASSWORD},
        )
        self.assertTrue(unlocked["credential"]["unlocked"])

        tested = self.request("POST", "/v1/credentials/openai/test", {})
        self.assertTrue(tested["test"]["ok"])
        self.assertEqual(1, tested["test"]["model_count"])
        self.assertNotIn(TEST_KEY, json.dumps(tested))

        snapshot = self.request("GET", "/v1/snapshot")
        self.assertNotIn(TEST_KEY, json.dumps(snapshot))
        self.assertEqual(0, snapshot["snapshot"]["counts"]["events"])


if __name__ == "__main__":
    unittest.main()
