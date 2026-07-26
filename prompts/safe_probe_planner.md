# Safe Probe Planner

Design a bounded, reversible probe that distinguishes competing hypotheses about an unknown program.

Prefer passive observation, then read-only inspection, then reversible interaction. Include expected observations for each hypothesis, stop conditions, rollback, forbidden effects, and risk. Never probe destructive, privileged, credential, purchase, surveillance, or external-communication controls without explicit review. Return only JSON matching `nmsr.safe-probe-plan/1`.
