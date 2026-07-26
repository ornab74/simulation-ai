extends Node
class_name SurfaceBridge

signal snapshot_changed(snapshot: Dictionary)
signal event_committed(event: Dictionary)
signal status_changed(status: String, detail: String)
signal memory_results(results: Array)
signal replay_completed(verification: Dictionary)
signal render_verified(result: Dictionary)
signal credential_changed(result: Dictionary)
signal prompt_catalog_changed(catalog: Dictionary)
signal prompt_details_changed(prompt: Dictionary)
signal prompt_validation_changed(validation: Dictionary)
signal prompt_run_completed(run: Dictionary)
signal prompt_runs_changed(runs: Array)
signal prompt_run_reviewed(run: Dictionary)
signal prompt_workflow_completed(workflow_run: Dictionary)
signal gemma_status_changed(result: Dictionary)

const ENDPOINT := "http://127.0.0.1:47890"
const TIMEOUT := 75.0

var status := "offline"
var detail := "Surface Core is not connected"
var snapshot: Dictionary = {}
var _request: HTTPRequest
var _poll_timer: Timer
var _busy := false
var _token := ""
var _core_autostarted := false

func _ready() -> void:
	_token = OS.get_environment("SIMULATION_AI_TOKEN")
	_request = HTTPRequest.new()
	_request.timeout = TIMEOUT
	add_child(_request)
	_poll_timer = Timer.new()
	_poll_timer.wait_time = 2.5
	_poll_timer.one_shot = false
	_poll_timer.timeout.connect(refresh_snapshot)
	add_child(_poll_timer)
	_boot_demo_snapshot()
	call_deferred("probe")

func probe() -> void:
	var response: Dictionary = await _api("GET", "/health", {})
	if bool(response.get("ok", false)):
		status = "online"
		detail = "Canonical Surface Core connected"
		_poll_timer.start()
		await refresh_snapshot()
	else:
		if not _core_autostarted:
			_core_autostarted = true
			_start_local_core()
			status = "starting"
			detail = "Starting the portable Surface Core runtime"
			await get_tree().create_timer(2.0).timeout
			await probe()
			return
		status = "demo"
		detail = "Running deterministic in-process preview"
	status_changed.emit(status, detail)
	_emit_snapshot()

func _start_local_core() -> void:
	var project_root := ProjectSettings.globalize_path("res://")
	var state_home := project_root.path_join(".simulation-ai")
	if not OS.has_feature("editor"):
		state_home = ProjectSettings.globalize_path("user://surface-core")
	var packaged_core := project_root.path_join("backend/simulation-ai-core")
	var python_path := project_root.path_join(".runtime/venv/bin/python")
	var bootstrap := project_root.path_join("scripts/bootstrap_runtime.py")
	var executable := "python3"
	var arguments := PackedStringArray([bootstrap, "--run-core"])
	if OS.get_name() == "Windows":
		packaged_core = project_root.path_join("backend/simulation-ai-core.exe")
		python_path = project_root.path_join(".runtime/venv/Scripts/python.exe")
		executable = "python.exe"
	if FileAccess.file_exists(packaged_core):
		executable = packaged_core
		arguments = PackedStringArray(["--host", "127.0.0.1", "--port", "47890", "--home", state_home])
	elif FileAccess.file_exists(python_path):
		executable = python_path
		arguments = PackedStringArray(["-m", "simulation_ai.server", "--host", "127.0.0.1", "--port", "47890", "--home", state_home])
	OS.create_process(executable, arguments, false)

func refresh_snapshot() -> Dictionary:
	if status != "online" or _busy:
		return {"ok": false, "error": "not_available"}
	var response: Dictionary = await _api("GET", "/v1/snapshot", {})
	if bool(response.get("ok", false)):
		snapshot = response.get("snapshot", snapshot)
		_emit_snapshot()
		return response
	status = "demo"
	detail = "Surface Core disconnected; preserving local preview"
	_poll_timer.stop()
	status_changed.emit(status, detail)
	_emit_snapshot()
	return response

