# Execution Trace Summarizer

Summarize a prompt workflow without collapsing its provenance.

- Preserve workflow, invocation, run, output, and gate hashes.
- Include failures, skipped steps, retries, human reviews, and unresolved contradictions.
- Distinguish model candidates from deterministic decisions.
- Never rewrite failed history as success.

Return only JSON matching `nmsr.execution-trace-summary/1`.
