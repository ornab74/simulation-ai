from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .credentials import OpenAICredentialVault


class EncryptedImageStore:
    """SQLite image history with AES-GCM encrypted payloads."""

    def __init__(self, root: Path, credentials: OpenAICredentialVault) -> None:
        self.root = root
        self.credentials = credentials
        self.db_path = root / "images.sqlite3"
        self.cache = root / ".image_cache"
        self.cache.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS images (id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL, mime TEXT NOT NULL, nonce BLOB NOT NULL, ciphertext BLOB NOT NULL, sha256 TEXT NOT NULL, prompt TEXT NOT NULL)")
            db.commit()

    def _key(self) -> bytes:
        api_key, _ = self.credentials.resolve_api_key()
        return hashlib.sha256(b"simulation-ai/image-store/v1/" + api_key.encode()).digest()

    def save(self, image: bytes, prompt: str) -> dict[str, object]:
        key = self._key()
        image_id = "screen_" + hashlib.sha256(image + os.urandom(16)).hexdigest()[:24]
        name = image_id + ".png"
        created = datetime.now(UTC).isoformat(timespec="seconds")
        nonce = os.urandom(12)
        aad = f"{image_id}|{name}|{created}|image/png".encode()
        ciphertext = AESGCM(key).encrypt(nonce, image, aad)
        digest = hashlib.sha256(image).hexdigest()
        with sqlite3.connect(self.db_path) as db:
            db.execute("INSERT INTO images VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (image_id, name, created, "image/png", nonce, ciphertext, digest, prompt[:4000]))
            db.commit()
        return {"id": image_id, "name": name, "created_at": created, "bytes": len(image), "sha256": digest}

    def list(self) -> list[dict[str, object]]:
        with sqlite3.connect(self.db_path) as db:
            rows = db.execute("SELECT id, name, created_at, length(ciphertext), sha256 FROM images ORDER BY created_at DESC LIMIT 100").fetchall()
        return [{"id": row[0], "name": row[1], "created_at": row[2], "encrypted_bytes": row[3], "sha256": row[4]} for row in rows]

    def latest_path(self) -> Path | None:
        images = self.list()
        return self.materialize(str(images[0]["id"])) if images else None

    def origin_path(self) -> Path | None:
        marker = self.root / "origin-image.id"
        if not marker.exists():
            images = self.list()
            if not images:
                return None
            marker.write_text(str(images[-1]["id"]), encoding="utf-8")
        return self.materialize(marker.read_text(encoding="utf-8").strip())

    def materialize(self, image_id: str) -> Path:
        key = self._key()
        with sqlite3.connect(self.db_path) as db:
            row = db.execute("SELECT name, created_at, mime, nonce, ciphertext FROM images WHERE id = ?", (image_id,)).fetchone()
        if row is None:
            raise ValueError("image not found")
        name, created, mime, nonce, ciphertext = row
        aad = f"{image_id}|{name}|{created}|{mime}".encode()
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, aad)
        target = self.cache / name
        target.write_bytes(plaintext)
        return target
