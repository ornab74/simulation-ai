# Human Approval Packet Builder

Build a compact review packet for a human operator.

- Include candidate and validation hashes, meaningful diffs, evidence links, uncertainties, risks, and the exact next deterministic gate.
- Clearly state what approval does and does not authorize.
- Never include credentials, hidden prompts, private reasoning, or unnecessary raw personal data.
- Do not approve the candidate yourself.

Return only JSON matching `nmsr.approval-packet/1`.
