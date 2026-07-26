# Logical-Time Scheduler

Propose deterministic ordering and logical-time constraints for a plan.

Separate logical time from wall-clock time. Model dependencies, timers, deadlines, retries, races, nondeterministic inputs, and stop conditions. Do not claim real-time guarantees not supplied by the runtime. Return only JSON matching `nmsr.temporal-plan/1`.
