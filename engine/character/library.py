"""
library.py — the cast.
======================

Five original characters, each defined as parametric vector data. Nothing here
is traced from or derived from any existing character; the shapes are circles,
ellipses and beziers composed from scratch, so the whole cast is yours to use
commercially with no attribution and nothing to license.

Each character exposes:
    build(expression, mouth, pose) -> (parts, palette)

SLOTS
  "mouth" — swapped every frame from the lip-sync timeline
  "eyes"  — swapped per scene from the emotion in the storyboard
  "brows" — swapped per scene, does most of the emotional work

WHY FIVE
Different content archetypes need different faces. A dark-humour punchline
lands wrong on a pastel capybara, and a wholesome NGO/empathy script lands
wrong on a deadpan skeleton-adjacent character. script_generator.py picks the
cast member to match the archetype it wrote for. See CAST_BY_ARCHETYPE below.

ADDING A CHARACTER
Write a build_<name>() returning (parts, palette), register it in CHARACTERS,
and it is immediately available to the renderer, the admin panel, and the
storyboard prompt — nothing else needs to change.
"""
from .rig import (
    Part, circle, ellipse, rounded_rect, arc, bezier, teardrop, translate, scale_pts, rotate,
)

# ── Shared palettes ──────────────────────────────────────────────────────────

PAL_CAPY = {
    "ink": (58, 44, 38), "body": (183, 141, 105), "body_dark": (156, 116, 84),
    "belly": (214, 181, 148), "blush": (232, 154, 143), "white": (255, 255, 255),
    "bg": (250, 226, 168),
}
PAL_CAT = {
    "ink": (58, 44, 38), "body": (232, 154, 78), "body_dark": (205, 126, 54),
    "belly": (250, 226, 190), "blush": (240, 152, 150), "white": (255, 255, 255),
    "bg": (252, 232, 196),
}
PAL_BIRD = {
    "ink": (36, 40, 44), "body": (94, 140, 146), "body_dark": (70, 112, 118),
    "belly": (232, 106, 140), "blush": (226, 132, 150), "white": (255, 255, 255),
    "beak": (198, 106, 86), "bg": (238, 228, 214),
}
PAL_STICK = {
    "ink": (24, 24, 26), "body": (255, 255, 255), "body_dark": (238, 238, 238),
    "belly": (255, 255, 255), "blush": (240, 160, 160), "white": (255, 255, 255),
    "bg": (250, 214, 42),
}
PAL_SUIT = {
    "ink": (40, 36, 42), "body": (108, 100, 132), "body_dark": (86, 79, 107),
    "belly": (226, 214, 196), "blush": (206, 138, 130), "white": (255, 255, 255),
    "tie": (188, 84, 62), "bg": (244, 240, 232),
}


# ── Mouth shapes (visemes) ───────────────────────────────────────────────────
# Six shapes is the standard minimum set for readable cartoon lip sync. More
# than this is wasted at Shorts scale — nobody is reading lips on a phone; the
# eye only needs to believe the mouth is moving with the audio.


def mouths(cx, cy, s=1.0, ink="ink"):
    """Returns dict of viseme name -> list[Part], centred at (cx, cy)."""
    def sc(pts):
        return [(cx + (x * s), cy + (y * s)) for (x, y) in pts]

    return {
        # closed / silence
        "REST": [Part(sc(arc(0, -2, 4.0, 20, 160)), None, ink, 2.0, "line", "mouth")],
        # m, b, p — pressed lips
        "MBP": [Part(sc(arc(0, 0, 4.6, 10, 170)), None, ink, 2.4, "line", "mouth")],
        # small vowel: e, i
        "EE": [Part(sc(ellipse(0, 0, 4.6, 2.0)), "ink", ink, 1.8, "fill", "mouth")],
        # open vowel: a
        "AA": [Part(sc(ellipse(0, 1, 5.2, 4.4)), "ink", ink, 1.8, "fill", "mouth")],
        # wide open: shouting
        "OH": [Part(sc(ellipse(0, 1.5, 4.2, 5.6)), "ink", ink, 1.8, "fill", "mouth")],
        # rounded: o, u, w
        "OO": [Part(sc(circle(0, 1, 3.2)), "ink", ink, 1.8, "fill", "mouth")],
        # smiling closed — used for happy REST
        "SMILE": [Part(sc(arc(0, -3, 5.4, 25, 155)), None, ink, 2.2, "line", "mouth")],
        "FROWN": [Part(sc(arc(0, 6, 5.0, 200, 340)), None, ink, 2.2, "line", "mouth")],
        "FLAT": [Part(sc([(-4.5, 0), (4.5, 0)]), None, ink, 2.2, "line", "mouth")],
    }


