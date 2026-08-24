"""
icon_library.py — a small, original vocabulary of line-art icons used by the
'whiteboard_sketch' render style.

Every icon is plain coordinate data (no SVG, no bitmap assets, no third-party
icon packs — so there's nothing here to license or attribute). Each icon is a
list of "strokes"; each stroke is a flat list of (x, y) points in a 0-100
normalized icon canvas (x right, y down). engine/styles/whiteboard_sketch.py
turns each stroke into a hand-drawn-looking polyline and can reveal it
progressively (stroke-by-stroke, point-by-point) to fake a "being drawn"
animation, or render it fully for a static pop-in.

Add a new icon by adding a new ICONS[...] entry — nothing else needs to
change; script_generator.py reads ICONS.keys() at prompt-build time so new
icons are automatically offered to the model.
"""
import math

Point = tuple
Stroke = list


def _circle(cx, cy, r, n=28, start=0, end=360):
    pts = []
    for i in range(n + 1):
        deg = start + (end - start) * i / n
        rad = math.radians(deg)
        pts.append((cx + r * math.cos(rad), cy + r * math.sin(rad)))
    return pts


def _rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]


def _star(cx, cy, r_outer, r_inner, points=5):
    pts = []
    for i in range(points * 2 + 1):
        r = r_outer if i % 2 == 0 else r_inner
        deg = -90 + i * (360 / (points * 2))
        rad = math.radians(deg)
        pts.append((cx + r * math.cos(rad), cy + r * math.sin(rad)))
    return pts


def _ellipse(cx, cy, rx, ry, n=28, start=0, end=360):
    pts = []
    for i in range(n + 1):
        deg = start + (end - start) * i / n
        rad = math.radians(deg)
        pts.append((cx + rx * math.cos(rad), cy + ry * math.sin(rad)))
    return pts


def _zigzag(x0, y0, x1, y1, bumps=4, amp=6):
    pts = []
    for i in range(bumps + 1):
        t = i / bumps
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
        y += amp if i % 2 == 0 else -amp
        pts.append((x, y))
    return pts


