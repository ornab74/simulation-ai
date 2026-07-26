extends Control
class_name WorldSurfaceCanvas

signal object_activated(object_id: String, screen_position: Vector2, double_click: bool)
signal desktop_pointer(button: String, screen_position: Vector2, double_click: bool)
signal canvas_command(command: String)
signal viewport_changed(zoom: float)

const ThemeFactory = preload("res://ui/theme_factory.gd")

var objects: Array[Dictionary] = []
var links: Array = []
var selected_object_id := ""
var hovered_object_id := ""
var pulse := 0.0
var simulation_running := true
var grid_step := 40.0
var zoom := 1.0
var pan := Vector2.ZERO
var _panning := false
var _pan_origin := Vector2.ZERO
var _drag_origin := Vector2.ZERO
var click_markers: Array[Dictionary] = []
var desktop_texture: Texture2D

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	focus_mode = Control.FOCUS_ALL
	set_process(true)
	queue_redraw()

func set_state(state: Dictionary) -> void:
	objects.clear()
	var source: Dictionary = state.get("objects", {})
	for object_id in source:
		var value: Dictionary = source[object_id]
		var layout: Array = value.get("layout", [0.5, 0.5])
		objects.append({
			"id": str(object_id),
			"label": str(value.get("label", object_id)),
			"position": Vector2(float(layout[0]), float(layout[1])) if layout.size() >= 2 else Vector2(0.5, 0.5),
			"radius": _radius_for_kind(str(value.get("type", "entity"))),
			"kind": str(value.get("type", "entity")),
			"status": str(value.get("status", "unknown")),
			"epistemic_class": str(value.get("epistemic_class", "unknown")),
		})
	links = state.get("ui", {}).get("topology_links", [])
	selected_object_id = str(state.get("selected_object_id", selected_object_id))
	simulation_running = bool(state.get("ui", {}).get("simulation_running", true))
	queue_redraw()

func set_selected(object_id: String) -> void:
	selected_object_id = object_id
	queue_redraw()

func set_running(value: bool) -> void:
	simulation_running = value
	queue_redraw()

func set_desktop_texture(texture: Texture2D) -> void:
	desktop_texture = texture
	queue_redraw()

func paint_click(position: Vector2, double_click: bool, annotation := "") -> void:
	click_markers.append({"position": position, "double_click": double_click, "annotation": annotation if not annotation.is_empty() else ("USER DOUBLE-CLICKED HERE" if double_click else "USER CLICKED HERE"), "age": 0.0})
	if click_markers.size() > 12:
		click_markers.pop_front()
	queue_redraw()

func reset_view() -> void:
	zoom = 1.0
	pan = Vector2.ZERO
	viewport_changed.emit(zoom)
	queue_redraw()

func _process(delta: float) -> void:
	if simulation_running:
		pulse = fmod(pulse + delta * 0.42, 1.0)
	for marker in click_markers:
		marker.age = minf(float(marker.age) + delta, 2.0)
		queue_redraw()

func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		if _panning:
			pan = event.position - _pan_origin + _drag_origin
			queue_redraw()
		else:
			hovered_object_id = _hit_test(event.position)
			queue_redraw()
	elif event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_MIDDLE:
			if event.pressed:
				_panning = true
				_pan_origin = event.position
				_drag_origin = pan
			else:
				_panning = false
			accept_event()
		elif event.button_index == MOUSE_BUTTON_WHEEL_UP and event.pressed:
			_zoom_at(event.position, 1.1)
			accept_event()
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN and event.pressed:
			_zoom_at(event.position, 0.9)
			accept_event()
		elif event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
			grab_focus()
			var hit := _hit_test(event.position)
			if hit.is_empty():
				hit = "surface.desktop"
			selected_object_id = hit
			paint_click(event.position, event.double_click)
			if desktop_texture != null:
				desktop_pointer.emit("left", _desktop_source_point(event.position), event.double_click)
			else:
				object_activated.emit(hit, event.position, event.double_click)
			queue_redraw()
		elif event.button_index == MOUSE_BUTTON_RIGHT and event.pressed:
			paint_click(event.position, false, "USER RIGHT-CLICKED HERE")
			desktop_pointer.emit("right", event.position, event.double_click)
			queue_redraw()
	elif event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_SPACE:
			canvas_command.emit("toggle_run")
			accept_event()
		elif event.keycode == KEY_F:
			reset_view()
			accept_event()

