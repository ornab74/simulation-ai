# Universal Software Ontology Mapper

Map target-specific concepts into the universal software ontology while preserving target-specific extensions.

Common ontology concepts include process, thread, file, directory, window, document, user, identity, permission, capability, device, service, network endpoint, package, application, event, timer, and resource.

## Rules

- Never force a lossy mapping when no equivalent exists.
- Preserve source identifiers and namespace target-specific fields.
- Distinguish equivalence, specialization, approximation, and no-match.
- Record cardinality, lifecycle, ownership, and permission differences.
- Do not merge objects solely because their labels look similar.

Return only JSON matching `nmsr.ontology-mapping/1`.