# ---------------------------------------------------------------------------
# ICONS: name -> list[Stroke]. Keep every icon inside the 5..95 box so it has
# breathing room when composed with others on a scene.
# ---------------------------------------------------------------------------
ICONS = {
    "lightbulb": [
        _circle(50, 38, 20),
        [(42, 56), (42, 66), (58, 66), (58, 56)],
        [(44, 70), (56, 70)],
        [(45, 76), (55, 76)],
        [(50, 8), (50, 16)],
        [(24, 20), (30, 26)],
        [(76, 20), (70, 26)],
        [(14, 38), (22, 38)],
        [(86, 38), (78, 38)],
    ],
    "arrow_up": [
        [(50, 90), (50, 15)],
        [(35, 32), (50, 12), (65, 32)],
    ],
    "arrow_down": [
        [(50, 10), (50, 85)],
        [(35, 68), (50, 88), (65, 68)],
    ],
    "arrow_right": [
        [(10, 50), (85, 50)],
        [(68, 35), (88, 50), (68, 65)],
    ],
    "circle_outline": [_circle(50, 50, 35)],
    "x_mark": [
        [(22, 22), (78, 78)],
        [(78, 22), (22, 78)],
    ],
    "check_mark": [
        [(15, 52), (40, 78), (88, 20)],
    ],
    "question_mark": [
        _circle(50, 35, 18, start=-40, end=220),
        [(50, 53), (50, 65)],
        _circle(50, 80, 3),
    ],
    "exclamation_mark": [
        [(50, 12), (50, 62)],
        _circle(50, 80, 3.5),
    ],
    "dollar_sign": [
        [(50, 8), (50, 92)],
        [(70, 22), (55, 15), (35, 22), (35, 40), (65, 45), (65, 68),
         (60, 78), (30, 78), (30, 70)],
    ],
    "percent_sign": [
        [(20, 80), (80, 20)],
        _circle(28, 28, 10),
        _circle(72, 72, 10),
    ],
    "person": [
        _circle(50, 26, 14),
        [(50, 40), (50, 62)],
        [(30, 90), (50, 62), (70, 90)],
        [(28, 62), (50, 50), (72, 62)],
    ],
    "people_two": [
        _circle(32, 24, 11), [(32, 35), (32, 55)], [(18, 85), (32, 55), (46, 85)],
        _circle(68, 24, 11), [(68, 35), (68, 55)], [(54, 85), (68, 55), (82, 85)],
    ],
    "chart_bar_up": [
        [(10, 90), (90, 90)],
        [(10, 90), (10, 10)],
        _rect(22, 70, 34, 90),
        _rect(42, 55, 54, 90),
        _rect(62, 35, 74, 90),
        _rect(78, 18, 90, 90),
    ],
    "chart_line_up": [
        [(10, 90), (90, 90)],
        [(10, 90), (10, 10)],
        [(15, 75), (35, 60), (50, 68), (70, 30), (90, 15)],
        [(80, 15), (90, 15), (90, 25)],
    ],
    "chart_line_down": [
        [(10, 10), (90, 10)],
        [(10, 10), (10, 90)],
        [(15, 25), (35, 40), (50, 32), (70, 70), (90, 85)],
        [(80, 85), (90, 85), (90, 75)],
    ],
    "gear": [
        _circle(50, 50, 20),
        _circle(50, 50, 9),
    ] + [
        [
            (50 + 20 * math.cos(math.radians(a)), 50 + 20 * math.sin(math.radians(a))),
            (50 + 30 * math.cos(math.radians(a)), 50 + 30 * math.sin(math.radians(a))),
        ]
        for a in range(0, 360, 45)
    ],
    "cloud": [
        _circle(35, 60, 16, start=100, end=280),
        _circle(55, 45, 20, start=140, end=360),
        _circle(72, 58, 14, start=200, end=390),
        [(20, 65), (80, 65)],
    ],
    "phone": [
        _rect(35, 8, 65, 92),
        [(45, 85), (55, 85)],
    ],
    "laptop": [
        _rect(30, 20, 70, 62),
        [(15, 78), (85, 78), (78, 62), (22, 62)],
    ],
    "book": [
        [(50, 20), (50, 85)],
        [(50, 20), (12, 15), (12, 78), (50, 85)],
        [(50, 20), (88, 15), (88, 78), (50, 85)],
    ],
    "clock": [
        _circle(50, 50, 35),
        [(50, 50), (50, 28)],
        [(50, 50), (68, 58)],
    ],
    "star": [_star(50, 50, 38, 16)],
    "magnifying_glass": [
        _circle(42, 42, 24),
        [(60, 60), (85, 85)],
    ],
    "key": [
        _circle(28, 50, 16),
        [(42, 50), (85, 50)],
        [(70, 50), (70, 62)],
        [(80, 50), (80, 60)],
    ],
    "lock": [
        _rect(25, 45, 75, 90),
        _circle(50, 45, 18, start=180, end=360),
        _circle(50, 65, 4),
    ],
    "globe": [
        _circle(50, 50, 35),
        [(15, 50), (85, 50)],
        _circle(50, 50, 35, start=270, end=450) if False else [(50, 15), (36, 50), (50, 85), (64, 50), (50, 15)],
    ],
    "building": [
        _rect(20, 10, 80, 90),
        [(35, 25), (35, 35)], [(50, 25), (50, 35)], [(65, 25), (65, 35)],
        [(35, 45), (35, 55)], [(50, 45), (50, 55)], [(65, 45), (65, 55)],
        [(35, 65), (35, 75)], [(50, 65), (50, 75)], [(65, 65), (65, 75)],
    ],
    "factory": [
        [(10, 90), (10, 55), (35, 68), (35, 45), (60, 58), (60, 30), (75, 30), (75, 90)],
        [(10, 90), (90, 90)],
        [(64, 30), (64, 15)],
        _zigzag(64, 15, 70, 5, bumps=3, amp=3),
    ],
    "rocket": [
        [(50, 8), (35, 45), (35, 75), (65, 75), (65, 45), (50, 8)],
        [(35, 60), (18, 85)],
        [(65, 60), (82, 85)],
        _circle(50, 40, 7),
        _zigzag(42, 78, 58, 92, bumps=3, amp=4),
    ],
    "brain": [
        [(30, 30), (20, 45), (25, 60), (20, 75), (35, 88), (50, 82),
         (65, 88), (80, 75), (75, 60), (80, 45), (70, 30), (55, 20),
         (50, 25), (45, 20), (30, 30)],
        [(50, 25), (50, 82)],
        [(30, 45), (45, 45)], [(55, 45), (70, 45)],
        [(30, 62), (45, 62)], [(55, 62), (70, 62)],
    ],
    "network_nodes": [
        _circle(50, 20, 9), _circle(20, 75, 9), _circle(80, 75, 9), _circle(50, 55, 9),
        [(50, 29), (50, 46)], [(45, 60), (26, 70)], [(55, 60), (74, 70)], [(29, 75), (71, 75)],
    ],
    "funnel": [
        [(12, 12), (88, 12), (58, 55), (58, 90), (42, 90), (42, 55), (12, 12)],
    ],
    "target": [_circle(50, 50, 35), _circle(50, 50, 20), _circle(50, 50, 6)],
    "shield": [
        [(50, 8), (85, 22), (85, 50), (50, 92), (15, 50), (15, 22), (50, 8)],
    ],
    "warning_triangle": [
        [(50, 10), (90, 85), (10, 85), (50, 10)],
        [(50, 35), (50, 65)],
        _circle(50, 76, 3),
    ],
    "heart": [
        _circle(32, 35, 18, start=140, end=360),
        _circle(68, 35, 18, start=180, end=400),
        [(15, 45), (50, 90), (85, 45)],
    ],
    "calendar": [
        _rect(15, 20, 85, 88),
        [(15, 38), (85, 38)],
        [(30, 10), (30, 25)], [(70, 10), (70, 25)],
    ],
    "envelope": [
        _rect(10, 22, 90, 78),
        [(10, 22), (50, 55), (90, 22)],
    ],
    "database": [
        _ellipse(50, 22, 32, 12),
        [(18, 22), (18, 78)],
        [(82, 22), (82, 78)],
        _ellipse(50, 50, 32, 12, start=0, end=180),
        _ellipse(50, 78, 32, 12, start=0, end=180),
    ],
    "chip": [
        _rect(30, 30, 70, 70),
        _rect(42, 42, 58, 58),
    ] + [
        [(x, 30), (x, 18)] for x in (38, 50, 62)
    ] + [
        [(x, 70), (x, 82)] for x in (38, 50, 62)
    ] + [
        [(30, y), (18, y)] for y in (38, 50, 62)
    ] + [
        [(70, y), (82, y)] for y in (38, 50, 62)
    ],
}


def available_icon_names():
    """Used by script_generator.py to tell Gemini which icons it may choose."""
    return sorted(ICONS.keys())


def get_icon_strokes(name):
    """Returns the stroke list for an icon name, falling back to a plain
    circle (never crashes the renderer on an unrecognized/hallucinated name)."""
    return ICONS.get(name, ICONS["circle_outline"])