VISEME_ORDER = ["REST", "MBP", "EE", "AA", "OH", "OO"]


# ── Eye sets ─────────────────────────────────────────────────────────────────


def eyes(lx, rx, y, s=1.0, ink="ink", white="white"):
    """Eye variants. Returns dict of name -> list[Part]."""
    def at(cx, pts):
        return [(cx + x * s, y + yy * s) for (x, yy) in pts]

    def both(fn):
        return fn(lx) + fn(rx)

    return {
        "NORMAL": both(lambda cx: [Part(at(cx, circle(0, 0, 3.4)), "ink", None, 0, "blank", "eyes")]),
        "BIG": both(lambda cx: [
            Part(at(cx, circle(0, 0, 5.0)), "ink", None, 0, "blank", "eyes"),
            Part(at(cx, circle(-1.6, -1.8, 1.7)), white, None, 0, "blank", "eyes"),
        ]),
        "HAPPY": both(lambda cx: [Part(at(cx, arc(0, 2, 4.0, 190, 350)), None, ink, 2.2, "line", "eyes")]),
        "CLOSED": both(lambda cx: [Part(at(cx, arc(0, -1, 4.0, 20, 160)), None, ink, 2.2, "line", "eyes")]),
        # heavy upper lid — the deadpan / unimpressed look that carries sarcasm.
        # The lid has to sit visibly ON the eyeball, not floating above it, or
        # it just reads as an eyebrow and the whole expression is lost.
        "DEADPAN": both(lambda cx: [
            Part(at(cx, circle(0, 0, 4.6)), white, ink, 1.9, "fill", "eyes"),
            Part(at(cx, circle(0, 1.4, 2.6)), "ink", None, 0, "blank", "eyes"),
            Part(at(cx, [(-4.9, -1.4), (4.9, -1.4)]), None, ink, 3.0, "line", "eyes"),
        ]),
        "WIDE": both(lambda cx: [
            Part(at(cx, circle(0, 0, 5.4)), white, ink, 1.8, "fill", "eyes"),
            Part(at(cx, circle(0, 0, 2.4)), "ink", None, 0, "blank", "eyes"),
        ]),
        "SAD": both(lambda cx: [
            Part(at(cx, circle(0, 0, 3.8)), "ink", None, 0, "blank", "eyes"),
            Part(at(cx, circle(-1.2, -1.4, 1.4)), white, None, 0, "blank", "eyes"),
        ]),
    }


def brows(lx, rx, y, s=1.0, ink="ink"):
    def at(cx, pts, flip=False):
        return [(cx + (-x if flip else x) * s, y + yy * s) for (x, yy) in pts]

    return {
        "NONE": [],
        "ANGRY": [
            Part(at(lx, [(-4, -2), (4, 1.5)]), None, ink, 2.6, "line", "brows"),
            Part(at(rx, [(-4, -2), (4, 1.5)], True), None, ink, 2.6, "line", "brows"),
        ],
        "SAD": [
            Part(at(lx, [(-4, 1.5), (4, -1.5)]), None, ink, 2.4, "line", "brows"),
            Part(at(rx, [(-4, 1.5), (4, -1.5)], True), None, ink, 2.4, "line", "brows"),
        ],
        "RAISED": [
            Part(at(lx, arc(0, 3, 4.2, 200, 340)), None, ink, 2.2, "line", "brows"),
            Part(at(rx, arc(0, 3, 4.2, 200, 340)), None, ink, 2.2, "line", "brows"),
        ],
        "FLAT": [
            Part(at(lx, [(-4, 0), (4, 0)]), None, ink, 2.4, "line", "brows"),
            Part(at(rx, [(-4, 0), (4, 0)]), None, ink, 2.4, "line", "brows"),
        ],
    }


# ── Character builders ───────────────────────────────────────────────────────


