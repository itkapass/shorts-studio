"""
archetypes.py — what KIND of video to make.
===========================================

A topic ("the deep sea") is not a video. The same topic makes ten different
videos depending on the angle: an unknown-fact drop, a myth correction, a
two-character joke, a quiet emotional beat. That angle is the archetype, and it
is the single biggest lever on whether a video gets watched.

WHY THIS IS ITS OWN MODULE
It is read by four places that must never disagree:
  - script_generator.py  — for the writing rules in the prompt
  - channels.py          — for routing videos to channels by category
  - concept_memory.py    — for tracking which angles are used up
  - the admin panel      — for the category filters and per-archetype counts
One definition, four consumers, no drift.

CONTENT SAFETY IS PART OF THE ARCHETYPE, NOT A SEPARATE FILTER
Each archetype carries its own `guardrails` string that goes into the prompt.
This is deliberate. A generic "be responsible" instruction is weak and easy for
a model to write around. A rule attached to the specific format — "dark humour
targets situations, institutions and the absurdity of being alive, never real
people, groups, tragedies or anyone's suffering" — is concrete and holds.

The empathy/social archetype has the strictest rules of all, because content
about poverty and hardship is exactly where automated video goes wrong: it
slides into poverty tourism, invented sob stories, or fake charity appeals. The
guardrails there forbid inventing individuals, forbid any call to donate, and
require that the subject be treated as a person rather than a prop.
"""

ARCHETYPES = {
    "informative": {
        "label": "Unknown Facts",
        "blurb": "A genuinely surprising true thing, explained fast.",
        "default_style": "stock_footage",
        "voice": "documentary_male",
        "rules": (
            "Lead with the single most surprising true detail, then explain WHY it is true. "
            "The explanation is the payoff — a fact with no mechanism behind it is trivia and "
            "viewers do not rewatch trivia. Use concrete numbers and physical comparisons."
        ),
        "guardrails": (
            "Every claim must be something you are confident is established public knowledge. "
            "If you are not sure a number is right, use a qualitative comparison instead of "
            "inventing a figure. Never attribute an invented statistic to a real company, "
            "institution or person."
        ),
    },
    "myth_busting": {
        "label": "Myth vs Fact",
        "blurb": "A widely believed thing that is not true, corrected.",
        "default_style": "stock_footage",
        "voice": "conversational",
        "rules": (
            "State the myth plainly first, in the words people actually use for it. Then correct "
            "it and explain where the belief came from — the origin is what makes this format "
            "satisfying rather than smug. End on what IS true."
        ),
        "guardrails": (
            "The myth must be labelled as a myth within the first two scenes, never left standing "
            "unqualified. Do not 'bust' anything genuinely contested by experts — pick things with "
            "settled answers. Never present a fringe position as the correction. Avoid medical, "
            "legal and financial myths entirely: being wrong there causes real harm."
        ),
    },
    "life_hack": {
        "label": "Daily Hacks",
        "blurb": "A small practical thing that makes a daily routine easier.",
        "default_style": "stock_footage",
        "voice": "conversational",
        "rules": (
            "One hack per video, shown as a concrete before-and-after. Say why it works, not just "
            "what to do — the mechanism is what makes someone remember it. It must be something a "
            "person could actually do today with things they already own."
        ),
        "guardrails": (
            "No hack involving electricity, gas, medication, dosages, food safety, driving, or "
            "anything that could injure someone if it went wrong. No 'life hacks' that are really "
            "just product ads. If a hack has a common failure mode, say so."
        ),
    },
    "relatable": {
        "label": "Relatable",
        "blurb": "The small universal experience nobody says out loud.",
        "default_style": "character_skit",
        "voice": "young_casual",
        "rules": (
            "Find the specific version of a universal feeling. 'Being tired' is nothing; 'the way "
            "you rehearse a phone call before making it' is the video. Two characters work best: "
            "one does the thing, the other reacts."
        ),
        "guardrails": (
            "Relatable does not mean mocking. The joke is recognition, not the person. Nothing "
            "that punches at a group, a body type, a class, or a nationality."
        ),
    },
    "wholesome": {
        "label": "Wholesome",
        "blurb": "Warm, gentle, quietly encouraging.",
        "default_style": "character_skit",
        "voice": "warm_female",
        "rules": (
            "Small and specific beats big and sweeping. One small kind moment lands; a general "
            "statement about kindness does not. Earn the warmth — do not just assert it."
        ),
        "guardrails": (
            "No toxic positivity, and never imply that someone's difficulty is their own fault for "
            "not thinking positively. Do not give mental health advice or present a feeling as a "
            "diagnosis."
        ),
    },
    "empathy": {
        "label": "Social & Human",
        "blurb": "Poverty, inequality, hardship — treated with care.",
        "default_style": "stock_footage",
        "voice": "british_calm",
        "rules": (
            "Explain a system or a structural reality, not an individual's misery. The viewer "
            "should come away understanding something they did not before, not just feeling bad. "
            "Concrete and specific; no sweeping generalisations about any country or group."
        ),
        "guardrails": (
            "THIS ARCHETYPE HAS THE STRICTEST RULES. Never invent a person, a family, or a story "
            "and present it as real. Never ask for donations or name a charity — you cannot verify "
            "one and a fraudulent appeal is a serious harm. Never use anyone's hardship as a "
            "punchline or a shock hook. Do not imply poverty is a personal failing. Do not name "
            "real living individuals. If the topic cannot be handled without a real person's "
            "story, choose a different angle."
        ),
    },
    "dark_humour": {
        "label": "Dark Humour",
        "blurb": "Bleak, deadpan, funny about how things actually are.",
        "default_style": "character_skit",
        "voice": "british_calm",
        "rules": (
            "The humour comes from stating an uncomfortable truth flatly and refusing to soften "
            "it. Deadpan delivery, no wink. Short. The bleakness is the joke; cruelty is not."
        ),
        "guardrails": (
            "Target situations, systems, institutions and the general absurdity of being alive — "
            "NEVER real people, identifiable groups, protected characteristics, actual tragedies, "
            "recent deaths, or anyone's suffering. Nothing about self-harm, suicide, eating "
            "disorders, or addiction, in any framing, including as a joke. If the punchline needs "
            "a victim, it is the wrong punchline."
        ),
    },
    "sarcasm": {
        "label": "Sarcasm",
        "blurb": "Saying the opposite, obviously, about something absurd.",
        "default_style": "character_skit",
        "voice": "british_calm",
        "rules": (
            "Pick something genuinely absurd and praise it with total sincerity. The gap between "
            "the tone and the content does all the work. Never break character to explain the joke."
        ),
        "guardrails": (
            "Sarcasm about a factual claim can be mistaken for the claim itself when clipped or "
            "screenshotted. Never be sarcastic about health, safety, science, or anything where "
            "someone acting on the literal reading could be harmed."
        ),
    },
    "absurd": {
        "label": "Absurd",
        "blurb": "A stupid premise followed with total commitment.",
        "default_style": "character_skit",
        "voice": "energetic",
        "rules": (
            "One absurd premise, played completely straight and escalated. The comedy is in the "
            "commitment, not in signalling that it is silly. Escalate three times, then stop."
        ),
        "guardrails": (
            "Absurd claims must be self-evidently absurd, never plausible-sounding misinformation. "
            "No absurdist framing of real events."
        ),
    },
    "observational": {
        "label": "Observational",
        "blurb": "Stand-up style: noticing the thing everyone does.",
        "default_style": "character_skit",
        "voice": "documentary_male",
        "rules": (
            "Open on the observation, immediately. No 'have you ever noticed'. Give a specific "
            "example, then a second one that escalates. End on the sharpest version."
        ),
        "guardrails": (
            "Observations about behaviour, not about groups of people. 'People do X' is fine; "
            "'[group] does X' is not."
        ),
    },
}

