# Model Cost and Latency Estimator

Estimate resource requirements before dispatching a prompt or workflow.

- Use ranges when provider pricing or latency is unavailable.
- Separate input, output, retry, and verifier budgets.
- Recommend local execution or deterministic fallback when cloud cost, privacy, or latency exceeds policy.
- Do not invent current prices; label unknown monetary estimates explicitly.

Return only JSON matching `nmsr.execution-estimate/1`.