func commit_interaction(packet: Dictionary) -> Dictionary:
	if status == "online":
		var response: Dictionary = await _api("POST", "/v1/interact", packet)
		if bool(response.get("ok", false)):
			event_committed.emit(response.get("event", {}))
			await refresh_snapshot()
			return response
		if str(response.get("error", "")) not in ["busy", "not_available"]:
			return response
	return _commit_demo(packet)

func create_branch(name: String) -> Dictionary:
	if status == "online":
		var response: Dictionary = await _api("POST", "/v1/branch/create", {"name": name})
		if bool(response.get("ok", false)):
			await refresh_snapshot()
			return response
		return response
	return _create_demo_branch(name)

func switch_branch(name: String) -> Dictionary:
	if status == "online":
		var response: Dictionary = await _api("POST", "/v1/branch/switch", {"name": name})
		if bool(response.get("ok", false)):
			await refresh_snapshot()
		return response
	for branch in snapshot.get("branches", []):
		if str(branch.get("name", "")) == name:
			var state: Dictionary = snapshot.get("state", {})
			state["branch"] = name
			state["state_hash"] = str(branch.get("state_hash", state.get("state_hash", "")))
			_emit_snapshot()
			return {"ok": true, "state": state}
	return {"ok": false, "error": "branch_not_found"}

func query_memory(query: String, object_ids: Array = []) -> Dictionary:
	if status == "online":
		var response: Dictionary = await _api("POST", "/v1/memory/query", {
			"query": query,
			"branch": snapshot.get("state", {}).get("branch", "main"),
			"object_ids": object_ids,
			"limit": 20,
		})
		var results: Array = response.get("results", [])
		memory_results.emit(results)
		return response
	var demo_results: Array = []
	for event in snapshot.get("events", []):
		if query.is_empty() or query.to_lower() in JSON.stringify(event).to_lower():
			demo_results.append({"score": 0.7, "record": {
				"memory_type": "episodic",
				"summary": "%s on %s" % [event.get("action", "event"), event.get("target_id", "surface")],
				"branch_scope": event.get("branch", "main"),
				"confidence": 0.8,
				"object_ids": [event.get("target_id", "")],
			}})
	memory_results.emit(demo_results)
	return {"ok": true, "results": demo_results}

func verify_replay() -> Dictionary:
	if status == "online":
		var response: Dictionary = await _api("POST", "/v1/replay", {})
		var verification: Dictionary = response.get("verification", {})
		replay_completed.emit(verification)
		return response
	var demo: Dictionary = snapshot.get("replay", {"verified": true, "problems": []})
	replay_completed.emit(demo)
	return {"ok": true, "verification": demo}

func verify_render(job_id: String, decision := "pass") -> Dictionary:
	var verification := {
		"decision": decision,
		"scores": {
			"semantic_fidelity": 0.97,
			"temporal_continuity": 0.95,
			"identity_stability": 0.98,
			"protected_region_stability": 0.99,
			"ui_usability": 1.0,
		},
	}
	if status == "online":
		var response: Dictionary = await _api("POST", "/v1/render/verify", {"job_id": job_id, "verification": verification})
		if bool(response.get("ok", false)):
			render_verified.emit(response)
			await refresh_snapshot()
		return response
	for job in snapshot.get("render_jobs", []):
		if str(job.get("job_id", "")) == job_id:
			job["status"] = "verified" if decision == "pass" else "fallback"
			job["verification"] = verification
			_emit_snapshot()
			var response := {"ok": true, "job": job}
			render_verified.emit(response)
			return response
	return {"ok": false, "error": "render_job_not_found"}

func get_openai_credential_status() -> Dictionary:
	if status == "online":
		var response: Dictionary = await _api("GET", "/v1/credentials/openai", {})
		if bool(response.get("ok", false)):
			credential_changed.emit(response)
		return response
	var credential: Dictionary = snapshot.get("credentials", {}).get("openai", {
		"configured": false, "unlocked": false, "env_available": false,
		"source": "none", "fingerprint": "", "secret_exposed": false,
	})
	var response := {"ok": true, "credential": credential, "demo": true}
	credential_changed.emit(response)
	return response

func save_openai_credential(api_key: String, password: String) -> Dictionary:
	return await _credential_action("/v1/credentials/openai/save", {"api_key": api_key, "password": password})

