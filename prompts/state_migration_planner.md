# State Migration Planner

Propose a deterministic migration between two semantic-state schema versions.

Preserve stable identities, provenance, epistemic labels, branch ancestry, and event references. Identify lossy transformations, defaults, unknown-field handling, rollback, and test vectors. Never rewrite historical events; migrations create new derived states with provenance. Return only JSON matching `nmsr.state-migration/1`.
