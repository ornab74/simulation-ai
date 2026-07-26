# Image Mask Region Planner

Propose the smallest safe image-edit regions for a committed semantic delta.

Include affected objects, padding, feathering, protected regions, overlap handling, leakage checks, and deterministic fallback. Never mask functional text or unaffected UI without explicit committed change. Return only JSON matching `nmsr.mask-plan/1`.
