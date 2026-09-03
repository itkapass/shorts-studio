# Shorts Studio — Project Context

**Paste this file plus `yt_shorts_studio_v2.zip` into a new chat to continue
without re-explaining anything.**

---

## What this is

A self-hosted pipeline that writes, renders and publishes YouTube Shorts.
Runs on free tiers only. Owner: itkapass. Repo: `itkapass/shorts-studio`.
Dashboard: `shorts-studio-vert.vercel.app`. Channel handle: `mind_scraping`.

**Flow:** GitHub Actions (cron) → Gemini writes → edge-TTS voices → MoviePy
renders → Supabase/R2 stores → human approves in dashboard → YouTube upload.

---

## Current state (as of this handoff)

**Working:** generation, rendering, publishing to one YouTube channel. Four
videos published. OAuth is in "In production" so tokens no longer expire
weekly. GitHub Pages hosts the required privacy/terms pages.

**Recently fixed, needs verifying on a real run:**
- Gemini quota overrun (was 7 API calls/video against a 20/day free tier)
- `check_duplicate()` signature mismatch that crashed every generation
- `datetime` shadowing that crashed the pipeline on its first line

**Known open items:** "Render in Cloud" returns GitHub API 404 (the
`GITHUB_PAT` needs Actions read+write, and `render-on-demand.yml` must be on
`main`). Some videos sit in "Awaiting Render" and are auto-expired after 3h.

---

## Architecture

```
engine/
  orchestrator.py       main pipeline; the batch loop lives here
  api_budget.py         Gemini daily-quota tracker  ← critical, see below
  script_generator.py   Gemini calls, retries, prompt assembly
  brief.py              STAGE 1: model plans the video before writing it
  personas.py           7 content domains (a "channel theme")
  topic_synthesizer.py  invents new topics inside a persona, forever
  lenses.py             12 question-types that force topic diversity
  narrative.py          9 story structures (loop_back, then_vs_now, POV...)
  archetypes.py         10 content formats + per-format safety guardrails
  pulse.py              current-affairs injection (Google News RSS, free)
  concept_memory.py     duplicate prevention (subject + wording)
  quality_gates.py      rejects broken renders before human review
  voice_engine.py       edge-tts → Piper → gTTS fallback chain
  video_compositor.py   final assembly + captions
  character/            5 original vector characters, lip sync, emotion tint
  styles/               stock_footage | character_skit | whiteboard | quote_card
  channels.py           multi-channel routing
  publisher.py          YouTube upload (--check / --setup)
  alerts.py             Telegram + email (--test)
  health_check.py       daily silent-failure detector
```

**Three-dial content model:** topic × archetype × narrative structure.
10 archetypes × 9 structures = 90 distinct video shapes per topic.

---

## THE CRITICAL CONSTRAINT: Gemini free tier

**~20 requests per day.** This is the binding limit on everything.

Current cost: **2 calls per video** (creative brief + storyboard).
Plus ~1 per persona for topic synthesis.

```
4 videos = 10 calls   OK
8 videos = 18 calls   OK
```

`api_budget.py` reserves before starting a video and hard-stops the run on a
429, rather than failing each video separately. **Any new feature that adds a
Gemini call must be counted against this budget.** A previous version added
per-scene b-roll ranking (5 extra calls/video) and silently broke everything.

429 is NOT retried — it's a daily condition, retrying just burns more quota.
503 IS retried (model busy, usually transient).

---

## Channel themes (personas)

A persona = a whole content domain attached to a channel. Set in
**Channels → Content persona**, or **Settings → Automatic Topic Rotation**.

| Key | Theme |
|---|---|
| `tech_science_explainer` | DevOps, AI, engineering, markets, how things work |
| `comedy_skits` | Animated character skits, dark humour, life comedy |
| `top10_and_facts` | Rankings, records, strange true things |
| `motivation_and_discipline` | Training, focus, wellbeing (never flat quote cards) |
| `what_if_physics` | Absurd hypotheticals answered with real science |
| `awareness_comedy` | Climate/population/resources through comedy, not lecturing |
| `everyday_origins` | Why ordinary objects are the way they are |

Each carries seed topics, preferred archetypes, a render style, a voice, and
its own writing instructions. `topic_synthesizer.py` invents new topics inside
a persona when its unused pool drops below 5. A topic counts as "used" the
moment it produces any video.

---

## Content safety (deliberate, do not weaken casually)

- Each archetype has its own guardrails **embedded in the prompt**, not a
  generic "be responsible" line.
- Comedic archetypes are **blocked before the model is called** on topics
  containing death/war/disaster/abuse markers.
- `pulse.py` screens every news headline before it can reach a prompt —
  blocks deaths, disasters, arrests, crime; for comedy also blocks anything
  about a named individual.
- The `empathy` archetype forbids inventing people, donation appeals, and
  using hardship as a hook.
- Political satire about real governments was deliberately **not** built.
  Population, climate, pop-culture physics and cultural comedy **were**.

---

## Recurring bug patterns in this codebase

Worth knowing, because they've each bitten more than once:

1. **Shadowed imports.** `from datetime import datetime` inside a function
   makes the name local for the *whole* function and breaks earlier uses.
   There's an AST scan in the history that catches these.
2. **Silent `.replace()` failures.** Patching by string match fails silently
   when whitespace differs. Always verify a patch applied.
3. **Signature drift.** A caller passing an argument the callee doesn't
   accept. Broke the duplicate check for days.
4. **Visual bugs are invisible in code.** Overlapping characters, covered
   mouths, misaligned floors — all found by rendering a frame and looking at
   it, never by reading. **For anything visual: render it and look.**

---

## Setup facts (already done, don't redo)

- Supabase, Vercel, GitHub Secrets: configured
- OAuth consent screen: **In production** (no more 7-day expiry)
- Privacy/terms pages: GitHub Pages at `itkapass.github.io/shorts-studio/`
- Storage: Supabase (1GB). Cloudflare R2 (10GB) supported but not set up.
- Alerts: Gmail working; Telegram configured
- `vercel.json` rewrite fixes the 404-on-refresh

**Uploads/day cap: 5, not 6.** YouTube gives 10,000 API units/project/day and
each upload costs 1,600. Quota is per Google Cloud *project*, not per channel —
multiple channels need separate projects to get separate budgets.

---

## Commands

```
python -m engine.publisher --check      what's configured / is YouTube connected
python -m engine.publisher --setup      re-authorize YouTube
python -m engine.alerts --test          send a test alert
python -m engine.health_check           full system check
python -m engine.orchestrator           generate locally
python -m engine.trending               preview trending topics
python -m engine.topic_synthesizer <persona>   preview invented topics
```

---

## Working style that has worked here

- Verify claims against the actual code before trusting them, including my own
  from earlier in a conversation.
- Test visually — render frames and look at them.
- Check that patches actually applied.
- Say plainly when something was my bug rather than smoothing over it.
- Flag when a request would create real risk (platform policy, safety), and
  offer the version that works instead of just refusing.

---

## Owner's goals

Unlimited diverse content across multiple themed channels, each channel one
domain, minimal manual input, high engagement, eventually monetized. Wants
genuinely original ideas contributed, not just their examples implemented.
Learning GitHub/DevOps/AI concepts along the way, so explanations of the *why*
are wanted, not just fixes.
