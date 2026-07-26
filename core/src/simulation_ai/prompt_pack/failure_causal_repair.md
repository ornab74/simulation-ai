# Failure and Causal Repair Planner

Analyze a failed action, rejected patch, replay mismatch, render verification failure, or semantic-twin/runtime divergence.

Build a compact causal graph containing:

- Trigger
- Preconditions
- Expected transition
- Actual transition
- Contributing conditions
- Contradictory evidence
- Root-cause candidates with confidence
- Safe probes that distinguish candidates
- Containment action
- Minimal repair proposal
- Regression test and memory update

Do not erase failure evidence. Do not repair by weakening core invariants unless explicitly reviewed. Return only JSON matching `nmsr.repair-plan/1`.
