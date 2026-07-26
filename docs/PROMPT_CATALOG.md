# Prompt Catalog

> Generated from `prompts/manifest.json` by `scripts/export-prompt-catalog.py`.

Pack: `simulation-ai-universal-runtime` v`3.0.0`
Roles: **72** total, **68** callable
Workflows: **15**

Every callable role is proposal, observation, review, routing, or verification only. A deterministic gate remains mandatory.

## Analyze

| Role | Authority | Risk | Runtime | Output schema | Tasks |
|---|---|---:|---|---|---|
| [`branch_comparison_analyst`](../prompts/branch_comparison_analyst.md) | `advisory-only` | `high` | `reasoning` | `nmsr.branch-analysis/1` | `compare_branches`, `counterfactual` |
| [`causal_graph_builder`](../prompts/causal_graph_builder.md) | `advisory-only` | `high` | `reasoning` | `nmsr.causal-graph/1` | `build_causal_graph`, `repair_failure` |
| [`contradiction_resolver`](../prompts/contradiction_resolver.md) | `advisory-only` | `high` | `reasoning` | `nmsr.contradiction-resolution/1` | `resolve_contradiction`, `remember` |

## Audit

| Role | Authority | Risk | Runtime | Output schema | Tasks |
|---|---|---:|---|---|---|
| [`replay_integrity_verifier`](../prompts/replay_integrity_verifier.md) | `verification-advisory` | `critical` | `local-deterministic-plus-reasoning` | `nmsr.replay-verification/1` | `verify_replay`, `audit_history` |

## Compile

| Role | Authority | Risk | Runtime | Output schema | Tasks |
|---|---|---:|---|---|---|
| [`action_compiler`](../prompts/action_compiler.md) | `operation-proposal-only` | `high` | `reasoning` | `nmsr.action-compilation/1` | `compile_action`, `execute_goal` |
| [`simulation_scenario_compiler`](../prompts/simulation_scenario_compiler.md) | `scenario-proposal-only` | `high` | `reasoning` | `nmsr.simulation-scenario/1` | `compile_scenario`, `simulate_program` |
| [`world_bootstrap_planner`](../prompts/world_bootstrap_planner.md) | `proposal-only` | `high` | `reasoning` | `nmsr.world-bootstrap/1` | `bootstrap_world`, `simulate_program`, `simulate_os` |

## Critic

| Role | Authority | Risk | Runtime | Output schema | Tasks |
|---|---|---:|---|---|---|
| [`patch_critic`](../prompts/patch_critic.md) | `advisory-only` | `high` | `reasoning` | `nmsr.patch-critique/1` | `critique_patch` |
| [`plan_critic`](../prompts/plan_critic.md) | `advisory-only` | `high` | `reasoning` | `nmsr.plan-review/1` | `critique_plan` |
| [`prompt_run_critic`](../prompts/prompt_run_critic.md) | `review-only` | `critical` | `reasoning` | `nmsr.prompt-run-review/1` | `review_prompt_run` |

## Deploy

| Role | Authority | Risk | Runtime | Output schema | Tasks |
|---|---|---:|---|---|---|
| [`deployment_readiness_reviewer`](../prompts/deployment_readiness_reviewer.md) | `deployment-advisory` | `critical` | `reasoning` | `nmsr.deployment-review/1` | `deployment_review` |

## Discover

| Role | Authority | Risk | Runtime | Output schema | Tasks |
|---|---|---:|---|---|---|
| [`safe_probe_planner`](../prompts/safe_probe_planner.md) | `probe-proposal-only` | `medium` | `reasoning` | `nmsr.safe-probe-plan/1` | `plan_probe`, `discover_program` |
| [`unknown_app_discovery_observer`](../prompts/unknown_app_discovery_observer.md) | `observation-only` | `medium` | `local-multimodal` | `nmsr.observation/1` | `discover_program` |

## Evaluate

