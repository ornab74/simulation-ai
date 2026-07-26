extends Control

const ThemeFactory = preload("res://ui/theme_factory.gd")
const WorldCanvasScript = preload("res://ui/world_canvas.gd")
const BridgeScript = preload("res://systems/surface_bridge.gd")
const CaptureScript = preload("res://systems/interaction_capture.gd")

var bridge: Variant
var capture: Variant
var world_canvas: Variant
var pages: Dictionary = {}
var nav_buttons: Dictionary = {}
var current_page := "Surface"
var current_snapshot: Dictionary = {}

var page_title: Label
var page_subtitle: Label
var connection_badge: Label
var connection_detail: Label
var branch_header_label: Label
var pause_button: Button
var toast_label: Label
var toast_timer: Timer

var state_hash_label: Label
var coherence_label: Label
var entropy_label: Label
var event_count_label: Label
var render_status_label: Label
var event_list: VBoxContainer
var timeline_list: VBoxContainer
var render_list: VBoxContainer
var adapter_grid: GridContainer
var prompt_pack_badge: Label
var prompt_pack_detail: Label
var prompt_stage_option: OptionButton
var prompt_search_input: LineEdit
var prompt_list: ItemList
var prompt_detail: RichTextLabel
var prompt_workflow_option: OptionButton
var prompt_workflow_detail: RichTextLabel
var prompt_validation_label: Label
var prompt_catalog: Dictionary = {}
var prompt_visible_entries: Array = []
var prompt_selected_id := ""
var prompt_input_editor: TextEdit
var prompt_model_input: LineEdit
var prompt_effort_option: OptionButton
var prompt_token_input: SpinBox
var prompt_execute_button: Button
var prompt_run_status: Label
var prompt_run_output: RichTextLabel
var prompt_runs_list: ItemList
var prompt_run_records: Array = []
var prompt_selected_run_id := ""
var prompt_review_note: LineEdit
var branch_option: OptionButton
var branch_input: LineEdit
var command_input: LineEdit
var command_run_button: Button
var inspector_title: Label
var inspector_status: Label
var inspector_body: RichTextLabel
var inspector_evidence: RichTextLabel
var memory_input: LineEdit
var memory_results_list: VBoxContainer
var memory_count_label: Label
var replay_status_label: Label
var cloud_toggle: CheckButton
var redact_toggle: CheckButton
var motion_toggle: CheckButton
var retention_option: OptionButton
var render_policy_option: OptionButton
var openai_status_badge: Label
var openai_status_detail: Label
var openai_key_input: LineEdit
var openai_password_input: LineEdit
var openai_import_button: Button
var openai_save_button: Button
var openai_unlock_button: Button
var openai_test_button: Button
var openai_lock_button: Button
var openai_clear_button: Button
var zoom_label: Label
var boot_overlay: Control
var boot_status: Label
var boot_progress: ProgressBar
var boot_continue: Button
var boot_download_button: Button
var boot_progress_tween: Tween
var boot_download_polling := false
var boot_app: Control
var boot_key_input: LineEdit
var boot_password_input: LineEdit
var desktop_type_option: OptionButton
var desktop_type := "Windows XP"
var boot_frame: TextureRect
var desktop_mode: Control
var desktop_tooltip: Label
var desktop_editor: LineEdit
var boot_image_requested := false
var vision_generating := false

func _ready() -> void:
	bridge = BridgeScript.new()
	capture = CaptureScript.new()
	add_child(bridge)
	add_child(capture)
	_build_app()
	bridge.snapshot_changed.connect(_on_snapshot_changed)
	bridge.status_changed.connect(_on_status_changed)
	bridge.replay_completed.connect(_on_replay_completed)
	bridge.memory_results.connect(_on_memory_results)
	bridge.render_verified.connect(_on_render_verified)
	bridge.credential_changed.connect(_on_credential_changed)
	bridge.prompt_catalog_changed.connect(_on_prompt_catalog_changed)
	bridge.prompt_details_changed.connect(_on_prompt_details_changed)
	bridge.prompt_validation_changed.connect(_on_prompt_validation_changed)
	bridge.prompt_run_completed.connect(_on_prompt_run_completed)
	bridge.prompt_runs_changed.connect(_on_prompt_runs_changed)
	bridge.prompt_run_reviewed.connect(_on_prompt_run_reviewed)
	bridge.prompt_workflow_completed.connect(_on_prompt_workflow_completed)
	bridge.gemma_status_changed.connect(_on_gemma_status)
	capture.packet_ready.connect(_on_packet_ready)
	_on_snapshot_changed(bridge.get_snapshot())
	call_deferred("_refresh_prompt_catalog")
	call_deferred("_begin_boot_sequence")

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("command_palette"):
		command_input.grab_focus()
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("new_branch"):
		_select_nav("Timeline")
		branch_input.grab_focus()
		get_viewport().set_input_as_handled()

func _build_app() -> void:
	var theme := Theme.new()
	theme.default_font = ThemeDB.fallback_font
	theme.default_font_size = 13
	self.theme = theme

	var background := TextureRect.new()
	background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var gradient := Gradient.new()
	gradient.colors = PackedColorArray([Color("#040711"), Color("#081326"), Color("#101b31")])
	gradient.offsets = PackedFloat32Array([0.0, 0.48, 1.0])
	var texture := GradientTexture2D.new()
	texture.gradient = gradient
	texture.width = 1440
	texture.height = 900
	texture.fill_from = Vector2(0.05, 0.0)
	texture.fill_to = Vector2(0.95, 1.0)
	background.texture = texture
	background.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	background.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(background)

	var app := HBoxContainer.new()
	boot_app = app
	app.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	app.add_theme_constant_override("separation", 0)
	add_child(app)
	app.add_child(_build_sidebar())

	var workspace := VBoxContainer.new()
	workspace.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	workspace.size_flags_vertical = Control.SIZE_EXPAND_FILL
	workspace.add_theme_constant_override("separation", 0)
	app.add_child(workspace)
	workspace.add_child(_build_topbar())

	var page_host := Control.new()
	page_host.size_flags_vertical = Control.SIZE_EXPAND_FILL
	page_host.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	workspace.add_child(page_host)
	pages["Surface"] = _build_surface_page()
	pages["Timeline"] = _build_timeline_page()
	pages["Memory"] = _build_memory_page()
	pages["Models"] = _build_models_page()
	pages["Screens"] = _build_screens_page()
	pages["Settings"] = _build_settings_page()
	for page_name in pages:
		var page: Control = pages[page_name]
		page.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		page.visible = page_name == current_page
		page_host.add_child(page)

	toast_label = Label.new()
	toast_label.visible = false
	toast_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	toast_label.position = Vector2(250, 78)
	toast_label.add_theme_stylebox_override("normal", ThemeFactory.panel(Color("#10243aed"), 12, ThemeFactory.CYAN, 1, 12))
	toast_label.add_theme_color_override("font_color", ThemeFactory.TEXT)
	toast_label.add_theme_font_size_override("font_size", 12)
	add_child(toast_label)
	toast_timer = Timer.new()
	toast_timer.one_shot = true
	toast_timer.wait_time = 3.0
	toast_timer.timeout.connect(func(): toast_label.visible = false)
	add_child(toast_timer)
	boot_overlay = _build_boot_overlay()
	add_child(boot_overlay)

func _build_boot_overlay() -> Control:
	var overlay := Panel.new()
	overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	overlay.z_index = 50
	overlay.add_theme_stylebox_override("panel", ThemeFactory.panel(Color("#050a12f8"), 0, ThemeFactory.CYAN, 0, 0))
	var center := VBoxContainer.new()
	center.set_anchors_preset(Control.PRESET_CENTER)
	center.position = Vector2(-260, -250)
	center.size = Vector2(520, 500)
	center.add_theme_constant_override("separation", 14)
	overlay.add_child(center)
	var glyph := Label.new()
	glyph.text = "◈  ◌  ◇"
	glyph.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	glyph.add_theme_font_size_override("font_size", 30)
	glyph.add_theme_color_override("font_color", ThemeFactory.CYAN)
	center.add_child(glyph)
	var title := Label.new()
	title.text = "WORLD MODEL INITIALIZATION"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.add_theme_font_size_override("font_size", 24)
	title.add_theme_color_override("font_color", ThemeFactory.TEXT)
	center.add_child(title)
	var sub := Label.new()
	sub.text = "Gemma vision compute  ·  deterministic world surface  ·  secure exports"
	sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	sub.add_theme_color_override("font_color", ThemeFactory.MUTED)
	center.add_child(sub)
	boot_status = Label.new()
	boot_status.text = "Scanning local model vault…"
	boot_status.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	boot_status.add_theme_color_override("font_color", ThemeFactory.MINT)
	center.add_child(boot_status)
	boot_progress = ProgressBar.new()
	boot_progress.show_percentage = false
	boot_progress.custom_minimum_size.y = 8
	center.add_child(boot_progress)
	var vault_label := Label.new()
	vault_label.text = "MODEL VAULT  ·  GEMMA 4 E2B  ·  SHA-256 VERIFIED  ·  CHUNKED RESUME"
	vault_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vault_label.add_theme_font_size_override("font_size", 10)
	vault_label.add_theme_color_override("font_color", ThemeFactory.CYAN)
	center.add_child(vault_label)
	boot_download_button = Button.new()
	boot_download_button.text = "DOWNLOAD / RESUME GEMMA"
	boot_download_button.visible = false
	boot_download_button.custom_minimum_size.y = 38
	ThemeFactory.apply_button(boot_download_button, false)
	boot_download_button.pressed.connect(_start_gemma_download)
	center.add_child(boot_download_button)
	boot_key_input = LineEdit.new()
	boot_key_input.placeholder_text = "Optional OpenAI API key (encrypted locally)"
	boot_key_input.secret = true
	ThemeFactory.apply_line_edit(boot_key_input)
	center.add_child(boot_key_input)
	boot_password_input = LineEdit.new()
	boot_password_input.placeholder_text = "Vault password (required when saving a key)"
	boot_password_input.secret = true
	ThemeFactory.apply_line_edit(boot_password_input)
	boot_password_input.text_submitted.connect(func(_value: String):
		if not boot_continue.disabled:
			_continue_from_boot()
	)
	center.add_child(boot_password_input)
	desktop_type_option = OptionButton.new()
	for type_name in ["Windows 95", "Windows XP", "Windows 7", "Windows 10", "Windows 11", "Windows 12", "Linux Ubuntu", "macOS"]:
		desktop_type_option.add_item(type_name)
	desktop_type_option.item_selected.connect(func(index: int): desktop_type = desktop_type_option.get_item_text(index))
	desktop_type_option.select(1)
	ThemeFactory.apply_option(desktop_type_option)
	center.add_child(desktop_type_option)
	boot_continue = Button.new()
	boot_continue.text = "CONTINUE TO WORLD"
	boot_continue.disabled = true
	boot_continue.custom_minimum_size.y = 48
	ThemeFactory.apply_button(boot_continue, true)
	boot_continue.pressed.connect(_continue_from_boot)
	center.add_child(boot_continue)
	var hint := Label.new()
	hint.text = "OpenAI key can be configured later in Settings; local simulation remains available offline."
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	hint.add_theme_font_size_override("font_size", 11)
	hint.add_theme_color_override("font_color", ThemeFactory.MUTED)
	center.add_child(hint)
	return overlay

func _begin_boot_sequence() -> void:
	if boot_overlay == null:
		return
	boot_app.visible = false
	boot_progress_tween = create_tween().set_loops()
	boot_progress_tween.tween_property(boot_progress, "value", 92.0, 1.6).set_trans(Tween.TRANS_SINE)
	boot_progress_tween.tween_property(boot_progress, "value", 18.0, 1.6).set_trans(Tween.TRANS_SINE)
	await get_tree().create_timer(0.35).timeout
	for _attempt in range(30):
		if bridge.status == "online":
			var result: Dictionary = await bridge.get_gemma_status()
			_on_gemma_status(result)
			if str(result.get("model", {}).get("state", "")) in ["starting", "downloading"]:
				call_deferred("_poll_gemma_download")
			var restored: Dictionary = await bridge.load_latest_screen()
			var restored_info: Dictionary = restored.get("image", {})
			if bool(restored.get("ok", false)) and not str(restored_info.get("path", "")).is_empty():
				_apply_saved_screen(str(restored_info.get("path", "")))
				boot_image_requested = true
			return
		boot_status.text = "Connecting to Surface Core… (%d/30)" % (_attempt + 1)
		await get_tree().create_timer(0.25).timeout
	boot_status.text = "Surface Core unavailable. Continue for offline mode, or start the local core."
	boot_progress.value = 25.0
	boot_continue.disabled = false

