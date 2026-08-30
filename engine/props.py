"""
props.py — objects the characters interact with.
================================================

WHY THIS EXISTS
A character standing on an empty stage saying words is a talking head. A
character standing NEXT TO the thing they are talking about is a scene. That
difference is most of the gap between a skit that reads as cheap and one that
reads as made on purpose.

Reviewing a batch of high-performing reference videos, the strongest ones all
did the same thing: the concept was VISIBLE as an object, not just spoken.
A character at the bottom of a staircase reads as "this is hard" before a
single word is heard. That is what props do here.

Every prop is drawn with the same parametric vector approach as the cast
(see character/rig.py), so props and characters share one visual language, one
outline weight, and one cost: zero.

SCALE AS MEANING
`ghost` and `mini` are not props but character MODES, handled in
character_skit.py. A second, smaller copy of the same character standing next
to the main one reads instantly as "the small voice in your head" with no
explanation. That trick is free here because sprites are cached by state, so a
second instance costs one extra cached render, not a second pipeline.

ADDING A PROP
Write a build_<name>() returning list[Part] in the 0..100 box, register it in
PROPS, and the storyboard prompt, the renderer and the admin panel all pick it
up automatically.
"""
from engine.character.rig import (
    Part, circle, ellipse, rounded_rect, arc, bezier, teardrop,
)

# Prop palette. Deliberately muted so props sit BEHIND the character in visual
# priority — a prop that out-competes the face for attention is a bug.
PROP_PALETTE = {
    "ink": (48, 44, 52),
    "metal": (168, 172, 182),
    "metal_dark": (128, 134, 146),
    "wood": (176, 138, 96),
    "wood_dark": (146, 112, 76),
    "screen": (150, 196, 224),
    "warm": (236, 154, 76),
    "hot": (226, 96, 62),
    "paper": (248, 246, 240),
    "shadow": (0, 0, 0),
}


def build_laptop():
    """Desk + open laptop. The 'work' prop."""
    return [
        Part(rounded_rect(18, 62, 88, 70, 3), "wood", "ink", 2.2),
        Part([(24, 70), (26, 92)], None, "ink", 2.6, "line"),
        Part([(82, 70), (80, 92)], None, "ink", 2.6, "line"),
        Part([(40, 38), (72, 38), (78, 62), (34, 62)], "metal", "ink", 2.2),
        Part([(43, 41), (69, 41), (74, 59), (38, 59)], "screen", None, 0, "blank"),
        Part(rounded_rect(32, 62, 80, 66, 2), "metal_dark", "ink", 2.0),
    ]


def build_stairs():
    """A staircase receding upward. Reads as 'this is a long climb' instantly."""
    parts = []
    steps = 9
    for i in range(steps):
        t = i / steps
        y = 88 - i * 8.0
        half = 40 * (1 - t * 0.72)
        parts.append(Part(
            [(50 - half, y), (50 + half, y), (50 + half * 0.88, y - 7), (50 - half * 0.88, y - 7)],
            "metal" if i % 2 else "metal_dark", "ink", 1.8,
        ))
    return parts


def build_campfire():
    return [
        Part([(30, 88), (70, 82)], None, "wood_dark", 4.0, "line"),
        Part([(32, 82), (68, 88)], None, "wood_dark", 4.0, "line"),
        Part([(50, 44), (40, 66), (50, 78), (60, 66)], "hot", "ink", 2.0),
        Part([(50, 54), (44, 68), (50, 76), (56, 68)], "warm", None, 0, "blank"),
    ]


def build_phone():
    return [
        Part(rounded_rect(36, 30, 64, 84, 5), (40, 42, 50), "ink", 2.4),
        Part(rounded_rect(39, 35, 61, 79, 2), "screen", None, 0, "blank"),
        Part(circle(50, 82, 1.8), "metal", None, 0, "blank"),
    ]


def build_clock():
    return [
        Part(circle(50, 50, 32), "paper", "ink", 3.0),
        Part(circle(50, 50, 2.5), "ink", None, 0, "blank"),
        Part([(50, 50), (50, 28)], None, "ink", 3.0, "line"),
        Part([(50, 50), (66, 58)], None, "ink", 2.4, "line"),
    ]


def build_door():
    return [
        Part(rounded_rect(28, 20, 72, 92, 3), "wood", "ink", 2.6),
        Part(rounded_rect(33, 26, 67, 54, 2), "wood_dark", "ink", 1.8),
        Part(circle(64, 62, 3.0), "metal", "ink", 1.8),
    ]