| Role | Authority | Risk | Runtime | Output schema | Tasks |
|---|---|---:|---|---|---|
| [`deterministic_test_generator`](../prompts/deterministic_test_generator.md) | `test-proposal-only` | `high` | `reasoning` | `nmsr.test-plan/1` | `generate_tests`, `promote_profile`, `deployment_review` |
| [`evaluation_reporter`](../prompts/evaluation_reporter.md) | `evaluation-advisory` | `high` | `reasoning` | `nmsr.evaluation-report/1` | `evaluate`, `promote_profile`, `deployment_review` |

## Interpret

| Role | Authority | Risk | Runtime | Output schema | Tasks |
|---|---|---:|---|---|---|
| [`intent_interpreter`](../prompts/intent_interpreter.md) | `intent-advisory` | `medium` | `local-or-cloud-reasoning` | `nmsr.intent/1` | `interpret_intent`, `interact` |

## Memory

| Role | Authority | Risk | Runtime | Output schema | Tasks |
|---|---|---:|---|---|---|
| [`execution_trace_summarizer`](../prompts/execution_trace_summarizer.md) | `summary-only` | `medium` | `local-or-cloud-reasoning` | `nmsr.execution-trace-summary/1` | `summarize_execution_trace` |

## Merge

| Role | Authority | Risk | Runtime | Output schema | Tasks |
|---|---|---:|---|---|---|
| [`semantic_merge_planner`](../prompts/semantic_merge_planner.md) | `proposal-only` | `critical` | `reasoning` | `nmsr.merge-plan/1` | `merge`, `merge_branch` |

## Normalize

| Role | Authority | Risk | Runtime | Output schema | Tasks |
|---|---|---:|---|---|---|
| [`universal_ontology_mapper`](../prompts/universal_ontology_mapper.md) | `proposal-only` | `medium` | `reasoning` | `nmsr.ontology-mapping/1` | `map_ontology`, `simulate_os` |

## Observe

| Role | Authority | Risk | Runtime | Output schema | Tasks |
|---|---|---:|---|---|---|
| [`accessibility_tree_observer`](../prompts/accessibility_tree_observer.md) | `observation-only` | `medium` | `local-structured` | `nmsr.observation/1` | `observe_accessibility`, `discover_program` |
| [`filesystem_runtime_observer`](../prompts/filesystem_runtime_observer.md) | `observation-only` | `medium` | `local-telemetry` | `nmsr.observation/1` | `observe_filesystem`, `simulate_os` |
| [`local_observer`](../prompts/local_observer.md) | `observation-only` | `medium` | `local-multimodal` | `nmsr.observation/1` | `observe`, `interact` |
| [`network_runtime_observer`](../prompts/network_runtime_observer.md) | `observation-only` | `medium` | `local-telemetry` | `nmsr.observation/1` | `observe_network`, `simulate_os` |
| [`os_runtime_observer`](../prompts/os_runtime_observer.md) | `observation-only` | `medium` | `local-or-cloud-multimodal` | `nmsr.observation/1` | `observe_os`, `simulate_os` |
| [`process_runtime_observer`](../prompts/process_runtime_observer.md) | `observation-only` | `medium` | `local-telemetry` | `nmsr.observation/1` | `observe_processes`, `simulate_os` |
| [`visual_anchor_extractor`](../prompts/visual_anchor_extractor.md) | `visual-observation-only` | `medium` | `multimodal-local-or-cloud` | `nmsr.anchor-manifest/1` | `extract_anchors`, `verify_frame` |

## Plan

| Role | Authority | Risk | Runtime | Output schema | Tasks |
|---|---|---:|---|---|---|
| [`cost_latency_estimator`](../prompts/cost_latency_estimator.md) | `budget-advisory` | `medium` | `local-or-cloud-reasoning` | `nmsr.execution-estimate/1` | `estimate_model_execution` |
| [`counterfactual_branch_planner`](../prompts/counterfactual_branch_planner.md) | `proposal-only` | `high` | `reasoning` | `nmsr.branch-plan/1` | `counterfactual`, `experiment` |
| [`goal_decomposer`](../prompts/goal_decomposer.md) | `proposal-only` | `high` | `reasoning` | `nmsr.goal-plan/1` | `decompose_goal`, `plan` |
| [`plan_synthesizer`](../prompts/plan_synthesizer.md) | `proposal-only` | `high` | `reasoning` | `nmsr.execution-plan/1` | `synthesize_plan`, `plan`, `execute_goal` |

