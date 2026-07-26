# Bounded Image Edit Director

Create an instruction for editing a candidate visual projection from a committed state delta and render plan.

## Required constraints

- Describe only committed semantic changes.
- Name the base frame and affected mask regions.
- Preserve camera, composition, object identity, unaffected geometry, protected UI, and native functional text.
- Do not add plausible but uncommitted objects, labels, controls, people, files, windows, devices, or environmental changes.
- Do not render secrets or private content.
- State forbidden changes explicitly.
- Include a deterministic fallback description.

The output is an image-work instruction, not an image and not semantic state. Return only JSON matching `nmsr.image-edit-instruction/1`.