func import_openai_environment(password: String) -> Dictionary:
	return await _credential_action("/v1/credentials/openai/import-env", {"password": password})

func unlock_openai_credential(password: String) -> Dictionary:
	return await _credential_action("/v1/credentials/openai/unlock", {"password": password})

func lock_openai_credential() -> Dictionary:
	return await _credential_action("/v1/credentials/openai/lock", {})

func clear_openai_credential(password: String) -> Dictionary:
	return await _credential_action("/v1/credentials/openai/clear", {"password": password})

func test_openai_credential() -> Dictionary:
	return await _credential_action("/v1/credentials/openai/test", {})

func _credential_action(path: String, payload: Dictionary) -> Dictionary:
	if status != "online":
		var unavailable := {"ok": false, "error": "surface_core_offline", "detail": "Credential operations require the local Surface Core."}
		credential_changed.emit(unavailable)
		return unavailable
	var response: Dictionary = await _api("POST", path, payload)
	if bool(response.get("ok", false)):
		await refresh_snapshot()
	credential_changed.emit(response)
	return response

func get_prompt_catalog() -> Dictionary:
	if status == "online":
		var response: Dictionary = await _api("GET", "/v1/prompts", {})
		if bool(response.get("ok", false)):
			var catalog: Dictionary = response.get("catalog", {})
			prompt_catalog_changed.emit(catalog)
		return response
	var catalog := _demo_prompt_catalog()
	prompt_catalog_changed.emit(catalog)
	return {"ok": true, "catalog": catalog, "demo": true}

func get_prompt_details(prompt_id: String) -> Dictionary:
	if status == "online":
		var response: Dictionary = await _api("GET", "/v1/prompts/%s" % prompt_id.uri_encode(), {})
		if bool(response.get("ok", false)):
			prompt_details_changed.emit(response.get("prompt", {}))
		return response
	var catalog := _demo_prompt_catalog()
	for prompt in catalog.get("prompts", []):
		if str(prompt.get("id", "")) == prompt_id:
			var detail: Dictionary = prompt.duplicate(true)
			detail["content"] = "Offline preview. Connect the Surface Core to inspect the complete versioned prompt text."
			prompt_details_changed.emit(detail)
			return {"ok": true, "prompt": detail, "demo": true}
	return {"ok": false, "error": "prompt_not_found"}

func validate_prompt_pack() -> Dictionary:
	if status == "online":
		var response: Dictionary = await _api("POST", "/v1/prompts/validate", {})
		if bool(response.get("ok", false)):
			prompt_validation_changed.emit(response.get("validation", {}))
		return response
	var validation := {"valid": true, "prompt_count": 72, "workflow_count": 15, "pack_version": "3.0.0", "problems": [], "demo": true}
	prompt_validation_changed.emit(validation)
	return {"ok": true, "validation": validation, "demo": true}

func validate_prompt_output(prompt_id: String, output: Dictionary) -> Dictionary:
	if status == "online":
		return await _api("POST", "/v1/prompts/validate-output", {"prompt_id": prompt_id, "output": output})
	return {
		"ok": true,
		"validation": {
			"schema": "nmsr.prompt-output-validation/1",
			"prompt_id": prompt_id,
			"valid": false,
			"findings": [{"path": "$", "message": "Connect the Surface Core for strict JSON Schema validation.", "validator": "offline"}],
			"deterministic_gate_required": true,
			"commit_authority": false,
		},
		"demo": true,
	}

func execute_prompt(prompt_id: String, inputs: Dictionary, model := "", reasoning_effort := "medium", max_output_tokens := 4096) -> Dictionary:
	if status != "online":
		var offline := {"ok": false, "error": "surface_core_offline", "detail": "Live prompt execution requires the local Surface Core and an unlocked credential."}
		prompt_run_completed.emit(offline)
		return offline
	var payload := {
		"prompt_id": prompt_id,
		"inputs": inputs,
		"reasoning_effort": reasoning_effort,
		"max_output_tokens": max_output_tokens,
	}
	if not model.strip_edges().is_empty():
		payload["model"] = model.strip_edges()
	var response: Dictionary = await _api("POST", "/v1/prompts/execute", payload)
	prompt_run_completed.emit(response.get("run", response))
	if bool(response.get("ok", false)):
		await get_prompt_runs()
	return response