func _on_gemma_status(result: Dictionary) -> void:
	if not bool(result.get("ok", false)):
		boot_status.text = "Gemma status unavailable: %s" % str(result.get("error", "Surface Core offline"))
		if boot_download_button != null:
			boot_download_button.visible = true
			boot_download_button.disabled = false
		boot_continue.disabled = false
		return
	var model: Dictionary = result.get("model", {})
	var state := str(model.get("state", ""))
	if state == "downloading" or state == "starting":
		if boot_progress_tween != null:
			boot_progress_tween.kill()
		var percent := int(round(float(model.get("progress", 0.0)) * 100.0))
		var downloaded := _format_bytes(int(model.get("downloaded_bytes", 0)))
		var total := _format_bytes(int(model.get("total_bytes", 0)))
		var completed := int(model.get("completed_chunks", 0))
		var chunks := int(model.get("chunks", 0))
		boot_status.text = "Downloading Gemma… %d%%  ·  %s / %s  ·  chunks %d/%d" % [percent, downloaded, total, completed, chunks]
		boot_progress.value = percent
		boot_download_button.visible = true
		boot_download_button.disabled = true
		boot_download_button.text = "DOWNLOADING · RESUME SAFE"
		boot_continue.disabled = false
		return
	if bool(model.get("verified", false)):
		if boot_progress_tween != null:
			boot_progress_tween.kill()
		boot_status.text = "✓ Gemma verified  ·  SHA-256 locked  ·  world runtime ready"
		boot_progress.value = 100.0
		if boot_download_button != null:
			boot_download_button.visible = false
		boot_continue.disabled = false
		call_deferred("_hide_saved_api_key_field")
	elif state in ["missing", "paused", "error", "corrupt"]:
		if boot_progress_tween != null:
			boot_progress_tween.kill()
		var downloaded := _format_bytes(int(model.get("downloaded_bytes", 0)))
		var total := _format_bytes(int(model.get("total_bytes", 0)))
		var detail := "Gemma is not installed yet."
		if state == "paused":
			detail = "Gemma download paused with %s / %s saved. Resume safely." % [downloaded, total]
		elif state == "error":
			detail = "Download paused: %s  (%s / %s saved)" % [str(model.get("error", "network interruption")), downloaded, total]
		elif state == "corrupt":
			detail = "Existing model failed SHA-256 verification. Download again to repair it."
		boot_status.text = detail
		boot_progress.value = float(model.get("progress", 0.0)) * 100.0
		if boot_download_button != null:
			boot_download_button.visible = true
			boot_download_button.disabled = false
			boot_download_button.text = "DOWNLOAD / RESUME GEMMA"
		boot_continue.disabled = false
		call_deferred("_hide_saved_api_key_field")
	else:
		boot_status.text = "Surface Core is starting…"

func _start_gemma_download() -> void:
	if bridge == null or bridge.status != "online":
		boot_status.text = "Surface Core is still starting; download will be available in a moment."
		return
	boot_download_button.disabled = true
	boot_download_button.text = "STARTING CHUNKED DOWNLOAD…"
	var result: Dictionary = await bridge.download_gemma()
	_on_gemma_status(result)
	await _poll_gemma_download()

func _poll_gemma_download() -> void:
	if boot_download_polling or bridge == null or bridge.status != "online":
		return
	boot_download_polling = true
	for _attempt in range(720):
		var result: Dictionary = await bridge.get_gemma_status()
		_on_gemma_status(result)
		var state := str(result.get("model", {}).get("state", ""))
		if state in ["ready", "error", "corrupt", "paused"]:
			break
		await get_tree().create_timer(0.5).timeout
	boot_download_polling = false
	if boot_download_button != null and not boot_download_button.disabled:
		boot_download_button.text = "DOWNLOAD / RESUME GEMMA"

func _format_bytes(value: int) -> String:
	if value < 1024 * 1024:
		return "%d KB" % maxi(1, value / 1024)
	if value < 1024 * 1024 * 1024:
		return "%.1f MB" % (float(value) / (1024.0 * 1024.0))
	return "%.2f GB" % (float(value) / (1024.0 * 1024.0 * 1024.0))

func _hide_saved_api_key_field() -> void:
	if boot_key_input == null or bridge.status != "online":
		return
	var response: Dictionary = await bridge.get_openai_credential_status()
	var credential: Dictionary = response.get("credential", {})
	if bool(credential.get("configured", false)):
		boot_key_input.visible = false
		boot_key_input.text = ""
		boot_key_input.placeholder_text = "Saved encrypted OpenAI key — enter vault password below to unlock"

func _continue_from_boot() -> void:
	if not boot_key_input.text.strip_edges().is_empty():
		if boot_password_input.text.length() < 12:
			boot_status.text = "Vault password must be at least 12 characters."
			return
		boot_status.text = "Encrypting OpenAI credential in the local vault…"
		var credential: Dictionary = await bridge.save_openai_credential(boot_key_input.text.strip_edges(), boot_password_input.text)
		if not bool(credential.get("ok", false)):
				boot_status.text = "Could not save key: %s" % str(credential.get("detail", credential.get("error", "unknown error")))
				return
	elif not boot_password_input.text.is_empty() and bridge.status == "online":
		if boot_password_input.text.length() < 12:
			boot_status.text = "Vault password must be at least 12 characters."
			return
		boot_status.text = "Unlocking the persisted OpenAI vault…"
		var unlocked: Dictionary = await bridge.unlock_openai_credential(boot_password_input.text)
		if not bool(unlocked.get("ok", false)) and str(unlocked.get("error", "")) != "not_configured":
			boot_status.text = "Could not unlock saved key: %s" % str(unlocked.get("detail", unlocked.get("error", "unknown error")))
			return
	# The encrypted image DB can only be opened after the vault is unlocked.
	# Retry restoration here before permitting a new origin-frame request.
	if not boot_image_requested and bridge.status == "online":
		var restored_after_unlock: Dictionary = await bridge.load_latest_screen()
		var restored_info_after_unlock: Dictionary = restored_after_unlock.get("image", {})
		if bool(restored_after_unlock.get("ok", false)) and not str(restored_info_after_unlock.get("path", "")).is_empty():
			_apply_saved_screen(str(restored_info_after_unlock.get("path", "")))
			boot_image_requested = true
	boot_app.visible = true
	if bridge.status == "online" and not boot_image_requested:
		boot_image_requested = true
		boot_status.text = "Generating %s origin desktop frame…" % desktop_type
		var origin_prompt := "Create the origin screen for a persistent %s desktop world model. Use a complete 1536x1024 landscape desktop, full frame visible, stable taskbar and system tray, coherent icon grid, accurate era-specific window chrome, readable UI geometry, no crop, no letterboxing, no modern elements, and no people. This is the canonical origin surface that all later edits must preserve." % desktop_type
		var image_result: Dictionary = await bridge.generate_boot_image(origin_prompt)
		var image_info: Dictionary = image_result.get("image", {})
		var image_path := str(image_info.get("path", ""))
		if bool(image_result.get("ok", false)) and not image_path.is_empty():
			var image := Image.load_from_file(image_path)
			if image != null and boot_frame != null:
				var texture := ImageTexture.create_from_image(image)
				boot_frame.texture = texture
				world_canvas.set_desktop_texture(texture)
				boot_frame.visible = false
				boot_status.text = "✓ OpenAI desktop frame received"
			else:
				boot_status.text = "Image saved, but could not load it: %s" % image_path
		else:
			boot_status.text = "Desktop frame unavailable: %s" % str(image_result.get("detail", image_result.get("error", "unknown error")))
	var tween := create_tween()
	tween.tween_property(boot_overlay, "modulate:a", 0.0, 0.55)
	await tween.finished
	boot_overlay.queue_free()

func _enter_desktop_mode(image: Image) -> void:
	if is_instance_valid(desktop_mode):
		return
	boot_app.visible = false
	desktop_mode = Control.new()
	desktop_mode.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	desktop_mode.z_index = 100
	add_child(desktop_mode)
	var screen := TextureRect.new()
	screen.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	screen.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	screen.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	screen.texture = ImageTexture.create_from_image(image)
	screen.mouse_filter = Control.MOUSE_FILTER_IGNORE
	desktop_mode.add_child(screen)
	desktop_tooltip = Label.new()
	desktop_tooltip.visible = false
	desktop_tooltip.mouse_filter = Control.MOUSE_FILTER_IGNORE
	desktop_tooltip.add_theme_stylebox_override("normal", ThemeFactory.panel(Color("#081321e8"), 8, ThemeFactory.CYAN, 1, 8))
	desktop_tooltip.add_theme_color_override("font_color", ThemeFactory.TEXT)
	desktop_mode.add_child(desktop_tooltip)
	var input_surface := Control.new()
	input_surface.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	input_surface.mouse_filter = Control.MOUSE_FILTER_STOP
	desktop_mode.add_child(input_surface)
	input_surface.gui_input.connect(func(event: InputEvent):
		if event is InputEventMouseMotion:
			_show_desktop_tooltip(event.position)
		elif event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
			if event.double_click:
				_exit_desktop_mode()
				return
			_show_desktop_tooltip(event.position)
			capture.capture_click("surface.desktop", "Desktop image surface", event.position, event.double_click)
			call_deferred("_run_click_vision_cycle", event.position, event.double_click)
	)
	var exit_button := Button.new()
	exit_button.text = "EXIT FULLSCREEN"
	exit_button.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	exit_button.position = Vector2(-90, -58)
	exit_button.custom_minimum_size = Vector2(180, 42)
	exit_button.z_index = 20
	ThemeFactory.apply_button(exit_button, true)
	exit_button.pressed.connect(_exit_desktop_mode)
	desktop_mode.add_child(exit_button)

func _show_desktop_tooltip(position: Vector2) -> void:
	if desktop_tooltip == null:
		return
	var region := "desktop surface"
	if position.y > size.y * 0.78 and position.x < size.x * 0.28:
		region = "Start menu control"
	elif position.x < size.x * 0.30 and position.y < size.y * 0.78:
		region = "desktop shortcut / icon region"
	desktop_tooltip.text = "%s\nClick mapped at (%d, %d)" % [region, roundi(position.x), roundi(position.y)]
	desktop_tooltip.position = Vector2(minf(position.x + 14.0, size.x - 250.0), minf(position.y + 14.0, size.y - 70.0))
	desktop_tooltip.visible = true

func _open_desktop_text_box(position: Vector2) -> void:
	if is_instance_valid(desktop_editor):
		desktop_editor.queue_free()
	desktop_editor = LineEdit.new()
	desktop_editor.placeholder_text = "Vision-detected text box · type here"
	desktop_editor.custom_minimum_size = Vector2(260, 38)
	desktop_editor.position = Vector2(clampf(position.x - 130.0, 8.0, size.x - 268.0), clampf(position.y - 19.0, 8.0, size.y - 46.0))
	ThemeFactory.apply_line_edit(desktop_editor)
	desktop_mode.add_child(desktop_editor)
	desktop_editor.grab_focus()
	desktop_editor.text_submitted.connect(func(value: String):
		capture.capture_text("desktop.textbox", value, false)
		capture.flush()
		_show_toast("Text input mapped to desktop coordinate.", ThemeFactory.MINT)
	)

func _exit_desktop_mode() -> void:
	if not is_instance_valid(desktop_mode):
		return
	desktop_mode.queue_free()
	desktop_mode = null
	boot_app.visible = true

func _toggle_desktop_fullscreen() -> void:
	if is_instance_valid(desktop_mode):
		_exit_desktop_mode()
	elif boot_frame != null and boot_frame.texture != null:
		var image := boot_frame.texture.get_image()
		_enter_desktop_mode(image)

func _apply_saved_screen(path: String) -> void:
	var image := Image.load_from_file(path)
	if image == null:
		return
	var texture := ImageTexture.create_from_image(image)
	boot_frame.texture = texture
	boot_frame.visible = false
	world_canvas.set_desktop_texture(texture)
	boot_status.text = "✓ Restored encrypted desktop frame"
	world_canvas.queue_redraw()

func _reset_desktop_to_origin() -> void:
	var response: Dictionary = await bridge.reset_desktop_screen()
	var image: Dictionary = response.get("image", {})
	if bool(response.get("ok", false)) and not str(image.get("path", "")).is_empty():
		_apply_saved_screen(str(image.get("path", "")))
		_show_toast("Desktop reset to encrypted origin frame.", ThemeFactory.MINT)
	else:
		_show_toast("No encrypted origin frame is available yet.", ThemeFactory.AMBER)

func _build_sidebar() -> Control:
	var sidebar := PanelContainer.new()
	sidebar.custom_minimum_size.x = 238
	sidebar.add_theme_stylebox_override("panel", ThemeFactory.panel(Color("#070d18f4"), 0, Color("#20304a"), 1, 0))
	var margin := MarginContainer.new()
	margin.add_theme_constant_override("margin_left", 18)
	margin.add_theme_constant_override("margin_right", 18)
	margin.add_theme_constant_override("margin_top", 20)
	margin.add_theme_constant_override("margin_bottom", 18)
	sidebar.add_child(margin)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 10)
	margin.add_child(col)

	var brand_row := HBoxContainer.new()
	brand_row.add_theme_constant_override("separation", 10)
	col.add_child(brand_row)
	var icon := Label.new()
	icon.text = "◈"
	icon.add_theme_font_size_override("font_size", 34)
	icon.add_theme_color_override("font_color", ThemeFactory.CYAN)
	brand_row.add_child(icon)
	var brand_copy := VBoxContainer.new()
	brand_row.add_child(brand_copy)
	var brand := Label.new()
	brand.text = "SIMULATION AI"
	brand.add_theme_font_size_override("font_size", 16)
	brand.add_theme_color_override("font_color", ThemeFactory.TEXT)
	brand_copy.add_child(brand)
	var version := Label.new()
	version.text = "MEMORIC SURFACE / v0.6"
	version.add_theme_font_size_override("font_size", 9)
	version.add_theme_color_override("font_color", ThemeFactory.MUTED)
	brand_copy.add_child(version)

	var divider := HSeparator.new()
	divider.modulate = ThemeFactory.LINE
	col.add_child(divider)
	var nav_label := _section_label("WORKSPACE")
	col.add_child(nav_label)
	for nav_name in ["Surface", "Timeline", "Memory", "Screens", "Models", "Settings"]:
		var nav := Button.new()
		nav.text = _nav_icon(nav_name) + "  " + nav_name
		nav.alignment = HORIZONTAL_ALIGNMENT_LEFT
		ThemeFactory.apply_button(nav, nav_name == current_page)
		nav.pressed.connect(_select_nav.bind(nav_name))
		nav_buttons[nav_name] = nav
		col.add_child(nav)

	var spacer := Control.new()
	spacer.size_flags_vertical = Control.SIZE_EXPAND_FILL
	col.add_child(spacer)

	var core_card := PanelContainer.new()
	core_card.add_theme_stylebox_override("panel", ThemeFactory.panel(Color("#0c1728"), 14, ThemeFactory.LINE, 1, 12))
	col.add_child(core_card)
	var core_col := VBoxContainer.new()
	core_col.add_theme_constant_override("separation", 5)
	core_card.add_child(core_col)
	core_col.add_child(_section_label("SURFACE CORE"))
	connection_badge = Label.new()
	connection_badge.text = "●  CONNECTING"
	connection_badge.add_theme_color_override("font_color", ThemeFactory.AMBER)
	core_col.add_child(connection_badge)
	connection_detail = Label.new()
	connection_detail.text = "Loopback authority\n127.0.0.1:47890"
	connection_detail.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	connection_detail.add_theme_font_size_override("font_size", 10)
	connection_detail.add_theme_color_override("font_color", ThemeFactory.MUTED)
	core_col.add_child(connection_detail)

	var invariant := Label.new()
	invariant.text = "PIXELS ≠ STATE"
	invariant.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	invariant.add_theme_stylebox_override("normal", ThemeFactory.panel(Color("#172536"), 10, ThemeFactory.LINE_BRIGHT, 1, 8))
	invariant.add_theme_color_override("font_color", ThemeFactory.MINT)
	invariant.add_theme_font_size_override("font_size", 10)
	col.add_child(invariant)
	return sidebar

