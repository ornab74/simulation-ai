# Candidate Frame Verifier

Compare the candidate frame with the committed state delta, render plan, previous verified frame, object anchors, masks, protected UI regions, and privacy manifest.

Score and explain:

- Semantic fidelity
- Temporal continuity
- Object identity stability
- Camera and composition continuity
- Protected-region stability
- Mask leakage
- Functional text exactness
- UI usability and accessibility
- Privacy redaction
- Unsupported additions or omissions
- Generated-content disclosure

Return one decision: `pass`, `retry`, `fallback`, `reject`, or `human_review`. A visual pass may create a frame manifest; it never changes semantic state. Return only JSON matching `nmsr.frame-verification/1`.
