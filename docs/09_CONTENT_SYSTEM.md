# 09 — How the content system works

This explains the three dials that decide what a video actually is, and how to
use them. Read this before you start tuning anything — it's the difference
between "the app makes videos" and "the app makes videos you'd actually watch".

---

## The three dials

A video is defined by three independent choices:

```
   TOPIC            ARCHETYPE              STRUCTURE
   what it's about  what kind of video     what shape it takes
   "deep sea"    ×  "myth vs fact"      ×  "misdirect"
```

Most automated video tools only have the first dial. That's why their output all
feels the same: same topic list, same voice, same shape, every day. Three dials
gives you 10 archetypes × 8 structures = **80 distinct video shapes per topic**,
before the writing even starts.

---

## Dial 1 — Topic

What the video is about. Managed in **Topic Studio**, or added on the fly in
**Concept Ledger → Add a topic**.

You can paste a reference link when adding a topic. That link is used *only* to
point the writer at the subject area. It writes something original in that
territory — it does not summarise or re-voice the linked video.

> **Why that distinction matters:** re-voicing another creator's script is a
> copyright problem, and it's exactly the "reused content" pattern that gets
> channels demonetised. Inspiration is a subject area. Copying is a script.

---

## Dial 2 — Archetype (what kind of video)

Ten formats. Each carries its own writing rules **and its own content limits**.

| Archetype | What it is | Default look |
|---|---|---|
| **Unknown Facts** | A surprising true thing, explained fast | Stock footage |
| **Myth vs Fact** | A widely believed thing that isn't true | Stock footage |
| **Daily Hacks** | A small practical thing for daily life | Stock footage |
| **Relatable** | The universal experience nobody says out loud | Character skit |
| **Wholesome** | Warm, gentle, quietly encouraging | Character skit |
| **Social & Human** | Poverty, inequality, hardship — handled with care | Stock footage |
| **Dark Humour** | Bleak, deadpan, funny about how things are | Character skit |
| **Sarcasm** | Saying the opposite, obviously | Character skit |
| **Absurd** | A stupid premise followed with total commitment | Character skit |
| **Observational** | Stand-up style: noticing what everyone does | Character skit |

### The guardrails are part of the format, not bolted on

Each archetype's content limits go into the prompt **with** its writing rules.
This is deliberate. A generic "be responsible" instruction is weak and easy to
write around. A rule attached to a specific format is concrete and holds:

> *Dark humour:* target situations, systems, institutions and the absurdity of
> being alive — never real people, identifiable groups, actual tragedies, or
> anyone's suffering. Nothing about self-harm, suicide, eating disorders or
> addiction, in any framing. If the punchline needs a victim, it's the wrong
> punchline.

**Social & Human has the strictest rules of all**, because that's exactly where
automated content goes wrong — it slides into poverty tourism, invented sob
stories, or fake charity appeals. So: never invent a person and present them as
real, never ask for donations or name a charity, never use hardship as a shock
hook, never imply poverty is a personal failing.

### Sensitive topics can't be paired with comedy

There's a hard block: comedic archetypes are refused on topics containing
markers like death, suicide, abuse, war, famine, disaster.

The check runs **before** the model is called, not after. The reliable way to
avoid a joke about a famine is to never ask for one — filtering afterwards means
the text existed, and eventually something ships it.

---

## Dial 3 — Structure (what shape it takes)

This is the dial nobody else has, and it's the highest-leverage one.

Short-form retention isn't lost gradually. It's lost at three specific moments:
the first 1.5 seconds, the transition out of the hook, and around the 60% mark
where the viewer can guess the ending. Every structure is built around those.

| Structure | Shape |
|---|---|
| **Straight through** | Hook → build → payoff. The default |
| **Then vs Now** | Same scenario in two eras, power reversed |
| **POV scenario** | Viewer dropped inside a situation, pinned title |
| **Escalating list** | Three examples, each worse than the last |
| **Loop back** | The last line makes the first line mean something new |
| **Misdirect** | Builds one expectation, delivers another |
| **Two voices** | Two characters who want different things |
| **Inner voice** | A character and a smaller copy of themselves |
| **Countdown** | Numbered items, strongest last |

### Loop back is the one to prioritise

Shorts autoplay on a loop. If your last line makes the first line land
differently, the video replays seamlessly — and **replays count as views**.

