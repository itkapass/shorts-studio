"""
lenses.py — the fix for a problem that would have appeared in about two weeks.
==============================================================================

THE PROBLEM I EXPECT WITHOUT THIS
topic_synthesizer.py currently says, in effect: "here are eight example topics,
invent more like them." That works for the first batch and then quietly rots.
Language models regress toward the centre of whatever you show them, so batch
three looks like batch two, and by batch ten every topic in a persona is the
same SHAPE — usually "how does X work" phrased forty different ways. The
concept ledger will not catch this, because those are genuinely different
subjects. They are just not different VIDEOS.

You asked for unlimited diverse content. Unlimited was already handled.
Diverse was not, and "tell the model to be diverse" does not work — it is the
single least reliable instruction you can give a language model.

THE FIX: FORCE THE QUESTION TYPE, NOT THE SUBJECT
A lens is a KIND of question. "How does a nuclear reactor work" and "who was
harmed building the first nuclear reactor" are the same subject through two
lenses, and they are completely different videos. By assigning each synthesis
request an explicit rotating lens, diversity becomes structural instead of
something we hope the model remembers to do.

This is also where a lot of genuinely good video ideas come from. Most
channels only ever use MECHANISM and SCALE. The interesting ones —
COUNTERFACTUAL, HIDDEN_COST, ORIGIN, EDGE_CASE — are underused because they
take more thought, which is exactly the kind of thing worth automating.
"""

LENSES = {
    "MECHANISM": {
        "label": "How it actually works",
        "question": "What is the actual mechanism, step by step, underneath this?",
        "example": "How a container is different from a virtual machine underneath",
        "good_for": ["tech_science_explainer", "everyday_origins"],
    },
    "ORIGIN": {
        "label": "Why it exists at all",
        "question": "Why does this exist? What problem did someone have that made this necessary?",
        "example": "Why traffic lights are red, green and amber and not any other colours",
        "good_for": ["everyday_origins", "tech_science_explainer", "human_universals"],
    },
    "SCALE": {
        "label": "How big, really",
        "question": "What is the true scale of this, expressed as something a person can picture?",
        "example": "If the internet's daily data were printed, how tall would the stack be",
        "good_for": ["top10_and_facts", "what_if_physics"],
    },
    "COUNTERFACTUAL": {
        "label": "What if it were different",
        "question": "What would actually happen if one specific thing about this changed?",
        "example": "What would actually happen if it snowed across the Sahara for one week",
        "good_for": ["what_if_physics", "awareness_through_comedy"],
    },
    "MISCONCEPTION": {
        "label": "What everyone gets wrong",
        "question": "What does almost everyone believe about this that is not true, and where did that belief come from?",
        "example": "Why 'we only use 10% of our brain' spread so far despite being nonsense",
        "good_for": ["top10_and_facts", "tech_science_explainer", "awareness_through_comedy"],
    },
    "HIDDEN_COST": {
        "label": "What it really costs",
        "question": "What is the real, non-obvious cost of this — in energy, time, land, water, attention, or human effort?",
        "example": "What a single video call actually costs in electricity and cooling water",
        "good_for": ["awareness_through_comedy", "tech_science_explainer"],
    },
    "EDGE_CASE": {
        "label": "Where it breaks",
        "question": "Where does this stop working, and what happens at that boundary?",
        "example": "The altitude where a helicopter simply cannot climb any higher, and why",
        "good_for": ["tech_science_explainer", "what_if_physics"],
    },
    "COMPARISON": {
        "label": "Versus the thing it's confused with",
        "question": "What is this most often confused with, and what actually separates them?",
        "example": "Weather versus climate, and why one cold week proves nothing either way",
        "good_for": ["tech_science_explainer", "awareness_through_comedy"],
    },
    "HUMAN_IMPACT": {
        "label": "Who this actually lands on",
        "question": "Who is actually affected by this, in a specific and concrete way?",
        "example": "What a two-degree shift actually changes for someone who farms rice",
        "good_for": ["awareness_through_comedy", "motivation_and_discipline"],
    },
    "RITUAL": {
        "label": "The thing everyone does",
        "question": "What is the small universal behaviour here that everyone does and nobody has ever discussed?",
        "example": "The specific way every culture signals 'I am leaving now' three times before leaving",
        "good_for": ["human_universals", "comedy_skits"],
    },
    "ABSURD_LOGIC": {
        "label": "Taken completely seriously",
        "question": "What happens if you follow this idea's own logic further than anyone sensible would?",
        "example": "Applying office meeting etiquette rigorously to a family dinner",
        "good_for": ["comedy_skits", "what_if_physics"],
    },
    "REVERSAL": {
        "label": "The opposite is true",
        "question": "In what specific case is the obvious version of this exactly backwards?",
        "example": "The situations where doing nothing is measurably the fastest way to finish",
        "good_for": ["motivation_and_discipline", "comedy_skits", "top10_and_facts"],
    },
}

LENS_KEYS = list(LENSES.keys())


def lenses_for_persona(persona_key: str) -> list:
    """Lenses that suit a persona, best-fit first.

    Every lens stays available to every persona — a lens list that is too
    narrow recreates the exact sameness problem this module exists to solve.
    Suited ones simply come first in the rotation.
    """
    preferred = [k for k, v in LENSES.items() if persona_key in v.get("good_for", [])]
    rest = [k for k in LENS_KEYS if k not in preferred]
    return preferred + rest


def pick_lenses(persona_key: str, count: int, rotation_index: int = 0) -> list:
    """Returns `count` DIFFERENT lenses for one synthesis batch.

    Different within a batch is the point: asking for six topics through one
    lens returns six variations of one video. Asking for six topics through
    six lenses returns six genuinely different videos about the same domain.

    Rotation is deterministic on `rotation_index` (the day) so consecutive
    days start from a different point rather than always leading with the
    same lens.
    """
    ordered = lenses_for_persona(persona_key)
    if not ordered:
        return []
    start = rotation_index % len(ordered)
    rotated = ordered[start:] + ordered[:start]
    return rotated[:max(1, min(count, len(rotated)))]


def prompt_block(lens_keys: list) -> str:
    """Formats an explicit lens assignment for the synthesis prompt."""
    if not lens_keys:
        return ""
    lines = []
    for i, key in enumerate(lens_keys, 1):
        lens = LENSES[key]
        lines.append(
            f"{i}. {lens['label']} — {lens['question']}\n"
            f"   (a topic of this shape looks like: \"{lens['example']}\")"
        )
    return (
        "ONE TOPIC PER LENS. Each numbered lens below is a different KIND of\n"
        "question. Topic 1 must answer lens 1, topic 2 must answer lens 2, and\n"
        "so on. Do not give two topics the same shape.\n\n"
        "This matters more than it looks: without it, every topic drifts into\n"
        '"how does X work", and a channel of forty how-does-X-work videos is\n'
        "indistinguishable from every other automated channel.\n\n"
        + "\n".join(lines)
    )
