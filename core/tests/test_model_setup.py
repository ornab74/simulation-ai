from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from simulation_ai.model_setup import GEMMA_CHUNK_BYTES, GEMMA_MODEL, GemmaSetup


def test_model_vault_reports_missing_and_resumable_chunks() -> None:
    with TemporaryDirectory() as temporary:
        setup = GemmaSetup(Path(temporary))
        missing = setup.status()
        assert missing["state"] == "missing"
        assert missing["verified"] is False
        assert missing["resumable"] is True

        setup.chunk_dir.mkdir()
        setup.manifest_path.write_text(
            json.dumps(
                {
                    "model": GEMMA_MODEL,
                    "sha256": missing["expected_sha256"],
                    "total_bytes": GEMMA_CHUNK_BYTES + 4,
                    "chunk_size": GEMMA_CHUNK_BYTES,
                    "chunks": 2,
                }
            ),
            encoding="utf-8",
        )
        (setup.chunk_dir / "chunk-000000.part").write_bytes(b"saved")
        paused = setup.status()
        assert paused["state"] == "paused"
        assert paused["downloaded_bytes"] == 5
        assert paused["completed_chunks"] == 0


def test_model_vault_accepts_only_the_expected_sha256() -> None:
    with TemporaryDirectory() as temporary:
        setup = GemmaSetup(Path(temporary))
        content = b"verified model fixture"
        expected = hashlib.sha256(content).hexdigest()
        with patch("simulation_ai.model_setup.GEMMA_SHA256", expected):
            setup.path.write_bytes(content)
            ready = setup.status()
            assert ready["state"] == "ready"
            assert ready["verified"] is True
            assert ready["sha256"] == expected