def build_money():
    parts = []
    for i, (dx, dy) in enumerate(((0, 0), (4, -5), (8, -10))):
        parts.append(Part(
            rounded_rect(26 + dx, 48 + dy, 74 + dx, 72 + dy, 2),
            (146, 190, 148) if i == 2 else (122, 168, 126), "ink", 2.0,
        ))
    parts.append(Part(circle(50 + 8, 60 - 10, 7), None, "ink", 2.0, "line"))
    return parts


def build_box():
    return [
        Part([(24, 46), (50, 34), (76, 46), (50, 58)], "wood", "ink", 2.2),
        Part([(24, 46), (24, 80), (50, 92), (50, 58)], "wood_dark", "ink", 2.2),
        Part([(76, 46), (76, 80), (50, 92), (50, 58)], "wood", "ink", 2.2),
    ]


def build_screen():
    """A big presentation screen / TV. For 'here is the data' beats."""
    return [
        Part(rounded_rect(14, 24, 86, 72, 3), (44, 48, 58), "ink", 2.6),
        Part(rounded_rect(18, 28, 82, 68, 2), "screen", None, 0, "blank"),
        Part([(50, 72), (50, 84)], None, "ink", 3.0, "line"),
        Part([(36, 88), (64, 88)], None, "ink", 3.4, "line"),
    ]


def build_plant():
    parts = [Part(rounded_rect(38, 66, 62, 90, 4), (198, 128, 96), "ink", 2.2)]
    for angle, length in ((-38, 34), (-8, 42), (26, 36)):
        import math
        a = math.radians(angle - 90)
        tipx = 50 + length * math.cos(a)
        tipy = 66 + length * math.sin(a)
        parts.append(Part(
            teardrop((50 + tipx) / 2, (66 + tipy) / 2, 9, tipx, tipy),
            (108, 168, 112), "ink", 2.0,
        ))
    return parts


def build_trophy():
    return [
        Part([(34, 26), (66, 26), (60, 58), (40, 58)], (226, 186, 92), "ink", 2.4),
        Part(arc(32, 34, 10, 90, 270), None, "ink", 2.6, "line"),
        Part(arc(68, 34, 10, 270, 450), None, "ink", 2.6, "line"),
        Part(rounded_rect(44, 58, 56, 74, 2), (206, 166, 76), "ink", 2.2),
        Part(rounded_rect(34, 74, 66, 86, 3), (176, 140, 64), "ink", 2.4),
    ]


PROPS = {
    "laptop":   {"build": build_laptop,   "label": "Laptop & desk", "means": "work, deadlines, being online"},
    "stairs":   {"build": build_stairs,   "label": "Staircase",     "means": "effort, a long climb, progress"},
    "campfire": {"build": build_campfire, "label": "Campfire",      "means": "rest, comfort, giving up on plans"},
    "phone":    {"build": build_phone,    "label": "Phone",         "means": "scrolling, messages, distraction"},
    "clock":    {"build": build_clock,    "label": "Clock",         "means": "time pressure, waiting, being late"},
    "door":     {"build": build_door,     "label": "Door",          "means": "leaving, opportunity, avoidance"},
    "money":    {"build": build_money,    "label": "Cash",          "means": "cost, salary, value"},
    "box":      {"build": build_box,      "label": "Box",           "means": "delivery, moving, the unknown"},
    "screen":   {"build": build_screen,   "label": "Presentation",  "means": "data, explaining, proof"},
    "plant":    {"build": build_plant,    "label": "Plant",         "means": "growth, home, calm"},
    "trophy":   {"build": build_trophy,   "label": "Trophy",        "means": "winning, achievement, status"},
}


def prop_names():
    return list(PROPS.keys())


def build_prop(name):
    spec = PROPS.get(name)
    return (spec["build"](), PROP_PALETTE) if spec else (None, PROP_PALETTE)


def prompt_vocabulary() -> str:
    """The prop list, formatted for the storyboard prompt.

    Includes what each prop MEANS, not just its name. Given only names, the
    model picks props that are literally mentioned in the line; given meanings,
    it picks props that visualise the idea — which is the entire point.
    """
    return "\n".join(f'   - "{k}" = {v["label"]}: use for {v["means"]}' for k, v in PROPS.items())


# ── Thought bubble ───────────────────────────────────────────────────────────


def build_thought_bubble(w_ratio=1.0):
    """A thought bubble, drawn in its own 0..100 box.

    Separate from the props table because it is positioned relative to the
    character's head rather than placed on the stage.
    """
    return [
        Part(ellipse(50, 42, 44 * w_ratio, 30), "paper", "ink", 2.4),
        Part(circle(30, 76, 7), "paper", "ink", 2.2),
        Part(circle(20, 90, 4), "paper", "ink", 2.0),
    ]
