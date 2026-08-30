"""
narrative.py — the SHAPE of the video, separate from its subject and its tone.
=============================================================================

THE THIRD AXIS
Until now a video was defined by two things: a topic (what it is about) and an
archetype (what kind of video it is). That is not enough. "Office culture" +
"observational" can still be written ten different ways, and which one you pick
is the single biggest lever on whether anyone watches to the end.

So this is the third axis: the STRUCTURE. Not what you say, but the shape you
say it in.

WHY STRUCTURE IS THE HIGHEST-LEVERAGE THING HERE
Short-form retention is not lost gradually, it is lost at specific moments:
  - The first ~1.5 seconds, before anyone has decided to stay.
  - The transition out of the hook, where the video has to prove the hook was
    not a lie.
  - The ~60% mark, where the viewer can already guess the ending.
Every structure below is designed around one or more of those moments. The
`loop_back` one is the most valuable and the least used: if the last line makes
the first line land differently, the video replays seamlessly, and replays
count as views. A 20-second video watched twice beats a 40-second video watched
once, on every metric the algorithm reads.

THE PERSISTENT BANNER
Several structures carry a `banner` — one line pinned to the top for the WHOLE
video ("POV: you accidentally share your screen"). This exists because of how
Shorts are actually consumed: people land mid-video, not at the start. Without
a banner, someone arriving at second nine has no idea what they are looking at
and swipes. With one, they are oriented instantly. It is the cheapest retention
device available and it costs one line of text.

HOW TO ADD ONE
Add an entry to STRUCTURES with `beats` (what each scene must do) and
optionally `banner_template`. It is immediately available to the writer, the
renderer and the admin panel.
"""

STRUCTURES = {
    "straight": {
        "label": "Straight through",
        "blurb": "Hook, build, payoff. The default.",
        "beats": (
            "Scene 1 is a hook that states something surprising and specific. "
            "Scenes 2 to n-1 build the explanation, each one adding information the "
            "previous did not have. The final scene delivers the payoff the hook "
            "promised. Nothing is restated."
        ),
        "banner": False,
    },

    "then_vs_now": {
        "label": "Then vs Now",
        "blurb": "The same situation in two eras, with the power reversed.",
        "beats": (
            "Split the video in half. The first half plays a scenario in one era or "
            "context; the second half plays THE SAME scenario in another, with the "
            "power dynamic reversed. The comedy and the point both come from the "
            "symmetry, so the second half must mirror the first beat for beat — same "
            "setting, same roles, opposite outcome. Label each half on screen with its "
            "era or context using the 'label' field."
        ),
        "banner": False,
        "needs_label": True,
        "min_scenes": 4,
    },

    "pov": {
        "label": "POV scenario",
        "blurb": "A situation the viewer is dropped inside, with a pinned title.",
        "beats": (
            "The whole video is one continuous scene the viewer is inside. Do not "
            "narrate it from outside — write it as it happens, in the moment. Each "
            "scene escalates the discomfort or absurdity of the situation by one step. "
            "The last scene is the worst possible version of it."
        ),
        "banner": True,
        "banner_template": "POV: {situation}",
    },

    "escalation": {
        "label": "Escalating list",
        "blurb": "Three examples, each worse than the last.",
        "beats": (
            "State a premise, then give exactly three examples of it, ordered so each "
            "is more extreme than the one before. The third must be genuinely absurd. "
            "Stop immediately after the third — a fourth example always weakens a "
            "rule-of-three."
        ),
        "banner": False,
    },

    "loop_back": {
        "label": "Loop back",
        "blurb": "The last line makes the first line mean something new.",
        "beats": (
            "Write the ending FIRST, then write an opening line that is innocuous on a "
            "first read and re-reads completely differently once the ending is known. "
            "The final scene must land on or point directly at that opening line, so "
            "the video plays seamlessly if it restarts. Do not explain the connection — "
            "if you have to point it out, it does not work."
        ),
        "banner": False,
        "note": (
            "Highest-value structure available. Shorts autoplay on loop, so a video "
            "that reads correctly on the second pass gets watched twice, and replays "
            "count. Prioritise this."
        ),
    },

    "misdirect": {
        "label": "Misdirect",
        "blurb": "Sets up one expectation, delivers a different one.",
        "beats": (
            "Spend the first 60% building an expectation the viewer is confident about. "
            "The turn happens in one scene and must be a genuine surprise that is also "
            "obvious in hindsight — every detail before it should still make sense "
            "afterwards. The final scene sits in the new reality without commenting on it."
        ),
        "banner": False,
    },

    "two_voices": {
        "label": "Two voices",
        "blurb": "Two characters who want different things.",
        "beats": (
            "Two characters with opposing positions, alternating. Both must be right "
            "about something — a character who only exists to be wrong is boring. The "
            "final line goes to whichever one has been losing the argument."
        ),
        "banner": False,
        "min_characters": 2,
    },

    "inner_voice": {
        "label": "Inner voice",
        "blurb": "One character and the smaller version of themselves.",
        "beats": (
            "One main character and a SMALLER copy of the same character representing "
            "their inner voice. The small one says what the big one will not. Mark the "
            "inner-voice scenes with \"scale\": \"mini\" so it renders smaller. End with "
            "the big one either giving in or refusing."
        ),
        "banner": False,
        "uses_scale": True,
    },

    "countdown": {
        "label": "Countdown",
        "blurb": "Numbered items, worst-to-best or best-to-worst.",
        "beats": (
            "Numbered items counting down. Put the strongest item LAST and say so early "
            "('number one will actually annoy you'), which gives a concrete reason to "
            "stay. Each item is one scene. Never more than five."
        ),
        "banner": True,
        "banner_template": "{count} {subject}",
    },
}