## Policy

| Role | Authority | Risk | Runtime | Output schema | Tasks |
|---|---|---:|---|---|---|
| [`epistemic_integrity_policy`](../prompts/epistemic_integrity_policy.md) | `shared-policy` | `critical` | `policy-layer` | — | — |
| [`runtime_execution_safety`](../prompts/runtime_execution_safety.md) | `shared-policy` | `critical` | `policy-layer` | — | — |
| [`simulation_constitution`](../prompts/simulation_constitution.md) | `shared-policy` | `critical` | `all` | — | — |
| [`untrusted_data_firewall`](../prompts/untrusted_data_firewall.md) | `shared-policy` | `critical` | `all` | — | — |

## Privacy

| Role | Authority | Risk | Runtime | Output schema | Tasks |
|---|---|---:|---|---|---|
| [`data_minimization_reviewer`](../prompts/data_minimization_reviewer.md) | `privacy-advisory` | `critical` | `local-reasoning` | `nmsr.data-minimization-review/1` | `minimize_model_data` |

## Profile

| Role | Authority | Risk | Runtime | Output schema | Tasks |
|---|---|---:|---|---|---|
| [`action_grammar_inducer`](../prompts/action_grammar_inducer.md) | `proposal-only` | `high` | `reasoning` | `nmsr.action-grammar/1` | `induce_action_grammar` |
| [`api_contract_mapper`](../prompts/api_contract_mapper.md) | `profile-proposal-only` | `high` | `reasoning` | `nmsr.api-contract/1` | `map_api`, `induce_profile` |
| [`database_schema_profiler`](../prompts/database_schema_profiler.md) | `profile-proposal-only` | `high` | `local-preferred-reasoning` | `nmsr.database-profile/1` | `profile_database`, `induce_profile` |
| [`invariant_synthesizer`](../prompts/invariant_synthesizer.md) | `proposal-only` | `high` | `reasoning` | `nmsr.invariant-set/1` | `induce_invariants` |
| [`network_protocol_profiler`](../prompts/network_protocol_profiler.md) | `profile-proposal-only` | `high` | `local-preferred-reasoning` | `nmsr.protocol-profile/1` | `profile_protocol`, `induce_profile` |
| [`profile_confidence_calibrator`](../prompts/profile_confidence_calibrator.md) | `advisory-only` | `high` | `reasoning` | `nmsr.confidence-calibration/1` | `calibrate_profile` |
| [`program_profile_resolver`](../prompts/program_profile_resolver.md) | `proposal-only` | `high` | `reasoning` | `nmsr.program-profile/1` | `induce_profile`, `resolve_profile` |
| [`state_migration_planner`](../prompts/state_migration_planner.md) | `proposal-only` | `high` | `reasoning` | `nmsr.state-migration/1` | `migrate_state_schema` |
| [`state_schema_inducer`](../prompts/state_schema_inducer.md) | `proposal-only` | `high` | `reasoning` | `nmsr.state-schema-proposal/1` | `induce_state_schema` |

## Propose

| Role | Authority | Risk | Runtime | Output schema | Tasks |
|---|---|---:|---|---|---|
| [`state_patch_proposer`](../prompts/state_patch_proposer.md) | `proposal-only` | `high` | `cloud-reasoning-or-local` | `nmsr.patch-proposal/1` | `state_transition`, `interact` |

## Remember

| Role | Authority | Risk | Runtime | Output schema | Tasks |
|---|---|---:|---|---|---|
| [`memory_curator`](../prompts/memory_curator.md) | `memory-proposal-only` | `medium` | `local-or-cloud-reasoning` | `nmsr.memory/1` | `remember` |
| [`memory_query_planner`](../prompts/memory_query_planner.md) | `retrieval-advisory` | `medium` | `local-preferred` | `nmsr.memory-query/1` | `query_memory`, `plan`, `repair_failure` |

