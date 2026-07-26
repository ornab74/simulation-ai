# Encrypted OpenAI Credential Vault

Simulation AI can use an OpenAI API key from either:

1. the `OPENAI_API_KEY` environment variable for the current Surface Core process; or
2. a password-wrapped local vault at `.simulation-ai/credentials/openai.vault.json`.

The Settings page can import the process environment key into the encrypted vault,
accept a manually pasted key, unlock or lock the vault, test authentication, and
remove the encrypted file.

## Cryptographic envelope

The vault uses:

- scrypt password derivation with a random 16-byte salt;
- a 32-byte wrapping key;
- AES-256-GCM with a random 12-byte nonce;
- versioned additional authenticated data;
- an atomic write followed by best-effort `0600` file permissions;
- a one-megabyte maximum envelope size and bounded KDF parameters.

The password is never stored. The decrypted key remains in process memory only
while the vault is unlocked. Locking zeroes the mutable in-memory key buffer.
Clearing the vault requires re-entering the correct password, even when the key
is already unlocked.

## Authority boundary

Credential routes are operational control-plane routes. They do **not** create:

- world-state mutations;
- event envelopes;
- evidence records;
- patch proposals;
- memories;
- render jobs;
- frame manifests.

Status responses contain only redacted metadata: configured, unlocked,
environment availability, source, creation time, and a short SHA-256 fingerprint.
The API key is never returned.

## Recommended launch

```bash
export SIMULATION_AI_TOKEN="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export OPENAI_API_KEY="your-key"
./scripts/run-dev.sh
```

Open **Settings → OpenAI Credential Vault**, enter a separate 12+ character
vault password, and choose **Import Env Key**. After a successful import, remove
`OPENAI_API_KEY` from future launch environments and unlock the encrypted vault
when needed.

`SIMULATION_AI_TOKEN` protects every loopback route from unauthenticated local
callers. The vault password separately protects the encrypted credential file.

## Test behavior

The **Test OpenAI** action sends `GET https://api.openai.com/v1/models` with
Bearer authentication. It reports only HTTP status, a model count, source, and
credential fingerprint. Upstream response bodies are not forwarded to the UI.

## Limits

Best-effort overwrite before deletion cannot guarantee forensic erasure on SSDs,
copy-on-write filesystems, snapshots, journaling storage, or backups. Full-device
encryption and operating-system account protections remain important.