func _build_topbar() -> Control:
	var top := PanelContainer.new()
	top.custom_minimum_size.y = 76
	top.add_theme_stylebox_override("panel", ThemeFactory.panel(Color("#091223e8"), 0, ThemeFactory.LINE, 1, 0))
	var margin := MarginContainer.new()
	margin.add_theme_constant_override("margin_left", 20)
	margin.add_theme_constant_override("margin_right", 20)
	margin.add_theme_constant_override("margin_top", 12)
	margin.add_theme_constant_override("margin_bottom", 12)
	top.add_child(margin)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	margin.add_child(row)
	var title_col := VBoxContainer.new()
	title_col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(title_col)
	page_title = Label.new()
	page_title.text = "World Surface"
	page_title.add_theme_font_size_override("font_size", 22)
	page_title.add_theme_color_override("font_color", ThemeFactory.TEXT)
	title_col.add_child(page_title)
	page_subtitle = Label.new()
	page_subtitle.text = "Persistent semantic state, proposal models, and verified projections"
	page_subtitle.add_theme_font_size_override("font_size", 10)
	page_subtitle.add_theme_color_override("font_color", ThemeFactory.MUTED)
	title_col.add_child(page_subtitle)

	branch_header_label = Label.new()
	branch_header_label.text = "BRANCH  main"
	branch_header_label.add_theme_stylebox_override("normal", ThemeFactory.panel(Color("#101d31"), 10, ThemeFactory.LINE, 1, 9))
	branch_header_label.add_theme_color_override("font_color", ThemeFactory.CYAN)
	branch_header_label.add_theme_font_size_override("font_size", 10)
	row.add_child(branch_header_label)
	pause_button = Button.new()
	pause_button.text = "Ⅱ  PAUSE"
	ThemeFactory.apply_button(pause_button, false, true)
	pause_button.pressed.connect(_toggle_running)
	row.add_child(pause_button)
	var branch_button := Button.new()
	branch_button.text = "+  BRANCH"
	ThemeFactory.apply_button(branch_button, true, true)
	branch_button.pressed.connect(func(): _select_nav("Timeline"); branch_input.grab_focus())
	row.add_child(branch_button)
	return top

func _build_surface_page() -> Control:
	var page := MarginContainer.new()
	_set_page_margins(page)
	var split := HSplitContainer.new()
	split.split_offset = 900
	split.add_theme_constant_override("separation", 12)
	page.add_child(split)

	var left := VBoxContainer.new()
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left.size_flags_vertical = Control.SIZE_EXPAND_FILL
	left.add_theme_constant_override("separation", 12)
	split.add_child(left)
	left.add_child(_build_metric_row())

	var canvas_panel := PanelContainer.new()
	canvas_panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	canvas_panel.custom_minimum_size.y = 390
	canvas_panel.add_theme_stylebox_override("panel", ThemeFactory.panel(Color("#081321ed"), 18, ThemeFactory.LINE_BRIGHT, 1, 0))
	world_canvas = WorldCanvasScript.new()
	world_canvas.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	world_canvas.object_activated.connect(_on_canvas_object)
	world_canvas.desktop_pointer.connect(_on_desktop_pointer)
	world_canvas.canvas_command.connect(_on_canvas_command)
	world_canvas.viewport_changed.connect(_on_canvas_zoom)
	canvas_panel.add_child(world_canvas)
	boot_frame = TextureRect.new()
	boot_frame.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	boot_frame.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	boot_frame.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	boot_frame.mouse_filter = Control.MOUSE_FILTER_IGNORE
	boot_frame.visible = false
	canvas_panel.add_child(boot_frame)
	left.add_child(canvas_panel)
	left.add_child(_build_command_dock())
	left.add_child(_build_event_stream())

	var inspector := PanelContainer.new()
	inspector.custom_minimum_size.x = 318
	inspector.add_theme_stylebox_override("panel", ThemeFactory.panel(Color("#0b1627f0"), 18, ThemeFactory.LINE, 1, 16))
	split.add_child(inspector)
	var inspector_col := VBoxContainer.new()
	inspector_col.add_theme_constant_override("separation", 10)
	inspector.add_child(inspector_col)
	inspector_col.add_child(_section_label("SEMANTIC INSPECTOR"))
	inspector_title = Label.new()
	inspector_title.text = "World Surface"
	inspector_title.add_theme_font_size_override("font_size", 20)
	inspector_title.add_theme_color_override("font_color", ThemeFactory.TEXT)
	inspector_col.add_child(inspector_title)
	inspector_status = Label.new()
	inspector_status.text = "● ACTIVE"
	inspector_status.add_theme_color_override("font_color", ThemeFactory.MINT)
	inspector_col.add_child(inspector_status)
	inspector_body = RichTextLabel.new()
	inspector_body.bbcode_enabled = true
	inspector_body.fit_content = true
	inspector_body.custom_minimum_size.y = 220
	inspector_body.add_theme_color_override("default_color", ThemeFactory.MUTED)
	inspector_col.add_child(inspector_body)
	var divider := HSeparator.new()
	divider.modulate = ThemeFactory.LINE
	inspector_col.add_child(divider)
	inspector_col.add_child(_section_label("EVIDENCE & AUTHORITY"))
	inspector_evidence = RichTextLabel.new()
	inspector_evidence.bbcode_enabled = true
	inspector_evidence.fit_content = true
	inspector_evidence.custom_minimum_size.y = 170
	inspector_col.add_child(inspector_evidence)
	var verify_button := Button.new()
	verify_button.text = "VERIFY NEXT QUEUED FRAME"
	ThemeFactory.apply_button(verify_button, true)
	verify_button.pressed.connect(_verify_next_render)
	inspector_col.add_child(verify_button)
	var fallback_button := Button.new()
	fallback_button.text = "FORCE DETERMINISTIC FALLBACK"
	ThemeFactory.apply_button(fallback_button, false)
	fallback_button.pressed.connect(_fallback_next_render)
	inspector_col.add_child(fallback_button)
	return page

func _build_screens_page() -> Control:
	var page := MarginContainer.new()
	_set_page_margins(page)
	var root := VBoxContainer.new()
	root.add_theme_constant_override("separation", 12)
	page.add_child(root)
	root.add_child(_page_intro("Screens & Past Clicks", "Persistent desktop frames, click observations, and generated continuations."))
	var refresh := Button.new()
	refresh.text = "REFRESH SCREEN HISTORY"
	ThemeFactory.apply_button(refresh, true)
	refresh.pressed.connect(_refresh_screen_history)
	root.add_child(refresh)
	var list := ItemList.new()
	list.name = "ScreenHistory"
	list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	list.add_theme_font_size_override("font_size", 14)
	root.add_child(list)
	call_deferred("_refresh_screen_history")
	return page

func _refresh_screen_history() -> void:
	if not pages.has("Screens") or bridge == null:
		return
	var list := pages["Screens"].find_child("ScreenHistory", true, false) as ItemList
	if list == null:
		return
	list.clear()
	var response: Dictionary = await bridge.list_screen_images()
	for image in response.get("images", []):
		list.add_item("%s  ·  encrypted  ·  %s" % [str(image.get("name", "screen")), str(image.get("created_at", ""))])

func _build_metric_row() -> Control:
	var grid := GridContainer.new()
	grid.columns = 5
	grid.add_theme_constant_override("h_separation", 10)
	var item: Dictionary
	item = _metric_card("STATE HASH", "—", "canonical HEAD", ThemeFactory.CYAN)
	state_hash_label = item.value
	grid.add_child(item.root)
	item = _metric_card("COHERENCE", "—", "hypothesis alignment", ThemeFactory.MINT)
	coherence_label = item.value
	grid.add_child(item.root)
	item = _metric_card("ENTROPY", "—", "live uncertainty", ThemeFactory.VIOLET)
	entropy_label = item.value
	grid.add_child(item.root)
	item = _metric_card("EVENTS", "0", "immutable envelopes", ThemeFactory.AMBER)
	event_count_label = item.value
	grid.add_child(item.root)
	item = _metric_card("RENDER", "—", "verified projection", ThemeFactory.MAGENTA)
	render_status_label = item.value
	grid.add_child(item.root)
	return grid

func _build_command_dock() -> Control:
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", ThemeFactory.panel(Color("#0b1729"), 15, ThemeFactory.LINE, 1, 12))
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	panel.add_child(row)
	var prompt := Label.new()
	prompt.text = ">_"
	prompt.add_theme_font_size_override("font_size", 18)
	prompt.add_theme_color_override("font_color", ThemeFactory.CYAN)
	row.add_child(prompt)
	command_input = LineEdit.new()
	command_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	command_input.placeholder_text = "goal: explore the city  ·  spawn:weather_node:environment  ·  render:keyframe"
	ThemeFactory.apply_line_edit(command_input)
	command_input.text_submitted.connect(func(_value): _run_command())
	row.add_child(command_input)
	command_run_button = Button.new()
	command_run_button.text = "RUN"
	ThemeFactory.apply_button(command_run_button, true)
	command_run_button.pressed.connect(_run_command)
	row.add_child(command_run_button)
	var reset_view := Button.new()
	reset_view.text = "FIT"
	ThemeFactory.apply_button(reset_view, false)
	reset_view.pressed.connect(func(): world_canvas.reset_view())
	row.add_child(reset_view)
	var fullscreen_button := Button.new()
	fullscreen_button.text = "FULLSCREEN"
	ThemeFactory.apply_button(fullscreen_button, true, true)
	fullscreen_button.pressed.connect(_toggle_desktop_fullscreen)
	row.add_child(fullscreen_button)
	var reset_desktop := Button.new()
	reset_desktop.text = "RESET DESKTOP"
	ThemeFactory.apply_button(reset_desktop, false, true)
	reset_desktop.pressed.connect(_reset_desktop_to_origin)
	row.add_child(reset_desktop)
	zoom_label = Label.new()
	zoom_label.text = "100%"
	zoom_label.custom_minimum_size.x = 46
	zoom_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	zoom_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	zoom_label.add_theme_color_override("font_color", ThemeFactory.MUTED)
	row.add_child(zoom_label)
	return panel

func _build_event_stream() -> Control:
	var panel := PanelContainer.new()
	panel.custom_minimum_size.y = 180
	panel.add_theme_stylebox_override("panel", ThemeFactory.panel(Color("#0a1424e8"), 16, ThemeFactory.LINE, 1, 12))
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 7)
	panel.add_child(col)
	var header := HBoxContainer.new()
	col.add_child(header)
	header.add_child(_section_label("LIVE EVENT STREAM"))
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(spacer)
	var timeline_button := Button.new()
	timeline_button.text = "OPEN TIMELINE →"
	ThemeFactory.apply_button(timeline_button, false, true)
	timeline_button.pressed.connect(_select_nav.bind("Timeline"))
	header.add_child(timeline_button)
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	col.add_child(scroll)
	event_list = VBoxContainer.new()
	event_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	event_list.add_theme_constant_override("separation", 5)
	scroll.add_child(event_list)
	return panel

func _build_timeline_page() -> Control:
	var page := MarginContainer.new()
	_set_page_margins(page)
	var root := VBoxContainer.new()
	root.add_theme_constant_override("separation", 12)
	page.add_child(root)
	root.add_child(_page_intro("Branch Timeline", "Immutable events, branch refs, replay integrity, and render lineage."))
	var controls := PanelContainer.new()
	controls.add_theme_stylebox_override("panel", ThemeFactory.panel(Color("#0b1729"), 14, ThemeFactory.LINE, 1, 12))
	root.add_child(controls)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	controls.add_child(row)
	branch_option = OptionButton.new()
	branch_option.custom_minimum_size.x = 190
	ThemeFactory.apply_option(branch_option)
	row.add_child(branch_option)
	var switch_button := Button.new()
	switch_button.text = "SWITCH"
	ThemeFactory.apply_button(switch_button, false)
	switch_button.pressed.connect(_switch_branch)
	row.add_child(switch_button)
	branch_input = LineEdit.new()
	branch_input.placeholder_text = "new branch name"
	branch_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	ThemeFactory.apply_line_edit(branch_input)
	branch_input.text_submitted.connect(func(_value): _create_branch())
	row.add_child(branch_input)
	var create_button := Button.new()
	create_button.text = "+ CREATE BRANCH"
	ThemeFactory.apply_button(create_button, true)
	create_button.pressed.connect(_create_branch)
	row.add_child(create_button)
	var replay_button := Button.new()
	replay_button.text = "VERIFY REPLAY"
	ThemeFactory.apply_button(replay_button, false)
	replay_button.pressed.connect(_verify_replay)
	row.add_child(replay_button)
	replay_status_label = Label.new()
	replay_status_label.text = "● PENDING"
	replay_status_label.custom_minimum_size.x = 100
	replay_status_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	replay_status_label.add_theme_color_override("font_color", ThemeFactory.MUTED)
	row.add_child(replay_status_label)

	var split := HSplitContainer.new()
	split.size_flags_vertical = Control.SIZE_EXPAND_FILL
	split.split_offset = 760
	split.add_theme_constant_override("separation", 12)
	root.add_child(split)
	var timeline_panel := _list_panel("EVENT ENVELOPES")
	timeline_list = timeline_panel.list
	split.add_child(timeline_panel.root)
	var render_panel := _list_panel("RENDER QUEUE & FRAMES")
	render_list = render_panel.list
	render_panel.root.custom_minimum_size.x = 380
	split.add_child(render_panel.root)
	return page

