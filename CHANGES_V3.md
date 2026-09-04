# v3 — Why nothing was generating, and what changed

Everything here was verified against the real codebase and the real GitHub
Actions logs, not written from memory.

**Start with `START_HERE_AFTER_DOWNLOAD.md`.** This file is the "what and why";
that one is the "do this."

---

## The four bugs that stopped the pipeline

### 1. One wrong word crashed every generation run

`engine/orchestrator.py` line 231 read `budget.spent`. The variable created
nine lines above it is called `_default_budget`. A name called `budget` is only
assigned much further down, **inside the video loop** — and Python marks a name
local to the whole function the moment it is assigned anywhere in it. So
reading it early raised `UnboundLocalError`.

The cruel part is *where* it sat: inside the branch that handles "the Gemini
quota is used up." So the single situation that branch existed to report
cleanly was the exact situation that crashed the workflow with exit code 1.

Every red **Generate Video Drafts** run in the Actions tab was this one word.

**Fixed.** It now prints a clear message and exits 0 — running out of a
free-tier allowance is an expected daily event, not something that should show
a red X.

---

### 2. A second undefined name, waiting to bite

`engine/orchestrator.py` line 676, inside `_save_and_finalize()`:

```python
"topic_label": topic.get("category") or None,
```

That function receives `topic_id` — an integer. There is no `topic` in scope.
This is a `NameError` on **every single video insert**, raised only *after* the
full render had already finished. Five minutes of compute, then the video
vanishes instead of reaching the queue.

It was invisible because the quota bugs stopped every run before any render
completed. Fixing the quota alone would have made this fire immediately.

**Fixed.** The label is passed properly as a `topic_label` parameter.

---

### 3. The one that actually cost you every day: UTC vs Pacific

`api_budget.py` keyed its daily counter on the **UTC** date. Gemini's
requests-per-day allowance resets at **midnight Pacific**, which is 07:00 UTC.
Those two "days" are offset by seven hours, and generation ran every 2 hours,
so the offset was hit every single day:

```
00:00 UTC   our counter rolls over to a fresh 20.
            Google still thinks it is YESTERDAY, and yesterday is spent.
00:00-07:00 runs start videos -> real 429 -> hard_stop() pins us to 20/20
            ...and under UTC keying, that pin lasts the whole UTC day.
07:00 UTC   Google's quota genuinely resets to full.
07:00-24:00 every run reads 20/20 and refuses to start, reporting
            "quota exhausted" against a quota that is completely untouched.
```

The first four runs of each day burned an empty allowance; the remaining eight
refused to use a full one.

**The tell** was in your own log: `20/20 Gemini calls used today` sitting next
to `0 made today already`. Those two numbers cannot both be true under normal
spending — only `hard_stop()` sets spend to exactly the budget without making
a video. That is what pointed at the day boundary.

**Fixed.** New `engine/daycycle.py` is the single source of truth for "today,"
and it answers in the timezone Google actually resets in. Nothing else in the
codebase builds a daily key, and `tools/selfcheck.py` fails the build if
anything tries.

---

### 4. Every 429 was treated as fatal for the day

Google returns HTTP 429 for **two different things**: the daily limit, and the
per-minute limit. They need opposite responses — the per-minute one clears in
about thirty seconds.

`is_quota_error()` treated them identically, so one natural burst (topic
synthesis and a storyboard landing in the same minute) would call `hard_stop()`
and throw away a completely intact daily allowance.

**Fixed.** They are now distinguished by the quota ID in the error body
(`...PerDay...` vs `...PerMinute...`), and the retry obeys Google's own
suggested `retryDelay` instead of guessing.

---

## Why channels 2 and 3 never got topics

Migration 002 seeded this:

```sql
INSERT INTO settings (key, value)
SELECT 'auto_topic_personas', 'tech_science_explainer'
```

And `resolve_active_personas()` checked three sources **in priority order,
returning at the first match**, with that setting first — on the reasoning
that "a person set it deliberately."