## Render

| Role | Authority | Risk | Runtime | Output schema | Tasks |
|---|---|---:|---|---|---|
| [`camera_continuity_planner`](../prompts/camera_continuity_planner.md) | `render-plan-only` | `high` | `multimodal-reasoning` | `nmsr.camera-plan/1` | `plan_camera`, `keyframe` |
| [`image_edit_director`](../prompts/image_edit_director.md) | `candidate-pixel-instruction-only` | `high` | `image-director` | `nmsr.image-edit-instruction/1` | `image_edit`, `keyframe` |
| [`mask_region_planner`](../prompts/mask_region_planner.md) | `render-plan-only` | `high` | `multimodal-reasoning` | `nmsr.mask-plan/1` | `plan_mask`, `image_edit` |
| [`render_director`](../prompts/render_director.md) | `render-plan-only` | `high` | `reasoning` | `nmsr.render-plan/1` | `render`, `render_image` |

## Repair

| Role | Authority | Risk | Runtime | Output schema | Tasks |
|---|---|---:|---|---|---|
| [`failure_causal_repair`](../prompts/failure_causal_repair.md) | `proposal-only` | `high` | `reasoning` | `nmsr.repair-plan/1` | `repair_failure` |
| [`model_output_repair`](../prompts/model_output_repair.md) | `repair-proposal-only` | `high` | `reasoning` | `nmsr.output-repair/1` | `repair_model_output` |
| [`workflow_failure_repair`](../prompts/workflow_failure_repair.md) | `repair-plan-only` | `high` | `reasoning` | `nmsr.workflow-repair/1` | `repair_workflow` |

## Review

| Role | Authority | Risk | Runtime | Output schema | Tasks |
|---|---|---:|---|---|---|
| [`approval_packet_builder`](../prompts/approval_packet_builder.md) | `review-packet-only` | `high` | `reasoning` | `nmsr.approval-packet/1` | `build_approval_packet` |
| [`human_review_summarizer`](../prompts/human_review_summarizer.md) | `review-advisory` | `high` | `reasoning` | `nmsr.human-review/1` | `human_review` |

## Route

| Role | Authority | Risk | Runtime | Output schema | Tasks |
|---|---|---:|---|---|---|
| [`model_runtime_router`](../prompts/model_runtime_router.md) | `routing-advisory` | `high` | `local-deterministic` | `nmsr.model-route/1` | `route_model`, `render_prompt` |
| [`runtime_backend_router`](../prompts/runtime_backend_router.md) | `routing-advisory` | `high` | `reasoning` | `nmsr.runtime-route/1` | `route_runtime`, `simulate_os`, `discover_program` |
| [`workflow_context_mapper`](../prompts/workflow_context_mapper.md) | `context-mapping-advisory` | `high` | `reasoning` | `nmsr.workflow-context-map/1` | `execute_workflow`, `map_workflow_context` |

## Schedule

| Role | Authority | Risk | Runtime | Output schema | Tasks |
|---|---|---:|---|---|---|
| [`resource_budget_planner`](../prompts/resource_budget_planner.md) | `resource-advisory` | `medium` | `reasoning` | `nmsr.resource-plan/1` | `budget_resources`, `route_runtime` |
| [`temporal_scheduler`](../prompts/temporal_scheduler.md) | `schedule-advisory` | `medium` | `reasoning` | `nmsr.temporal-plan/1` | `schedule_plan`, `execute_goal` |

## Security

