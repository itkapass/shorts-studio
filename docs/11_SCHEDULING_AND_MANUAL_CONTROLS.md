# 11 — Scheduling and manual controls

Everything about *when* things happen, and how to override it.

---

## The daily rhythm

| Time (UTC) | Time (IST) | What happens | Gemini cost |
|---|---|---|---|
| 07:00 | 12:30 PM | Gemini's free allowance refills (Google does this, not us) | — |
| 07:30 | 1:00 PM | **Add Topics** — invents fresh topics for every channel | 1 per channel |
| 08:00 | 1:30 PM | **Generate** — one video | 2 |
| 11:00 | 4:30 PM | Generate — one video | 2 |
| 14:00 | 7:30 PM | Generate — one video | 2 |
| 17:00 | 10:30 PM | Generate — one video | 2 |
| 20:00 | 1:30 AM | Generate — one video | 2 |
| 23:00 | 4:30 AM | Generate — one video | 2 |
| every hour | | **Publish** — uploads one video *if a channel is due* | 0 |

**Daily total: 15 of your ~20 free Gemini requests.** The remaining 5 are
deliberate headroom for retries and for pressing the manual buttons.

Generation time does not affect your audience at all — a video made at 4:30 AM
sits in your review queue until you approve it. Only **publish** time affects
reach, and that has its own schedule below.

---

## Why generation runs at those specific hours

Gemini's daily allowance resets at **midnight Pacific = 07:00 UTC**.

All six generation runs sit between 08:00 and 23:00 UTC, which is 01:00 to
16:00 Pacific — comfortably inside one quota day, starting an hour after it
refills.

This is not cosmetic. The old schedule ran every 2 hours around the clock, so
the runs at 00:00, 02:00, 04:00 and 06:00 UTC were still inside Google's
*previous* day and were spending an allowance that was already gone. They got
rejected, the system concluded "quota exhausted," and that conclusion stuck for
the rest of the day — including the many hours when a completely fresh quota
was sitting there unused.

The symptom was a log saying `20/20 Gemini calls used today` next to
`0 made today already`. Those two numbers cannot both be true under normal
spending, which is what gave the bug away.

---

## Why publishing is spaced out

**The old behaviour:** the publish job ran every 30 minutes and uploaded every
approved video it found. So a channel capped at 4 videos/day did not post 4
videos across the day — it posted **all four inside the first two hours**, then
went silent for twenty-two.

That is bad twice over:

1. **Reach.** Shorts are surfaced over hours, not minutes. Four videos released
   minutes apart compete with each other for the same slice of impressions
   instead of each getting its own window. And the channel is invisible for the
   rest of the day.
2. **Pattern.** A burst followed by total silence, at the same time every day,
   is a far more machine-looking signature than a steady cadence.

**The new behaviour:** the gap between uploads is worked out from the channel's
daily cap.

| Daily cap | Gap between uploads |
|---|---|
| 2/day | every 12 hours |
| 3/day | every 8 hours |
| 4/day | every 6 hours |
| 6/day | every 4 hours |

It is **derived**, not configured, so changing the cap changes the spacing
automatically and the two can never drift out of sync.

The job still wakes hourly — that keeps it responsive — but almost every run
just checks the clock, finds the gap has not passed, and exits in about ten
seconds. In the log:

```
[publish] ⏳ Holding 'Why bridges hum' — last upload was only 94 min ago;
          this channel posts one every 360 min. Next slot in 4h 26m.
```

**A green run that published nothing is the normal outcome, not a failure.**

### Overriding the spacing

Settings → **Minimum Gap Between Uploads (minutes)**.

- `0` (the default) means "work it out from the daily cap." Almost always right.
- Any other number forces that exact gap for every channel.

---

## Publish Now

Spacing is right for the robot and wrong for you when something is
time-sensitive. A reaction to today's news is worthless in six hours.

**Video Queue → Approved & Scheduled → green "Publish Now" button.**

It does two things at once: flags that specific video as a queue-jumper, and
starts the publish job immediately. Live in a minute or two.

It skips the spacing gap. It does **not** skip the daily cap — pushing past
that returns a YouTube 403 that burns quota and helps nobody.

---

## The manual buttons

On the **Dashboard** and **Topic Studio** pages:

| Button | What it does | Time | Cost |
|---|---|---|---|
| **Add Topics Now** | Invents fresh topics for every enabled channel | ~1 min | 1 Gemini request per channel |
| **Generate Video Now** | Writes and renders one video into your queue | ~8 min | 2 Gemini requests |
| **Publish Next Approved** | Uploads the next video that is due | ~1 min | free |

Each button starts a real GitHub Actions run — nothing happens in your browser.
You get a "Watch it run" link to follow along.

**Use them for:** testing a change without waiting hours, retrying after a
failure, or filling a gap after a quiet day.

### Setting them up

They need the `trigger-workflow` edge function deployed with a GitHub token.
Full steps are in `START_HERE_AFTER_DOWNLOAD.md` step 3.

Without it, the buttons show a clear error and everything else keeps working —
you just use the Actions tab instead.

**Security note:** the function has a hardcoded list of workflows it is allowed
to start. A caller cannot name an arbitrary file, even a real one in your repo.
The GitHub token stays server-side as a Supabase secret and never reaches the
browser.

---

## Settings reference

| Setting | Default | What it controls |
|---|---|---|
| Daily Video Generation Batch | `6` | Ceiling on videos per day, across all runs |
| Videos Per Run | `1` | How many one scheduled run may render |
| Publish Per Run | `1` | How many uploads per publish wake-up |
| Minimum Gap Between Uploads | `0` | `0` = derive from daily cap |
| Automatic Topic Rotation | *(blank)* | Extra personas on top of your channels |

### Videos Per Run — leave this at 1

Rendering is the heaviest thing this project does: ffmpeg, text-to-speech and
Whisper captioning, all on a free shared machine. Two videos in one run doubles
how long the job holds that machine and doubles what you lose if it times out.

Six small runs recover from failure far better than three big ones. Lose a run,
lose one video.

### Automatic Topic Rotation — leave this blank

Every **enabled channel** already gets topics invented for it automatically.
This box only *adds* extra personas on top, for domains that do not have a
channel yet.

It used to be able to silently switch channels off. It was seeded with the
single value `tech_science_explainer` when your database was created, and the
code treated it as an override that beat everything else — so the Comedy and
Tamil Quotes channels could never get topics no matter how they were configured
on the Channels page, and nothing anywhere reported a problem.

It is now additive only. It can add personas; it can never remove them.

---

## Changing the schedule yourself

Edit the `cron:` line at the top of the workflow file, commit, push.

**Two rules:**

1. **Cron is always UTC.** IST is UTC+5:30. To run at 9 PM IST, write `30 15`.
2. **Keep generation between 08:00 and 23:00 UTC.** Anything earlier lands in
   the previous Gemini quota day and re-creates the bug this release fixed.

`tools/selfcheck.py` enforces rule 2 — it will fail if you schedule a
generation run before 07:00 UTC, and tell you why.

---

## Increasing your capacity

Six videos a day is what one free Gemini key supports. To go higher:

**Option A — separate Google accounts (free).** Gemini's limit is per Google
Cloud **project**, not per API key. Three keys made inside one account share one
20/day pool. Three keys from three *separate Google accounts* give you three
independent pools. See `docs/10` step 5.

**Option B — enable billing (paid).** Removes the daily cap entirely. Be aware
that enabling billing on a project removes its free tier completely, so use a
separate project if you want to keep a free one for testing.
