"""
personas.py — a channel is a DOMAIN, not just a routing address.
=================================================================

WHAT THIS CHANGES
Until now, "channel" meant one thing: where a finished video gets uploaded.
What decided WHAT got made was a flat, global pool of topics and a rotation
across all 10 archetypes, with no concept of "this channel is a tech explainer
and that one is a comedy channel" — routing happened only after the fact, by
matching a video's archetype tag.

A persona is the missing piece: a whole content domain — the tech/DevOps/
science explainer, the comedy channel, the top-10/facts channel, the
motivation channel — each with its own subject universe, its own preferred
formats, its own voice, its own writing instructions. Attach a persona to a
channel and the pipeline knows not just where to send finished videos, but
what kind of videos to keep inventing for it, forever.

WHY THIS IS THE RIGHT ABSTRACTION FOR "UNLIMITED CONTENT"
You do not want to type "Kubernetes... Docker... Terraform... hypervisors..."
one topic at a time. You want to say ONCE "explain developer/cloud/infra
concepts to a curious non-expert" and have the app keep inventing new specific
videos inside that domain indefinitely. A persona is exactly that: the seed
list below is not the ceiling, it is a handful of examples of the domain's
SHAPE, handed to topic_synthesizer.py so it knows what "on-domain" means when
it invents the next fifty topics nobody typed.

THE FOUR STARTER PERSONAS
These come directly from your four channels, adjusted in exactly one place —
see the note on `comedy_skits` below.

ADDING YOUR OWN
Copy one of these, change the fields, add it to PERSONAS. It shows up in the
Channels page immediately.
"""