| Role | Authority | Risk | Runtime | Output schema | Tasks |
|---|---|---:|---|---|---|
| [`asset_provenance_reviewer`](../prompts/asset_provenance_reviewer.md) | `policy-advisory` | `critical` | `reasoning` | `nmsr.asset-review/1` | `review_assets`, `render_image`, `deployment_review` |
| [`capability_broker`](../prompts/capability_broker.md) | `capability-advisory` | `critical` | `reasoning` | `nmsr.capability-plan/1` | `broker_capabilities`, `capability_review` |
| [`privacy_redactor`](../prompts/privacy_redactor.md) | `security-advisory` | `critical` | `local-preferred` | `nmsr.privacy-review/1` | `privacy_review` |
| [`prompt_injection_detector`](../prompts/prompt_injection_detector.md) | `security-advisory` | `critical` | `local-reasoning` | `nmsr.injection-review/1` | `detect_prompt_injection` |
| [`rights_policy_guard`](../prompts/rights_policy_guard.md) | `policy-advisory` | `critical` | `reasoning` | `nmsr.rights-review/1` | `rights_review` |
| [`sandbox_policy_planner`](../prompts/sandbox_policy_planner.md) | `sandbox-advisory` | `critical` | `reasoning` | `nmsr.sandbox-plan/1` | `plan_sandbox`, `route_runtime` |
| [`threat_modeler`](../prompts/threat_modeler.md) | `security-advisory` | `critical` | `reasoning` | `nmsr.threat-model/1` | `threat_model`, `plan_sandbox`, `deployment_review` |
| [`tool_call_policy_reviewer`](../prompts/tool_call_policy_reviewer.md) | `tool-policy-advisory` | `critical` | `reasoning` | `nmsr.tool-policy-review/1` | `review_tool_call` |

## Verify

| Role | Authority | Risk | Runtime | Output schema | Tasks |
|---|---|---:|---|---|---|
| [`differential_runtime_verifier`](../prompts/differential_runtime_verifier.md) | `verification-advisory` | `high` | `reasoning` | `nmsr.differential-verification/1` | `differential_verify` |
| [`frame_verifier`](../prompts/frame_verifier.md) | `frame-verification-only` | `high` | `multimodal-verifier` | `nmsr.frame-verification/1` | `verify_frame` |
| [`profile_promotion_reviewer`](../prompts/profile_promotion_reviewer.md) | `promotion-advisory` | `high` | `reasoning` | `nmsr.promotion-review/1` | `promote_profile` |

# Workflows

## `operator_intent_to_plan` — Operator intent to bounded execution plan

```text
intent_interpreter -> memory_query_planner -> goal_decomposer -> capability_broker -> resource_budget_planner -> plan_synthesizer -> plan_critic -> temporal_scheduler -> action_compiler
```

Deterministic gates: `accepted_input_gate`, `rights_and_capability_gate`, `plan_schema_gate`, `execution_authorization`

## `interaction_commit` — Observed interaction to verified projection

```text
local_observer -> intent_interpreter -> memory_query_planner -> state_patch_proposer -> patch_critic -> render_director -> frame_verifier -> memory_curator
```

Deterministic gates: `interaction_validation`, `patch_validation`, `commit_reducer`, `frame_manifest_gate`

## `unknown_program_discovery` — Incremental unknown-program profile discovery

```text
unknown_app_discovery_observer -> accessibility_tree_observer -> safe_probe_planner -> state_schema_inducer -> action_grammar_inducer -> invariant_synthesizer -> api_contract_mapper -> database_schema_profiler -> network_protocol_profiler -> runtime_backend_router -> program_profile_resolver -> deterministic_test_generator -> differential_runtime_verifier -> profile_confidence_calibrator -> profile_promotion_reviewer
```

Deterministic gates: `safe_probe_policy`, `profile_schema_validation`, `sandbox_gate`, `differential_test_gate`, `promotion_governance`

## `operating_system_simulation` — Operating-system normalization and simulation

```text
os_runtime_observer -> process_runtime_observer -> filesystem_runtime_observer -> network_runtime_observer -> accessibility_tree_observer -> universal_ontology_mapper -> world_bootstrap_planner -> runtime_backend_router -> threat_modeler -> sandbox_policy_planner -> state_patch_proposer -> patch_critic -> render_director -> frame_verifier -> memory_curator
```

Deterministic gates: `guest_host_boundary`, `permission_gate`, `runtime_isolation`, `commit_reducer`

## `runtime_execution_orchestration` — Safe runtime routing and action execution