def build_capy(expression="NORMAL", mouth="REST", brow="NONE", pose="idle"):
    """Round, calm, unbothered. The wholesome/relatable workhorse."""
    P = []
    # feet (planted — bob=False so the body bounces above them)
    P.append(Part(ellipse(40, 92, 6.5, 4.0), "body_dark", "ink", 2.0, "fill", None, False))
    P.append(Part(ellipse(60, 92, 6.5, 4.0), "body_dark", "ink", 2.0, "fill", None, False))
    # body
    P.append(Part(rounded_rect(30, 56, 70, 93, 15), "body", "ink", 2.4))
    P.append(Part(ellipse(50, 78, 12, 13), "belly", None, 0, "blank"))
    # arms
    P.append(Part(ellipse(29, 70, 5.5, 9), "body", "ink", 2.2))
    P.append(Part(ellipse(71, 70, 5.5, 9), "body", "ink", 2.2))
    # ears
    P.append(Part(ellipse(31, 21, 6.5, 5.5), "body_dark", "ink", 2.2))
    P.append(Part(ellipse(69, 21, 6.5, 5.5), "body_dark", "ink", 2.2))
    # head
    P.append(Part(ellipse(50, 35, 25, 22, squash_top=0.86), "body", "ink", 2.6))
    # muzzle
    P.append(Part(ellipse(50, 44, 11, 7.5), "belly", None, 0, "blank"))
    # blush
    P.append(Part(ellipse(32, 42, 5.0, 3.2), "blush", None, 0, "blank"))
    P.append(Part(ellipse(68, 42, 5.0, 3.2), "blush", None, 0, "blank"))

    E = eyes(40, 60, 34)
    B = brows(40, 60, 26)
    M = mouths(50, 45, 1.0)
    P += E.get(expression, E["NORMAL"])
    P += B.get(brow, B["NONE"])
    P += M.get(mouth, M["REST"])
    return P, PAL_CAPY


def build_cat(expression="NORMAL", mouth="REST", brow="NONE", pose="idle"):
    """Sharper, more reactive. Good for the character who objects, panics, or
    delivers the punchline against a calmer straight-man."""
    P = []
    # tail
    P.append(Part(bezier((70, 88), (92, 78), (86, 58)), None, "ink", 4.5, "line", None, False))
    P.append(Part(ellipse(38, 93, 6, 3.6), "body_dark", "ink", 2.0, "fill", None, False))
    P.append(Part(ellipse(62, 93, 6, 3.6), "body_dark", "ink", 2.0, "fill", None, False))
    P.append(Part(rounded_rect(32, 58, 68, 94, 14), "body", "ink", 2.4))
    P.append(Part(ellipse(50, 80, 10, 12), "belly", None, 0, "blank"))
    P.append(Part(ellipse(31, 71, 5, 8.5), "body", "ink", 2.2))
    P.append(Part(ellipse(69, 71, 5, 8.5), "body", "ink", 2.2))
    # pointed ears
    P.append(Part([(32, 22), (28, 6), (44, 16)], "body", "ink", 2.4))
    P.append(Part([(68, 22), (72, 6), (56, 16)], "body", "ink", 2.4))
    P.append(Part([(33, 20), (31, 11), (40, 17)], "blush", None, 0, "blank"))
    P.append(Part([(67, 20), (69, 11), (60, 17)], "blush", None, 0, "blank"))
    P.append(Part(ellipse(50, 34, 24, 21, squash_top=0.9), "body", "ink", 2.6))
    P.append(Part(ellipse(50, 43, 10, 6.5), "belly", None, 0, "blank"))
    P.append(Part(ellipse(31, 41, 4.6, 3.0), "blush", None, 0, "blank"))
    P.append(Part(ellipse(69, 41, 4.6, 3.0), "blush", None, 0, "blank"))
    # whiskers
    for sx, d in ((26, -1), (74, 1)):
        P.append(Part([(sx, 40), (sx + d * 8, 38)], None, "ink", 1.6, "line"))
        P.append(Part([(sx, 43), (sx + d * 8, 44)], None, "ink", 1.6, "line"))
    # nose
    P.append(Part([(47.5, 38.5), (52.5, 38.5), (50, 41)], "ink", None, 0, "blank"))

    E = eyes(40, 60, 33)
    B = brows(40, 60, 25)
    M = mouths(50, 45, 1.0)
    P += E.get(expression, E["NORMAL"])
    P += B.get(brow, B["NONE"])
    P += M.get(mouth, M["REST"])
    return P, PAL_CAT