func get_prompt_runs(limit := 50) -> Dictionary:
	if status != "online":
		prompt_runs_changed.emit([])
		return {"ok": true, "runs": [], "demo": true}
	var response: Dictionary = await _api("GET", "/v1/prompt-runs?limit=%s" % clampi(limit, 1, 200), {})
	if bool(response.get("ok", false)):
		prompt_runs_changed.emit(response.get("runs", []))
	return response

func review_prompt_run(run_id: String, decision: String, note := "") -> Dictionary:
	if status != "online":
		return {"ok": false, "error": "surface_core_offline"}
	var response: Dictionary = await _api("POST", "/v1/prompt-runs/review", {
		"run_id": run_id, "decision": decision, "note": note, "reviewed_by": "operator"
	})
	if bool(response.get("ok", false)):
		prompt_run_reviewed.emit(response.get("run", {}))
		await get_prompt_runs()
	return response

func execute_prompt_workflow(workflow_id: String, step_inputs: Dictionary, model := "", reasoning_effort := "medium", max_steps := 0) -> Dictionary:
	if status != "online":
		return {"ok": false, "error": "surface_core_offline"}
	var payload := {
		"workflow_id": workflow_id, "step_inputs": step_inputs,
		"reasoning_effort": reasoning_effort, "stop_on_invalid": true,
	}
	if not model.strip_edges().is_empty():
		payload["model"] = model.strip_edges()
	if max_steps > 0:
		payload["max_steps"] = max_steps
	var response: Dictionary = await _api("POST", "/v1/prompt-workflows/execute", payload)
	if bool(response.get("ok", false)):
		prompt_workflow_completed.emit(response.get("workflow_run", {}))
	return response

func route_prompt_workflow(task_type: String) -> Dictionary:
	if status == "online":
		return await _api("POST", "/v1/prompts/route", {"task_type": task_type})
	return {"ok": true, "route": {"task_type": task_type, "workflows": _demo_prompt_catalog().get("workflows", []), "direct_prompts": []}, "demo": true}

func get_snapshot() -> Dictionary:
	return snapshot.duplicate(true)

func get_gemma_status() -> Dictionary:
	if status != "online":
		return {"ok": false, "error": "surface_core_offline"}
	var response: Dictionary = {}
	for _attempt in range(20):
		response = await _api("GET", "/v1/models/gemma/status", {})
		if str(response.get("error", "")) != "busy":
			gemma_status_changed.emit(response)
			return response
		await get_tree().create_timer(0.15).timeout
	response = {"ok": false, "error": "surface_core_busy", "detail": "Surface Core did not become available during model startup."}
	gemma_status_changed.emit(response)
	return response

func download_gemma() -> Dictionary:
	if status != "online":
		return {"ok": false, "error": "surface_core_offline"}
	var response := await _api("POST", "/v1/models/gemma/download", {})
	gemma_status_changed.emit(response)
	return response

func generate_boot_image(prompt := "") -> Dictionary:
	if status != "online":
		return {"ok": false, "error": "surface_core_offline"}
	var payload := {}
	if not prompt.is_empty():
		payload["prompt"] = prompt
	return await _api("POST", "/v1/render/generate-boot", payload)

func describe_click(position: Vector2, double_click: bool, button := "left") -> Dictionary:
	if status != "online":
		return {"ok": false, "error": "surface_core_offline"}
	return await _api("POST", "/v1/vision/describe-click", {"x": position.x, "y": position.y, "double_click": double_click, "button": button})

func generate_click_frame(prompt: String) -> Dictionary:
	if status != "online":
		return {"ok": false, "error": "surface_core_offline"}
	return await _api("POST", "/v1/render/generate-boot", {"prompt": prompt, "edit_previous": true})

func list_screen_images() -> Dictionary:
	if status != "online":
		return {"ok": false, "error": "surface_core_offline"}
	return await _api("GET", "/v1/artifacts/images", {})