func _build_memory_page() -> Control:
	var page := MarginContainer.new()
	_set_page_margins(page)
	var root := VBoxContainer.new()
	root.add_theme_constant_override("separation", 12)
	page.add_child(root)
	root.add_child(_page_intro("Memoric Retrieval", "Branch-aware episodic, contradiction, causal, and render memory."))
	var search_panel := PanelContainer.new()
	search_panel.add_theme_stylebox_override("panel", ThemeFactory.panel(Color("#0b1729"), 14, ThemeFactory.LINE, 1, 12))
	root.add_child(search_panel)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	search_panel.add_child(row)
	memory_input = LineEdit.new()
	memory_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	memory_input.placeholder_text = "Search interactions, objects, failures, or contradictions"
	ThemeFactory.apply_line_edit(memory_input)
	memory_input.text_submitted.connect(func(_value): _search_memory())
	row.add_child(memory_input)
	var search_button := Button.new()
	search_button.text = "RETRIEVE"
	ThemeFactory.apply_button(search_button, true)
	search_button.pressed.connect(_search_memory)
	row.add_child(search_button)
	memory_count_label = Label.new()
	memory_count_label.text = "0 records"
	memory_count_label.custom_minimum_size.x = 100
	memory_count_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	memory_count_label.add_theme_color_override("font_color", ThemeFactory.MUTED)
	row.add_child(memory_count_label)

	var split := HSplitContainer.new()
	split.size_flags_vertical = Control.SIZE_EXPAND_FILL
	split.split_offset = 850
	split.add_theme_constant_override("separation", 12)
	root.add_child(split)
	var results_panel := _list_panel("RETRIEVED MEMORY")
	memory_results_list = results_panel.list
	split.add_child(results_panel.root)
	var policy := PanelContainer.new()
	policy.custom_minimum_size.x = 330
	policy.add_theme_stylebox_override("panel", ThemeFactory.panel(Color("#0b1627f0"), 18, ThemeFactory.LINE, 1, 16))
	split.add_child(policy)
	var policy_col := VBoxContainer.new()
	policy_col.add_theme_constant_override("separation", 10)
	policy.add_child(policy_col)
	policy_col.add_child(_section_label("MEMORY CONTRACT"))
	var contract := RichTextLabel.new()
	contract.bbcode_enabled = true
	contract.fit_content = true
	contract.text = "[color=#72f1b8]✓[/color] Raw events remain authoritative\n\n[color=#72f1b8]✓[/color] Summaries link to source evidence\n\n[color=#ff79d1]◆[/color] Branches remain isolated\n\n[color=#ffc66d]◇[/color] Contradictions are retained\n\n[color=#ff7b8e]×[/color] Secrets are never memory content"
	policy_col.add_child(contract)
	return page

func _build_models_page() -> Control:
	var page := MarginContainer.new()
	_set_page_margins(page)
	var scroll := ScrollContainer.new()
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	page.add_child(scroll)
	var root := VBoxContainer.new()
	root.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	root.add_theme_constant_override("separation", 12)
	scroll.add_child(root)
	root.add_child(_page_intro("Model, Prompt & Authority Plane", "Versioned prompts observe, propose, route, render, and verify. Only the deterministic Surface Core commits."))

	adapter_grid = GridContainer.new()
	adapter_grid.columns = 2
	adapter_grid.add_theme_constant_override("h_separation", 12)
	adapter_grid.add_theme_constant_override("v_separation", 12)
	root.add_child(adapter_grid)

	var prompt_panel := PanelContainer.new()
	prompt_panel.custom_minimum_size.y = 360
	prompt_panel.add_theme_stylebox_override("panel", ThemeFactory.panel(Color("#091629f2"), 18, ThemeFactory.LINE_BRIGHT, 1, 16))
	root.add_child(prompt_panel)
	var prompt_col := VBoxContainer.new()
	prompt_col.add_theme_constant_override("separation", 10)
	prompt_panel.add_child(prompt_col)

	var prompt_header := HBoxContainer.new()
	prompt_header.add_theme_constant_override("separation", 10)
	prompt_col.add_child(prompt_header)
	var prompt_title := Label.new()
	prompt_title.text = "VERSIONED PROMPT STUDIO"
	prompt_title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	prompt_title.add_theme_color_override("font_color", ThemeFactory.CYAN)
	prompt_title.add_theme_font_size_override("font_size", 13)
	prompt_header.add_child(prompt_title)
	prompt_pack_badge = Label.new()
	prompt_pack_badge.text = "● LOADING"
	prompt_pack_badge.add_theme_color_override("font_color", ThemeFactory.AMBER)
	prompt_header.add_child(prompt_pack_badge)
	var validate := Button.new()
	validate.text = "VALIDATE PACK"
	ThemeFactory.apply_button(validate, false, true)
	validate.pressed.connect(_validate_prompt_pack)
	prompt_header.add_child(validate)
	var refresh := Button.new()
	refresh.text = "REFRESH"
	ThemeFactory.apply_button(refresh, true, true)
	refresh.pressed.connect(_refresh_prompt_catalog)
	prompt_header.add_child(refresh)

	prompt_pack_detail = Label.new()
	prompt_pack_detail.text = "Loading prompt manifest, content hashes, workflows, and output contracts…"
	prompt_pack_detail.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	prompt_pack_detail.add_theme_color_override("font_color", ThemeFactory.MUTED)
	prompt_col.add_child(prompt_pack_detail)

	var prompt_split := HSplitContainer.new()
	prompt_split.custom_minimum_size.y = 270
	prompt_split.split_offset = 430
	prompt_split.add_theme_constant_override("separation", 12)
	prompt_col.add_child(prompt_split)

	var catalog_col := VBoxContainer.new()
	catalog_col.custom_minimum_size.x = 390
	catalog_col.add_theme_constant_override("separation", 8)
	prompt_split.add_child(catalog_col)
	prompt_search_input = LineEdit.new()
	prompt_search_input.placeholder_text = "Search roles, authority, tags, schemas…"
	prompt_search_input.clear_button_enabled = true
	prompt_search_input.text_changed.connect(_on_prompt_search_changed)
	catalog_col.add_child(prompt_search_input)
	var filter_row := HBoxContainer.new()
	filter_row.add_theme_constant_override("separation", 8)
	catalog_col.add_child(filter_row)
	prompt_stage_option = OptionButton.new()
	prompt_stage_option.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	for stage in ["ALL STAGES", "OBSERVE", "DISCOVER", "INTERPRET", "PROFILE", "PROPOSE", "CRITIC", "PLAN", "COMPILE", "ROUTE", "NORMALIZE", "ANALYZE", "SCHEDULE", "RENDER", "VERIFY", "AUDIT", "REPAIR", "MEMORY", "REMEMBER", "PRIVACY", "EVALUATE", "SECURITY", "REVIEW", "DEPLOY", "POLICY"]:
		prompt_stage_option.add_item(stage)
	prompt_stage_option.item_selected.connect(_on_prompt_stage_selected)
	filter_row.add_child(prompt_stage_option)
	prompt_validation_label = Label.new()
	prompt_validation_label.text = "HASH —"
	prompt_validation_label.add_theme_color_override("font_color", ThemeFactory.MUTED)
	filter_row.add_child(prompt_validation_label)
	prompt_list = ItemList.new()
	prompt_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	prompt_list.allow_reselect = true
	prompt_list.item_selected.connect(_on_prompt_selected)
	catalog_col.add_child(prompt_list)

	var detail_col := VBoxContainer.new()
	detail_col.add_theme_constant_override("separation", 8)
	prompt_split.add_child(detail_col)
	prompt_workflow_option = OptionButton.new()
	prompt_workflow_option.item_selected.connect(_on_prompt_workflow_selected)
	detail_col.add_child(prompt_workflow_option)
	prompt_workflow_detail = RichTextLabel.new()
	prompt_workflow_detail.bbcode_enabled = true
	prompt_workflow_detail.fit_content = true
	prompt_workflow_detail.custom_minimum_size.y = 72
	prompt_workflow_detail.add_theme_stylebox_override("normal", ThemeFactory.panel(Color("#0c1b30"), 10, ThemeFactory.LINE, 1, 10))
	detail_col.add_child(prompt_workflow_detail)
	prompt_detail = RichTextLabel.new()
	prompt_detail.bbcode_enabled = true
	prompt_detail.size_flags_vertical = Control.SIZE_EXPAND_FILL
	prompt_detail.scroll_active = true
	prompt_detail.add_theme_stylebox_override("normal", ThemeFactory.panel(Color("#07111f"), 12, ThemeFactory.LINE, 1, 12))
	prompt_detail.text = "[color=#8fa3c2]Select a prompt to inspect its role, authority ceiling, input contract, output schema, and complete system text.[/color]"
	detail_col.add_child(prompt_detail)

	root.add_child(_build_prompt_execution_console())

	var topology := PanelContainer.new()
	topology.custom_minimum_size.y = 190
	topology.add_theme_stylebox_override("panel", ThemeFactory.panel(Color("#0a1424e8"), 18, ThemeFactory.LINE, 1, 18))
	root.add_child(topology)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 12)
	topology.add_child(col)
	col.add_child(_section_label("AUTHORITY PIPELINE"))
	var pipeline := Label.new()
	pipeline.text = "USER EVENT  →  OBSERVER PROMPT  →  PATCH PROMPT  →  CRITIC  →  DETERMINISTIC GATE  →  STATE DAG  →  RENDER PROMPT  →  FRAME VERIFIER"
	pipeline.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	pipeline.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	pipeline.add_theme_stylebox_override("normal", ThemeFactory.panel(Color("#111f35"), 14, ThemeFactory.LINE_BRIGHT, 1, 16))
	pipeline.add_theme_color_override("font_color", ThemeFactory.CYAN)
	pipeline.add_theme_font_size_override("font_size", 13)
	col.add_child(pipeline)
	var notes := RichTextLabel.new()
	notes.bbcode_enabled = true
	notes.fit_content = true
	notes.text = "[color=#72f1b8]Canonical:[/color] schemas, preconditions, refs, hashes, replay, privacy and rights.

