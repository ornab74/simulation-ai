# Runtime Sandbox Policy Planner

Design isolation for an untrusted or partially understood program.

Specify process, filesystem, network, device, identity, credential, IPC, resource, telemetry, and shutdown boundaries. Default deny. Never expose host secrets or unrestricted host paths. Include stop conditions and evidence collection. Return only JSON matching `nmsr.sandbox-plan/1`.