func load_latest_screen() -> Dictionary:
	if status != "online":
		return {"ok": false, "error": "surface_core_offline"}
	return await _api("GET", "/v1/artifacts/images/latest", {})

func reset_desktop_screen() -> Dictionary:
	if status != "online":
		return {"ok": false, "error": "surface_core_offline"}
	return await _api("POST", "/v1/render/reset-desktop", {})

func _api(method: String, path: String, payload: Dictionary) -> Dictionary:
	# HTTPRequest is intentionally shared, but startup polling and boot checks
	# can arrive together. Queue briefly instead of exposing a transient busy
	# state to the UI.
	for _attempt in range(40):
		if not _busy:
			break
		await get_tree().create_timer(0.1).timeout
	if _busy:
		return {"ok": false, "error": "busy", "detail": "Surface Core request queue timed out."}
	_busy = true
	var headers := PackedStringArray(["Content-Type: application/json"])
	if not _token.is_empty():
		headers.append("Authorization: Bearer %s" % _token)
	var http_method := HTTPClient.METHOD_GET if method == "GET" else HTTPClient.METHOD_POST
	var body := "" if method == "GET" else JSON.stringify(payload)
	var err := _request.request(ENDPOINT + path, headers, http_method, body)
	if err != OK:
		_busy = false
		return {"ok": false, "error": "transport", "detail": error_string(err)}
	var result: Array = await _request.request_completed
	_busy = false
	if result.size() < 4:
		return {"ok": false, "error": "transport_result"}
	var status_code := int(result[1])
	var parsed: Variant = JSON.parse_string(result[3].get_string_from_utf8())
	if parsed is not Dictionary:
		return {"ok": false, "error": "json"}
	if status_code < 200 or status_code >= 300:
		return parsed
	return parsed

