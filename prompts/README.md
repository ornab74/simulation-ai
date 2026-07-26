# Simulation AI Prompt Pack

This directory is the human-readable mirror of the versioned prompt pack loaded by `simulation_ai.prompts.PromptRegistry`.

The pack is a role registry, not a collection of informal chat templates. Each role declares:

- stable ID and semantic version
- authority ceiling
- workflow stage and task routing
- required and optional inputs
- strict JSON output schema
- risk, latency, modalities, and preferred runtime class
- mandatory deterministic gate
- content and pack hashes

Four non-callable policies are prepended to every callable role:

1. `simulation_constitution`
2. `untrusted_data_firewall`
3. `epistemic_integrity_policy`
4. `runtime_execution_safety`

Model outputs remain observations, proposals, routes, reviews, or candidate render instructions. The deterministic Surface Core is the only commit and execution authority.

Validate with:

```bash
PYTHONPATH=core/src python -m simulation_ai.prompts --validate
```