def build_bird(expression="DEADPAN", mouth="FLAT", brow="FLAT", pose="idle"):
    """Small, grumpy, permanently unimpressed. Carries dry wit and dark humour
    without the content itself having to be mean."""
    P = []
    P.append(Part([(42, 95), (36, 99), (48, 99)], "beak", "ink", 1.8, "fill", None, False))
    P.append(Part([(58, 95), (52, 99), (64, 99)], "beak", "ink", 1.8, "fill", None, False))
    P.append(Part(ellipse(50, 68, 24, 27, squash_top=0.92), "body", "ink", 2.6))
    P.append(Part(ellipse(50, 74, 15, 17), "belly", None, 0, "blank"))
    # wings
    P.append(Part(bezier((29, 62), (22, 74), (33, 84)), "body_dark", "ink", 2.2))
    P.append(Part(bezier((71, 62), (78, 74), (67, 84)), "body_dark", "ink", 2.2))
    # head tuft
    P.append(Part(bezier((46, 20), (44, 6), (54, 12)), None, "ink", 3.0, "line"))
    P.append(Part(bezier((52, 19), (56, 7), (60, 15)), None, "ink", 3.0, "line"))
    P.append(Part(ellipse(50, 34, 21, 19), "body", "ink", 2.6))
    P.append(Part(ellipse(32, 40, 4.2, 2.8), "blush", None, 0, "blank"))
    P.append(Part(ellipse(68, 40, 4.2, 2.8), "blush", None, 0, "blank"))

    E = eyes(41, 59, 33)
    B = brows(41, 59, 25)
    P += E.get(expression, E["DEADPAN"])
    P += B.get(brow, B["FLAT"])
    # A beak sits exactly where a mouth would go, so drawing both means the
    # beak covers the mouth and the bird silently never lip-syncs. Instead the
    # beak IS the mouth slot: the upper half is fixed and the lower half
    # swings down by an amount taken from the viseme.
    P += _bird_beak(mouth)
    return P, PAL_BIRD


# How far the lower beak drops for each viseme, in 0..100 units.
_BEAK_OPEN = {
    "REST": 0.0, "FLAT": 0.0, "MBP": 0.0, "SMILE": 0.5, "FROWN": 0.0,
    "EE": 1.6, "OO": 2.8, "AA": 4.6, "OH": 6.2,
}


def _bird_beak(mouth):
    drop = _BEAK_OPEN.get(mouth, 0.0)
    upper = [(50, 39), (42, 45), (58, 45)]
    lower = [(42, 45), (58, 45), (50, 50 + drop)]
    return [
        Part(upper, "beak", "ink", 2.2, "fill", "mouth"),
        Part(lower, "beak", "ink", 2.2, "fill", "mouth"),
    ]


def build_stick(expression="WIDE", mouth="AA", brow="NONE", pose="idle"):
    """Deliberately crude: big head, thin limbs, flat colour. The 'shitpost'
    register — reads instantly at thumbnail size and suits absurd one-liners."""
    P = []
    # Legs hang from the torso base, not from the neck — splaying them from
    # the neck alongside the arms is what makes a stick figure read as an
    # insect instead of a person.
    P.append(Part([(50, 78), (43, 96)], None, "ink", 3.4, "line", None, False))
    P.append(Part([(50, 78), (57, 96)], None, "ink", 3.4, "line", None, False))
    P.append(Part([(50, 58), (50, 79)], None, "ink", 3.8, "line"))
    P.append(Part([(50, 63), (36, 74)], None, "ink", 3.4, "line"))
    P.append(Part([(50, 63), (64, 74)], None, "ink", 3.4, "line"))
    P.append(Part(ellipse(50, 34, 23, 25, squash_top=0.95), "body", "ink", 3.4))

    E = eyes(41, 59, 32, 1.05)
    B = brows(41, 59, 23)
    M = mouths(50, 46, 1.15)
    P += E.get(expression, E["WIDE"])
    P += B.get(brow, B["NONE"])
    P += M.get(mouth, M["AA"])
    return P, PAL_STICK