func _zoom_at(point: Vector2, factor: float) -> void:
	var old_zoom := zoom
	zoom = clampf(zoom * factor, 0.65, 1.8)
	if is_equal_approx(old_zoom, zoom):
		return
	var world_point := (point - size * 0.5 - pan) / old_zoom
	pan = point - size * 0.5 - world_point * zoom
	viewport_changed.emit(zoom)
	queue_redraw()

func _screen_position(normalized: Vector2) -> Vector2:
	var base := Vector2(size.x * normalized.x, size.y * normalized.y)
	return (base - size * 0.5) * zoom + size * 0.5 + pan

func _hit_test(point: Vector2) -> String:
	for object in objects:
		var center := _screen_position(object.position)
		if point.distance_to(center) <= float(object.radius) * zoom + 12.0:
			return str(object.id)
	return ""

func _draw() -> void:
	if desktop_texture != null:
		draw_rect(Rect2(Vector2.ZERO, size), Color("#050a12"), true)
		var source_size := desktop_texture.get_size()
		var scale_factor := minf(size.x / maxf(source_size.x, 1.0), size.y / maxf(source_size.y, 1.0))
		var display_size := source_size * scale_factor
		var display_rect := Rect2((size - display_size) * 0.5, display_size)
		draw_texture_rect(desktop_texture, display_rect, false)
		_draw_click_markers()
		return
	_draw_background()
	_draw_grid()
	_draw_connections()
	for object in objects:
		_draw_object(object)
	_draw_click_markers()
	_draw_viewport_hud()
	_draw_hover_card()

func _draw_background() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), Color("#07101d"), true)
	var center := size * 0.5 + pan * 0.12
	for index in range(5, 0, -1):
		var radius := minf(size.x, size.y) * (0.12 + index * 0.09)
		draw_circle(center, radius, Color(ThemeFactory.CYAN, 0.006 + index * 0.004))

func _draw_grid() -> void:
	var step := grid_step * zoom
	var grid_color := Color("#29426348")
	var x := fmod(size.x * 0.5 + pan.x, step)
	while x < size.x:
		draw_line(Vector2(x, 0), Vector2(x, size.y), grid_color, 1.0)
		x += step
	var y := fmod(size.y * 0.5 + pan.y, step)
	while y < size.y:
		draw_line(Vector2(0, y), Vector2(size.x, y), grid_color, 1.0)
		y += step

func _draw_click_markers() -> void:
	for marker in click_markers:
		var point: Vector2 = marker.position
		var fade := 1.0 - float(marker.age) / 2.0
		var color := ThemeFactory.MAGENTA if bool(marker.double_click) else ThemeFactory.AMBER
		draw_circle(point, 18.0 + (1.0 - fade) * 18.0, Color(color, 0.10 * fade))
		draw_arc(point, 12.0 + (1.0 - fade) * 10.0, 0.0, TAU, 32, Color(color, fade), 2.0, true)
		draw_line(point - Vector2(7, 0), point + Vector2(7, 0), Color(color, fade), 2.0)
		draw_line(point - Vector2(0, 7), point + Vector2(0, 7), Color(color, fade), 2.0)
		draw_string(ThemeDB.fallback_font, point + Vector2(16, -10), "%s  (%d, %d)" % [str(marker.annotation), roundi(point.x), roundi(point.y)], HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(color, fade))