func _demo_prompt_catalog() -> Dictionary:
	var prompts: Array = [
		{"id":"intent_interpreter","title":"Operator Intent Interpreter","stage":"interpret","authority":"intent-advisory","version":"1.0.0","risk_level":"medium","latency_class":"interactive","preferred_model_class":"local-or-cloud-reasoning","modalities":["text","structured-data"],"tags":["interpret","interact"],"deterministic_gate_required":true,"output_schema":"nmsr.intent/1","required_inputs":["interaction_packet","current_state"],"optional_inputs":["conversation_context","selected_objects","active_goals","retrieved_memory"],"description":"Separates literal interaction from inferred semantic intent.","callable":true},
		{"id":"local_observer","title":"Local Multimodal Surface Observer","stage":"observe","authority":"observation-only","version":"2.0.0","risk_level":"medium","latency_class":"interactive","preferred_model_class":"local-multimodal","modalities":["text","structured-data","image"],"tags":["observe","interact"],"deterministic_gate_required":true,"output_schema":"nmsr.observation/1","required_inputs":["interaction_packet","current_state"],"optional_inputs":["before_frame","after_frame","ui_tree","retrieved_memory"],"description":"Turns telemetry and visual evidence into an observation report.","callable":true},
		{"id":"plan_synthesizer","title":"Bounded Plan Synthesizer","stage":"plan","authority":"proposal-only","version":"1.0.0","risk_level":"high","latency_class":"deliberate","preferred_model_class":"reasoning","modalities":["text","structured-data"],"tags":["plan","execute_goal"],"deterministic_gate_required":true,"output_schema":"nmsr.execution-plan/1","required_inputs":["current_state","goal_plan","program_profile"],"optional_inputs":["retrieved_memory","capability_plan","resource_plan","temporal_plan"],"description":"Produces an auditable, bounded semantic action plan.","callable":true},
		{"id":"state_patch_proposer","title":"Minimal State Patch Proposer","stage":"propose","authority":"proposal-only","version":"2.0.0","risk_level":"high","latency_class":"deliberate","preferred_model_class":"cloud-reasoning-or-local","modalities":["text","structured-data"],"tags":["propose","interact"],"deterministic_gate_required":true,"output_schema":"nmsr.patch-proposal/1","required_inputs":["current_state","observation","operator_intent"],"optional_inputs":["retrieved_memory","active_goals","program_profile"],"description":"Proposes a minimal evidence-linked patch without commit authority.","callable":true},
		{"id":"runtime_backend_router","title":"Runtime Backend Router","stage":"route","authority":"routing-advisory","version":"1.0.0","risk_level":"high","latency_class":"interactive","preferred_model_class":"reasoning","modalities":["text","structured-data"],"tags":["route","simulate_os"],"deterministic_gate_required":true,"output_schema":"nmsr.runtime-route/1","required_inputs":["target_descriptor","requested_fidelity","host_capabilities"],"optional_inputs":["rights_policy","security_policy","available_backends"],"description":"Routes a target to a semantic twin, container, VM, emulator, or remote runtime.","callable":true},
		{"id":"threat_modeler","title":"Simulation Threat Modeler","stage":"security","authority":"security-advisory","version":"1.0.0","risk_level":"critical","latency_class":"interactive","preferred_model_class":"reasoning","modalities":["text","structured-data"],"tags":["security","threat_model"],"deterministic_gate_required":true,"output_schema":"nmsr.threat-model/1","required_inputs":["system_scope","data_flows"],"optional_inputs":["runtime_routes","capabilities","credential_status","deployment_target"],"description":"Builds the trust-boundary and attack-surface review.","callable":true},
		{"id":"frame_verifier","title":"Candidate Frame Verifier","stage":"verify","authority":"frame-verification-only","version":"2.0.0","risk_level":"high","latency_class":"deliberate","preferred_model_class":"multimodal-verifier","modalities":["text","structured-data","image"],"tags":["verify","verify_frame"],"deterministic_gate_required":true,"output_schema":"nmsr.frame-verification/1","required_inputs":["committed_state_delta","render_plan","candidate_frame","previous_frame_manifest"],"optional_inputs":["object_anchors","mask_manifest","privacy_manifest"],"description":"Verifies candidate pixels without granting semantic authority.","callable":true},
		{"id":"deployment_readiness_reviewer","title":"Deployment Readiness Reviewer","stage":"deploy","authority":"deployment-advisory","version":"1.0.0","risk_level":"critical","latency_class":"background","preferred_model_class":"reasoning","modalities":["text","structured-data"],"tags":["deploy","deployment_review"],"deterministic_gate_required":true,"output_schema":"nmsr.deployment-review/1","required_inputs":["release_candidate","deployment_policy"],"optional_inputs":["test_report","threat_model","rights_review","rollback_plan","observability_plan"],"description":"Reviews evidence before release authorization.","callable":true},
	]
	return {
		"schema":"nmsr.prompt-catalog/1", "pack_id":"simulation-ai-universal-runtime", "pack_version":"3.0.0",
		"prompt_count":72, "callable_prompt_count":68, "openai_strict_prompt_count":10, "workflow_count":15, "valid":true, "pack_sha256":"offline-preview-v3",
		"prompts":prompts,
		"workflows":[
			{"id":"operator_intent_to_plan","title":"Operator intent to bounded execution plan","prompts":["intent_interpreter","memory_query_planner","goal_decomposer","capability_broker","plan_synthesizer","plan_critic","action_compiler"],"deterministic_gates":["accepted_input_gate","execution_authorization"]},
			{"id":"interaction_commit","title":"Observed interaction to verified projection","prompts":["local_observer","intent_interpreter","state_patch_proposer","patch_critic","render_director","frame_verifier","memory_curator"],"deterministic_gates":["interaction_validation","patch_validation","commit_reducer","frame_manifest_gate"]},
			{"id":"unknown_program_discovery","title":"Incremental unknown-program profile discovery","prompts":["unknown_app_discovery_observer","safe_probe_planner","state_schema_inducer","action_grammar_inducer","invariant_synthesizer","program_profile_resolver","profile_promotion_reviewer"],"deterministic_gates":["safe_probe_policy","promotion_governance"]},
			{"id":"operating_system_simulation","title":"Operating-system normalization and simulation","prompts":["os_runtime_observer","process_runtime_observer","filesystem_runtime_observer","network_runtime_observer","runtime_backend_router","sandbox_policy_planner"],"deterministic_gates":["guest_host_boundary","runtime_isolation","commit_reducer"]},
			{"id":"generated_visual_projection","title":"Bounded generated visual projection","prompts":["render_director","visual_anchor_extractor","mask_region_planner","camera_continuity_planner","image_edit_director","frame_verifier"],"deterministic_gates":["mask_gate","protected_region_gate","frame_manifest_gate"]},
			{"id":"deployment_readiness","title":"Release and deployment readiness","prompts":["deterministic_test_generator","evaluation_reporter","threat_modeler","replay_integrity_verifier","deployment_readiness_reviewer"],"deterministic_gates":["ci_gate","security_gate","release_authorization"]},
		]
	}