def build_suit(expression="DEADPAN", mouth="REST", brow="FLAT", pose="mic"):
    """Rounded person in a shirt and tie. The 'explaining something obvious
    with total confidence' character — fits stand-up-style observational bits
    and 'corporate person says the quiet part out loud'."""
    P = []
    P.append(Part([(44, 88), (42, 97)], None, "ink", 3.0, "line", None, False))
    P.append(Part([(56, 88), (58, 97)], None, "ink", 3.0, "line", None, False))
    P.append(Part(ellipse(50, 70, 23, 22, squash_top=0.9), "body", "ink", 2.6))
    P.append(Part([(50, 52), (44, 62), (50, 84), (56, 62)], "belly", "ink", 1.8))
    P.append(Part([(50, 54), (46, 60), (50, 76), (54, 60)], "tie", "ink", 1.6))
    P.append(Part(bezier((28, 66), (22, 78), (34, 86)), "body_dark", "ink", 2.2))
    P.append(Part(ellipse(50, 32, 20, 21, squash_top=0.92), "belly", "ink", 2.6))
    P.append(Part(ellipse(33, 38, 4.2, 2.8), "blush", None, 0, "blank"))

    if pose == "mic":
        # Hand + microphone, held clear of the mouth. Held any closer and the
        # mic head covers the mouth slot, which silently disables the lip sync
        # that is the entire point of this character.
        P.append(Part(bezier((74, 70), (79, 58), (71, 50)), "body_dark", "ink", 2.2))
        P.append(Part(rounded_rect(67, 46, 74, 58, 3), (52, 52, 58), "ink", 2.0))
        P.append(Part(circle(70.5, 43, 6.0), (68, 68, 76), "ink", 2.2))
        P.append(Part(circle(70.5, 43, 3.2), (44, 44, 50), None, 0, "blank"))

    E = eyes(42, 58, 31)
    B = brows(42, 58, 23)
    M = mouths(49, 43, 0.95)
    P += E.get(expression, E["DEADPAN"])
    P += B.get(brow, B["FLAT"])
    P += M.get(mouth, M["REST"])
    return P, PAL_SUIT


# `defaults` is what each character looks like at rest. Without this, build()
# would stamp one global default face onto everyone and every character would
# come out wearing the capybara's neutral expression — which silently erased
# the bird's whole personality (its deadpan is the joke) and dropped the
# comedian's microphone, because those live in per-character defaults.
CHARACTERS = {
    "capy": {
        "build": build_capy, "label": "Capy",
        "desc": "round, calm, unbothered — wholesome and relatable",
        "defaults": {"expression": "NORMAL", "mouth": "SMILE", "brow": "NONE", "pose": "idle"},
    },
    "cat": {
        "build": build_cat, "label": "Mochi",
        "desc": "sharp and reactive — objects, panics, delivers punchlines",
        "defaults": {"expression": "BIG", "mouth": "SMILE", "brow": "NONE", "pose": "idle"},
    },
    "bird": {
        "build": build_bird, "label": "Pip",
        "desc": "small and permanently unimpressed — dry wit, dark humour",
        "defaults": {"expression": "DEADPAN", "mouth": "FLAT", "brow": "FLAT", "pose": "idle"},
    },
    "stick": {
        "build": build_stick, "label": "Doodle",
        "desc": "crude big-head stick figure — absurd one-liners, shitposts",
        "defaults": {"expression": "WIDE", "mouth": "AA", "brow": "NONE", "pose": "idle"},
    },
    "suit": {
        "build": build_suit, "label": "Mr. Fine",
        "desc": "person with a mic — confident observational stand-up",
        "defaults": {"expression": "DEADPAN", "mouth": "REST", "brow": "FLAT", "pose": "mic"},
    },
}

# Which cast member fits which content archetype. script_generator.py reads
# this so the model never has to guess, and so a dark-humour line never lands
# on a pastel capybara by accident.
CAST_BY_ARCHETYPE = {
    "relatable":     ["capy", "cat"],
    "wholesome":     ["capy", "cat"],
    "empathy":       ["capy", "bird"],
    "dark_humour":   ["bird", "stick"],
    "sarcasm":       ["bird", "suit"],
    "absurd":        ["stick", "cat"],
    "observational": ["suit", "bird"],
    "informative":   ["suit", "capy"],
    "myth_busting":  ["suit", "bird"],
    "life_hack":     ["capy", "suit"],
}


def available_characters():
    return list(CHARACTERS.keys())


def character_labels():
    return {k: v["label"] for k, v in CHARACTERS.items()}


def build(name, expression=None, mouth=None, brow=None, pose=None):
    """Builds a character. Any argument left as None falls back to that
    character's own default rather than a shared global one — see the note
    on `defaults` above for why that distinction matters."""
    spec = CHARACTERS.get(name) or CHARACTERS["capy"]
    d = spec["defaults"]
    return spec["build"](
        expression if expression is not None else d["expression"],
        mouth if mouth is not None else d["mouth"],
        brow if brow is not None else d["brow"],
        pose if pose is not None else d["pose"],
    )


def character_defaults(name):
    spec = CHARACTERS.get(name) or CHARACTERS["capy"]
    return dict(spec["defaults"])


def cast_for_archetype(archetype: str):
    return CAST_BY_ARCHETYPE.get(archetype, ["capy", "cat"])
