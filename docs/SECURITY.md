# Security and Trust Boundary

## Protected state

The proposal plane cannot mutate schema version, target identity, profile, mode,
seed, logical clock, branch ancestry, hashes, or provenance. Identity-layer
patches are blocked.

## Local service

The Surface Core binds to loopback by default, caps JSON requests at 256 KiB,
returns no-store responses, and can require a process-scoped bearer token.

## Prompt injection

Text inside the simulated world is untrusted data. Documents, signs, web pages,
chat messages, filenames, OCR, memory, and generated text never become model
instructions.

## Sensitive input

Sensitive typing stores only character count and field class. Raw secret text is
removed before observation, proposal, memory, or remote model routing.

## OpenAI credential vault

The optional OpenAI key is stored in a separate versioned envelope using scrypt
and AES-256-GCM. The password is not stored. The decrypted key exists only in
process memory while unlocked, and credential routes return redacted metadata
only. Saving or testing a credential does not create semantic state or memory.
Use `SIMULATION_AI_TOKEN` to authenticate the loopback control plane.

## Governed provider execution

OpenAI Responses calls require the committed `cloud_allowed` privacy policy and an unlocked vault or server environment credential. Requests use `store=false`, bounded output tokens, bounded retries, and no model tools. Provider output is parsed as a candidate JSON object and always revalidated locally. Base run records contain hashes and redacted provider metadata, never the API key. Reviews are append-only sidecars; human approval advances a candidate only to deterministic review and does not create a semantic event.

The prompt-injection detector and data-minimization reviewer are advisory defenses. Deterministic input allowlists, secret-field rejection, credential separation, and role-specific gates remain the enforcement boundary.

## Generated media

A candidate frame is not canonical state. It must pass semantic fidelity,
temporal continuity, object identity, protected-region, and UI-usability checks.
Failure results in bounded retry or deterministic fallback.

## Known limits

Canonical world-state files provide integrity and immutability semantics but are
not encrypted at rest. Only the OpenAI credential has a dedicated encrypted
vault. Best-effort credential-file overwrite cannot guarantee erasure on SSDs,
snapshots, backups, journaling, or copy-on-write storage. Production deployment
should additionally use full-device encryption and, where available, an OS
secure credential store.