[color=#55ddff]Proposal-only:[/color] observations, intent, patches, profiles, routes, render plans and memory suggestions.

[color=#ffc66d]Candidate-only:[/color] generated pixels and visual interpretations."
	col.add_child(notes)
	return page

func _build_prompt_execution_console() -> Control:
	var panel := PanelContainer.new()
	panel.custom_minimum_size.y = 430
	panel.add_theme_stylebox_override("panel", ThemeFactory.panel(Color("#071426f2"), 18, ThemeFactory.VIOLET, 1, 16))
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 10)
	panel.add_child(col)
	var header := HBoxContainer.new()
	header.add_theme_constant_override("separation", 10)
	col.add_child(header)
	var title := Label.new()
	title.text = "GOVERNED PROMPT RUN CONSOLE"
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title.add_theme_color_override("font_color", ThemeFactory.VIOLET)
	title.add_theme_font_size_override("font_size", 13)
	header.add_child(title)
	prompt_run_status = Label.new()
	prompt_run_status.text = "SELECT A CALLABLE ROLE"
	prompt_run_status.add_theme_color_override("font_color", ThemeFactory.MUTED)
	header.add_child(prompt_run_status)

	var controls := HBoxContainer.new()
	controls.add_theme_constant_override("separation", 8)
	col.add_child(controls)
	prompt_model_input = LineEdit.new()
	prompt_model_input.placeholder_text = "Model override (default: encrypted settings)"
	prompt_model_input.custom_minimum_size.x = 280
	ThemeFactory.apply_line_edit(prompt_model_input)
	controls.add_child(prompt_model_input)
	prompt_effort_option = OptionButton.new()
	for effort in ["none", "minimal", "low", "medium", "high", "xhigh"]:
		prompt_effort_option.add_item(effort)
	prompt_effort_option.select(3)
	controls.add_child(prompt_effort_option)
	prompt_token_input = SpinBox.new()
	prompt_token_input.min_value = 128
	prompt_token_input.max_value = 100000
	prompt_token_input.step = 128
	prompt_token_input.value = 4096
	prompt_token_input.custom_minimum_size.x = 130
	prompt_token_input.suffix = " tokens"
	controls.add_child(prompt_token_input)
	prompt_execute_button = Button.new()
	prompt_execute_button.text = "EXECUTE CANDIDATE"
	ThemeFactory.apply_button(prompt_execute_button, true)
	prompt_execute_button.pressed.connect(_execute_selected_prompt)
	controls.add_child(prompt_execute_button)

	var warning := Label.new()
	warning.text = "Provider calls use store=false. Outputs are immutable candidates, locally schema-validated, and remain non-authoritative even after human approval."
	warning.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	warning.add_theme_stylebox_override("normal", ThemeFactory.panel(Color("#1a1630"), 10, ThemeFactory.VIOLET, 1, 9))
	warning.add_theme_color_override("font_color", ThemeFactory.TEXT)
	col.add_child(warning)

	var split := HSplitContainer.new()
	split.custom_minimum_size.y = 300
	split.split_offset = 560
	split.add_theme_constant_override("separation", 12)
	col.add_child(split)
	var input_col := VBoxContainer.new()
	input_col.add_theme_constant_override("separation", 6)
	split.add_child(input_col)
	input_col.add_child(_section_label("DECLARED INPUTS · JSON"))
	prompt_input_editor = TextEdit.new()
	prompt_input_editor.size_flags_vertical = Control.SIZE_EXPAND_FILL
	prompt_input_editor.placeholder_text = "Select a callable role to load its required-input template."
	prompt_input_editor.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	prompt_input_editor.add_theme_font_size_override("font_size", 12)
	prompt_input_editor.add_theme_color_override("font_color", ThemeFactory.TEXT)
	prompt_input_editor.add_theme_stylebox_override("normal", ThemeFactory.panel(Color("#050d18"), 10, ThemeFactory.LINE, 1, 10))
	input_col.add_child(prompt_input_editor)

	var result_col := VBoxContainer.new()
	result_col.add_theme_constant_override("separation", 6)
	split.add_child(result_col)
	result_col.add_child(_section_label("IMMUTABLE RUN HISTORY"))
	prompt_runs_list = ItemList.new()
	prompt_runs_list.custom_minimum_size.y = 92
	prompt_runs_list.item_selected.connect(_on_prompt_run_selected)
	result_col.add_child(prompt_runs_list)
	prompt_run_output = RichTextLabel.new()
	prompt_run_output.bbcode_enabled = false
	prompt_run_output.size_flags_vertical = Control.SIZE_EXPAND_FILL
	prompt_run_output.scroll_active = true
	prompt_run_output.text = "No model run selected."
	prompt_run_output.add_theme_font_size_override("normal_font_size", 11)
	prompt_run_output.add_theme_stylebox_override("normal", ThemeFactory.panel(Color("#050d18"), 10, ThemeFactory.LINE, 1, 10))
	result_col.add_child(prompt_run_output)
	var review_row := HBoxContainer.new()
	review_row.add_theme_constant_override("separation", 8)
	result_col.add_child(review_row)
	prompt_review_note = LineEdit.new()
	prompt_review_note.placeholder_text = "Review note; approval only advances to deterministic review"
	prompt_review_note.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	ThemeFactory.apply_line_edit(prompt_review_note)
	review_row.add_child(prompt_review_note)
	var approve := Button.new()
	approve.text = "APPROVE FOR GATE"
	ThemeFactory.apply_button(approve, true, true)
	approve.pressed.connect(_review_selected_prompt_run.bind("approve"))
	review_row.add_child(approve)
	var revise := Button.new()
	revise.text = "NEEDS REVISION"
	ThemeFactory.apply_button(revise, false, true)
	revise.pressed.connect(_review_selected_prompt_run.bind("needs-revision"))
	review_row.add_child(revise)
	var reject := Button.new()
	reject.text = "REJECT"
	ThemeFactory.apply_button(reject, false, true)
	reject.pressed.connect(_review_selected_prompt_run.bind("reject"))
	review_row.add_child(reject)
	return panel

func _build_settings_page() -> Control:
	var page := MarginContainer.new()
	_set_page_margins(page)
	var scroll := ScrollContainer.new()
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	page.add_child(scroll)
	var root := VBoxContainer.new()
	root.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	root.add_theme_constant_override("separation", 12)
	scroll.add_child(root)
	root.add_child(_page_intro("Runtime Policy", "Privacy, encrypted provider credentials, retention, render routing, and motion controls."))

	var openai := _settings_card("OPENAI CREDENTIAL VAULT")
	root.add_child(openai.root)
	var status_row := HBoxContainer.new()
	status_row.add_theme_constant_override("separation", 12)
	openai.col.add_child(status_row)
	openai_status_badge = Label.new()
	openai_status_badge.text = "● NOT CONFIGURED"
	openai_status_badge.add_theme_color_override("font_color", ThemeFactory.RED)
	openai_status_badge.custom_minimum_size.x = 170
	status_row.add_child(openai_status_badge)
	openai_status_detail = Label.new()
	openai_status_detail.text = "No encrypted OpenAI credential is configured."
	openai_status_detail.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	openai_status_detail.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	openai_status_detail.add_theme_color_override("font_color", ThemeFactory.MUTED)
	status_row.add_child(openai_status_detail)

	var credential_note := Label.new()
	credential_note.text = "The key is encrypted locally with scrypt + AES-256-GCM. It is never written to world state, events, evidence, prompts, memory, render jobs, or logs."
	credential_note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	credential_note.add_theme_stylebox_override("normal", ThemeFactory.panel(Color("#0a2030"), 11, ThemeFactory.CYAN, 1, 10))
	credential_note.add_theme_color_override("font_color", ThemeFactory.TEXT)
	openai.col.add_child(credential_note)

	var credential_fields := GridContainer.new()
	credential_fields.columns = 2
	credential_fields.add_theme_constant_override("h_separation", 12)
	credential_fields.add_theme_constant_override("v_separation", 8)
	openai.col.add_child(credential_fields)
	var key_col := VBoxContainer.new()
	credential_fields.add_child(key_col)
	var key_label := Label.new()
	key_label.text = "OpenAI API key"
	key_label.add_theme_color_override("font_color", ThemeFactory.MUTED)
	key_col.add_child(key_label)
	openai_key_input = LineEdit.new()
	openai_key_input.placeholder_text = "Paste a key or import OPENAI_API_KEY"
	openai_key_input.secret = true
	openai_key_input.context_menu_enabled = false
	openai_key_input.custom_minimum_size.x = 310
	ThemeFactory.apply_line_edit(openai_key_input)
	key_col.add_child(openai_key_input)
	var password_col := VBoxContainer.new()
	credential_fields.add_child(password_col)
	var password_label := Label.new()
	password_label.text = "Vault password (12+ characters)"
	password_label.add_theme_color_override("font_color", ThemeFactory.MUTED)
	password_col.add_child(password_label)
	openai_password_input = LineEdit.new()
	openai_password_input.placeholder_text = "Required to save, unlock, or clear"
	openai_password_input.secret = true
	openai_password_input.context_menu_enabled = false
	openai_password_input.custom_minimum_size.x = 270
	ThemeFactory.apply_line_edit(openai_password_input)
	password_col.add_child(openai_password_input)

	var credential_actions := GridContainer.new()
	credential_actions.columns = 3
	credential_actions.add_theme_constant_override("h_separation", 8)
	credential_actions.add_theme_constant_override("v_separation", 8)
	openai.col.add_child(credential_actions)
	openai_import_button = Button.new()
	openai_import_button.text = "IMPORT ENV KEY"
	ThemeFactory.apply_button(openai_import_button, false, true)
	openai_import_button.pressed.connect(_import_openai_environment)
	credential_actions.add_child(openai_import_button)
	openai_save_button = Button.new()
	openai_save_button.text = "SAVE ENCRYPTED"
	ThemeFactory.apply_button(openai_save_button, true, true)
	openai_save_button.pressed.connect(_save_openai_credential)
	credential_actions.add_child(openai_save_button)
	openai_unlock_button = Button.new()
	openai_unlock_button.text = "UNLOCK"
	ThemeFactory.apply_button(openai_unlock_button, false, true)
	openai_unlock_button.pressed.connect(_unlock_openai_credential)
	credential_actions.add_child(openai_unlock_button)
	openai_test_button = Button.new()
	openai_test_button.text = "TEST OPENAI"
	ThemeFactory.apply_button(openai_test_button, false, true)
	openai_test_button.pressed.connect(_test_openai_credential)
	credential_actions.add_child(openai_test_button)
	openai_lock_button = Button.new()
	openai_lock_button.text = "LOCK"
	ThemeFactory.apply_button(openai_lock_button, false, true)
	openai_lock_button.pressed.connect(_lock_openai_credential)
	credential_actions.add_child(openai_lock_button)
	openai_clear_button = Button.new()
	openai_clear_button.text = "CLEAR VAULT"
	ThemeFactory.apply_danger_button(openai_clear_button, true)
	openai_clear_button.pressed.connect(_clear_openai_credential)
	credential_actions.add_child(openai_clear_button)

	var grid := GridContainer.new()
	grid.columns = 2
	grid.add_theme_constant_override("h_separation", 12)
	grid.add_theme_constant_override("v_separation", 12)
	root.add_child(grid)

	var privacy := _settings_card("PRIVACY & RETENTION")
	grid.add_child(privacy.root)
	cloud_toggle = CheckButton.new()
	cloud_toggle.text = "Allow privacy-approved cloud model calls"
	cloud_toggle.toggled.connect(func(value): capture.capture_command("privacy:cloud:%s" % ("on" if value else "off")))
	privacy.col.add_child(cloud_toggle)
	redact_toggle = CheckButton.new()
	redact_toggle.text = "Redact sensitive typed content"
	redact_toggle.button_pressed = true
	redact_toggle.toggled.connect(func(value): capture.capture_command("privacy:redaction:%s" % ("on" if value else "off")))
	privacy.col.add_child(redact_toggle)
	var retention_label := Label.new()
	retention_label.text = "Frame retention"
	retention_label.add_theme_color_override("font_color", ThemeFactory.MUTED)
	privacy.col.add_child(retention_label)
	retention_option = OptionButton.new()
	for option in ["ephemeral", "bounded", "persistent-keyframes"]: retention_option.add_item(option)
	retention_option.select(1)
	ThemeFactory.apply_option(retention_option)
	retention_option.item_selected.connect(func(index): capture.capture_command("privacy:retention:%s" % retention_option.get_item_text(index)))
	privacy.col.add_child(retention_option)

	var render := _settings_card("RENDER & PRESENTATION")
	grid.add_child(render.root)
	var render_label := Label.new()
	render_label.text = "Default render policy"
	render_label.add_theme_color_override("font_color", ThemeFactory.MUTED)
	render.col.add_child(render_label)
	render_policy_option = OptionButton.new()
	for option in ["native-first", "composite-first", "generative-keyframes"]: render_policy_option.add_item(option)
	ThemeFactory.apply_option(render_policy_option)
	render_policy_option.item_selected.connect(func(index): capture.capture_command("render-policy:%s" % render_policy_option.get_item_text(index)))
	render.col.add_child(render_policy_option)
	motion_toggle = CheckButton.new()
	motion_toggle.text = "Reduced motion"
	motion_toggle.toggled.connect(func(value): capture.capture_command("motion:reduced:%s" % ("on" if value else "off")))
	render.col.add_child(motion_toggle)
	var keyframe := Button.new()
	keyframe.text = "QUEUE GENERATIVE KEYFRAME"
	ThemeFactory.apply_button(keyframe, true)
	keyframe.pressed.connect(func(): capture.capture_command("render:keyframe"))
	render.col.add_child(keyframe)
	var regional := Button.new()
	regional.text = "QUEUE REGIONAL IMAGE EDIT"
	ThemeFactory.apply_button(regional, false)
	regional.pressed.connect(func(): capture.capture_command("render:regional"))
	render.col.add_child(regional)

	var hard_boundary := PanelContainer.new()
	hard_boundary.add_theme_stylebox_override("panel", ThemeFactory.panel(Color("#171724"), 16, ThemeFactory.RED, 1, 16))
	root.add_child(hard_boundary)
	var boundary_text := Label.new()
	boundary_text.text = "HARD BOUNDARY  ·  Models cannot write identity, rights policy, hashes, branch ancestry, or provenance history. Generated frames cannot become state without verification."
	boundary_text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	boundary_text.add_theme_color_override("font_color", ThemeFactory.TEXT)
	hard_boundary.add_child(boundary_text)
	return page

func _select_nav(name: String) -> void:
	if not pages.has(name):
		return
	current_page = name
	for page_name in pages:
		pages[page_name].visible = page_name == name
	for nav_name in nav_buttons:
		ThemeFactory.apply_button(nav_buttons[nav_name], nav_name == name)
	var copy := {
		"Surface": ["World Surface", "Persistent semantic state, proposal models, and verified projections"],
		"Timeline": ["Branch Timeline", "Immutable events, branch refs, replay integrity, and render lineage"],
		"Memory": ["Memoric Retrieval", "Branch-aware episodic, contradiction, causal, and render memory"],
		"Models": ["Model & Authority Plane", "Proposal adapters remain subordinate to deterministic state"],
		"Settings": ["Runtime Policy", "Encrypted OpenAI credentials, privacy, retention, rendering, and presentation"],
	}
	page_title.text = copy[name][0]
	page_subtitle.text = copy[name][1]

func _on_snapshot_changed(value: Dictionary) -> void:
	current_snapshot = value
	if world_canvas != null and world_canvas.desktop_texture == null and boot_frame != null and boot_frame.texture != null:
		world_canvas.set_desktop_texture(boot_frame.texture)
		boot_frame.visible = false
	capture.sync_authority(value)
	var state: Dictionary = value.get("state", {})
	if state.is_empty():
		return
	world_canvas.set_state(state)
	var hash_text := str(state.get("state_hash", "—"))
	state_hash_label.text = hash_text.left(12) if hash_text.length() > 12 else hash_text
	coherence_label.text = "%.1f%%" % (float(state.get("coherence", 0.0)) * 100.0)
	entropy_label.text = "%.3f b" % float(state.get("entropy_bits", 0.0))
	event_count_label.text = str(value.get("counts", {}).get("events", value.get("events", []).size()))
	render_status_label.text = str(state.get("render", {}).get("status", "unknown")).to_upper()
	render_status_label.add_theme_color_override("font_color", ThemeFactory.status_color(render_status_label.text))
	branch_header_label.text = "BRANCH  %s" % str(state.get("branch", "main"))
	var running := bool(state.get("ui", {}).get("simulation_running", true))
	pause_button.text = "Ⅱ  PAUSE" if running else "▶  RESUME"
	world_canvas.set_running(running)
	_populate_events(value.get("events", []))
	_populate_timeline(value.get("events", []))
	_populate_render_jobs(value.get("render_jobs", []), value.get("frames", []))
	_populate_branches(value.get("branches", []))
	_populate_adapters(value.get("adapters", []))
	_update_inspector(str(state.get("selected_object_id", "node.surface")))
	_update_settings(state)
	_update_openai_credential(value.get("credentials", {}).get("openai", {}))
	memory_count_label.text = "%s records" % str(value.get("counts", {}).get("memories", 0))
	_on_replay_completed(value.get("replay", {}))

func _on_status_changed(new_status: String, new_detail: String) -> void:
	connection_badge.text = "●  %s" % new_status.to_upper()
	connection_badge.add_theme_color_override("font_color", ThemeFactory.status_color(new_status))
	connection_detail.text = new_detail + "\n127.0.0.1:47890"
	if new_status == "online":
		call_deferred("_refresh_prompt_catalog")

func _on_canvas_object(object_id: String, position: Vector2, double_click: bool) -> void:
	capture.capture_click(object_id, _object_label(object_id), position, double_click)
	_update_inspector(object_id)
	call_deferred("_run_click_vision_cycle", position, double_click)

func _on_desktop_pointer(button: String, position: Vector2, double_click: bool) -> void:
	capture.capture_click("surface.desktop", "Desktop surface", position, double_click, button)
	call_deferred("_run_click_vision_cycle", position, double_click, button)

func _run_click_vision_cycle(position: Vector2, double_click: bool, button := "left") -> void:
	if bridge.status != "online":
		return
	vision_generating = true
	_show_toast("◌  VISION MODEL GENERATING…  mapping click and preparing next frame", ThemeFactory.AMBER)
	var described: Dictionary = await bridge.describe_click(position, double_click, button)
	if not bool(described.get("ok", false)):
		vision_generating = false
		_show_toast("Vision observation unavailable: %s" % str(described.get("error", "unknown")), ThemeFactory.AMBER)
		return
	var description := str(described.get("description", ""))
	_show_toast(description, ThemeFactory.CYAN)
	var frame: Dictionary = await bridge.generate_click_frame("""
You are the visual transition director for a persistent desktop world model. Edit the supplied previous desktop frame; do not generate an unrelated replacement.

FRAME CONTRACT
- Target canvas: exactly 1536x1024 landscape.
- The complete desktop must remain visible edge-to-edge with no crop, zoom, letterboxing, perspective tilt, cinematic framing, or UI redesign.
- Preserve stable anchors across frames: desktop bounds, horizon/background geometry, icon centers and labels, taskbar top edge and baseline, Start button bounds, process buttons, notification area, clock, window borders, title-bar height, menu alignment, font scale, and cursor-relative composition.
- Treat the previous image as the authoritative visual surface for continuity, while treating generated pixels as non-authoritative candidates.

USER OPERATION OBSERVATION
- A visible annotation says USER CLICKED HERE or USER RIGHT-CLICKED HERE at local displayed coordinates (%d, %d).
- Zoom analysis into the annotation and nearby region before editing.
- Gemma observation: %s
- Determine the precise target: desktop background, icon/shortcut, window, title bar, menu item, Start button, taskbar process button, system tray, clock, scrollbar, text box, button, checkbox, or unknown.
- Report internally: target bounding box, center point, visible label, control role, confidence, and whether the click is inside the control or merely nearby.
- If text is present, preserve exact spelling, casing, caret/focus state, placeholder, entered value, and baseline. Never hallucinate text that is not supported by the previous frame or observation.

TRANSITION RULES
- Apply only the requested gesture and its deterministic visual consequence.
- Left click selects or activates the identified control.
- Right click opens the correct contextual menu anchored to the clicked target, unless the previous frame and observation show another behavior.
- Double-click opens the identified shortcut/window only when target identity is sufficiently supported.
- A taskbar process click changes window visibility/focus without moving the process button.
- A Start-button click opens the Start menu from the exact button bounds.
- A clock/system-tray click changes only the corresponding tray panel.
- A text-box interaction preserves the box geometry and applies only the supplied typed text.
- Unknown or low-confidence targets must preserve the prior frame and show no invented UI.

OUTPUT QUALITY GATES
- No new icons, windows, controls, shadows, people, logos, or objects unless caused by the observed operation.
- No accidental deletion, displacement, scale drift, duplicated controls, text mutation, or taskbar movement.
- Keep all unaffected pixels and structural relationships stable.
- Prefer a visually conservative edit over an imaginative continuation.
""" % [roundi(position.x), roundi(position.y), description])
	vision_generating = false
	if bool(frame.get("ok", false)):
		var generated_info: Dictionary = frame.get("image", {})
		var generated_path := str(generated_info.get("path", ""))
		if boot_frame != null and not generated_path.is_empty():
			var generated_image := Image.load_from_file(generated_path)
			if generated_image != null:
				var generated_texture := ImageTexture.create_from_image(generated_image)
				boot_frame.texture = generated_texture
				world_canvas.set_desktop_texture(generated_texture)
				boot_frame.visible = false
		_show_toast("Vision frame generated and saved for verification.", ThemeFactory.MINT)
	else:
		_show_toast("Vision generation failed: %s" % str(frame.get("detail", frame.get("error", "unknown"))), ThemeFactory.RED)

func _on_canvas_command(command: String) -> void:
	capture.capture_command(command)

func _on_canvas_zoom(value: float) -> void:
	zoom_label.text = "%.0f%%" % (value * 100.0)

func _on_packet_ready(packet: Dictionary) -> void:
	command_run_button.disabled = true
	var response: Dictionary = await bridge.commit_interaction(packet)
	command_run_button.disabled = false
	if bool(response.get("ok", false)):
		var event: Dictionary = response.get("event", {})
		_show_toast("Committed %s → %s" % [event.get("action", "event"), event.get("target_id", "surface")], ThemeFactory.MINT)
	else:
		_show_toast("Commit rejected: %s" % str(response.get("error", "unknown error")), ThemeFactory.RED)

func _run_command() -> void:
	var command := command_input.text.strip_edges()
	if command.is_empty():
		return
	command_input.clear()
	capture.capture_command(command)

func _toggle_running() -> void:
	capture.capture_command("toggle_run")

func _create_branch() -> void:
	var name := branch_input.text.strip_edges()
	if name.is_empty():
		name = "experiment-%d" % int(Time.get_unix_time_from_system())
	var response: Dictionary = await bridge.create_branch(name)
	if bool(response.get("ok", false)):
		branch_input.clear()
		_show_toast("Created branch %s" % name, ThemeFactory.MAGENTA)
	else:
		_show_toast("Branch rejected: %s" % str(response.get("error", "unknown")), ThemeFactory.RED)

func _switch_branch() -> void:
	if branch_option.item_count <= 0:
		return
	var name := branch_option.get_item_text(branch_option.selected)
	var response: Dictionary = await bridge.switch_branch(name)
	_show_toast("Switched to %s" % name if bool(response.get("ok", false)) else "Branch switch failed", ThemeFactory.CYAN if bool(response.get("ok", false)) else ThemeFactory.RED)

func _verify_replay() -> void:
	replay_status_label.text = "● VERIFYING"
	replay_status_label.add_theme_color_override("font_color", ThemeFactory.AMBER)
	await bridge.verify_replay()

func _on_replay_completed(verification: Dictionary) -> void:
	if verification.is_empty():
		return
	var verified := bool(verification.get("verified", false))
	replay_status_label.text = "● VERIFIED" if verified else "● FAILED"
	replay_status_label.add_theme_color_override("font_color", ThemeFactory.MINT if verified else ThemeFactory.RED)

func _search_memory() -> void:
	var state: Dictionary = current_snapshot.get("state", {})
	var selected := str(state.get("selected_object_id", ""))
	await bridge.query_memory(memory_input.text.strip_edges(), [selected] if not selected.is_empty() else [])

func _on_memory_results(results: Array) -> void:
	_clear(memory_results_list)
	if results.is_empty():
		memory_results_list.add_child(_empty_label("No memory matched this query."))
		return
	for result in results:
		var record: Dictionary = result.get("record", {})
		var panel := PanelContainer.new()
		panel.add_theme_stylebox_override("panel", ThemeFactory.panel(Color("#101c30"), 12, ThemeFactory.LINE, 1, 11))
		memory_results_list.add_child(panel)
		var col := VBoxContainer.new()
		col.add_theme_constant_override("separation", 5)
		panel.add_child(col)
		var header := HBoxContainer.new()
		col.add_child(header)
		var kind := Label.new()
		kind.text = str(record.get("memory_type", "memory")).to_upper()
		kind.add_theme_color_override("font_color", ThemeFactory.status_color(str(record.get("epistemic_class", "inferred"))))
		header.add_child(kind)
		var spacer := Control.new()
		spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		header.add_child(spacer)
		var score := Label.new()
		score.text = "SCORE %.3f" % float(result.get("score", 0.0))
		score.add_theme_color_override("font_color", ThemeFactory.MUTED)
		header.add_child(score)
		var summary := Label.new()
		summary.text = str(record.get("summary", ""))
		summary.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		summary.add_theme_color_override("font_color", ThemeFactory.TEXT)
		col.add_child(summary)
		var meta := Label.new()
		meta.text = "branch %s  ·  confidence %.0f%%  ·  %s" % [record.get("branch_scope", "global"), float(record.get("confidence", 0.0)) * 100.0, ", ".join(record.get("object_ids", []))]
		meta.add_theme_font_size_override("font_size", 10)
		meta.add_theme_color_override("font_color", ThemeFactory.MUTED)
		col.add_child(meta)

func _save_openai_credential() -> void:
	var api_key := openai_key_input.text.strip_edges()
	var password := openai_password_input.text
	if api_key.is_empty():
		_show_toast("Enter an OpenAI API key or use Import Env Key", ThemeFactory.AMBER)
		return
	if password.length() < 12:
		_show_toast("Vault password must contain at least 12 characters", ThemeFactory.AMBER)
		return
	_set_credential_buttons_disabled(true)
	var response: Dictionary = await bridge.save_openai_credential(api_key, password)
	_set_credential_buttons_disabled(false)
	if bool(response.get("ok", false)):
		openai_key_input.clear()
		openai_password_input.clear()
		_show_toast("OpenAI key encrypted locally and unlocked", ThemeFactory.MINT)
	else:
		_show_credential_error(response)

func _import_openai_environment() -> void:
	var password := openai_password_input.text
	if password.length() < 12:
		_show_toast("Enter a 12+ character vault password first", ThemeFactory.AMBER)
		return
	_set_credential_buttons_disabled(true)
	var response: Dictionary = await bridge.import_openai_environment(password)
	_set_credential_buttons_disabled(false)
	if bool(response.get("ok", false)):
		openai_key_input.clear()
		openai_password_input.clear()
		_show_toast("OPENAI_API_KEY imported into the encrypted vault", ThemeFactory.MINT)
	else:
		_show_credential_error(response)

func _unlock_openai_credential() -> void:
	if openai_password_input.text.is_empty():
		_show_toast("Enter the vault password", ThemeFactory.AMBER)
		return
	_set_credential_buttons_disabled(true)
	var response: Dictionary = await bridge.unlock_openai_credential(openai_password_input.text)
	_set_credential_buttons_disabled(false)
	openai_password_input.clear()
	if bool(response.get("ok", false)):
		_show_toast("OpenAI credential unlocked in process memory", ThemeFactory.MINT)
	else:
		_show_credential_error(response)

func _test_openai_credential() -> void:
	_set_credential_buttons_disabled(true)
	var response: Dictionary = await bridge.test_openai_credential()
	_set_credential_buttons_disabled(false)
	if not bool(response.get("ok", false)):
		_show_credential_error(response)
		return
	var result: Dictionary = response.get("test", {})
	var color := ThemeFactory.MINT if bool(result.get("ok", false)) else ThemeFactory.AMBER
	_show_toast("%s  ·  HTTP %s  ·  %s models" % [result.get("detail", "OpenAI test complete"), result.get("status_code", 0), result.get("model_count", 0)], color)

func _lock_openai_credential() -> void:
	_set_credential_buttons_disabled(true)
	var response: Dictionary = await bridge.lock_openai_credential()
	_set_credential_buttons_disabled(false)
	openai_key_input.clear()
	openai_password_input.clear()
	_show_toast("OpenAI credential removed from process memory" if bool(response.get("ok", false)) else "Credential lock failed", ThemeFactory.CYAN if bool(response.get("ok", false)) else ThemeFactory.RED)

func _clear_openai_credential() -> void:
	_set_credential_buttons_disabled(true)
	var response: Dictionary = await bridge.clear_openai_credential(openai_password_input.text)
	_set_credential_buttons_disabled(false)
	openai_key_input.clear()
	openai_password_input.clear()
	if bool(response.get("ok", false)):
		_show_toast("Encrypted OpenAI credential removed", ThemeFactory.AMBER)
	else:
		_show_credential_error(response)

func _on_credential_changed(response: Dictionary) -> void:
	if bool(response.get("ok", false)):
		_update_openai_credential(response.get("credential", {}))

func _show_credential_error(response: Dictionary) -> void:
	var detail := str(response.get("detail", response.get("error", "Credential operation failed")))
	_show_toast(detail, ThemeFactory.RED)

func _set_credential_buttons_disabled(disabled: bool) -> void:
	for button in [openai_import_button, openai_save_button, openai_unlock_button, openai_test_button, openai_lock_button, openai_clear_button]:
		if is_instance_valid(button):
			button.disabled = disabled
	if not disabled:
		_update_openai_credential(current_snapshot.get("credentials", {}).get("openai", {}))

func _update_openai_credential(credential: Dictionary) -> void:
	if not is_instance_valid(openai_status_badge):
		return
	var configured := bool(credential.get("configured", false))
	var unlocked := bool(credential.get("unlocked", false))
	var env_available := bool(credential.get("env_available", false))
	if configured and unlocked:
		openai_status_badge.text = "● ENCRYPTED / UNLOCKED"
		openai_status_badge.add_theme_color_override("font_color", ThemeFactory.MINT)
	elif configured:
		openai_status_badge.text = "● ENCRYPTED / LOCKED"
		openai_status_badge.add_theme_color_override("font_color", ThemeFactory.AMBER)
	elif env_available:
		openai_status_badge.text = "● ENV KEY AVAILABLE"
		openai_status_badge.add_theme_color_override("font_color", ThemeFactory.CYAN)
	else:
		openai_status_badge.text = "● NOT CONFIGURED"
		openai_status_badge.add_theme_color_override("font_color", ThemeFactory.RED)
	var parts: Array[String] = []
	parts.append("source %s" % str(credential.get("source", "none")))
	if not str(credential.get("fingerprint", "")).is_empty():
		parts.append("fingerprint %s" % credential.get("fingerprint", ""))
	if not str(credential.get("created_at", "")).is_empty():
		parts.append("created %s" % credential.get("created_at", ""))
	parts.append("secret never exposed")
	openai_status_detail.text = "  ·  ".join(parts)
	openai_import_button.disabled = not env_available
	openai_unlock_button.disabled = not configured or unlocked
	openai_test_button.disabled = not unlocked and not env_available
	openai_lock_button.disabled = not unlocked
	openai_clear_button.disabled = not configured

func _verify_next_render() -> void:
	await _resolve_next_render("pass")

func _fallback_next_render() -> void:
	await _resolve_next_render("fallback")

func _resolve_next_render(decision: String) -> void:
	for job in current_snapshot.get("render_jobs", []):
		if str(job.get("status", "")) == "queued":
			var response: Dictionary = await bridge.verify_render(str(job.get("job_id", "")), decision)
			if bool(response.get("ok", false)):
				_show_toast("Render %s" % ("verified" if decision == "pass" else "fell back safely"), ThemeFactory.MINT if decision == "pass" else ThemeFactory.AMBER)
			else:
				_show_toast("Render decision failed", ThemeFactory.RED)
			return
	_show_toast("No queued render job", ThemeFactory.MUTED)

func _verify_render_job(job_id: String, decision: String) -> void:
	var response: Dictionary = await bridge.verify_render(job_id, decision)
	if not bool(response.get("ok", false)):
		_show_toast("Render decision failed: %s" % str(response.get("error", "unknown")), ThemeFactory.RED)

func _refresh_adapters() -> void:
	var response: Dictionary = await bridge.refresh_snapshot()
	_show_toast("Adapter state refreshed" if bool(response.get("ok", false)) else "Adapter refresh unavailable", ThemeFactory.MINT if bool(response.get("ok", false)) else ThemeFactory.AMBER)

func _on_render_verified(_result: Dictionary) -> void:
	_show_toast("Render manifest updated", ThemeFactory.MINT)

func _update_inspector(object_id: String) -> void:
	var state: Dictionary = current_snapshot.get("state", {})
	var objects: Dictionary = state.get("objects", {})
	var object: Dictionary = objects.get(object_id, {})
	if object.is_empty():
		inspector_title.text = object_id
		inspector_status.text = "◇ SURFACE CONTROL"
		inspector_status.add_theme_color_override("font_color", ThemeFactory.MUTED)
		inspector_body.text = "[color=#8fa3c2]This target is part of the control surface rather than the world object graph.[/color]"
		return
	inspector_title.text = str(object.get("label", object_id))
	var status := str(object.get("status", "unknown"))
	inspector_status.text = "●  %s" % status.to_upper()
	inspector_status.add_theme_color_override("font_color", ThemeFactory.status_color(status))
	var properties: Dictionary = object.get("properties", {})
	var property_lines: Array[String] = []
	for key in properties:
		property_lines.append("[color=#8fa3c2]%s[/color]  %s" % [str(key).replace("_", " ").capitalize(), str(properties[key])])
	inspector_body.text = "[color=#55ddff]%s[/color]\n\nID  %s\nTYPE  %s\nEPISTEMIC  %s\n\n%s" % [
		str(object.get("label", object_id)), object_id, object.get("type", "entity"), object.get("epistemic_class", "unknown"), "\n".join(property_lines)
	]
	var authority := str(properties.get("authority", "deterministic state object"))
	inspector_evidence.text = "[color=#72f1b8]Authority[/color]\n%s\n\n[color=#55ddff]Current state[/color]\n%s\n\n[color=#ffc66d]Render boundary[/color]\n%s" % [authority, str(state.get("state_hash", "")).left(18), "Candidate pixels cannot mutate this object."]

func _refresh_prompt_catalog() -> void:
	prompt_pack_badge.text = "● LOADING"
	prompt_pack_badge.add_theme_color_override("font_color", ThemeFactory.AMBER)
	await bridge.get_prompt_catalog()
	await bridge.get_prompt_runs()

func _validate_prompt_pack() -> void:
	prompt_validation_label.text = "VALIDATING…"
	prompt_validation_label.add_theme_color_override("font_color", ThemeFactory.AMBER)
	await bridge.validate_prompt_pack()

func _on_prompt_catalog_changed(catalog: Dictionary) -> void:
	prompt_catalog = catalog.duplicate(true)
	var valid := bool(catalog.get("valid", false))
	prompt_pack_badge.text = "● VALID" if valid else "● INVALID"
	prompt_pack_badge.add_theme_color_override("font_color", ThemeFactory.MINT if valid else ThemeFactory.RED)
	prompt_pack_detail.text = "%s  ·  v%s  ·  %s prompts (%s callable / %s provider-strict)  ·  %s workflows  ·  SHA %s" % [
		catalog.get("pack_id", "prompt-pack"), catalog.get("pack_version", "—"), catalog.get("prompt_count", 0),
		catalog.get("callable_prompt_count", 0), catalog.get("openai_strict_prompt_count", 0), catalog.get("workflow_count", 0), str(catalog.get("pack_sha256", "—")).left(16)
	]
	prompt_validation_label.text = "SHA %s" % str(catalog.get("pack_sha256", "—")).left(8)
	prompt_validation_label.add_theme_color_override("font_color", ThemeFactory.MINT if valid else ThemeFactory.RED)
	prompt_workflow_option.clear()
	for workflow in catalog.get("workflows", []):
		prompt_workflow_option.add_item(str(workflow.get("title", workflow.get("id", "workflow"))))
	if prompt_workflow_option.item_count > 0:
		prompt_workflow_option.select(0)
		_on_prompt_workflow_selected(0)
	_populate_prompt_catalog()

func _on_prompt_stage_selected(_index: int) -> void:
	_populate_prompt_catalog()

func _on_prompt_search_changed(_value: String) -> void:
	_populate_prompt_catalog()

func _populate_prompt_catalog() -> void:
	prompt_list.clear()
	prompt_visible_entries.clear()
	var filter := "all"
	if prompt_stage_option.selected > 0:
		filter = prompt_stage_option.get_item_text(prompt_stage_option.selected).to_lower()
	var query := prompt_search_input.text.strip_edges().to_lower() if is_instance_valid(prompt_search_input) else ""
	for prompt in prompt_catalog.get("prompts", []):
		if filter != "all" and str(prompt.get("stage", "")).to_lower() != filter:
			continue
		var tags: Array = prompt.get("tags", [])
		var haystack := "%s %s %s %s %s %s" % [prompt.get("id", ""), prompt.get("title", ""), prompt.get("description", ""), prompt.get("authority", ""), prompt.get("output_schema", ""), " ".join(tags)]
		if not query.is_empty() and not haystack.to_lower().contains(query):
			continue
		prompt_visible_entries.append(prompt)
		var callable_mark := "◆" if bool(prompt.get("callable", true)) else "◇"
		var risk := str(prompt.get("risk_level", "medium")).to_upper()
		prompt_list.add_item("%s  %s  ·  %s  ·  %s" % [callable_mark, prompt.get("title", prompt.get("id", "prompt")), str(prompt.get("authority", "")).to_upper(), risk])
	if prompt_list.item_count > 0:
		prompt_list.select(0)
		_on_prompt_selected(0)
	else:
		prompt_detail.text = "[color=#8fa3c2]No prompts match this stage filter.[/color]"

func _on_prompt_selected(index: int) -> void:
	if index < 0 or index >= prompt_visible_entries.size():
		return
	var prompt: Dictionary = prompt_visible_entries[index]
	prompt_selected_id = str(prompt.get("id", ""))
	prompt_detail.text = _format_prompt_metadata(prompt, "Loading complete prompt text…")
	if is_instance_valid(prompt_run_status):
		prompt_run_status.text = "READY · %s" % prompt_selected_id
		prompt_run_status.add_theme_color_override("font_color", ThemeFactory.MUTED)
	await bridge.get_prompt_details(str(prompt.get("id", "")))

func _on_prompt_details_changed(prompt: Dictionary) -> void:
	prompt_detail.text = _format_prompt_metadata(prompt, str(prompt.get("content", "No prompt content returned.")))
	if bool(prompt.get("callable", true)) and is_instance_valid(prompt_input_editor):
		var template: Dictionary = prompt.get("input_template", {})
		prompt_input_editor.text = JSON.stringify(template, "  ")

func _format_prompt_metadata(prompt: Dictionary, content: String) -> String:
	var required: Array = prompt.get("required_inputs", [])
	var optional: Array = prompt.get("optional_inputs", [])
	var modalities: Array = prompt.get("modalities", [])
	var tags: Array = prompt.get("tags", [])
	var escaped := content.replace("[", "［").replace("]", "］")
	return "[color=#55ddff][font_size=18]%s[/font_size][/color]
[color=#8fa3c2]%s · v%s · %s[/color]

[color=#72f1b8]AUTHORITY[/color]  %s
[color=#72f1b8]RISK / LATENCY[/color]  %s / %s
[color=#72f1b8]MODEL CLASS[/color]  %s
[color=#72f1b8]MODALITIES[/color]  %s
[color=#72f1b8]DETERMINISTIC GATE[/color]  %s
[color=#72f1b8]OUTPUT[/color]  %s
[color=#72f1b8]REQUIRED INPUTS[/color]  %s
[color=#72f1b8]OPTIONAL INPUTS[/color]  %s
[color=#72f1b8]TAGS[/color]  %s
[color=#72f1b8]CONTENT SHA[/color]  %s

[color=#ffc66d]SYSTEM PROMPT[/color]
%s" % [
		prompt.get("title", prompt.get("id", "Prompt")), prompt.get("stage", "stage"), prompt.get("version", "—"), prompt.get("runtime_class", "runtime"),
		prompt.get("authority", "none"), prompt.get("risk_level", "medium"), prompt.get("latency_class", "deliberate"), prompt.get("preferred_model_class", "unspecified"), ", ".join(modalities),
		"REQUIRED" if bool(prompt.get("deterministic_gate_required", true)) else "NOT REQUIRED", prompt.get("output_schema", "none"), ", ".join(required), ", ".join(optional), ", ".join(tags), str(prompt.get("content_sha256", "—")).left(20), escaped
	]

func _on_prompt_workflow_selected(index: int) -> void:
	var workflows: Array = prompt_catalog.get("workflows", [])
	if index < 0 or index >= workflows.size():
		prompt_workflow_detail.text = ""
		return
	var workflow: Dictionary = workflows[index]
	var prompt_ids: Array = workflow.get("prompts", [])
	var gates: Array = workflow.get("deterministic_gates", [])
	prompt_workflow_detail.text = "[color=#ff79d1]%s[/color]
%s
[color=#72f1b8]Deterministic gates:[/color] %s" % [
		workflow.get("id", "workflow"), "  →  ".join(prompt_ids), ", ".join(gates) if not gates.is_empty() else "core authority boundary"
	]

func _execute_selected_prompt() -> void:
	if prompt_selected_id.is_empty():
		_show_toast("Select a callable prompt role first", ThemeFactory.AMBER)
		return
	var parsed: Variant = JSON.parse_string(prompt_input_editor.text)
	if parsed is not Dictionary:
		_show_toast("Prompt inputs must be a JSON object", ThemeFactory.RED)
		return
	prompt_execute_button.disabled = true
	prompt_run_status.text = "DISPATCHING · NON-AUTHORITATIVE"
	prompt_run_status.add_theme_color_override("font_color", ThemeFactory.AMBER)
	var effort := prompt_effort_option.get_item_text(prompt_effort_option.selected)
	var response: Dictionary = await bridge.execute_prompt(
		prompt_selected_id, parsed, prompt_model_input.text, effort, int(prompt_token_input.value)
	)
	prompt_execute_button.disabled = false
	if not bool(response.get("ok", false)):
		prompt_run_status.text = "FAILED · %s" % response.get("error", "provider")
		prompt_run_status.add_theme_color_override("font_color", ThemeFactory.RED)
		prompt_run_output.text = JSON.stringify(response, "  ")

func _on_prompt_run_completed(run: Dictionary) -> void:
	if run.has("error") and not run.has("schema"):
		prompt_run_output.text = JSON.stringify(run, "  ")
		return
	prompt_selected_run_id = str(run.get("run_id", ""))
	var valid := bool(run.get("validation", {}).get("valid", false))
	prompt_run_status.text = "%s · %s · GATE REQUIRED" % ["VALIDATED" if valid else "INVALID", str(run.get("model", "model"))]
	prompt_run_status.add_theme_color_override("font_color", ThemeFactory.MINT if valid else ThemeFactory.RED)
	prompt_run_output.text = JSON.stringify(run, "  ")
	_show_toast("Model candidate validated; no state was committed" if valid else "Model candidate failed local validation", ThemeFactory.MINT if valid else ThemeFactory.RED)

func _on_prompt_runs_changed(runs: Array) -> void:
	prompt_run_records = runs.duplicate(true)
	prompt_runs_list.clear()
	for run in prompt_run_records:
		var approval: Dictionary = run.get("approval", {})
		var label := "%s · %s · %s · %s" % [
			str(run.get("status", "unknown")).to_upper(), str(run.get("prompt_id", "prompt")),
			str(run.get("model", "model")), str(approval.get("status", "pending")).to_upper()
		]
		prompt_runs_list.add_item(label)
	if prompt_runs_list.item_count > 0:
		prompt_runs_list.select(0)
		_on_prompt_run_selected(0)

func _on_prompt_run_selected(index: int) -> void:
	if index < 0 or index >= prompt_run_records.size():
		return
	var run: Dictionary = prompt_run_records[index]
	prompt_selected_run_id = str(run.get("run_id", ""))
	prompt_run_output.text = JSON.stringify(run, "  ")

func _review_selected_prompt_run(decision: String) -> void:
	if prompt_selected_run_id.is_empty():
		_show_toast("Select a model run first", ThemeFactory.AMBER)
		return
	var response: Dictionary = await bridge.review_prompt_run(prompt_selected_run_id, decision, prompt_review_note.text)
	if not bool(response.get("ok", false)):
		_show_toast("Run review failed", ThemeFactory.RED)

func _on_prompt_run_reviewed(run: Dictionary) -> void:
	prompt_run_output.text = JSON.stringify(run, "  ")
	prompt_review_note.clear()
	_show_toast("Human review recorded; deterministic gate still required", ThemeFactory.CYAN)

func _on_prompt_workflow_completed(workflow_run: Dictionary) -> void:
	prompt_run_output.text = JSON.stringify(workflow_run, "  ")
	_show_toast("Workflow trace stored; all gates remain pending", ThemeFactory.VIOLET)

func _on_prompt_validation_changed(validation: Dictionary) -> void:
	var valid := bool(validation.get("valid", false))
	prompt_validation_label.text = "VALID" if valid else "%s ERRORS" % validation.get("problems", []).size()
	prompt_validation_label.add_theme_color_override("font_color", ThemeFactory.MINT if valid else ThemeFactory.RED)
	_show_toast("Prompt pack valid: %s prompts, %s workflows" % [validation.get("prompt_count", 0), validation.get("workflow_count", 0)] if valid else "Prompt pack validation failed", ThemeFactory.MINT if valid else ThemeFactory.RED)

func _populate_events(events: Array) -> void:
	_clear(event_list)
	if events.is_empty():
		event_list.add_child(_empty_label("No committed events yet. Interact with a topology node or run a command."))
		return
	for event in events.slice(0, mini(events.size(), 8)):
		event_list.add_child(_event_row(event, true))

func _populate_timeline(events: Array) -> void:
	_clear(timeline_list)
	if events.is_empty():
		timeline_list.add_child(_empty_label("The timeline begins after the first committed interaction."))
		return
	for event in events:
		timeline_list.add_child(_event_row(event, false))

func _populate_render_jobs(jobs: Array, frames: Array) -> void:
	_clear(render_list)
	if jobs.is_empty():
		render_list.add_child(_empty_label("No render jobs. Native genesis frame is verified."))
	for job in jobs:
		var panel := PanelContainer.new()
		panel.add_theme_stylebox_override("panel", ThemeFactory.panel(Color("#101c30"), 12, ThemeFactory.LINE, 1, 10))
		render_list.add_child(panel)
		var col := VBoxContainer.new()
		col.add_theme_constant_override("separation", 5)
		panel.add_child(col)
		var header := HBoxContainer.new()
		col.add_child(header)
		var mode := Label.new()
		mode.text = str(job.get("mode", "native_ui")).to_upper()
		mode.add_theme_color_override("font_color", ThemeFactory.CYAN)
		header.add_child(mode)
		var spacer := Control.new()
		spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		header.add_child(spacer)
		var status := Label.new()
		status.text = "● %s" % str(job.get("status", "unknown")).to_upper()
		status.add_theme_color_override("font_color", ThemeFactory.status_color(str(job.get("status", "unknown"))))
		header.add_child(status)
		var id_label := Label.new()
		id_label.text = str(job.get("job_id", "")).left(30)
		id_label.add_theme_font_size_override("font_size", 9)
		id_label.add_theme_color_override("font_color", ThemeFactory.MUTED)
		col.add_child(id_label)
		if str(job.get("status", "")) == "queued":
			var buttons := HBoxContainer.new()
			col.add_child(buttons)
			var verify := Button.new()
			verify.text = "VERIFY"
			ThemeFactory.apply_button(verify, true, true)
			verify.pressed.connect(_verify_render_job.bind(str(job.get("job_id", "")), "pass"))
			buttons.add_child(verify)
			var fallback := Button.new()
			fallback.text = "FALLBACK"
			ThemeFactory.apply_button(fallback, false, true)
			fallback.pressed.connect(_verify_render_job.bind(str(job.get("job_id", "")), "fallback"))
			buttons.add_child(fallback)
	if not frames.is_empty():
		var frame_title := _section_label("RECENT FRAME MANIFESTS")
		render_list.add_child(frame_title)
	for frame in frames:
		var label := Label.new()
		label.text = "%s  ·  %s  ·  %s" % [str(frame.get("frame_id", "")).left(20), frame.get("render_mode", "native_ui"), frame.get("status", "verified")]
		label.add_theme_stylebox_override("normal", ThemeFactory.panel(Color("#0b1728"), 9, ThemeFactory.LINE, 1, 8))
		label.add_theme_color_override("font_color", ThemeFactory.MUTED)
		render_list.add_child(label)

func _populate_branches(branches: Array) -> void:
	branch_option.clear()
	for branch in branches:
		branch_option.add_item(str(branch.get("name", "main")))
		if bool(branch.get("active", false)):
			branch_option.select(branch_option.item_count - 1)

func _populate_adapters(adapters: Array) -> void:
	_clear(adapter_grid)
	for adapter in adapters:
		var card := PanelContainer.new()
		card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		card.add_theme_stylebox_override("panel", ThemeFactory.panel(Color("#0d192c"), 16, ThemeFactory.LINE, 1, 15))
		adapter_grid.add_child(card)
		var col := VBoxContainer.new()
		col.add_theme_constant_override("separation", 6)
		card.add_child(col)
		var header := HBoxContainer.new()
		col.add_child(header)
		var title := Label.new()
		title.text = str(adapter.get("label", "Adapter"))
		title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		title.add_theme_font_size_override("font_size", 16)
		title.add_theme_color_override("font_color", ThemeFactory.TEXT)
		header.add_child(title)
		var status := Label.new()
		status.text = "● %s" % str(adapter.get("status", "unknown")).to_upper()
		status.add_theme_color_override("font_color", ThemeFactory.status_color(str(adapter.get("status", "unknown"))))
		header.add_child(status)
		var runtime := Label.new()
		runtime.text = "RUNTIME  %s" % str(adapter.get("runtime", "unknown"))
		runtime.add_theme_color_override("font_color", ThemeFactory.MUTED)
		col.add_child(runtime)
		var authority := Label.new()
		authority.text = "AUTHORITY  %s" % str(adapter.get("authority", "none"))
		authority.add_theme_color_override("font_color", ThemeFactory.CYAN if "commit" in str(adapter.get("authority", "")) else ThemeFactory.MUTED)
		col.add_child(authority)
		var locality := Label.new()
		locality.text = "LOCAL" if bool(adapter.get("local", false)) else "REMOTE / OPTIONAL"
		locality.add_theme_font_size_override("font_size", 9)
		locality.add_theme_color_override("font_color", ThemeFactory.MINT if bool(adapter.get("local", false)) else ThemeFactory.AMBER)
		col.add_child(locality)

func _update_settings(state: Dictionary) -> void:
	var ui: Dictionary = state.get("ui", {})
	var privacy: Dictionary = ui.get("privacy", {})
	cloud_toggle.set_block_signals(true)
	redact_toggle.set_block_signals(true)
	motion_toggle.set_block_signals(true)
	retention_option.set_block_signals(true)
	render_policy_option.set_block_signals(true)
	cloud_toggle.button_pressed = bool(privacy.get("cloud_allowed", false))
	redact_toggle.button_pressed = bool(privacy.get("redact_sensitive_inputs", true))
	motion_toggle.button_pressed = bool(ui.get("reduced_motion", false))
	_select_option_text(retention_option, str(privacy.get("frame_retention", "bounded")))
	_select_option_text(render_policy_option, str(ui.get("render_policy", "native-first")))
	cloud_toggle.set_block_signals(false)
	redact_toggle.set_block_signals(false)
	motion_toggle.set_block_signals(false)
	retention_option.set_block_signals(false)
	render_policy_option.set_block_signals(false)

func _event_row(event: Dictionary, compact: bool) -> Control:
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", ThemeFactory.panel(Color("#101b2e"), 10, ThemeFactory.LINE, 1, 7 if compact else 10))
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	panel.add_child(row)
	var index := Label.new()
	index.text = "#%03d" % int(event.get("index", 0))
	index.custom_minimum_size.x = 44
	index.add_theme_color_override("font_color", ThemeFactory.MUTED)
	row.add_child(index)
	var action := Label.new()
	action.text = str(event.get("action", "event")).to_upper()
	action.custom_minimum_size.x = 104
	action.add_theme_color_override("font_color", ThemeFactory.CYAN)
	row.add_child(action)
	var target := Label.new()
	target.text = str(event.get("target_id", "surface"))
	target.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	target.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	target.add_theme_color_override("font_color", ThemeFactory.TEXT)
	row.add_child(target)
	var branch := Label.new()
	branch.text = str(event.get("branch", "main"))
	branch.custom_minimum_size.x = 92
	branch.add_theme_color_override("font_color", ThemeFactory.MAGENTA if str(event.get("epistemic_class", "")) == "counterfactual" else ThemeFactory.MUTED)
	row.add_child(branch)
	var status := Label.new()
	status.text = "● %s" % str(event.get("status", "committed")).to_upper()
	status.custom_minimum_size.x = 96
	status.add_theme_color_override("font_color", ThemeFactory.status_color(str(event.get("status", "committed"))))
	row.add_child(status)
	return panel

func _metric_card(label_text: String, value_text: String, detail_text: String, accent: Color) -> Dictionary:
	var panel := PanelContainer.new()
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	panel.add_theme_stylebox_override("panel", ThemeFactory.panel(Color("#0d192b"), 14, ThemeFactory.LINE, 1, 11))
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 2)
	panel.add_child(col)
	var label := Label.new()
	label.text = label_text
	label.add_theme_font_size_override("font_size", 9)
	label.add_theme_color_override("font_color", ThemeFactory.MUTED)
	col.add_child(label)
	var value := Label.new()
	value.text = value_text
	value.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	value.add_theme_font_size_override("font_size", 18)
	value.add_theme_color_override("font_color", accent)
	col.add_child(value)
	var detail := Label.new()
	detail.text = detail_text
	detail.add_theme_font_size_override("font_size", 9)
	detail.add_theme_color_override("font_color", ThemeFactory.MUTED_DARK)
	col.add_child(detail)
	return {"root": panel, "value": value}

func _list_panel(title: String) -> Dictionary:
	var panel := PanelContainer.new()
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	panel.add_theme_stylebox_override("panel", ThemeFactory.panel(Color("#0a1424e8"), 16, ThemeFactory.LINE, 1, 12))
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 8)
	panel.add_child(col)
	col.add_child(_section_label(title))
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	col.add_child(scroll)
	var list := VBoxContainer.new()
	list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	list.add_theme_constant_override("separation", 7)
	scroll.add_child(list)
	return {"root": panel, "list": list}

func _settings_card(title: String) -> Dictionary:
	var panel := PanelContainer.new()
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	panel.add_theme_stylebox_override("panel", ThemeFactory.panel(Color("#0d192b"), 16, ThemeFactory.LINE, 1, 16))
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 10)
	panel.add_child(col)
	col.add_child(_section_label(title))
	return {"root": panel, "col": col}

func _page_intro(title: String, subtitle: String) -> Control:
	var col := VBoxContainer.new()
	var heading := Label.new()
	heading.text = title
	heading.add_theme_font_size_override("font_size", 24)
	heading.add_theme_color_override("font_color", ThemeFactory.TEXT)
	col.add_child(heading)
	var copy := Label.new()
	copy.text = subtitle
	copy.add_theme_color_override("font_color", ThemeFactory.MUTED)
	col.add_child(copy)
	return col

func _section_label(text: String) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", 9)
	label.add_theme_color_override("font_color", ThemeFactory.MUTED)
	return label

func _empty_label(text: String) -> Label:
	var label := Label.new()
	label.text = text
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.add_theme_stylebox_override("normal", ThemeFactory.panel(Color("#0b1525"), 10, ThemeFactory.LINE, 1, 10))
	label.add_theme_color_override("font_color", ThemeFactory.MUTED)
	return label

func _show_toast(text: String, color: Color) -> void:
	toast_label.text = text
	toast_label.add_theme_color_override("font_color", color)
	toast_label.visible = true
	toast_timer.start()

func _clear(container: Node) -> void:
	for child in container.get_children():
		child.queue_free()

func _set_page_margins(page: MarginContainer) -> void:
	page.add_theme_constant_override("margin_left", 16)
	page.add_theme_constant_override("margin_right", 16)
	page.add_theme_constant_override("margin_top", 14)
	page.add_theme_constant_override("margin_bottom", 14)

func _object_label(object_id: String) -> String:
	return str(current_snapshot.get("state", {}).get("objects", {}).get(object_id, {}).get("label", object_id))

func _select_option_text(option: OptionButton, value: String) -> void:
	for index in range(option.item_count):
		if option.get_item_text(index) == value:
			option.select(index)
			return

func _nav_icon(name: String) -> String:
	match name:
		"Surface": return "◈"
		"Timeline": return "≋"
		"Memory": return "◎"
		"Models": return "◇"
		"Settings": return "⚙"
		_: return "•"
