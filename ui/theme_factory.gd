extends RefCounted
class_name SimulationThemeFactory

const INK := Color("#050812")
const INK_SOFT := Color("#08101f")
const PANEL := Color("#0d1628f2")
const PANEL_ALT := Color("#111d33e8")
const PANEL_RAISED := Color("#15233bea")
const LINE := Color("#263a59")
const LINE_BRIGHT := Color("#38577e")
const TEXT := Color("#eef5ff")
const MUTED := Color("#8fa3c2")
const MUTED_DARK := Color("#627594")
const CYAN := Color("#55ddff")
const VIOLET := Color("#a685ff")
const MINT := Color("#72f1b8")
const AMBER := Color("#ffc66d")
const RED := Color("#ff7b8e")
const MAGENTA := Color("#ff79d1")

static func panel(fill: Color = PANEL, radius: int = 18, border: Color = LINE, width: int = 1, padding := 16) -> StyleBoxFlat:
	var box := StyleBoxFlat.new()
	box.bg_color = fill
	box.border_color = border
	box.set_border_width_all(width)
	box.set_corner_radius_all(radius)
	box.content_margin_left = padding
	box.content_margin_right = padding
	box.content_margin_top = padding
	box.content_margin_bottom = padding
	return box

static func button(fill: Color, hover: Color, pressed: Color, radius: int = 12) -> Dictionary:
	return {
		"normal": panel(fill, radius, Color(fill, 0.0), 0, 10),
		"hover": panel(hover, radius, Color(hover, 0.0), 0, 10),
		"pressed": panel(pressed, radius, Color(pressed, 0.0), 0, 10),
		"focus": panel(Color(hover, 0.82), radius, CYAN, 1, 10),
	}

static func apply_button(control: Button, primary := false, compact := false) -> void:
	var styles := button(
		Color("#173b5b") if primary else Color("#111d30"),
		Color("#20557d") if primary else Color("#192b45"),
		Color("#102f4b") if primary else Color("#0b1527")
	)
	for state in ["normal", "hover", "pressed", "focus"]:
		control.add_theme_stylebox_override(state, styles[state])
	control.add_theme_color_override("font_color", TEXT)
	control.add_theme_color_override("font_hover_color", TEXT)
	control.add_theme_color_override("font_pressed_color", TEXT)
	control.add_theme_font_size_override("font_size", 12 if compact else 13)
	control.custom_minimum_size.y = 32 if compact else 40

static func apply_danger_button(control: Button, compact := false) -> void:
	apply_button(control, false, compact)
	control.add_theme_stylebox_override("normal", panel(Color("#351722"), 12, Color("#6d2b3d"), 1, 10))
	control.add_theme_stylebox_override("hover", panel(Color("#512033"), 12, RED, 1, 10))
	control.add_theme_stylebox_override("pressed", panel(Color("#28101a"), 12, RED, 1, 10))

static func apply_line_edit(control: LineEdit) -> void:
	control.add_theme_stylebox_override("normal", panel(Color("#081322"), 11, LINE, 1, 11))
	control.add_theme_stylebox_override("focus", panel(Color("#0b1728"), 11, CYAN, 1, 11))
	control.add_theme_color_override("font_color", TEXT)
	control.add_theme_color_override("font_placeholder_color", MUTED_DARK)
	control.add_theme_color_override("caret_color", CYAN)
	control.custom_minimum_size.y = 40

static func apply_option(control: OptionButton) -> void:
	apply_button(control, false)
	control.add_theme_color_override("font_color", TEXT)

static func status_color(status: String) -> Color:
	match status.to_lower():
		"online", "verified", "ready", "active", "indexed", "watching", "pass":
			return MINT
		"queued", "candidate", "review", "fallback-ready", "queue-ready", "contract-ready", "locked":
			return AMBER
		"counterfactual", "branch", "speculative":
			return MAGENTA
		"offline", "rejected", "error", "failed", "credential-required":
			return RED
		_:
			return CYAN

static func kind_color(kind: String) -> Color:
	match kind:
		"model": return VIOLET
		"planner": return MAGENTA
		"world": return CYAN
		"store": return MINT
		"render": return AMBER
		"verifier": return Color("#75a7ff")
		_: return TEXT