DEFAULT_STRUCTURE = "straight"

# Which structures suit which archetype. The writer is given a shortlist rather
# than the full menu — a countdown does not fit a wholesome beat, and offering
# it anyway just invites a bad pairing.
STRUCTURE_BY_ARCHETYPE = {
    "informative":   ["straight", "misdirect", "countdown", "loop_back"],
    "myth_busting":  ["misdirect", "straight", "then_vs_now"],
    "life_hack":     ["straight", "countdown"],
    "relatable":     ["pov", "loop_back", "inner_voice", "escalation"],
    "wholesome":     ["loop_back", "two_voices", "straight"],
    "empathy":       ["then_vs_now", "straight"],
    "dark_humour":   ["loop_back", "misdirect", "escalation", "then_vs_now"],
    "sarcasm":       ["pov", "escalation", "two_voices"],
    "absurd":        ["escalation", "misdirect", "pov"],
    "observational": ["pov", "escalation", "inner_voice", "two_voices"],
}


def structure_names():
    return list(STRUCTURES.keys())


def get_structure(name: str) -> dict:
    return STRUCTURES.get(name, STRUCTURES[DEFAULT_STRUCTURE])


def structures_for(archetype: str) -> list:
    return STRUCTURE_BY_ARCHETYPE.get(archetype, ["straight", "loop_back"])


def pick_structure(archetype: str, rotation_index: int = 0) -> str:
    """Rotates through the structures that suit an archetype.

    Rotation rather than random choice, deliberately: random repeats itself in
    visible clumps, and three POV videos in a row is exactly what makes a
    channel look automated.
    """
    options = structures_for(archetype)
    return options[rotation_index % len(options)]


def prompt_block(structure: str, num_scenes: int) -> str:
    """The structure's rules, formatted for the storyboard prompt."""
    s = get_structure(structure)
    lines = [f"STRUCTURE: {s['label']} — {s['blurb']}", "", s["beats"]]

    if s.get("note"):
        lines += ["", f"WHY THIS STRUCTURE: {s['note']}"]

    if s.get("banner"):
        lines += [
            "",
            'PINNED BANNER: set a top-level "banner" field — one short line that stays on '
            "screen for the entire video. People land in the middle of Shorts, not at the "
            "start, so this is what orients someone arriving at second nine instead of "
            "second zero. Keep it under 60 characters.",
        ]
        if s.get("banner_template"):
            lines.append(f'   Shape it like: "{s["banner_template"]}"')

    if s.get("needs_label"):
        lines += [
            "",
            'SCENE LABELS: give each scene a "label" field (a year, an era, a context) '
            "shown as a small tag on screen. The two halves must use different labels.",
        ]

    if s.get("uses_scale"):
        lines += [
            "",
            'SCALE: add "scale": "mini" to any scene spoken by the inner voice. It renders '
            "the same character smaller beside the main one, which reads as an inner voice "
            "with no explanation needed.",
        ]

    if s.get("min_scenes") and num_scenes < s["min_scenes"]:
        lines += ["", f"NOTE: this structure needs at least {s['min_scenes']} scenes to work."]

    return "\n".join(lines)


def validate(storyboard: dict, structure: str) -> list:
    """Returns a list of warnings where the storyboard does not honour its
    structure. Warnings, not errors: a slightly-off structure still makes a
    watchable video, and discarding a finished model call over it wastes the
    most expensive step in the pipeline."""
    s = get_structure(structure)
    scenes = storyboard.get("scenes", [])
    out = []

    if s.get("banner") and not storyboard.get("banner"):
        out.append("structure expects a pinned banner but none was written")

    if s.get("needs_label"):
        labels = {sc.get("label") for sc in scenes if sc.get("label")}
        if len(labels) < 2:
            out.append("then_vs_now needs at least two different scene labels")

    if s.get("min_characters", 0) > 1:
        chars = {sc.get("character") for sc in scenes if sc.get("character")}
        if len(chars) < 2:
            out.append("structure needs two characters but only one was used")

    if s.get("uses_scale") and not any(sc.get("scale") == "mini" for sc in scenes):
        out.append("inner_voice structure has no 'mini' scaled scenes")

    return out
