extends Node
class_name InteractionCapture

signal packet_ready(packet: Dictionary)

var logical_time := 0
var branch := "main"
var parent_state_hash := "genesis"
var session_id := ""
var cloud_allowed := false
var _sequence := 0
var _pending_text := ""
var _pending_character_count := 0
var _pending_control := ""
var _pending_sensitive := false
var _typing_timer: Timer

func _ready() -> void:
	session_id = "session_%s" % str(Time.get_unix_time_from_system()).replace(".", "_")
	_typing_timer = Timer.new()
	_typing_timer.one_shot = true
	_typing_timer.wait_time = 0.65
	_typing_timer.timeout.connect(_flush_typing)
	add_child(_typing_timer)

func sync_authority(snapshot: Dictionary) -> void:
	var state: Dictionary = snapshot.get("state", {})
	if state.is_empty():
		return
	logical_time = int(state.get("logical_time", logical_time))
	branch = str(state.get("branch", branch))
	parent_state_hash = str(state.get("state_hash", parent_state_hash))
	var privacy: Dictionary = state.get("ui", {}).get("privacy", {})
	cloud_allowed = bool(privacy.get("cloud_allowed", cloud_allowed))

func capture_click(target_id: String, label: String, position: Vector2, double_click := false, button := "left") -> void:
	_flush_typing()
	_emit_packet({
		"kind": "double_click" if double_click else "click",
		"pointer": {
			"x": roundi(position.x),
			"y": roundi(position.y),
			"button": button,
			"click_count": 2 if double_click else 1,
		},
		"text": null,
	}, {
		"node_id": target_id,
		"accessible_label": label,
		"sensitive": false,
	})

func capture_focus(target_id: String, label: String) -> void:
	_flush_typing()
	_emit_packet({"kind": "focus"}, {
		"node_id": target_id,
		"accessible_label": label,
		"sensitive": false,
	})

func capture_drag(target_id: String, label: String, from: Vector2, to: Vector2) -> void:
	_flush_typing()
	_emit_packet({
		"kind": "drag",
		"drag": {
			"from": {"x": roundi(from.x), "y": roundi(from.y)},
			"to": {"x": roundi(to.x), "y": roundi(to.y)},
		},
	}, {
		"node_id": target_id,
		"accessible_label": label,
		"sensitive": false,
	})

func capture_scroll(target_id: String, delta: float, position: Vector2) -> void:
	_flush_typing()
	_emit_packet({
		"kind": "scroll",
		"scroll": {"delta": delta, "x": roundi(position.x), "y": roundi(position.y)},
	}, {
		"node_id": target_id,
		"accessible_label": "Scrollable surface",
		"sensitive": false,
	})

func capture_command(command: String) -> void:
	_flush_typing()
	_emit_packet({"kind": "command", "name": command}, {
		"node_id": "surface.command",
		"accessible_label": command,
		"sensitive": false,
	})

func capture_text(control_id: String, delta: String, sensitive := false) -> void:
	if _pending_control != control_id or _pending_sensitive != sensitive:
		_flush_typing()
	_pending_control = control_id
	_pending_sensitive = sensitive
	_pending_character_count += delta.length()
	if not sensitive:
		_pending_text += delta
	_typing_timer.start()

func flush() -> void:
	_flush_typing()

func _flush_typing() -> void:
	if _pending_character_count <= 0:
		return
	var action := {
		"kind": "type",
		"text": null if _pending_sensitive else _pending_text,
		"typed_character_count": _pending_character_count,
	}
	_emit_packet(action, {
		"node_id": _pending_control,
		"accessible_label": "Sensitive text input" if _pending_sensitive else "Text input",
		"sensitive": _pending_sensitive,
	})
	_pending_text = ""
	_pending_character_count = 0
	_pending_control = ""
	_pending_sensitive = false

func _emit_packet(action: Dictionary, target: Dictionary) -> void:
	_sequence += 1
	var packet := {
		"schema": "nmsr.interaction/1",
		"event_id": "%s_%06d" % [session_id, _sequence],
		"session_id": session_id,
		"branch": branch,
		"logical_time": logical_time + 1,
		"parent_state_hash": parent_state_hash,
		"monotonic_timestamp_ns": Time.get_ticks_usec() * 1000,
		"source": "godot",
		"action": action,
		"target": target,
		"ui_tree_hash": "pending",
		"scene_graph_hash": "pending",
		"before_frame_id": "",
		"after_native_frame_id": "",
		"privacy": {
			"cloud_allowed": cloud_allowed,
			"frame_retention": "bounded",
			"redactions": ["sensitive-input"] if bool(target.get("sensitive", false)) else [],
		},
	}
	packet_ready.emit(packet)
