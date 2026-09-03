# Setting up your 3 channels — start to finish

Follow these in order. Each one builds on the last.

---

## Step 1: Update your code (5 min)

1. Unzip the new download.
2. Copy everything into your project folder, overwriting old files. Keep your `.env` if you have one.
3. Open a terminal in that folder:
   ```
   git add -A
   git commit -m "3 channels + duplicate-check fix + spread scheduling"
   git push
   ```

## Step 2: Run the database migration (2 min)

1. Supabase → your project → **SQL Editor** → **New query**
2. Open `supabase/migrations/002_channels_and_concepts.sql`, copy **all** of it, paste it in
3. Click **Run**. Expect: `Success. No rows returned.`
4. Safe to run again anytime — it only adds things, never deletes.

## Step 3: Redeploy your dashboard (2 min)

Vercel → your project → **Deployments** → **⋯** on the top one → **Redeploy**

Wait a minute, then open your dashboard. You should now see topic badges showing when each was created and where it came from.

---

## Step 4: Create your 3 channels

Go to **Channels** in your dashboard. Do this three times.

### Channel 1 — Science & Tech

1. **Add channel**
2. Name: `Science & Tech` (or whatever you want)
3. **Content persona**: pick **Tech, Science & How Things Work**
4. Categories fill in automatically — leave them
5. Publishing: **Manual** for now (see note below)
6. **Save**

### Channel 2 — Comedy

Same steps, but:
- Name: `Comedy` (or whatever you want)
- **Content persona**: **Comedy, Dark Humour & Life Sketches**

### Channel 3 — Tamil Words & Quotes

Same steps, but:
- Name: `Tamil Quotes` (or whatever you want)
- **Content persona**: **Tamil Words, Wisdom & Original Lines**

> **Why "Manual" to start:** Each channel needs its own YouTube login before it can auto-post (Step 6). Leave all three on Manual for your first week, watch what comes out, then switch to Automatic once you're happy. You can change this anytime.

---

## Step 5: Give each channel its own free Gemini key (10 min, but this is the important one)

**Why this matters:** Gemini's free tier is about 20 requests a day — but that limit is *per API key*, not per app. One shared key across 3 channels means they fight over the same 20. Three separate keys means each channel gets its own 20, for free.

### Get 3 free keys

You need 3 different **Google accounts** (your key generation is limited to one free key per Google account, on your normal account, so a second/third Gmail address is the easiest path — a plain new Gmail address works fine, no verification needed).

For each of the 3 accounts:

1. Go to **aistudio.google.com**
2. Sign in with that Google account
3. Click **Get API key** (left sidebar) → **Create API key**
4. Copy the key it gives you — looks like `AIzaSy...`

You now have 3 keys. Label them in a note: which key is for Science, which for Comedy, which for Tamil Quotes.

### Add them to GitHub

Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**, one at a time:

| Secret name | Value |
|---|---|
| `GEMINI_API_KEY` | Your original key (used as the fallback default) |
| `GEMINI_API_KEY_SCIENCE` | The Science channel's key |
| `GEMINI_API_KEY_COMEDY` | The Comedy channel's key |
| `GEMINI_API_KEY_TAMIL` | The Tamil Quotes channel's key |

### Tell each channel which suffix to use

Back in **Channels**, edit each one:

| Channel | Secret name suffix |
|---|---|
| Science & Tech | `SCIENCE` |
| Comedy | `COMEDY` |
| Tamil Quotes | `TAMIL` |

This is the exact same "suffix" box already used for YouTube credentials — same idea, now also used for Gemini.

**If you skip this step:** everything still works, all 3 channels just share the one default key and its one 20/day quota between them. Worth doing when you have 10 minutes, not required to get started.

---

## Step 6: Connect YouTube for each channel (only when ready to go Automatic)

Repeat this once per channel:

1. Google Cloud Console → make a **new project** for this channel
2. **APIs & Services → Library** → enable **YouTube Data API v3**
3. **APIs & Services → Credentials → Create Credentials → OAuth client ID → Desktop app**
4. Copy the Client ID and Client Secret
5. In an **incognito window**, signed into the Google account for *that* channel's YouTube:
   ```
   set YOUTUBE_CLIENT_ID=paste-it-here
   set YOUTUBE_CLIENT_SECRET=paste-it-here
   python -m engine.publisher --setup
   ```
6. It prints a refresh token. Add all 3 values as GitHub secrets with the matching suffix (`YOUTUBE_CLIENT_ID_SCIENCE`, etc. — same pattern as the Gemini keys above)
7. Back in **Channels**, switch that channel's Publishing to **Automatic**

Full details with screensholder-style steps are in `docs/07_YOUTUBE_AND_CHANNELS.md` if you get stuck on any part of this.

---

## Step 7: Set up alerts, if you haven't (5 min)

Run the **Test Alerts** workflow: Actions tab → **Test Alerts** → **Run workflow**. If nothing arrives on your phone/email, set up Telegram per `docs/08_ALERTS_AND_MONITORING.md` — it's the fastest one to configure.

---

## Step 8: Turn on automatic topic invention

Dashboard → **Settings** → **Automatic Topic Rotation**, type:

```
tech_science_explainer, comedy_skits, quotes_and_poetry
```

This is what makes Gemini invent new specific topics on its own, forever, instead of you typing them in. It tops up whenever a channel's topic pool runs low.

---

## Step 9: Generate your first batch

Actions tab → **Generate Video Drafts** → **Run workflow**. Leave "how many" blank.

Wait about 10–15 minutes, then check **Video Queue** → **Pending Review**.

---

## Your daily routine from here

1. Generation now runs **automatically every 2 hours**, a couple of videos at a time — you don't have to trigger it.
2. A few times a day, open **Video Queue**, watch what's new, **Approve** the good ones, **Reject** the rest.
3. Once a week, glance at **Topic Studio** — the badge on each topic tells you if it was **✨ AI-invented** or **🌱 seed (fallback)**. If you're seeing a lot of 🌱, your Gemini quota is running out — that's your cue to check the per-channel keys in Step 5.

That's it. You don't need to add topics by hand anymore on any of the 3 channels.

---

## Quick troubleshooting

| Problem | What to check |
|---|---|
| Nothing generates | Actions → Generate Video Drafts → open the log, read the printed lines |
| Videos feel repetitive | Topic Studio → are topics mostly 🌱 not ✨? That means Gemini quota is out — set up per-channel keys (Step 5) |
| Tamil text shows boxes/squares | Make sure you copied the whole `assets/fonts/` folder, including `NotoSansTamil-Bold.ttf` |
| No alerts arrive | Run the **Test Alerts** workflow — it will tell you plainly what's missing |
| A channel isn't publishing | Check its Publishing mode is **Automatic**, not Manual, and that its YouTube secrets exist for its suffix |
