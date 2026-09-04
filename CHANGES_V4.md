# v4 — A backup for Gemini, automatic database updates, and knowing what happened

No database migration in this release — everything here is code only.

**Start with `START_HERE_AFTER_DOWNLOAD.md`.**

---

## 1. A free backup when Gemini's quota is genuinely gone

**The problem this solves:** the pipeline was fully dependent on one Gemini
key. When that key's daily allowance ran out — including from a stale
counter left over from an earlier bug — there was no way to test anything,
generate anything, or even confirm a fix worked, until midnight Pacific.
Three days were lost to exactly this.

**What changed:** new `engine/backup_provider.py` calls **Groq**
(groq.com — a hosting company, unrelated to xAI's "Grok"), which has a
genuinely free tier: no card, roughly 14,400 requests a day, OpenAI-compatible
API so no new dependency was needed.

It's wired into the single function every Gemini call in this project already
funnels through (`_call_model_with_clear_errors` in `script_generator.py`),
so topic invention, the creative brief, and storyboard writing are all
covered by one change:

- Gemini is tried first, always.
- A per-minute 429 just retries Gemini — that clears in seconds on its own
  and switching providers over it would be jumping ship too early.
- Only a **confirmed daily** 429 falls through to Groq.
- Leave `GROQ_API_KEY` unset and none of this activates; the pipeline
  behaves exactly as before.

**Every result is honestly tagged.** A `_ModelResponse(text, provider)`
wrapper carries `.provider` ("gemini" or "groq") through the whole call
chain. This project already had a strong opinion about never letting a
fallback pretend to be the real thing — the `persona-auto` vs
`persona-seed-fallback` topic badges are exactly that philosophy — so this
extends the same honesty to a second axis:

- Topic Studio: a distinct 🔁 **AI-invented (Groq backup)** badge, never
  the same ✨ badge Gemini-invented topics get.
- Video Queue: a small badge on any video whose script came from the backup.

See `docs/13_BACKUP_AI_PROVIDER.md` for setup (about 2 minutes) and exactly
what it does and doesn't cover.

---

## 2. Automatic database updates — no more pasting SQL by hand

**The problem this solves:** every update that changed the database ended
with "open Supabase, paste this SQL, press Run." A fine one-time step, a bad
recurring one — it needs remembering every single time, forever, and the one
time it's forgotten, new code silently expects something that was never
created. (This already happened once: `publish_now` didn't exist until it
was manually added.)

**What changed:** new `.github/workflows/deploy-migrations.yml` runs the
Supabase CLI's own migration tool on every push to `main` that touches
`supabase/migrations/`. The CLI tracks which files it's already applied, so
this is always safe to run — new files apply, already-seen ones are skipped.

**One-time setup required** (three GitHub secrets, a bootstrap command to
tell the CLI about migrations already applied by hand): see
`docs/14_AUTOMATIC_MIGRATIONS.md`. After that, a future zip's new migration
file needs nothing but `git push`.

---

## 3. Knowing what actually happened, without opening the dashboard

**The problem this solves:** a green workflow run tells you it didn't crash.
It tells you nothing about what it did. Checking meant leaving GitHub,
opening the dashboard, clicking into Topic Studio or the Video Queue — a lot
of friction for "did that just work?", and exactly the wrong amount of
friction during an actual emergency.

**What changed:** new `engine/step_summary.py` writes straight onto the
GitHub Actions run's own **Summary** tab — the page you're already looking
at when a run finishes:

- **Add Topics**: exactly which topics were added, for which channel, and
  which model invented each one (Gemini, Groq backup, or seed fallback).
- **Generate Video Drafts**: the video's title, channel, format, visual
  style, which AI wrote it, and its quality-gate verdict.

Both also send an optional Telegram alert (if alerts are configured,
docs/08) on genuine success — not just failure — so a real result reaches
you immediately without you having to go look.

---

## Files changed

**New**

```
engine/backup_provider.py                 Groq fallback (OpenAI-compatible, no new dependency)
engine/step_summary.py                    GitHub Actions Summary tab writer
.github/workflows/deploy-migrations.yml   automatic Supabase migration deploy
docs/13_BACKUP_AI_PROVIDER.md
docs/14_AUTOMATIC_MIGRATIONS.md
```

**Changed**

```
engine/script_generator.py    _call_model_with_clear_errors now returns a
                              uniform _ModelResponse(text, provider); falls
                              back to Groq only on a confirmed daily 429,
                              never a per-minute one
engine/topic_synthesizer.py   tags each synthesized topic with its real
                              provider; ensure_persona_topic_pool now
                              returns a rich dict (added/from_gemini/
                              from_groq/from_seed/topics), always the same
                              shape, never a bare int
engine/brief.py               creative_brief._provider recorded
engine/orchestrator.py        writes step-summary + optional alert for both
                              topic top-ups and successful video generation
.github/workflows/
  add-topics.yml, generate.yml, render-on-demand.yml   pass GROQ_API_KEY through
admin-panel/src/pages/
  TopicStudio.jsx    new badge for persona-auto-groq
  VideoQueue.jsx     new badge when a video's script came from the backup
.env.example         documents GROQ_API_KEY / GROQ_MODEL
tools/selfcheck.py   3 new checks: fallback wiring, workflows pass the
                     secret through, migrations stay idempotent
```

---

## Verified before packaging

```
python3 tools/selfcheck.py   -> 10/10 checks pass
cd admin-panel && npx vite build   -> builds clean
```

Plus a direct simulation of the fallback chain (mocked Gemini 429, mocked
Groq response) confirming: a per-day 429 with no Groq key raises a clear
error mentioning docs/13; the same 429 with a Groq key configured returns a
response tagged `provider="groq"`; a per-minute 429 is correctly classified
as retryable rather than falling back; and an ordinary successful Gemini
call is tagged `provider="gemini"`.

---

## Still not done, still your call

- Per-channel Gemini keys from separate Google accounts (docs/10 step 5) —
  not urgent, one key comfortably covers 6 videos/day.
- Per-channel YouTube OAuth for channels 2 and 3.
- Switching channels 2/3 from Manual to Automatic publishing.

None of these block anything today.