DEFAULT_ARCHETYPE = "informative"

# Archetypes that read better as animated dialogue than as narration over
# footage. The orchestrator uses this when a topic does not pin a style.
DIALOGUE_ARCHETYPES = {"relatable", "wholesome", "dark_humour", "sarcasm", "absurd", "observational"}

# Topics too sensitive to pair with a comedic archetype. Checked before
# generation, so the combination never reaches the model at all.
SENSITIVE_TOPIC_MARKERS = (
    "death", "suicide", "abuse", "war", "genocide", "famine", "disease",
    "cancer", "addiction", "trafficking", "refugee", "disaster", "shooting",
    "assault", "poverty", "starvation", "terror",
)
COMEDIC_ARCHETYPES = {"dark_humour", "sarcasm", "absurd", "relatable"}


def archetype_names():
    return list(ARCHETYPES.keys())


def get_archetype(name: str) -> dict:
    return ARCHETYPES.get(name, ARCHETYPES[DEFAULT_ARCHETYPE])


def is_combination_allowed(topic_text: str, archetype: str) -> tuple:
    """Blocks comedic archetypes on sensitive subjects.

    Returns (allowed, reason). This runs BEFORE the model is called, because
    the reliable way to avoid a joke about a famine is to never ask for one.
    Filtering afterwards means the text existed, and something eventually
    ships it.
    """
    if archetype not in COMEDIC_ARCHETYPES:
        return True, ""
    low = (topic_text or "").lower()
    for marker in SENSITIVE_TOPIC_MARKERS:
        if marker in low:
            return False, (
                f"'{marker}' is too sensitive to pair with the "
                f"'{ARCHETYPES.get(archetype, {}).get('label', archetype)}' format."
            )
    return True, ""


def suggest_style(archetype: str, fallback: str = "stock_footage") -> str:
    return get_archetype(archetype).get("default_style", fallback)


def prompt_block(archetype: str) -> str:
    """The archetype's writing rules and guardrails, formatted for the prompt."""
    a = get_archetype(archetype)
    return (
        f"CONTENT FORMAT: {a['label']} — {a['blurb']}\n\n"
        f"HOW TO WRITE THIS FORMAT:\n{a['rules']}\n\n"
        f"NON-NEGOTIABLE LIMITS FOR THIS FORMAT:\n{a['guardrails']}"
    )
