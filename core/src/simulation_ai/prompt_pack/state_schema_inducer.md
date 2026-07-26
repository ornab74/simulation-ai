# State Schema Inducer

Propose a typed semantic state schema for a discovered program or operating-system subsystem.

## Requirements

- Define stable object identities and lifecycle states.
- Separate persistent state, session state, transient UI state, derived state, and external dependencies.
- Mark authoritative sources for every field.
- Define epistemic and provenance metadata.
- Identify protected, sensitive, and branch-local fields.
- Include extension points for target-specific concepts.
- Avoid encoding pixel coordinates as primary semantic truth.
- Describe migrations and unknown-field handling.

Return only JSON matching `nmsr.state-schema-proposal/1`.
