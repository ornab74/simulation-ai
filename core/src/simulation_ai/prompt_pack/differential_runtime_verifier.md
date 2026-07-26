# Differential Runtime Verifier

Compare a semantic twin prediction with a real, virtualized, emulated, or remote runtime observation.

Determine:

- Inputs that were equivalent
- Expected semantic effects
- Actual observed effects
- Timing and ordering differences
- State, API, filesystem, process, network, and visual mismatches
- Benign nondeterminism versus model error
- Missing instrumentation
- Rule confidence changes
- Whether a profile rule may be promoted, retained as hypothesis, or rejected

Do not hide mismatches through narrative equivalence. Return only JSON matching `nmsr.differential-verification/1`.
