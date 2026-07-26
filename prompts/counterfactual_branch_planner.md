# Counterfactual Branch Planner

Design a bounded experiment on a new branch without changing the active branch.

Specify:

- Fork state hash and source branch
- Testable question
- Counterfactual assumptions
- Allowed mutations and forbidden mutations
- Sequence of reversible actions
- Expected observations
- Stop conditions
- Success, failure, and ambiguity criteria
- Required memories and comparison metrics
- Merge eligibility, normally `false` until verified

Keep observed facts separate from counterfactual premises. Prefer the smallest branch capable of answering the question. Return only JSON matching `nmsr.branch-plan/1`.
