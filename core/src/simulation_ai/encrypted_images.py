from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path
import unicodedata

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .credentials import OpenAICredentialVault


class EncryptedImageStore:
    """SQLite image history with AES-GCM encrypted payloads and metadata."""

    MAX_IMAGE_BYTES = 50 * 1024 * 1024
    MAX_IMAGE_PIXELS = 8_294_400
    MAX_IMAGE_EDGE = 3840
    _PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

    def __init__(self, root: Path, credentials: OpenAICredentialVault) -> None:
        self.root = root
        self.credentials = credentials
        self.db_path = root / "images.sqlite3"
        self.cache = root / ".image_cache"
        self.root.mkdir(parents=True, exist_ok=True)
        self.cache.mkdir(parents=True, exist_ok=True)
        self._secure_directory(self.root)
        self._secure_directory(self.cache)
        for cached in self.cache.iterdir():
            if cached.is_file() and not cached.is_symlink():
                self._secure_file(cached)
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS images ("
                "id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL, "
                "mime TEXT NOT NULL, nonce BLOB NOT NULL, ciphertext BLOB NOT NULL, "
                "sha256 TEXT NOT NULL, prompt TEXT NOT NULL DEFAULT '', "
                "prompt_nonce BLOB, prompt_ciphertext BLOB)"
            )
            columns = {str(row[1]) for row in db.execute("PRAGMA table_info(images)")}
            if "prompt_nonce" not in columns:
                db.execute("ALTER TABLE images ADD COLUMN prompt_nonce BLOB")
            if "prompt_ciphertext" not in columns:
                db.execute("ALTER TABLE images ADD COLUMN prompt_ciphertext BLOB")
            db.commit()
        self._secure_file(self.db_path)

    def _key(self) -> bytes:
        api_key, _ = self.credentials.resolve_api_key()
        key = hashlib.sha256(b"simulation-ai/image-store/v1/" + api_key.encode()).digest()
        self._migrate_legacy_prompts(key)
        return key

    def save(self, image: bytes, prompt: str) -> dict[str, object]:
        self._validate_png(image)
        key = self._key()
        image_id = "screen_" + hashlib.sha256(image + os.urandom(16)).hexdigest()[:24]
        name = image_id + ".png"
        created = datetime.now(UTC).isoformat(timespec="seconds")
        nonce = os.urandom(12)
        ciphertext = AESGCM(key).encrypt(nonce, image, self._image_aad(image_id, name, created))
        prompt_nonce = os.urandom(12)
        prompt_text = self._sanitize_prompt(prompt)
        prompt_ciphertext = AESGCM(key).encrypt(
            prompt_nonce,
            prompt_text.encode("utf-8"),
            self._prompt_aad(image_id, name, created),
        )
        digest = hashlib.sha256(image).hexdigest()
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO images (id, name, created_at, mime, nonce, ciphertext, sha256, prompt, prompt_nonce, prompt_ciphertext) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (image_id, name, created, "image/png", nonce, ciphertext, digest, "", prompt_nonce, prompt_ciphertext),
            )
            db.commit()
        self._secure_file(self.db_path)
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
            self._secure_file(marker)
        return self.materialize(marker.read_text(encoding="utf-8").strip())

    def materialize(self, image_id: str) -> Path:
        key = self._key()
        with sqlite3.connect(self.db_path) as db:
            row = db.execute("SELECT name, created_at, mime, nonce, ciphertext FROM images WHERE id = ?", (image_id,)).fetchone()
        if row is None:
            raise ValueError("image not found")
        name, created, mime, nonce, ciphertext = row
        if mime != "image/png" or not isinstance(name, str) or Path(name).name != name or not name.endswith(".png"):
            raise ValueError("stored image metadata is invalid")
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, self._image_aad(image_id, name, created))
        self._validate_png(plaintext)
        target = self.cache / name
        with tempfile.NamedTemporaryFile(dir=self.cache, prefix=".materialize-", suffix=".tmp", delete=False) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(plaintext)
            temporary.flush()
            os.fsync(temporary.fileno())
        self._secure_file(temporary_path)
        os.replace(temporary_path, target)
        self._secure_file(target)
        return target

    @staticmethod
    def _secure_directory(path: Path) -> None:
        try:
            os.chmod(path, 0o700)
        except OSError:
            pass

    @staticmethod
    def _secure_file(path: Path) -> None:
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    @staticmethod
    def _sanitize_prompt(prompt: str) -> str:
        return "".join(
            char for char in str(prompt)
            if char in "\t\n" or (ord(char) >= 32 and unicodedata.category(char) not in {"Cc", "Cf"})
        ).strip()[:4000]

    @staticmethod
    def _image_aad(image_id: str, name: str, created: str) -> bytes:
        return f"{image_id}|{name}|{created}|image/png".encode()

    @staticmethod
    def _prompt_aad(image_id: str, name: str, created: str) -> bytes:
        return f"{image_id}|{name}|{created}|image-prompt".encode()

    def _migrate_legacy_prompts(self, key: bytes) -> None:
        with sqlite3.connect(self.db_path) as db:
            rows = db.execute("SELECT id, name, created_at, prompt FROM images WHERE prompt_nonce IS NULL AND prompt <> ''").fetchall()
            for image_id, name, created, prompt in rows:
                nonce = os.urandom(12)
                encrypted = AESGCM(key).encrypt(
                    nonce,
                    self._sanitize_prompt(str(prompt)).encode("utf-8"),
                    self._prompt_aad(str(image_id), str(name), str(created)),
                )
                db.execute("UPDATE images SET prompt = '', prompt_nonce = ?, prompt_ciphertext = ? WHERE id = ?", (nonce, encrypted, image_id))
            db.commit()
        self._secure_file(self.db_path)

    def _validate_png(self, image: bytes) -> None:
        if not isinstance(image, bytes) or len(image) > self.MAX_IMAGE_BYTES or len(image) < 33:
            raise ValueError("image exceeds the safe size limit")
        if image[:8] != self._PNG_SIGNATURE or image[12:16] != b"IHDR":
            raise ValueError("only PNG desktop frames are accepted")
        width = int.from_bytes(image[16:20], "big")
        height = int.from_bytes(image[20:24], "big")
        if not width or not height or width > self.MAX_IMAGE_EDGE or height > self.MAX_IMAGE_EDGE or width * height > self.MAX_IMAGE_PIXELS:
            raise ValueError("image dimensions exceed the safe limit")
        if b"IEND" not in image[-32:]:
            raise ValueError("image is truncated")