A 20-second video watched twice beats a 40-second video watched once on every
metric the algorithm reads. This structure is heavily under-used because it's
hard to write, and it's exactly the kind of thing a model with an explicit
instruction is good at.

### Structures rotate, they don't randomise

Random selection repeats itself in visible clumps. Three POV videos in a row is
precisely what makes a channel look automated. The rotation is deterministic, so
consecutive videos are always different shapes.

---

## The visual layer

### Render styles

| Style | What it looks like |
|---|---|
| **Character Skit** | 2D animated characters who talk, blink, react |
| **Stock Footage** | Real b-roll from Pexels with a slow zoom |
| **Whiteboard Sketch** | A hand-drawn diagram that builds as it's explained |
| **Quote Card** | Minimal drifting gradient, captions carry everything |

### The cast

Five original characters, drawn as vector maths rather than generated images:

| Character | Personality | Suits |
|---|---|---|
| **Capy** | Round, calm, unbothered | Wholesome, relatable |
| **Mochi** (cat) | Sharp, reactive | Punchlines, objecting |
| **Pip** (bird) | Permanently unimpressed | Dry wit, dark humour |
| **Doodle** (stick figure) | Crude, big-headed | Absurd one-liners |
| **Mr. Fine** (with mic) | Confidently explaining the obvious | Observational |

**Why drawn and not AI-generated:** consistency. Ask any image model for "the
same cat again" and you get a different cat. These are identical in every frame
of every video, forever, at zero cost, with no copyright exposure — nothing here
is traced from or derived from anyone else's character.

The honest trade-off: this is clean flat-vector cartooning. It won't produce
painterly illustration. That's the right ceiling for short-form, where
readability at thumbnail size beats detail.

Each character has its own voice, so a two-hander sounds like two people.

### Props

A character alone on a stage is a talking head. A character standing next to the
thing they're talking about is a scene.

Eleven props — laptop, stairs, campfire, phone, clock, door, cash, box,
presentation screen, plant, trophy — chosen by **meaning**, not by words
literally in the line. A character at the bottom of a staircase reads as "this
is hard" before a word is spoken.

### Camera and screen furniture

- **Push-in** — a slow zoom toward the speaker, allowed on **at most one scene**
  per video. Used everywhere it means nothing and induces nausea. Used once, on
  the turn, it signals "this line matters" without saying so.
- **Pinned banner** — one line held on screen for the whole video ("POV: ...").
  This exists because people land in the *middle* of Shorts, not at the start.
  Someone arriving at second nine with no banner has no idea what they're
  watching and swipes. Cheapest retention device available.
- **Era labels** — small tags for Then-vs-Now comparisons.
- **Mini scale** — a smaller copy of the same character reads instantly as an
  inner voice, with no explanation needed.

---

## Captions

- Break at **punctuation**, not every N words, so each card is a readable
  fragment.
- The word currently being spoken is **highlighted in gold**. The moving
  highlight is what makes short-form captions feel alive rather than like a
  subtitle track, and the eye tracks the moving element.
- Timings come from the **TTS engine itself**, not from transcribing the audio
  back. That's why numbers and hyphenated words stay intact and nothing gets
  misheard.
- Highlight is off for character skits — the animated face is already the moving
  thing on screen, and two competing movements is worse than one.

---

## What happens each run

```
1.  Pick topic, archetype, structure   (structure rotates)
2.  Load the concept ledger            (everything already made)
3.  Write the storyboard               (rules + limits + avoid-list)
4.  Check for repeats                  → skip BEFORE rendering
5.  Generate voice                     (per-character for skits)
6.  Render                             (~5 min for 45 seconds)
7.  Quality gates                      → reject broken ones automatically
8.  Upload to storage, queue for you
9.  You approve / reject / export
10. Publish → record concept → delete file
```

Steps 4 and 7 exist so that by the time a video reaches you, it's neither a
repeat nor mechanically broken. **Your review is for judging whether it's
*good*** — the part no automated check can do.

---

## The honest bit about volume

You asked for 2 videos per topic per day. The capacity is built.

But the concept ledger will start refusing generations once a topic's genuinely
distinct angles are used up, and **that's it working correctly, not breaking**.
Forcing volume past that point is precisely the pattern that triggers YouTube's
inauthentic-content review.

The lever that actually works is fewer, sharper videos with real retention.
Ten strong videos a week will outperform sixty repetitive ones, and won't put
your channel at risk.