func _boot_demo_snapshot() -> void:
	var objects := {
		"node.observer": {"type":"model", "label":"Local Observer", "status":"ready", "epistemic_class":"observed", "layout":[0.20,0.35], "properties":{"authority":"proposal-only"}},
		"node.planner": {"type":"planner", "label":"Patch Planner", "status":"ready", "epistemic_class":"inferred", "layout":[0.42,0.20], "properties":{"authority":"proposal-only"}},
		"node.surface": {"type":"world", "label":"World Surface", "status":"active", "epistemic_class":"observed", "layout":[0.48,0.46], "properties":{"authority":"deterministic-core"}},
		"node.memory": {"type":"store", "label":"Memoric Store", "status":"indexed", "epistemic_class":"observed", "layout":[0.76,0.34], "properties":{"branch_aware":true}},
		"node.renderer": {"type":"render", "label":"Render Queue", "status":"verified", "epistemic_class":"observed", "layout":[0.66,0.70], "properties":{"image_state_authoritative":false}},
		"node.verifier": {"type":"verifier", "label":"Frame Verifier", "status":"watching", "epistemic_class":"observed", "layout":[0.34,0.74], "properties":{"anchor_checks":true}},
	}
	snapshot = {
		"schema": "nmsr.snapshot/1",
		"state": {
			"schema_version": "nmsr.surface-state/2",
			"map_id": "simulation-ai-demo",
			"target": "semantic-topology",
			"profile": "world-surface-studio",
			"mode": "hybrid",
			"seed": 42,
			"logical_time": 0,
			"branch": "main",
			"parent_state_hash": "",
			"state_hash": "demo_genesis",
			"entropy_bits": 0.72,
			"coherence": 0.94,
			"selected_object_id": "node.surface",
			"active_focus_id": "surface.viewport",
			"objects": objects,
			"ui": {
				"simulation_running": true,
				"last_command": "",
				"inputs": {},
				"topology_links": [
					["node.observer","node.surface","observe"], ["node.surface","node.planner","state"],
					["node.planner","node.surface","propose"], ["node.surface","node.memory","remember"],
					["node.surface","node.renderer","render"], ["node.renderer","node.verifier","verify"],
					["node.verifier","node.surface","present"], ["node.memory","node.planner","retrieve"],
				],
				"privacy": {"cloud_allowed": false, "frame_retention":"bounded", "redact_sensitive_inputs":true},
				"render_policy": "native-first",
				"reduced_motion": false,
			},
			"goals": [], "plans": [], "hypotheses": [], "claims": [],
			"layer_state": {"events":{"last_action":{}}, "meta_model":{"failures":0,"contradictions":0}},
			"render": {"status":"verified", "requested_mode":"native_ui", "committed_frame_id":"frame_genesis", "pending_job_id":""},
			"provenance": {"generated_content_disclosure":true, "authority":"deterministic-core", "pixel_state_authoritative":false},
		},
		"events": [],
		"branches": [{"name":"main", "state_hash":"demo_genesis", "logical_time":0, "active":true, "parent_state_hash":""}],
		"render_jobs": [],
		"frames": [{"frame_id":"frame_genesis", "status":"verified", "render_mode":"native_ui"}],
		"counts": {"states":1, "events":0, "evidence":0, "proposals":0, "memories":0, "render_jobs":0, "frames":1},
		"credentials": {"openai": {"provider":"openai", "configured":false, "unlocked":false, "env_available":false, "source":"none", "fingerprint":"", "created_at":"", "secret_exposed":false}},
		"adapters": [
			{"id":"local-observer","label":"Gemma 4 E2B Observer","status":"fallback-ready","runtime":"deterministic-observer-v1","authority":"observation only","local":true},
			{"id":"state-planner","label":"GPT-5.6 Patch Planner","status":"credential-required","runtime":"rule-patch-proposer-v2 / none","authority":"proposal only","local":false},
			{"id":"image-worker","label":"OpenAI Image Edit Worker","status":"credential-required","runtime":"openai-image-edit-adapter / none","authority":"candidate pixels only","local":false},
			{"id":"surface-core","label":"Deterministic Surface Core","status":"online","runtime":"python-standard-library","authority":"canonical commit","local":true},
		],
		"replay": {"verified":true, "event_count":0, "state_count":1, "head":"demo_genesis", "problems":[]},
	}
	_emit_snapshot()

