from __future__ import annotations

from base64 import b64decode, b64encode
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
import os
from pathlib import Path
from threading import RLock
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


_VAULT_FORMAT = "simulation-ai-openai-vault-v1"
_PROVIDER = "openai"
_AAD = b"simulation-ai/openai-credential/v1"
_DEFAULT_TEST_URL = "https://api.openai.com/v1/models"


class CredentialVaultError(ValueError):
    """Safe, user-facing credential-vault error.

    Messages must never contain API keys, passwords, ciphertext, or response
    bodies from upstream providers.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(slots=True)
class CredentialStatus:
    configured: bool
    unlocked: bool
    env_available: bool
    source: str
    fingerprint: str
    created_at: str
    provider: str = _PROVIDER
    format: str = _VAULT_FORMAT

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "format": self.format,
            "configured": self.configured,
            "unlocked": self.unlocked,
            "env_available": self.env_available,
            "source": self.source,
            "fingerprint": self.fingerprint,
            "created_at": self.created_at,
            "secret_exposed": False,
        }


class OpenAICredentialVault:
    """Password-wrapped local OpenAI API credential.

    The encrypted file contains a versioned AES-256-GCM envelope. The wrapping
    key is derived with scrypt from a password that is never stored. The API key
    exists in process memory only while the vault is unlocked. The key is never
    returned by status APIs and is never written into semantic state, events,
    evidence, proposals, memory, or render records.
    """

    def __init__(
        self,
        home: Path,
        *,
        scrypt_n: int = 1 << 15,
        scrypt_r: int = 8,
        scrypt_p: int = 1,
        minimum_password_characters: int = 12,
        test_url: str = _DEFAULT_TEST_URL,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        self.directory = Path(home) / "credentials"
        self.path = self.directory / "openai.vault.json"
        self.scrypt_n = scrypt_n
        self.scrypt_r = scrypt_r
        self.scrypt_p = scrypt_p
        self.minimum_password_characters = minimum_password_characters
        self.test_url = test_url
        self._opener = opener
        self._api_key: bytearray | None = None
        self._source = ""
        self._created_at = ""
        self._lock = RLock()

    def status(self) -> CredentialStatus:
        with self._lock:
            configured = self.path.exists()
            header = self._read_header_metadata() if configured else {}
            source = self._source if self._api_key is not None else str(header.get("source", ""))
            created_at = self._created_at if self._api_key is not None else str(header.get("createdAt", ""))
            return CredentialStatus(
                configured=configured,
                unlocked=self._api_key is not None,
                env_available=bool(os.environ.get("OPENAI_API_KEY", "").strip()),
                source=source or ("environment" if os.environ.get("OPENAI_API_KEY", "").strip() else "none"),
                fingerprint=self._fingerprint(self._api_key) if self._api_key is not None else "",
                created_at=created_at,
            )

    def import_environment(self, password: str) -> CredentialStatus:
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise CredentialVaultError(
                "environment_key_missing",
                "OPENAI_API_KEY is not present in the Surface Core process environment.",
            )
        return self.save(api_key, password, source="environment-import")

    def save(self, api_key: str, password: str, *, source: str = "settings-entry") -> CredentialStatus:
        with self._lock:
            clean_key = self._validate_api_key(api_key)
            self._validate_password(password)

            # Replacing an existing vault always requires proving possession of
            # its current password, even when the credential is already unlocked.
            if self.path.exists():
                self.unlock(password)

            salt = os.urandom(16)
            nonce = os.urandom(12)
            wrapping_key = bytearray(self._derive_key(password, salt, self.scrypt_n, self.scrypt_r, self.scrypt_p))
            created_at = datetime.now(UTC).isoformat(timespec="seconds")
            clear = bytearray(
                json.dumps(
                    {
                        "provider": _PROVIDER,
                        "api_key": clean_key,
                        "source": source,
                        "created_at": created_at,
                    },
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")
            )
            try:
                cipher_text = AESGCM(bytes(wrapping_key)).encrypt(nonce, bytes(clear), _AAD)
                envelope = {
                    "format": _VAULT_FORMAT,
                    "version": 1,
                    "provider": _PROVIDER,
                    "source": source,
                    "createdAt": created_at,
                    "kdf": {
                        "algorithm": "scrypt",
                        "salt": b64encode(salt).decode("ascii"),
                        "n": self.scrypt_n,
                        "r": self.scrypt_r,
                        "p": self.scrypt_p,
                        "length": 32,
                    },
                    "cipher": {
                        "algorithm": "AES-256-GCM",
                        "nonce": b64encode(nonce).decode("ascii"),
                        "ciphertext": b64encode(cipher_text).decode("ascii"),
                        "aad": "simulation-ai/openai-credential/v1",
                    },
                }
                self._atomic_write(envelope)
                self._set_unlocked(clean_key, source, created_at)
                return self.status()
            finally:
                self._zero(wrapping_key)
                self._zero(clear)

    def unlock(self, password: str) -> CredentialStatus:
        with self._lock:
            if not self.path.exists():
                raise CredentialVaultError("not_configured", "No encrypted OpenAI credential is configured.")
            envelope = self._read_envelope()
            self._validate_envelope(envelope)
            kdf = dict(envelope["kdf"])
            cipher = dict(envelope["cipher"])
            try:
                salt = b64decode(str(kdf["salt"]), validate=True)
                nonce = b64decode(str(cipher["nonce"]), validate=True)
                cipher_text = b64decode(str(cipher["ciphertext"]), validate=True)
            except Exception as exc:
                raise CredentialVaultError("invalid_vault", "The encrypted credential vault is malformed.") from exc

            wrapping_key = bytearray(
                self._derive_key(password, salt, int(kdf["n"]), int(kdf["r"]), int(kdf["p"]))
            )
            clear: bytearray | None = None
            try:
                try:
                    clear = bytearray(AESGCM(bytes(wrapping_key)).decrypt(nonce, cipher_text, _AAD))
                except InvalidTag as exc:
                    raise CredentialVaultError(
                        "authentication_failed",
                        "The credential-vault password is incorrect or the vault was modified.",
                    ) from exc
                try:
                    payload = json.loads(bytes(clear).decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise CredentialVaultError("invalid_vault", "The decrypted credential record is malformed.") from exc
                if payload.get("provider") != _PROVIDER:
                    raise CredentialVaultError("provider_mismatch", "The credential record is not an OpenAI key.")
                api_key = self._validate_api_key(str(payload.get("api_key", "")))
                self._set_unlocked(
                    api_key,
                    str(payload.get("source", envelope.get("source", "encrypted-vault"))),
                    str(payload.get("created_at", envelope.get("createdAt", ""))),
                )
                return self.status()
            finally:
                self._zero(wrapping_key)
                self._zero(clear)

    def lock(self) -> CredentialStatus:
        with self._lock:
            self._zero(self._api_key)
            self._api_key = None
            self._source = ""
            self._created_at = ""
            return self.status()

    def clear(self, password: str = "") -> CredentialStatus:
        with self._lock:
            if not self.path.exists():
                self.lock()
                return self.status()
            if not password:
                raise CredentialVaultError(
                    "password_required",
                    "Enter the credential-vault password before clearing the encrypted key.",
                )
            # Always re-authenticate destructive deletion, even if the vault is
            # already unlocked in process memory.
            self.unlock(password)
            self.lock()
            self._best_effort_delete(self.path)
            return self.status()

    def resolve_api_key(self) -> tuple[str, str]:
        """Return a short-lived key copy and its source for provider calls."""
        with self._lock:
            if self._api_key is not None:
                return bytes(self._api_key).decode("utf-8"), "encrypted-vault"
            env_key = os.environ.get("OPENAI_API_KEY", "").strip()
            if env_key:
                return self._validate_api_key(env_key), "environment"
            if self.path.exists():
                raise CredentialVaultError("locked", "The encrypted OpenAI credential is locked.")
            raise CredentialVaultError("not_configured", "No OpenAI API credential is available.")

    def test_connection(self, *, timeout: float = 12.0) -> dict[str, Any]:
        api_key, source = self.resolve_api_key()
        request = Request(
            self.test_url,
            method="GET",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "User-Agent": "simulation-ai-core/0.3",
            },
        )
        try:
            with self._opener(request, timeout=timeout) as response:
                status_code = int(getattr(response, "status", 200))
                body = response.read(2 * 1024 * 1024)
            model_count = 0
            try:
                parsed = json.loads(body)
                if isinstance(parsed, dict) and isinstance(parsed.get("data"), list):
                    model_count = len(parsed["data"])
            except (UnicodeDecodeError, json.JSONDecodeError):
                pass
            return {
                "ok": 200 <= status_code < 300,
                "provider": _PROVIDER,
                "source": source,
                "status_code": status_code,
                "model_count": model_count,
                "fingerprint": self._fingerprint_text(api_key),
                "detail": "OpenAI authentication succeeded." if 200 <= status_code < 300 else "OpenAI returned an unexpected status.",
            }
        except HTTPError as exc:
            status_code = int(exc.code)
            detail = {
                401: "OpenAI rejected the API key.",
                403: "The API key is authenticated but not permitted for this request.",
                429: "OpenAI accepted the request but rate limits or quota prevented the test.",
            }.get(status_code, "OpenAI returned an error while testing the key.")
            return {
                "ok": False,
                "provider": _PROVIDER,
                "source": source,
                "status_code": status_code,
                "model_count": 0,
                "fingerprint": self._fingerprint_text(api_key),
                "detail": detail,
            }
        except (URLError, TimeoutError, OSError) as exc:
            return {
                "ok": False,
                "provider": _PROVIDER,
                "source": source,
                "status_code": 0,
                "model_count": 0,
                "fingerprint": self._fingerprint_text(api_key),
                "detail": f"OpenAI could not be reached: {type(exc).__name__}.",
            }

    def _set_unlocked(self, api_key: str, source: str, created_at: str) -> None:
        self._zero(self._api_key)
        self._api_key = bytearray(api_key.encode("utf-8"))
        self._source = source
        self._created_at = created_at

    def _read_header_metadata(self) -> dict[str, Any]:
        try:
            envelope = self._read_envelope()
            return {
                "source": envelope.get("source", "encrypted-vault"),
                "createdAt": envelope.get("createdAt", ""),
            }
        except CredentialVaultError:
            return {"source": "invalid-vault", "createdAt": ""}

    def _read_envelope(self) -> dict[str, Any]:
        try:
            if self.path.stat().st_size > 1024 * 1024:
                raise CredentialVaultError("invalid_vault", "The credential vault is unexpectedly large.")
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise CredentialVaultError("not_configured", "No encrypted OpenAI credential is configured.") from exc
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CredentialVaultError("invalid_vault", "The credential vault could not be read.") from exc
        if not isinstance(value, dict):
            raise CredentialVaultError("invalid_vault", "The credential vault root must be an object.")
        return value

    def _validate_envelope(self, envelope: dict[str, Any]) -> None:
        if envelope.get("format") != _VAULT_FORMAT or envelope.get("provider") != _PROVIDER:
            raise CredentialVaultError("invalid_vault", "Unsupported credential-vault format.")
        kdf = envelope.get("kdf")
        cipher = envelope.get("cipher")
        if not isinstance(kdf, dict) or not isinstance(cipher, dict):
            raise CredentialVaultError("invalid_vault", "Credential-vault cryptographic metadata is missing.")
        if kdf.get("algorithm") != "scrypt" or cipher.get("algorithm") != "AES-256-GCM":
            raise CredentialVaultError("invalid_vault", "Unsupported credential-vault cryptography.")
        n, r, p = int(kdf.get("n", 0)), int(kdf.get("r", 0)), int(kdf.get("p", 0))
        if n < (1 << 14) or n > (1 << 20) or n & (n - 1) or not 1 <= r <= 32 or not 1 <= p <= 16:
            raise CredentialVaultError("invalid_vault", "Credential-vault KDF parameters are outside policy.")

    def _derive_key(self, password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
        if not password:
            raise CredentialVaultError("password_required", "Enter the credential-vault password.")
        try:
            return Scrypt(salt=salt, length=32, n=n, r=r, p=p).derive(password.encode("utf-8"))
        except (ValueError, MemoryError) as exc:
            raise CredentialVaultError("kdf_failed", "The credential-vault key derivation failed.") from exc

    def _validate_password(self, password: str) -> None:
        if len(password) < self.minimum_password_characters:
            raise CredentialVaultError(
                "weak_password",
                f"Use at least {self.minimum_password_characters} characters for the credential-vault password.",
            )
        if len(password) > 1024:
            raise CredentialVaultError("password_too_long", "The credential-vault password is too long.")

    @staticmethod
    def _validate_api_key(api_key: str) -> str:
        clean = api_key.strip()
        if len(clean) < 20 or len(clean) > 512 or any(char.isspace() for char in clean):
            raise CredentialVaultError("invalid_api_key", "Enter a valid OpenAI API key without whitespace.")
        return clean

    def _atomic_write(self, value: dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.directory, 0o700)
        except OSError:
            pass
        tmp = self.path.with_name(f".{self.path.name}.tmp")
        data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8")
        with tmp.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        tmp.replace(self.path)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    @staticmethod
    def _best_effort_delete(path: Path) -> None:
        try:
            size = path.stat().st_size
            with path.open("r+b", buffering=0) as handle:
                handle.write(os.urandom(size))
                handle.flush()
                os.fsync(handle.fileno())
        except OSError:
            pass
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            raise CredentialVaultError("delete_failed", "The encrypted credential file could not be removed.") from exc

    @staticmethod
    def _fingerprint(value: bytearray | None) -> str:
        if not value:
            return ""
        return sha256(bytes(value)).hexdigest()[:12]

    @staticmethod
    def _fingerprint_text(value: str) -> str:
        return sha256(value.encode("utf-8")).hexdigest()[:12] if value else ""

    @staticmethod
    def _zero(value: bytearray | None) -> None:
        if value is None:
            return
        for index in range(len(value)):
            value[index] = 0
