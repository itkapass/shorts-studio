# 12 — GitHub Actions, explained simply

## What GitHub Actions actually is

GitHub gives you a **free computer in the cloud**. You write a file saying
"run this command at this time," and GitHub rents you a fresh computer,
runs it, and throws the computer away.

That is the whole idea. Your laptop can be off. Your internet can be down.
The videos still get made.

Three things to know:

1. **Every run starts from nothing.** A fresh, empty machine every time.
   That is why every workflow re-installs Python and ffmpeg — it is not
   waste, there is genuinely nothing there.
2. **Nothing survives the run.** Anything the run creates is deleted when it
   ends. That is why videos are uploaded to Supabase storage immediately
   after rendering — if they stayed on the runner, they would vanish.
3. **A workflow is just a text file.** Everything in `.github/workflows/` is
   editable in a text editor. Nothing is hidden.

**Where to look:** your repo → **Actions** tab. Green check = worked.
Red X = broke. Grey = still running.

---

## Your seven workflows

### 1. Add Topics — `add-topics.yml`

**When:** once a day, 07:30 UTC (1:00 PM IST). Plus the "Add Topics Now" button.

**What it does:** asks Gemini to invent new video topics for each of your
channels and saves them into Topic Studio.

**Costs:** 1 Gemini request per channel. Takes about a minute.

**Why it runs at that time:** Gemini's free daily allowance refills at
midnight Pacific, which is 07:00 UTC. Running 30 minutes after that means the
day's video runs always start with a full pool of fresh ideas.

**Why it is separate now:** this used to be bolted onto the front of the
generate run. That meant you could not refill the idea pool without also
rendering videos — and if the render half failed, the topics were never saved
either. Different jobs, different costs, so now different buttons.

---

### 2. Generate Video Drafts — `generate.yml`

**When:** 6 times a day — 08:00, 11:00, 14:00, 17:00, 20:00, 23:00 UTC.
Plus the "Generate Video Now" button.

**What it does:** picks a topic, plans the video, writes the script, generates
the voice, renders the video with ffmpeg, and puts it in your review queue.

**Costs:** 2 Gemini requests per video. Takes about 8 minutes.

**It never publishes anything.** A video made here sits in Pending Review
until you approve it.

**Why those six specific times:** they all sit inside a single Gemini quota
day. The allowance resets at 07:00 UTC, so a run at, say, 04:00 UTC would be
spending the *previous* day's allowance — which is exactly the bug that was
producing zero videos a day. Every run is now safely after the reset.

**Why one video per run and not four:** rendering is the heaviest thing this
project does — ffmpeg, text-to-speech and Whisper captioning, all on a free
shared machine. Two videos in one run doubles how long the job holds that
machine and doubles what you lose if it times out. Six small runs recover from
a failure far better than three big ones: lose a run, lose one video.

---

### 3. Publish Approved Videos — `publish.yml`

**When:** every hour, at 7 past. Plus the "Publish Now" button on any approved
video.

**What it does:** checks whether a channel is due for an upload. If yes,
uploads one approved video to YouTube. If no, exits in about 10 seconds.

**It wakes hourly but does not publish hourly.** The gap between uploads comes
from each channel's daily cap: 4/day becomes one every 6 hours. So most of
these runs do nothing, and that is correct.

**Green check but nothing published** is the normal outcome. Read the log and
you will see a line like:

```
[publish] ⏳ Holding 'Why bridges hum' — last upload was only 94 min ago;
          this channel posts one every 360 min. Next slot in 4h 26m.
```

That is the system working, not failing.

**Publish Now** skips the gap for one specific video. It still respects the
daily cap, because pushing past that returns a YouTube error that burns quota.

---

### 4. Health Check — `health-check.yml`

**When:** once a day.

**What it does:** looks for silent failures — the kind where nothing crashed
but nothing happened either. No videos in three days, storage nearly full,
YouTube credentials expired. Sends you an alert if it finds one.

This exists because the worst failures are the quiet ones. A red X is easy;
a pipeline that runs green every day and produces nothing is not.

---

### 5. Keepalive — `keepalive.yml`

**When:** every 10 days.

**What it does:** makes a tiny commit so the repo looks active.

**Why:** GitHub automatically switches off scheduled workflows in any repo
with no activity for 60 days. Without this, your whole pipeline would silently
stop after two quiet months.

---

### 6. Cleanup Old Storage — `cleanup.yml`

**When:** weekly.

**What it does:** deletes video files that have already been published or
rejected.

**Why:** the free Supabase tier gives you 1 GB. A Short is roughly 5–10 MB, so
without cleanup you would fill it in a few months and renders would start
failing at the upload step.

---

### 7. Test Alerts — `test-alerts.yml`

**When:** only when you press it.

**What it does:** sends a test alert to Telegram and email, and tells you
plainly which ones are not configured.

**Why:** alerts fail silently by design when their secrets are missing — the
alert system cannot alert you that alerting is broken. This is how you check.

---

## Reading a failed run

1. Actions tab → click the red X
2. Click the job name on the left
3. Click the step with the red X to expand it
4. **Scroll to the bottom.** The real error is almost always in the last
   10 lines. Everything above is normal setup noise.

### Errors you are likely to see

| What you see | What it means | What to do |
|---|---|---|
| `429 RESOURCE_EXHAUSTED` + `PerDay` | Today's free Gemini allowance is gone | Nothing. It refills at midnight Pacific. Lower "Daily Video Generation Batch" if it happens every day. |
| `429` + `PerMinute` | Too many requests in one minute | Nothing — it retries itself. |
| `503 UNAVAILABLE` | Gemini is busy right now | Nothing — it retries 4 times automatically. If all 4 fail, press "Generate Video Now" later. |
| `invalid_grant` | Your YouTube login expired | Re-run `python engine/publisher.py --setup` and update the secret. See docs/04. |
| `column "publish_now" does not exist` | You skipped migration 003 | Run `supabase/migrations/003_...sql` in the Supabase SQL Editor. |
| `No videos generated: 18/20 spent` | Quota used up, reported cleanly | Nothing. This is a message, not a crash — the run will be green. |

---

## Running something by hand

**From the dashboard (easiest):** press the buttons in the "Run something now"
panel on the Dashboard or Topic Studio page.

**From GitHub:** Actions tab → pick the workflow on the left → **Run workflow**
button on the right → **Run workflow** again in the dropdown.

Generate Video Drafts has two optional boxes when run by hand:

- **How many videos** — leave blank for normal behaviour, or type a number to
  make exactly that many right now.
- **Skip inventing new topics** — tick this to save Gemini requests when you
  only want to test rendering.

---

## One thing worth understanding

Look at the top of any workflow file and you will see something like:

```yaml
schedule:
  - cron: '0 8,11,14,17,20,23 * * *'
```

That is a **cron expression**. Five fields:

```
minute  hour  day-of-month  month  day-of-week
   0    8,11,...     *        *         *
```

`*` means "every." So this reads: *at minute 0, on hours 8, 11, 14, 17, 20 and
23, every day, every month, every weekday.*

**Cron times are always UTC.** IST is UTC+5:30, so 08:00 UTC is 1:30 PM for
you. This trips people up constantly — and in this project it was not just
confusing, it was the actual bug: the schedule was written in UTC while
Gemini's quota resets on Pacific time, and the seven-hour gap between those two
"days" was quietly destroying every day's output.