func _draw_connections() -> void:
	var centers: Dictionary = {}
	for object in objects:
		centers[object.id] = _screen_position(object.position)
	for link in links:
		if link.size() < 2 or not centers.has(link[0]) or not centers.has(link[1]):
			continue
		var a: Vector2 = centers[link[0]]
		var b: Vector2 = centers[link[1]]
		var relation := str(link[2]) if link.size() > 2 else "flow"
		var color := _relation_color(relation)
		draw_line(a, b, Color(color, 0.38), 2.0 * zoom, true)
		if simulation_running:
			var offset := fmod(pulse + float(abs(hash(relation)) % 100) / 100.0, 1.0)
			var marker := a.lerp(b, offset)
			draw_circle(marker, 3.2 * zoom, color)
		var midpoint := a.lerp(b, 0.5)
		draw_string(ThemeDB.fallback_font, midpoint + Vector2(6, -6), relation.to_upper(), HORIZONTAL_ALIGNMENT_LEFT, -1, 9, Color(ThemeFactory.MUTED, 0.75))

func _draw_object(object: Dictionary) -> void:
	var center := _screen_position(object.position)
	var radius := float(object.radius) * zoom
	var object_id := str(object.id)
	var is_selected := object_id == selected_object_id
	var is_hovered := object_id == hovered_object_id
	var fill := ThemeFactory.kind_color(str(object.kind))
	var status_color := ThemeFactory.status_color(str(object.status))
	var halo_alpha := 0.10 + (0.06 * sin(pulse * TAU))
	if is_selected or is_hovered:
		draw_circle(center, radius + 18.0 * zoom, Color(fill, halo_alpha + 0.14))
	draw_circle(center, radius + 7.0 * zoom, Color("#06101d"))
	draw_circle(center, radius, Color(fill, 0.24 if not is_selected else 0.46))
	draw_arc(center, radius, 0, TAU, 72, fill, (2.5 if not is_selected else 4.0) * zoom, true)
	draw_arc(center, radius + 6.0 * zoom, -PI * 0.5, -PI * 0.5 + TAU * (0.72 + 0.08 * sin(pulse * TAU)), 48, Color(status_color, 0.78), 1.4 * zoom, true)
	var font := ThemeDB.fallback_font
	var label := str(object.label)
	var font_size := maxi(10, roundi(14 * zoom))
	var label_size := font.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size)
	draw_string(font, center + Vector2(-label_size.x * 0.5, 5), label, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, ThemeFactory.TEXT)
	var status := str(object.status).to_upper()
	var status_size := font.get_string_size(status, HORIZONTAL_ALIGNMENT_LEFT, -1, 10)
	draw_string(font, center + Vector2(-status_size.x * 0.5, radius + 24), status, HORIZONTAL_ALIGNMENT_LEFT, -1, 10, status_color)
	_draw_epistemic_marker(center + Vector2(radius * 0.70, -radius * 0.70), str(object.epistemic_class))

func _draw_epistemic_marker(point: Vector2, epistemic: String) -> void:
	var color := ThemeFactory.MUTED
	match epistemic:
		"observed": color = ThemeFactory.MINT
		"inferred": color = ThemeFactory.CYAN
		"counterfactual": color = ThemeFactory.MAGENTA
		"speculative": color = ThemeFactory.AMBER
		"unknown": color = ThemeFactory.MUTED
	draw_circle(point, 5.0 * zoom, Color("#07101d"))
	draw_circle(point, 3.0 * zoom, color)

func _draw_viewport_hud() -> void:
	var font := ThemeDB.fallback_font
	draw_string(font, Vector2(22, 30), "LIVE SEMANTIC TOPOLOGY", HORIZONTAL_ALIGNMENT_LEFT, -1, 12, ThemeFactory.MUTED)
	draw_string(font, Vector2(22, 49), "WHEEL: ZOOM  ·  MIDDLE/RIGHT: PAN  ·  F: FIT", HORIZONTAL_ALIGNMENT_LEFT, -1, 9, ThemeFactory.MUTED_DARK)
	var state_text := "RUNNING" if simulation_running else "PAUSED"
	var state_color := ThemeFactory.MINT if simulation_running else ThemeFactory.AMBER
	draw_circle(Vector2(size.x - 118, 25), 4.0, state_color)
	draw_string(font, Vector2(size.x - 106, 30), state_text, HORIZONTAL_ALIGNMENT_LEFT, -1, 11, state_color)
	draw_string(font, Vector2(size.x - 112, 49), "ZOOM %.0f%%" % (zoom * 100.0), HORIZONTAL_ALIGNMENT_LEFT, -1, 9, ThemeFactory.MUTED)

