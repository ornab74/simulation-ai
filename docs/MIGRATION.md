# Multiverse Generator Migration

The chess product is intentionally excluded. Simulation AI reuses architecture,
not product-specific filenames.

## Retained patterns

- Godot-owned interactive surface and local service bridge.
- Loopback-only process boundary and bounded request sizes.
- Deterministic reducer authority.
- Local model installation and artifact-verification concepts.
- Responsive programmatic Godot UI.
- Native fallback when a model or image worker is unavailable.

## Removed completely

- Board, square, and piece state.
- Legal-move lists and chess turn routes.
- Caissa identity, prompts, profiles, and saved games.
- Chess-side color, skill, opening, and history controls.
- Chess test suites, assets, and release packaging.

## Replacement capability map

| Old responsibility | Simulation AI replacement |
|---|---|
| Chess reducer | Typed world-state patch validator |
| Legal move allowlist | Authorized JSON-pointer paths and invariants |
| Move history | Immutable world event envelopes |
| Saved game | Content-addressed state and branch refs |
| Chess analysis | Observation and proposal adapters |
| Board presenter | Semantic topology and verified render queue |

The migration proceeds by capability. This avoids keeping stale chess coupling
merely to preserve source-tree parity.
