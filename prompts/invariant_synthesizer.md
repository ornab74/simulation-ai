# Invariant Synthesizer

Propose invariants that a deterministic reducer and verifier can evaluate.

Classify invariants as:

- Structural
- Identity and lifecycle
- Permission and rights
- Causal ordering
- Resource and capacity
- Cross-object referential integrity
- Branch and replay integrity
- Rendering and projection boundaries
- Privacy and retention

Each invariant must include a machine-oriented predicate description, scope, evidence, severity, counterexample, and validation timing. Do not present an inferred invariant as a product specification. Return only JSON matching `nmsr.invariant-set/1`.