func _draw_hover_card() -> void:
	if desktop_texture != null and not _panning:
		var point := get_local_mouse_position()
		var region := _desktop_region(point)
		var card_size := Vector2(230, 52)
		var card_point := point + Vector2(16, 16)
		card_point.x = minf(card_point.x, size.x - card_size.x - 10)
		card_point.y = minf(card_point.y, size.y - card_size.y - 10)
		draw_style_box(ThemeFactory.panel(Color("#0d192aec"), 10, ThemeFactory.CYAN, 1, 9), Rect2(card_point, card_size))
		draw_string(ThemeDB.fallback_font, card_point + Vector2(11, 20), region, HORIZONTAL_ALIGNMENT_LEFT, -1, 12, ThemeFactory.TEXT)
		draw_string(ThemeDB.fallback_font, card_point + Vector2(11, 39), "Vision target · (%d, %d)" % [roundi(point.x), roundi(point.y)], HORIZONTAL_ALIGNMENT_LEFT, -1, 9, ThemeFactory.MUTED)
		return
	if hovered_object_id.is_empty():
		return
	var found: Dictionary = {}
	for object in objects:
		if str(object.id) == hovered_object_id:
			found = object
			break
	if found.is_empty():
		return
	var card_size := Vector2(190, 52)
	var point := get_local_mouse_position() + Vector2(16, 16)
	point.x = minf(point.x, size.x - card_size.x - 10)
	point.y = minf(point.y, size.y - card_size.y - 10)
	draw_style_box(ThemeFactory.panel(Color("#0d192aec"), 10, ThemeFactory.LINE_BRIGHT, 1, 9), Rect2(point, card_size))
	draw_string(ThemeDB.fallback_font, point + Vector2(11, 20), str(found.label), HORIZONTAL_ALIGNMENT_LEFT, -1, 12, ThemeFactory.TEXT)
	draw_string(ThemeDB.fallback_font, point + Vector2(11, 39), "%s · %s" % [str(found.kind), str(found.epistemic_class)], HORIZONTAL_ALIGNMENT_LEFT, -1, 9, ThemeFactory.MUTED)

func _desktop_region(point: Vector2) -> String:
	if point.y > size.y * 0.88:
		if point.x < size.x * 0.14: return "Start button / Start menu"
		if point.x > size.x * 0.82: return "system tray / clock"
		return "taskbar process / window switcher"
	if point.x < size.x * 0.20 and point.y < size.y * 0.78:
		return "desktop icon / shortcut column"
	return "desktop background / application surface"

func _desktop_source_point(point: Vector2) -> Vector2:
	if desktop_texture == null:
		return point
	var source_size := desktop_texture.get_size()
	var scale_factor := minf(size.x / maxf(source_size.x, 1.0), size.y / maxf(source_size.y, 1.0))
	var display_size := source_size * scale_factor
	var display_origin := (size - display_size) * 0.5
	return ((point - display_origin) / maxf(scale_factor, 0.0001)).clamp(Vector2.ZERO, source_size)

func _radius_for_kind(kind: String) -> float:
	match kind:
		"world": return 44.0
		"model", "planner": return 34.0
		"store", "render", "verifier": return 36.0
		_: return 30.0

func _relation_color(relation: String) -> Color:
	match relation:
		"observe": return ThemeFactory.VIOLET
		"propose": return ThemeFactory.MAGENTA
		"state", "present": return ThemeFactory.CYAN
		"remember", "retrieve": return ThemeFactory.MINT
		"render", "verify": return ThemeFactory.AMBER
		_: return ThemeFactory.MUTED
