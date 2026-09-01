# What changed in this version

## New: the third dial

Videos are now defined by **topic × archetype × structure** instead of just
topic. 10 archetypes × 9 structures = **90 distinct video shapes per topic**.

- **10 content archetypes** — unknown facts, myth-busting, daily hacks,
  relatable, wholesome, social/human, dark humour, sarcasm, absurd,
  observational. Each carries its own writing rules *and* its own content
  limits, embedded directly in the prompt.
- **9 narrative structures** — straight, then-vs-now, POV, escalation,
  loop-back, misdirect, two-voices, inner-voice, countdown. Rotated, not
  randomised, so consecutive videos are never the same shape.
- **Hard block** on comedic archetypes over sensitive topics, checked *before*
  the model is called.

## New: the character skit style

A full 2D animation renderer. Five original vector characters who talk with real
lip sync, blink, breathe and react across 10 emotions. Each has its own voice.

Also: 11 props chosen by meaning, a pinned banner for mid-video arrivals,
one-per-video camera push-in, era labels, and mini-scale characters for the
inner-voice device.

Drawn as vector maths, not generated images — identical in every frame forever,
zero cost, no copyright exposure.

## Fixed: every defect found in the sample videos

| Was | Now |
|---|---|
| `186 ,000`, `high -performance` | Word timings come from the TTS engine itself. Whisper removed entirely |
| "fabs" heard as "phabs" | No transcription step, so nothing can be misheard |
| Random b-roll (power plant for a data centre) | AI ranks candidates for relevance |
| Whiteboard icons cramped in a corner | Full width, larger icons, scaled to fill |
| Gold word highlight never rendered | Wired up and working |
| Captions cut mid-sentence | Break at punctuation |

Also removed a 75 MB model download and ~40 seconds from every render.

## Fixed: every warning from the previous session

| Warning | Fix |
|---|---|
| YouTube login expires every 7 days | docs/07 — needs 3 public pages first; `docs-site/` provides them |
| Gemini model name goes stale | Auto-discovers the current model from Google's live list |
| ffmpeg must be installed locally | Render on Actions; clear error message if it's missing |
| Publish-per-run too high | Per-channel caps, stops *before* the API call |
| Supabase 1 GB storage | Cloudflare R2 (10 GB, no egress) + delete-on-terminal-state |
| Topics all off = silent nothing | Health check catches it; validation prevents it |
| `.env` leaking | Nothing but placeholders ships; channels store variable *names* |
| Auto-approve risk | Never overrides a duplicate flag or a quality warning |
| GitHub disables cron after 60 days | Keepalive workflow commits every 10 days automatically |
| edge-tts is unofficial | Falls back to Piper (fully offline) then gTTS |

## New systems

- **Concept ledger** — checks both wording *and* subject matter, refuses repeats
  *before* rendering, records only on publish. Readable `concepts.jsonl` plus a
  database copy.
- **Quality gates** — black frames, silent audio, wrong duration, frozen video,
  caption overflow. Catches the exact black-frame bug from the old build.
- **Alerts** — Telegram and email, three severity levels.
- **Health check** — every morning, attempts a real token refresh.
- **Multi-channel** — unlimited channels, category routing, per-channel quotas.
- **Manual export** — zip with video, thumbnail, captions, hashtags, checklist.
- **Two new dashboard pages** — Channels, Concept Ledger. Sidebar regrouped into
  pipeline order.

## New files

```
engine/archetypes.py          engine/character/rig.py
engine/narrative.py           engine/character/library.py
engine/props.py               engine/character/lipsync.py
engine/concept_memory.py      engine/styles/character_skit.py
engine/quality_gates.py       engine/model_registry.py
engine/alerts.py              engine/channels.py
engine/health_check.py        engine/storage_r2.py
engine/manual_export.py
admin-panel/src/pages/ChannelsPage.jsx
admin-panel/src/pages/ConceptLedger.jsx
.github/workflows/keepalive.yml
.github/workflows/health-check.yml
supabase/migrations/002_channels_and_concepts.sql
docs/00, 06, 07, 08, 09
```

`engine/storage.py` is now a shim forwarding to `storage_r2.py`, so any existing
command still works.


## Corrections to the previous docs

Two mistakes in the first version of these docs, both fixed here:

1. **"Switching OAuth to Production is a 2-minute click"** — wrong. Google
   requires a public home page, privacy policy and terms of service on an
   authorized domain before it will let you publish an External app. The
   `docs-site/` folder now contains all three pages ready to host free on
   GitHub Pages, and docs/07 walks through it.

2. **`python engine/publisher.py --setup`** — wrong command. Running a file
   directly puts `engine/` on the Python path instead of the project root, so
   the `engine.config` import fails. The correct form is
   `python -m engine.publisher --setup`. Every script now also accepts the
   direct form, because making both work beats telling someone they typed it
   wrong.

## New files

```
docs-site/index.html      app home page      } required by Google
docs-site/privacy.html    privacy policy     } before it will let you
docs-site/terms.html      terms of service   } publish to Production
docs-site/_style.css
```
