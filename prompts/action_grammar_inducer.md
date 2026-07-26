# Action Grammar Inducer

Infer a candidate action grammar from repeated interaction and runtime evidence.

For each action define:

- Stable action ID and human label
- Parameters and types
- Valid target classes
- Preconditions
- Deterministic effects or effect hypotheses
- Observable postconditions
- Error outcomes
- Reversibility and undo mapping
- Safety class
- Required permissions
- Evidence and confidence

Separate UI gestures from semantic actions. Multiple gestures may map to one semantic action. Return only JSON matching `nmsr.action-grammar/1`.
