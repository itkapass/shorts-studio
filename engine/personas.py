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
            "Explains one real concept per video to a smart non-expert. Software and "
            "infrastructure, computing fundamentals, engineering and manufacturing, physics "
            "and biology, markets and money, general knowledge, grounded 'what if' "
            "futures, and life-admin explainers — the financial and legal machinery adults "
            "are expected to already understand but were never actually taught. Every video "
            "answers what it actually is, why it exists, and where you'd run into it — or, "
            "for a what-if, what would genuinely follow from a real premise."
        ),
        "seed_topics": [
            "What Kubernetes actually does and why nobody could agree on a simpler way to run containers at scale",
            "Docker vs a virtual machine — what a container really is underneath",
            "What Terraform does and why 'infrastructure as code' was such a big deal",
            "What a Large Language Model actually is, in plain terms",
            "Retrieval-Augmented Generation (RAG) — why AI models need a memory they don't already have",
            "Why new programming languages keep getting invented instead of everyone using one",
            "What a hypervisor is and how one computer pretends to be ten",
            "Product companies vs service companies — why they make money completely differently",
            "How a service company like a large IT consultancy actually bills and earns revenue",
            "How the stock market actually decides a price — prediction, reaction, or something else",
            "Is investing skill or luck — what separates the two, honestly",
            "Who actually sets the price of gold, and why it moves",
            "How a factory builds something bigger than the factory itself",
            "How a tractor tire is actually made, start to finish",
            "The physics of a nuclear weapon — fission vs fusion, explained conceptually, not technically",
            "Unknown facts about HIV that most people have never been taught",
            "The oldest technology still in everyday use, and why it never got replaced",
            "A once-dominant piece of technology almost nobody uses today, and why it lost",
            "An ordinary object that is secretly a marvel of engineering nobody thinks about",
            "A famous product launch that was actually a total failure, and what caused it",
            "A company that dominated its market and then collapsed within a decade — what changed",
            "General-knowledge question round: the kind of fact people assume they know and usually get wrong",
            "If AI writes most code within a decade, what would software engineers actually spend their day doing instead",
            "What historical conditions have actually preceded world wars, and whether today matches them",
            "What the world would actually do if crude oil supply seriously dropped tomorrow",
            "Is there a real ceiling on how high gold can go, and what would have to happen to hit it",
            "What a credit score actually measures, and the one factor that moves it the most",
            "How a mortgage payment is actually split between interest and the loan itself, and why that ratio flips over time",
            "What's actually in a rental lease that almost nobody reads before signing",
            "Renting vs buying, worked through as real numbers instead of a vibe",
            "How a car loan is structured, and why the total cost isn't what the sticker implies",
            "What a health insurance premium is actually paying for, and how it gets calculated",
            "How a pension or retirement fund actually grows money over decades",
            "What actually happens, step by step, when you miss a loan payment",
            "How income tax brackets actually work, and the myth of 'earning more pushes you into a worse bracket'",
        ],
        "preferred_archetypes": ["informative", "myth_busting", "life_hack"],
        "preferred_render_style": "stock_footage",
        "preferred_voice": "documentary_male",
        "default_temperature": 0.7,
        "flavor_instructions": (
            "Write like a sharp engineer or analyst explaining their own field to a smart "
            "friend outside it — respect the viewer's intelligence, zero condescension, no "
            "filler like 'let's dive in'. Anchor every abstract concept in one concrete "
            "real-world example.\n"
            "For 'what if' futures (AI and jobs, resource shocks, geopolitical shifts): reason "
            "from real, established mechanisms and say plainly which parts are genuine "
            "uncertainty rather than presenting a guess as a forecast. Never write tactical, "
            "operational, or how-to content about conflict or weapons — the lens is always "
            "'what conditions or incentives lead here', historical and analytical, never "
            "'how it would be carried out'.\n"
            "For markets and money: never state a specific future price or 'will happen' "
            "prediction as fact. Explain the mechanism and the genuine uncertainty."
        ),
    },
    "comedy_skits": {
        "label": "Comedy, Dark Humour & Life Sketches",
        "description": (
            "Animated character skits and conversations about ordinary life. Dark, deadpan, "
            "sarcastic and absurd registers. Fresh, specific jokes — never the joke format "
            "everyone has already seen a hundred versions of. Current-affairs comedy reacting "
            "to what's actually in the news this week, plus evergreen bits about superstition, "
            "health anxiety, overthinking, finding something absurd in a bad situation, and a "
            "pet's-eye-view strand — a cat or bird character's internal monologue narrating "
            "human behaviour it finds baffling."
        ),
        "seed_topics": [
            "The group chat that never dies but nobody wants to reply to first",
            "What your face actually does during a meeting that could have been an email",
            "The specific lie everyone tells about being 'on their way'",
            "The five stages of realising you replied to the wrong chat",
            "The internal negotiation before finally making a dentist appointment",
            "Why the smoke alarm only ever needs a battery at 2am",
            "Googling one symptom and ending up diagnosing yourself with something incurable",
            "The specific logic of being convinced the ceiling fan noise is definitely a ghost",
            "Walking past a temple, mosque, or graveyard just a little faster for no defensible reason",
            "The internal monologue of someone re-reading a text for the ninth time before sending it",
            "Finding a genuinely funny detail in the middle of a day that is going terribly",
            "Explaining a common superstition completely straight-faced as though it were physics",
            "The elaborate mental gymnastics required to justify not going to the gym today",
            "What it's actually like inside the head of someone who is 'fine' and definitely not overthinking this",
            "A cat's internal monologue watching its owner apologise to furniture they walked into",
            "A cat's take on why humans announce they are leaving the house three separate times before actually leaving",
            "A bird's internal monologue watching its owner take a video call sitting inches from actual daylight outside",
            "A cat's genuine confusion about why the human refills a bowl that still has food in it",
            "A pet's-eye-view of what 'we're going to the vet' actually sounds like from the other side of that sentence",
            "A cat's private theory about what the human is actually doing on the glowing rectangle for six hours a day",
        ],
        "preferred_archetypes": ["dark_humour", "sarcasm", "absurd", "observational", "relatable"],
        "preferred_render_style": "character_skit",
        "preferred_voice": "conversational",
        "default_temperature": 1.1,
        "flavor_instructions": (
            "CREATIVITY IS THE WHOLE JOB HERE. Actively avoid the most obvious version of any "
            "joke format — if the setup is one anyone could finish in their head, throw it out "
            "and find the specific, unexpected angle instead. A joke that reads as generic "
            "'AI comedy' has failed at the one thing this persona exists to do.\n"
            "Deadpan over silly. The joke is recognition, not cruelty. Target situations, "
            "habits and institutions — never a real, identifiable person, country, or "
            "government, and never a place or group of people used as shorthand for 'unfunny' "
            "or 'backward' — that is punching down, not writing a joke.\n"
            "Superstition and ghost bits mock the SPIRAL OF LOGIC, never anyone's genuine faith.\n"
            "Health bits are about anxious BEHAVIOUR (googling symptoms, catastrophising), never "
            "about an actual illness, disability, or real patient.\n"
            "'Dirty mind in a bad situation' means finding something absurd or cheeky to laugh "
            "at in chaos — wit, not explicit content; this needs to stay advertiser-friendly.\n"
            "For current-affairs bits: react to what a headline implies, never state it as fact, "
            "never name a real individual. If nothing in the news gives a genuinely fresh angle, "
            "write the evergreen version instead of forcing a topical one.\n"
            "For pet's-eye-view bits: write it as the pet's own first-person internal monologue, "
            "genuinely confused by or judging human behaviour — never a narrator describing the "
            "pet from outside. Use the 'cat' or 'bird' character alone (single-character "
            "monologue, not a conversation). The humour comes from the pet treating an ordinary "
            "human habit as inexplicable, the way an outside observer with different priorities "
            "genuinely would."
        ),
    },


    "quotes_and_poetry": {
        "label": "Tamil Words, Wisdom & Original Lines",
        "description": (
            "Tamil language and culture in short, elegant video-cards — a bold headline, a "
            "thin divider, a small line unpacking its meaning. This is NOT just quotes: it "
            "spans several distinct strands, and Gemini should range freely across all of "
            "them rather than favouring one. AUTHENTIC strands present something real that "
            "already exists in Tamil oral or linguistic tradition: proverbs, tongue twisters, "
            "grandmothers' rhyming sayings, village rhyming folk statements, regional slang, "
            "and words with no clean English equivalent. ORIGINAL strands are new writing in "
            "a poetic register: aphorisms, short poems, haiku. The two must never be confused "
            "— an authentic strand claims to be real and must actually be real; an original "
            "strand claims to be new and must actually be new."
        ),
        "seed_topics": [
            # Authentic — real proverbs, explained
            "The Tamil proverb 'கூரையிலிருந்து விழுந்தவன் குட்டியிலும் விழுந்தான்' and what it actually warns against",
            "The old Tamil saying about a crow and a palm fruit, and the coincidence it describes",
            "A well-known Tamil proverb about patience that most people quote half of without knowing the rest",
            # Authentic — tongue twisters, played as a challenge
            "A classic Tamil tongue twister about a fox and a bell, and why it's nearly impossible to say fast",
            "A traditional Tamil tongue twister built entirely from one repeating consonant sound",
            # Authentic — grandmothers' / village rhyming sayings
            "An old rhyming Tamil saying grandmothers use about rain, and why it rhymes the way it does",
            "A village rhyming saying about the seasons that doesn't survive translation into English",
            "A traditional rhyming warning Tamil parents used before refrigerators existed, about food and the moon",
            # Authentic — regional slang, explained
            "A Tamil slang word for someone who talks a lot without saying anything, and where it likely comes from",
            "A Chennai-specific slang word and the very particular situation it's reserved for",
            "A Tamil word for a very specific kind of stubbornness that has no single English word",
            # Authentic — words with no clean English equivalent
            "A Tamil word for the ache of missing a place rather than a person",
            "A Tamil word that describes a very specific kind of comfortable silence between two people",
            # Authentic — numerals and counting culture
            "How traditional Tamil numerals actually worked before Arabic numerals took over",
            "A traditional Tamil counting rhyme taught to children, and what each line is actually for",
            # Original — new aphorisms, poems, haiku (never copied from an existing work)
            "An original short line about carrying on after being let down by people you trusted",
            "A haiku about the specific ache of missing a version of yourself you used to be",
            "An original aphorism about the cost of being understood by almost no one",
            "A short poem about choosing peace over being right",
            "An original line about the loneliness of being surrounded and still unseen",
            "An original aphorism about growth that looks like loss while it's happening",
        ],
        "preferred_archetypes": ["informative", "wholesome", "myth_busting", "life_hack"],
        "preferred_render_style": "quote_card",
        "preferred_voice": "warm_female",
        "default_temperature": 0.85,
        "flavor_instructions": (
            "TWO DIFFERENT KINDS OF HONESTY REQUIRED HERE, DEPENDING ON THE STRAND:\n"
            "For AUTHENTIC strands (proverb, tongue twister, folk rhyme, slang, numeral fact): "
            "the item presented must be a REAL one that genuinely exists in Tamil tradition or "
            "usage. Never invent a saying and present it as an old proverb or traditional "
            "rhyme — that is fabricating cultural heritage and passing it off as real, which is "
            "a form of misinformation, not creative writing. If you are not confident something "
            "is genuinely traditional, do not present it as traditional — pick a different, "
            "well-established example instead, or write it as an ORIGINAL line instead and "
            "label it that way.\n"
            "For ORIGINAL strands (aphorism, poem, haiku): the line must be genuinely new "
            "writing — never quote, adapt, or lightly reword an existing poem, song lyric, or "
            "famous quotation, even one out of copyright.\n"
            "NAMING FOR DUPLICATE PREVENTION: always name the topic around the SPECIFIC item "
            "— quote or closely paraphrase the actual proverb/word/phrase in the topic name "
            "itself, not just 'a Tamil proverb about patience'. A vague topic name lets the "
            "same real proverb get selected again later under different wording; naming the "
            "specific item is what makes repeat detection actually work.\n"
            "One idea per card, stated once. The elaboration line explains the FEELING or "
            "MEANING behind the headline — for authentic strands, this is where the real "
            "translation or cultural context goes; it never just restates the headline in "
            "other words."
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
        "default_temperature": 0.75,  # real facts/rankings — precision over flourish
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
        "default_temperature": 0.85,  # creative premise, but the physics must stay real
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
        "default_temperature": 1.0,  # comedy-led, but the underlying facts must stay accurate
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
        "default_temperature": 0.7,  # historical/factual explainer — precision over flourish
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
        "default_temperature": 0.8,  # needs real conviction, but grounded in real mechanisms
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