No person had. The migration had.

So from the moment your database was created, source 1 always matched with
exactly one persona, and source 2 — *personas attached to enabled channels* —
became unreachable dead code. Adding a Comedy channel and a Tamil Quotes
channel had literally no effect on topic invention, forever, and nothing
anywhere reported a problem. The log line
`Using auto_topic_personas setting: ['tech_science_explainer']` read like
correct behaviour.

**Fixed two ways:**

- **Code:** sources are now **unioned, not raced**. Any persona with an enabled
  channel always gets topics — that is what enabling a channel means, and a
  setting should not be able to silently cancel it. The setting can now only
  *add* personas, never remove them.
- **Database:** migration 003 clears the stale seeded value, guarded on the
  exact seeded string so anything you have since typed yourself is untouched.

### Related: topic invention hid its own quota errors

`synthesize_topics()` caught **every** exception including 429 and returned an
empty list, after which the caller quietly filled the pool from the static seed
list. So when quota ran out, the dashboard showed "the AI has stopped inventing
topics" (a content problem) when the truth was "the API key is out of quota"
(an infrastructure problem). Two completely different fixes, and the logs
pointed at neither.

It was also spending **unbudgeted** Gemini calls — real requests the tracker
never counted — so the budget system started every run already wrong about how
much room was left, which is part of how it kept walking into 429s it existed
to prevent.

**Fixed.** Quota errors propagate. Topic synthesis reserves and records its
spend like everything else, against its own channel's key.

---

## Scheduling: rebuilt around how people actually watch

### Publishing is now spread across the day

**Before:** the publish job ran every 30 minutes and uploaded every approved
video the moment it found one. A channel capped at 4/day did not post 4 videos
across the day — it posted all four inside the first two hours, then went
silent for twenty-two.

Four Shorts released minutes apart compete with each other for the same slice
of impressions instead of each getting its own window. And a daily
burst-then-silence pattern is a much more machine-looking signature than a
steady cadence.

**Now:** the gap is **derived** from each channel's daily cap — 4/day becomes
one upload every 6 hours, automatically. Derived rather than configured, so
changing the cap changes the spacing and the two can never drift apart.

The job wakes hourly (down from every 30 min, halving your Actions minutes) and
almost always exits in ten seconds after checking the clock. **A green run that
published nothing is now the normal outcome.**

### Publish Now

New `publish_now` column and a green button on every approved video. It flags
that specific video as a queue-jumper *and* triggers the publish job
immediately — live in a minute or two.

Skips the spacing gap. Still respects the daily cap, because pushing past that
returns a YouTube 403 that burns quota and helps nobody.

### Generation: one video per run, six times a day

Was two videos per run, twelve times a day, around the clock.

- **One per run** because rendering is the heaviest step in the pipeline
  (ffmpeg, TTS, Whisper, on a free shared machine). Two in one job doubles how
  long it holds the runner and doubles what is lost to a timeout. Six small
  runs recover from failure far better than three big ones.
- **08:00, 11:00, 14:00, 17:00, 20:00, 23:00 UTC** because all six sit inside a
  single Gemini quota day, starting an hour after it refills.

### Topics are their own workflow now

New `.github/workflows/add-topics.yml`, daily at 07:30 UTC.

Topic invention used to be bolted onto the front of the generate run, so you
could not refill the idea pool without also spending 2 requests per video and
ten minutes of rendering — and if the render half failed, the topics were never
saved either. Two different jobs with two different costs, so now two buttons.
It skips ffmpeg and Whisper entirely and finishes in about a minute.

### The daily budget now adds up

```
6 videos x 2 requests (creative brief + storyboard)  = 12
3 channels x 1 request for topic invention           =  3
                                                 total 15  of ~20
```

The remaining 5 are deliberate headroom for retries and manual button presses.

---

## Manual controls

New `supabase/functions/trigger-workflow/` edge function and a
`ManualControls` panel on the Dashboard and Topic Studio:

| Button | Time | Cost |
|---|---|---|
| Add Topics Now | ~1 min | 1 Gemini request per channel |
| Generate Video Now | ~8 min | 2 Gemini requests |
| Publish Next Approved | ~1 min | free |

Each shows its time and Gemini cost on the button, so you know what you are
spending before you press it. Each starts a real GitHub Actions run — nothing
happens in the browser.

**Security:** the function has a hardcoded allow-list of workflows. A caller
cannot name an arbitrary file, even a real one in your repo. Passing the name
straight through would mean anyone who could log in could run anything in
`.github/workflows` — including something destructive you add later. The GitHub
token stays server-side as a Supabase secret.

---

## A documentation error worth knowing about

`docs/10` said Gemini's free tier is "about 20 requests a day — but that limit
is *per API key*."

It is **per Google Cloud project**. Three API keys created inside one Google
account share **one** 20/day pool. Making them would have given you nothing and
told you nothing — no error, no warning.

The step-by-step instructions still work, because they tell you to use three
*separate Google accounts*, and separate accounts mean separate projects. Only
the stated reason was wrong. But it is the kind of wrong that costs an
afternoon, so it is corrected in place with a note explaining the difference.

---

## New: `tools/selfcheck.py`

```
python3 tools/selfcheck.py
```

Every bug in this release shared one property: **nothing in the project could
have caught it except a human reading a log after it had already wasted a day
of quota.** Two of them were undefined names — catchable by a static scan in
under a second.

Seven checks:

1. Every Python file parses
2. **No undefined names anywhere in `engine/`** — the check that would have
   caught bugs 1 and 2 instantly
3. No daily counter is built without `daycycle` — guards the fix for bug 3
4. Workflows are valid YAML, and **no generation run is scheduled before 07:00
   UTC** — mechanically prevents re-introducing bug 3
5. Persona/lens/archetype counts, and every persona has a temperature
6. Upload spacing is wired up and actually called (not dead code)
7. Topic persona resolution uses the union form and is budget-aware

Run it before every push.

---

## Files changed

**New**

```
engine/daycycle.py                                one definition of "today"
tools/selfcheck.py                                pre-push checks
.github/workflows/add-topics.yml                  topics as its own job
supabase/migrations/003_scheduling_and_manual_controls.sql
supabase/functions/trigger-workflow/index.ts      manual buttons
admin-panel/src/components/ManualControls.jsx     the button panel
START_HERE_AFTER_DOWNLOAD.md
docs/11_SCHEDULING_AND_MANUAL_CONTROLS.md
docs/12_GITHUB_ACTIONS_EXPLAINED.md
```

**Changed**

```
engine/orchestrator.py        both crash bugs; Pacific keying; budget helper
                              moved above topic synthesis; --topics-only and
                              --skip-topics; per-run cap from settings
engine/api_budget.py          Pacific keying; PerDay vs PerMinute; retry delay
engine/topic_synthesizer.py   union persona resolution; budget-aware; quota
                              errors propagate
engine/channels.py            min_gap_minutes, ready_to_publish,
                              minutes_since_last_publish
engine/publish_approved.py    spacing enforcement; publish_now queue jumpers
.github/workflows/generate.yml    6 runs/day inside one quota day
.github/workflows/publish.yml     hourly wake, spacing decided in code
admin-panel/  Dashboard, TopicStudio, VideoQueue, SettingsPage, index.css
docs/10_THREE_CHANNEL_SETUP.md    per-project correction
requirements.txt              tzdata (Windows needs it for zoneinfo)
```

---

## Still not done, and still your call

- Per-channel Gemini keys from separate Google accounts (docs/10 step 5).
  Not urgent — one key comfortably supports 6 videos/day.
- Per-channel YouTube OAuth for channels 2 and 3.
- Switching channels 2 and 3 from Manual to Automatic publishing.

None of these block anything. The pipeline works on one shared key today.
