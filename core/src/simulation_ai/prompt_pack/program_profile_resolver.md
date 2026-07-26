# Program Profile Resolver

Assemble a candidate `ProgramProfile` from verified discovery evidence and component proposals.

A profile includes:

- Program family and supported versions
- Execution strategy and runtime adapter
- State schema
- Action grammar
- Deterministic reducer bindings
- Invariant set
- Observer bindings
- Renderer bindings
- Capability and permission model
- Probe policy
- Known gaps, unsupported behaviors, and confidence

Do not claim complete compatibility. Every profile capability must be labeled as observed, inferred, emulated, proxied, or unsupported. Return only JSON matching `nmsr.program-profile/1`.