func _commit_demo(packet: Dictionary) -> Dictionary:
	var state: Dictionary = snapshot.get("state", {})
	var target_id := str(packet.get("target", {}).get("node_id", "surface.unknown"))
	var action: Dictionary = packet.get("action", {})
	var kind := str(action.get("kind", "unknown"))
	var parent := str(state.get("state_hash", "demo_genesis"))
	state["parent_state_hash"] = parent
	state["logical_time"] = int(state.get("logical_time", 0)) + 1
	if target_id in state.get("objects", {}):
		state["selected_object_id"] = target_id
		state["objects"][target_id]["status"] = "selected"
	state["active_focus_id"] = target_id
	if kind == "command":
		var command := str(action.get("name", ""))
		if command == "toggle_run": state["ui"]["simulation_running"] = not bool(state["ui"].get("simulation_running", true))
		elif command == "pause": state["ui"]["simulation_running"] = false
		elif command == "resume": state["ui"]["simulation_running"] = true
		elif command.begins_with("render:keyframe"):
			state["render"]["status"] = "queued"
			state["render"]["requested_mode"] = "new_keyframe"
			var job := {"job_id":"demo_render_%d" % state.logical_time, "event_id":packet.get("event_id",""), "state_hash":"pending", "branch":state.branch, "mode":"new_keyframe", "status":"queued", "affected_object_ids":["node.surface"], "semantic_changes":[command], "prompt":"Generate the next verified world keyframe."}
			snapshot["render_jobs"].push_front(job)
	state["state_hash"] = "demo_%06d_%s" % [state.logical_time, target_id.replace(".", "_")]
	var event := {
		"index": snapshot.get("events", []).size() + 1,
		"event_id": packet.get("event_id", "demo"),
		"action": kind,
		"arguments": action,
		"target_id": target_id,
		"logical_time": state.logical_time,
		"branch": state.branch,
		"parent_state_hash": parent,
		"resulting_state_hash": state.state_hash,
		"epistemic_class": "observed",
		"status": "committed",
	}
	snapshot["events"].push_front(event)
	snapshot["counts"]["events"] = snapshot["events"].size()
	snapshot["counts"]["states"] = int(snapshot["counts"].get("states", 1)) + 1
	event_committed.emit(event)
	_emit_snapshot()
	return {"ok": true, "state": state, "event": event, "mode": "demo"}

func _create_demo_branch(name: String) -> Dictionary:
	var clean := name.to_lower().strip_edges().replace(" ", "-")
	if clean.is_empty(): clean = "branch-%d" % int(Time.get_unix_time_from_system())
	for branch in snapshot.get("branches", []): branch["active"] = false
	var state: Dictionary = snapshot.get("state", {})
	state["branch"] = clean
	state["logical_time"] = int(state.get("logical_time", 0)) + 1
	state["state_hash"] = "demo_branch_%s_%d" % [clean, state.logical_time]
	snapshot["branches"].push_front({"name":clean, "state_hash":state.state_hash, "logical_time":state.logical_time, "active":true, "parent_state_hash":state.parent_state_hash})
	_emit_snapshot()
	return {"ok": true, "state": state, "branches": snapshot.branches}

func _emit_snapshot() -> void:
	snapshot_changed.emit(get_snapshot())
