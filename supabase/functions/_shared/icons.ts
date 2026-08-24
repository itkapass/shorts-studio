// _shared/icons.ts
//
// Mirrors the icon names in engine/styles/icon_library.py's ICONS dict.
// This IS duplicated data (Python owns the real stroke geometry; this file
// only needs the names so Gemini knows what it's allowed to pick from) —
// a genuine, known trade-off of having generation reachable from both a
// Python CLI/cron path and a browser/edge-function path. If you add a new
// icon in icon_library.py, add its name here too, or whiteboard_sketch
// videos generated from the Admin Panel just won't offer it as an option
// (icon_library.get_icon_strokes() still falls back gracefully either way
// — this list only limits what's presented, not correctness).
export const ICON_NAMES = [
  "arrow_down", "arrow_right", "arrow_up", "book", "brain", "building",
  "calendar", "chart_bar_up", "chart_line_down", "chart_line_up",
  "check_mark", "chip", "circle_outline", "clock", "cloud", "database",
  "dollar_sign", "envelope", "exclamation_mark", "factory", "funnel",
  "gear", "globe", "heart", "key", "laptop", "lightbulb", "lock",
  "magnifying_glass", "network_nodes", "people_two", "percent_sign",
  "person", "phone", "question_mark", "rocket", "shield", "star",
  "target", "warning_triangle", "x_mark",
];