PERSONAS = {
    "tech_science_explainer": {
        "label": "Tech, Science & How Things Work",
        "description": (
            "Explains one real concept per video to a smart non-expert — the kind of "
            "person who is curious but has never had it explained plainly. Covers "
            "software and infrastructure concepts, computing fundamentals, engineering "
            "and manufacturing, physics and biology, and how money, markets and big "
            "companies actually work. Every video answers three things about its subject: "
            "what it actually is, why it exists or was invented, and where you would "
            "actually run into it."
        ),
        "seed_topics": [
            "What Kubernetes actually does and why nobody could agree on a simpler way to run containers at scale",
            "Docker vs a virtual machine — what a container really is underneath",
            "What Terraform does and why 'infrastructure as code' was such a big deal",
            "What a Large Language Model actually is, in plain terms",
            "Retrieval-Augmented Generation (RAG) — why AI models need a memory they don't already have",
            "What NLP is and why understanding language is such a hard problem for a computer",
            "Why new programming languages keep getting invented instead of everyone using one",
            "What a hypervisor is and how one computer pretends to be ten",
            "What virtualization actually means, with a real analogy",
            "Product companies vs service companies — why they make money completely differently",
            "How the stock market actually decides a price — prediction, reaction, or something else",
            "Is investing skill or luck — what separates the two, honestly",
            "Who actually sets the price of gold, and why it moves",
            "How a factory builds something bigger than the factory itself",
            "How a tractor tire is actually made, start to finish",
            "The physics of a nuclear weapon — fission vs fusion, explained conceptually, not technically",
            "Unknown facts about HIV that most people have never been taught",
            "Diseases medicine still can't cure, and why they're so hard to solve",
        ],
        "preferred_archetypes": ["informative", "myth_busting", "life_hack"],
        "preferred_render_style": "stock_footage",
        "preferred_voice": "documentary_male",
        "flavor_instructions": (
            "Write like a sharp engineer explaining their own field to a smart friend outside "
            "it — respect the viewer's intelligence, zero condescension, no filler like 'let's "
            "dive in'. Anchor every abstract concept in one concrete real-world example. If the "
            "subject involves markets, money, or unresolved science, be explicit that some of it "
            "is genuinely debated or uncertain rather than presenting a confident-sounding guess "
            "as settled fact."
        ),
    },

    "comedy_skits": {
        "label": "Comedy, Dark Humour & Life Sketches",
        "description": (
            "Animated character skits and conversations about ordinary life — work, "
            "relationships, group chats, the small absurd rituals everyone recognises. "
            "Dark, deadpan, sarcastic and absurd registers, often landing on a small "
            "moral or observation rather than just a punchline."
        ),
        "seed_topics": [
            "The group chat that never dies but nobody wants to reply to first",
            "What your face actually does during a meeting that could have been an email",
            "The specific lie everyone tells about being 'on their way'",
            "Why saying 'per my last email' is the most violent sentence in the English language",
            "The five stages of realising you replied to the wrong chat",
            "What your houseplants think about how often you remember they exist",
            "The internal negotiation before finally making a dentist appointment",
            "Why the smoke alarm only ever needs a battery at 2am",
        ],
        "preferred_archetypes": ["dark_humour", "sarcasm", "absurd", "observational", "relatable"],
        "preferred_render_style": "character_skit",
        "preferred_voice": "conversational",
        "flavor_instructions": (
            "Deadpan over silly. The joke is recognition, not cruelty. Target situations, "
            "habits and institutions — never a real, identifiable person, country, or "
            "government. If the punchline needs a real-world victim, it is the wrong "
            "punchline; find the version that is funny without one."
        ),
    },

    "top10_and_facts": {
        "label": "Top 10s, Records & Strange True Things",
        "description": (
            "Rankings, records, and the specific true facts people actually trade at "
            "3am — the tallest, the richest, the most sold, the most won, plus the odd "
            "true survival fact and the harmless psychology question everyone secretly "
            "wonders about themselves. No sourcing required beyond public record; "
            "nothing that needs a citation to a paper nobody can check."
        ),
        "seed_topics": [
            "The 10 best-selling cars of all time, and why the top one makes total sense",
            "How tall the tallest man ever recorded actually was, next to things you know the size of",
            "The current 10 richest people alive, and how differently each of them actually got there",
            "Which countries win the most Olympic medals per person, not just in total",
            "What to actually do if lightning strikes near you in a car versus in the open",
            "Insomnia vs just never actually trying to fall asleep on purpose — what's the real difference",
            "The most unusual recurring dream theme people report, and what sleep science actually says about it",
            "Diseases doctors still cannot cure, ranked by how close we've actually gotten",
        ],
        "preferred_archetypes": ["informative", "myth_busting"],
        "preferred_render_style": "stock_footage",
        "preferred_voice": "energetic",
        "flavor_instructions": (
            "Open with the number or the rank immediately — never bury the specific fact "
            "behind a windup. For anything psychological or medical (insomnia, dreams, sleep), "
            "clearly separate what is established science from what is folk wisdom or still "
            "debated, and never present either as medical advice."
        ),
    },


    # ── Personas added beyond the four you specified ────────────────────────
    # You asked me to bring my own. These three are chosen because each one
    # solves a problem the first four don't:
    #
    #  what_if_physics    — the highest-ceiling format on short-form. Real
    #                       science answering an absurd question. Covers your
    #                       Thanos, snow-in-the-Sahara and sun-in-the-Atlantic
    #                       ideas properly: the comedy is the premise, the
    #                       payoff is that the answer is genuinely true.
    #  awareness_comedy   — your "moral through trolling" idea, done in the
    #                       way that actually survives. El Nino, population,
    #                       resource use — landed through absurdity rather
    #                       than lecturing, because nobody shares a lecture.
    #  everyday_origins   — the most sustainable domain of the whole set.
    #                       Every manufactured object on earth is one video,
    #                       it never runs out, it offends nobody, and "why is
    #                       it like that" is the most reliably clickable
    #                       question in existence.

    "what_if_physics": {
        "label": "What If — Real Science, Absurd Questions",
        "description": (
            "Takes a deliberately ridiculous hypothetical and answers it with actual "
            "physics, biology or engineering, following the consequences honestly wherever "
            "they lead. The question is the hook; the fact that the answer is real is the "
            "payoff. Covers pop-culture scenarios, planetary what-ifs, and scale questions "
            "nobody thinks to ask."
        ),
        "seed_topics": [
            "What would actually happen to Earth's ecosystems if half of all life vanished instantly",
            "If it snowed across the Sahara for a week, what would actually change",
            "What would happen if the Atlantic Ocean got direct sunlight at midnight",
            "If everyone on Earth jumped at the same moment, would anything actually happen",
            "What would happen to your body in the ten seconds after stepping onto Mars unprotected",
            "If the Moon disappeared tonight, how long before anyone noticed something wrong",
            "What if every human alive stood in one place — how much land would we actually need",
            "How deep could you dig before something stopped you, and what would stop you",
        ],
        "preferred_archetypes": ["informative", "absurd", "myth_busting"],
        "preferred_render_style": "stock_footage",
        "preferred_voice": "documentary_male",
        "flavor_instructions": (
            "Ask the ridiculous question with a completely straight face, then answer it with "
            "real science and follow the consequences honestly — including the boring or "
            "anticlimactic ones, which are often the funniest part. Never invent numbers to "
            "make the answer more dramatic; the real answer is the whole point, and a made-up "
            "one destroys the format. When referencing a film or comic scenario, describe the "
            "SITUATION generically rather than naming characters or franchises."
        ),
    },

    "awareness_comedy": {
        "label": "Awareness Through Comedy",
        "description": (
            "Real issues — climate patterns, population, water, energy, waste, resource "
            "use — landed through absurdity, exaggeration and comic framing rather than "
            "lecturing. The video is genuinely funny AND the viewer ends up understanding "
            "something real. Nobody shares a lecture; people share a joke that turned out "
            "to be true."
        ),
        "seed_topics": [
            "El Nino explained as one ocean current having a mood swing that ruins everyone's year",
            "Why the population panic and the population-collapse panic are somehow both happening at once",
            "The absurd amount of water hiding inside one cotton t-shirt",
            "Treating your household electricity bill like a crime investigation",
            "Why 'just recycle it' turns out to be the easy half of a much harder problem",
            "The comic scale of how much food gets thrown away before it ever reaches a shop",
            "Explaining carbon footprints as an argument between everyone's daily habits",
            "Why fixing traffic by adding lanes works exactly as well as loosening your belt to lose weight",
        ],
        "preferred_archetypes": ["sarcasm", "absurd", "observational", "myth_busting"],
        "preferred_render_style": "character_skit",
        "preferred_voice": "conversational",
        "flavor_instructions": (
            "The comedy carries the information — it is not decoration on top of a lesson. "
            "Never moralise, never scold the viewer, never end on 'we must all do better'; "
            "that ending is why this genre usually fails. Exaggerate SYSTEMS, scale and "
            "absurd consequences, never a country, ethnicity, or the people affected by a "
            "problem. On population specifically: it is a story about resources, cities and "
            "birth rates, never about any particular nation having 'too many' people. Keep "
            "every underlying fact accurate — a joke built on a wrong number is just "
            "misinformation that got a laugh."
        ),
    },

    "everyday_origins": {
        "label": "Why Ordinary Things Are The Way They Are",
        "description": (
            "The hidden history and engineering logic inside completely ordinary objects "
            "and habits. Why this shape, why this colour, why this standard, who decided, "
            "and what disaster or argument caused it. Effectively inexhaustible — every "
            "manufactured object and social convention on earth is one video."
        ),
        "seed_topics": [
            "Why traffic lights are red, amber and green and not any other three colours",
            "Why keyboards are laid out in an order that seems designed to slow you down",
            "Why almost every shipping container on the planet is the exact same size",
            "Why pencils are yellow, and the marketing decision behind it",
            "Why plug sockets are shaped completely differently in different countries",
            "Why bread is sliced the thickness it is, and the law that once banned slicing it",
            "Why aeroplane windows are round, and what happened when they weren't",
            "Why the tiny hole in an aeroplane window exists and what it is actually doing",
        ],
        "preferred_archetypes": ["informative", "myth_busting", "life_hack"],
        "preferred_render_style": "stock_footage",
        "preferred_voice": "british_calm",
        "flavor_instructions": (
            "Open on the ordinary object as though the viewer has never questioned it, then "
            "reveal that there is a specific reason and it is more interesting than expected. "
            "The best version of this format ends on a genuine 'I will never look at that the "
            "same way' beat. Where the real origin is disputed or the popular story is a myth, "
            "say so plainly — the corrected version is usually the better video anyway."
        ),
    },

    "motivation_and_discipline": {
        "label": "Motivation, Discipline & Wellbeing",
        "description": (
            "Discipline, training, focus, and the mental and physical habits behind them — "
            "explained with a real mechanism, never just an inspirational quote card. Covers "
            "physical training, mental focus, daily discipline, and wellbeing practices with "
            "genuine scientific grounding, kept separate from anything spiritual presented as "
            "unproven fact."
        ),
        "seed_topics": [
            "Why discipline is a skill you build, not a personality trait you either have or don't",
            "What actually happens in your body in the first five minutes of a workout",
            "The real reason most people quit a new habit in the first two weeks, and what actually prevents it",
            "What 'progressive overload' means and why your first month of training isn't supposed to be the hard part",
            "The physiology of stress — what your body is actually doing, and what actually calms it down",
            "Why sleep is a performance tool, not just rest, with the actual mechanism behind it",
            "What meditation measurably does in the brain, separated clearly from claims that aren't proven yet",
            "The difference between motivation and discipline, and why waiting for the first one is the trap",
        ],
        "preferred_archetypes": ["informative", "wholesome", "life_hack"],
        "preferred_render_style": "stock_footage",
        "preferred_voice": "energetic",
        "flavor_instructions": (
            "This is the one persona where flat text cards are a real failure mode — "
            "explicitly avoid quote_card. Ground every claim in an actual mechanism (what "
            "happens in the body or brain), not just an assertion that something works. For "
            "anything spiritual or alternative, say plainly whether it is scientifically "
            "supported or not — do not blur the line for the sake of a cleaner message. "
            "The camera push-in exists for exactly this persona's peak line; use it."
        ),
    },
}

DEFAULT_PERSONA = None  # no persona = today's behaviour, unchanged


def persona_keys():
    return list(PERSONAS.keys())


def get_persona(key: str) -> dict | None:
    return PERSONAS.get(key)


def persona_labels() -> dict:
    return {k: v["label"] for k, v in PERSONAS.items()}


def flavor_prompt_block(persona_key: str) -> str:
    """Persona writing instructions, formatted for the brief/script prompt."""
    p = get_persona(persona_key)
    if not p:
        return ""
    return f"\nCHANNEL VOICE: {p['label']}\n{p['flavor_instructions']}\n"