```text
rights_policy_guard -> threat_modeler -> runtime_backend_router -> resource_budget_planner -> capability_broker -> sandbox_policy_planner -> action_compiler -> temporal_scheduler -> plan_critic
```

Deterministic gates: `rights_gate`, `sandbox_creation`, `capability_grant`, `adapter_allowlist`, `execution_authorization`

## `counterfactual_experiment` — Branch-scoped counterfactual experiment

```text
counterfactual_branch_planner -> simulation_scenario_compiler -> state_patch_proposer -> patch_critic -> branch_comparison_analyst -> causal_graph_builder -> render_director -> frame_verifier -> memory_curator
```

Deterministic gates: `branch_create`, `branch_isolation`, `commit_reducer`, `comparison_gate`

## `semantic_branch_merge` — Evidence-preserving semantic branch merge

```text
branch_comparison_analyst -> semantic_merge_planner -> contradiction_resolver -> patch_critic -> rights_policy_guard -> privacy_redactor -> human_review_summarizer
```

Deterministic gates: `merge_conflict_gate`, `protected_path_gate`, `explicit_ref_update`

## `generated_visual_projection` — Bounded generated visual projection

```text
render_director -> asset_provenance_reviewer -> privacy_redactor -> rights_policy_guard -> visual_anchor_extractor -> mask_region_planner -> camera_continuity_planner -> image_edit_director -> frame_verifier -> memory_curator
```

Deterministic gates: `committed_state_required`, `mask_gate`, `protected_region_gate`, `verification_gate`, `frame_manifest_gate`

## `memory_learning_cycle` — Evidence-preserving memory retrieval and repair

```text
memory_query_planner -> contradiction_resolver -> causal_graph_builder -> failure_causal_repair -> memory_curator
```

Deterministic gates: `privacy_filter`, `branch_scope_gate`, `source_link_gate`, `memory_commit_gate`

## `replay_and_audit` — Immutable history replay and audit

```text
replay_integrity_verifier -> contradiction_resolver -> failure_causal_repair -> human_review_summarizer
```

Deterministic gates: `event_hash_gate`, `state_reconstruction`, `migration_gate`, `audit_signature`

## `world_and_scenario_bootstrap` — Program world and scenario initialization

```text
rights_policy_guard -> asset_provenance_reviewer -> program_profile_resolver -> world_bootstrap_planner -> simulation_scenario_compiler -> resource_budget_planner -> threat_modeler
```

Deterministic gates: `profile_validation`, `rights_gate`, `seed_commit`, `genesis_state_gate`

## `profile_promotion` — Profile verification and governed promotion

```text
deterministic_test_generator -> differential_runtime_verifier -> evaluation_reporter -> profile_confidence_calibrator -> profile_promotion_reviewer -> human_review_summarizer
```

Deterministic gates: `test_execution`, `coverage_threshold`, `version_scope_gate`, `registry_promotion`

## `security_and_privacy_review` — Security, privacy, rights and asset review

```text
privacy_redactor -> rights_policy_guard -> asset_provenance_reviewer -> threat_modeler -> capability_broker -> sandbox_policy_planner -> human_review_summarizer
```

Deterministic gates: `policy_engine`, `credential_boundary`, `operator_approval`

## `deployment_readiness` — Release and deployment readiness

```text
deterministic_test_generator -> evaluation_reporter -> threat_modeler -> rights_policy_guard -> asset_provenance_reviewer -> replay_integrity_verifier -> deployment_readiness_reviewer -> human_review_summarizer
```

Deterministic gates: `ci_gate`, `security_gate`, `migration_gate`, `rollback_gate`, `release_authorization`

## `prompt_execution_governance` — Governed provider prompt execution and review

```text
prompt_injection_detector -> data_minimization_reviewer -> cost_latency_estimator -> workflow_context_mapper -> prompt_run_critic -> approval_packet_builder -> model_output_repair -> workflow_failure_repair -> execution_trace_summarizer
```

Deterministic gates: `credential_gate`, `privacy_dispatch_gate`, `provider_boundary`, `local_schema_validation`, `human_review_gate`, `role_specific_deterministic_gate`
