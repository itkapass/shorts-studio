# 07 — YouTube: the 7-day fix, quotas, and multiple channels

This document fixes the two things most likely to break your publishing, and
then shows you how to run more than one channel.

Read sections 1–3 even if you only ever want one channel. Section 3 in
particular saves you from having to re-authorise every single week, forever.

---

## 1. The two facts that explain almost every YouTube problem

**Fact one: refresh tokens expire after 7 days while your app is in "Testing".**

Google gives every OAuth app a publishing status. New apps start in **Testing**.
In Testing mode, Google deliberately expires refresh tokens after 7 days. Your
publishing works perfectly for a week, then silently stops. Nothing crashes,
nothing warns you — uploads just stop happening.

Section 3 fixes this permanently.

**Fact two: your daily upload limit is per Google Cloud PROJECT, not per channel.**

Google gives each Cloud project 10,000 API "units" per day. A video upload costs
1,600 units. So:

```
10,000 ÷ 1,600 = 6 uploads per day, per project
```

This catches people out constantly: they add five channels expecting 30 uploads
a day, point all five at the same Cloud project, and get 6 uploads a day shared
between all of them.

**Give each channel its own Google Cloud project and each one gets its own
10,000 units.** Projects are free and unlimited. Section 5 covers this.

---

## 2. If you haven't set up YouTube publishing at all yet

Follow `docs/04_AUTONOMOUS_YOUTUBE_PUBLISHING.md` first, then come back here
for section 3. Section 3 is the part that document doesn't cover, and it's the
one that matters most long-term.

---

## 3. The permanent fix: switch to "In production"

**Do this once. It takes about two minutes and stops the weekly expiry forever.**

1. Go to **https://console.cloud.google.com/**
2. Top-left, make sure the **project selector** shows the project you created
   for this app. If not, click it and pick the right one.
3. Left sidebar → **APIs & Services** → **OAuth consent screen**
4. You'll see **Publishing status: Testing**
5. Click **PUBLISH APP**
6. A dialog appears. Click **CONFIRM**.

The status now reads **In production**. Refresh tokens stop expiring on the
7-day clock.

### "It's warning me about verification. Is that a problem?"

No. Google will say the app needs verification because it uses a "sensitive
scope" (uploading to YouTube). Here's what that actually means for you:

- **You can publish without being verified.** The app works.
- The only difference: when you authorise it, Google shows a warning screen
  saying "Google hasn't verified this app".
- You click **Advanced** → **Go to [your app name] (unsafe)** and continue.
- That warning is Google protecting *strangers* from *your* app. You are not a
  stranger to your own app. There is nothing unsafe about authorising software
  you built to access an account you own.
- Unverified production apps are capped at 100 users. You are one user.

**Verification only matters if you plan to let other people use your app.** For
your own channels, publishing without verification is the normal, correct path.

### Now regenerate your token

Once in production, generate a fresh refresh token — the old one still has the
7-day clock attached to it:

```bash
python engine/publisher.py --setup
```

Follow the browser flow, click through the unverified-app warning, then copy the
refresh token it prints into your `YOUTUBE_REFRESH_TOKEN` GitHub secret.

**This token does not expire.** You should not need to do this again.

### Confirm it worked

Repo → **Actions** → **Health Check** → **Run workflow**. Look for:

```
✓ YouTube auth [Main Channel]: token refreshed OK
```

The health check runs every morning at 06:43 UTC and attempts a real token
refresh. If your token ever does break, you get an alert that morning rather
than discovering it a fortnight later.

---

## 4. Setting your upload cap correctly

In the dashboard: **Channels** → edit a channel → **Uploads per day**.

**Set this to 5, not 6.**

The hard ceiling is 6. Set it to 6 and a single retried upload — which happens
occasionally on a network blip — pushes you over. Going over doesn't fail
gracefully: you get a 403, and the failed attempt *still consumes quota*, so the
next run starts even further behind. Setting 5 leaves room for exactly that.

The app stops before the cap rather than after, and sends you an alert when it
does. Quota resets at midnight Pacific Time.

---

## 5. Running multiple channels

The design goal here was that adding your fifth or fiftieth channel is a form
submission, not a code change.

### Step 1 — Make a separate Google Cloud project per channel

This is the part that actually gets you more uploads per day. For each channel:

1. **console.cloud.google.com** → project dropdown → **New Project**
2. Name it after the channel, e.g. `shorts-science`
3. **APIs & Services** → **Library** → search **YouTube Data API v3** → **Enable**
4. **OAuth consent screen** → set it up → **PUBLISH APP** (section 3 above)
5. **Credentials** → **Create Credentials** → **OAuth client ID** → **Desktop app**
6. Save the Client ID and Client Secret

### Step 2 — Generate a token for that channel

Log into the browser with **the Google account that owns that YouTube channel**,
then:

```bash
YOUTUBE_CLIENT_ID=<that project's id> \
YOUTUBE_CLIENT_SECRET=<that project's secret> \
python engine/publisher.py --setup
```

> Watch out for this: if you're signed into several Google accounts, the browser
> picks one for you and you can authorise the wrong channel. Use an incognito
> window and sign in deliberately.

### Step 3 — Add the secrets with a suffix

Pick a short uppercase suffix per channel, e.g. `SCIENCE`. In
**GitHub → Settings → Secrets and variables → Actions**, add:

```
YOUTUBE_CLIENT_ID_SCIENCE
YOUTUBE_CLIENT_SECRET_SCIENCE
YOUTUBE_REFRESH_TOKEN_SCIENCE
```

### Step 4 — Add the channel in the dashboard

**Channels** → **Add channel**:

| Field | What to put |
|---|---|
| Channel name | Science Shorts |
| Publishing | Automatic |
| Secret name suffix | `SCIENCE` |
| Uploads per day | 5 |
| Categories | tick the content types this channel should receive |

The dashboard shows you the exact secret names it will look for, so you can
check they match what you added.

**No credentials are ever typed into the dashboard.** The channel row stores
only the *name* of the environment variables. The actual secrets live in GitHub
Secrets. If your database ever leaked, no channel would be compromised.

### Step 5 — Route your categories

Each channel accepts a set of content categories. When a video is ready, it goes
to the first enabled channel that accepts its category.

A sensible split:

| Channel | Categories |
|---|---|
| Science channel | Unknown Facts, Myth vs Fact, Daily Hacks |
| Comedy channel | Relatable, Dark Humour, Sarcasm, Absurd, Observational |
| Wholesome channel | Wholesome, Social & Human |

If nothing accepts a category, the video is marked for manual export instead of
being force-posted somewhere it doesn't belong.

Tick **Catch-all** on one channel to have it receive anything unclaimed.

---

## 6. "Post it manually instead"

Any channel can be set to **Manual** publishing, and any individual video can be
sent to manual export from the queue.

When you do, you get a zip containing:

```
video.mp4          the finished video
thumbnail.jpg      a frame from ~30% in
title.txt          ready to paste
description.txt    description with hashtags already appended
hashtags.txt       hashtags alone, for other platforms
captions.srt       subtitles you can upload
script.txt         the narration as plain text
POST_THIS.md       step-by-step upload checklist
```

Two settings in that checklist matter a lot and are easy to get wrong:

- **"No, it's not made for kids"** must be set. Getting this wrong disables
  comments, removes the video from recommendations, and blocks monetisation.
- **Upload the .srt.** Most Shorts are watched muted. Real captions measurably
  lift watch time on top of the burned-in ones.

After exporting, the file is deleted from storage and the video leaves the
pipeline. It's yours now.

---

## 7. Quick reference

| Problem | Cause | Fix |
|---|---|---|
| Publishing stopped after a week | App still in "Testing" | Section 3 |
| `invalid_grant` | Expired or wrong refresh token | Section 3, regenerate |
| Only 6 uploads/day across all channels | Shared Cloud project | Section 5, one project each |
| 403 quota errors | Cap set to 6 with retries | Set cap to 5 |
| Video published but isn't a Short | Wrong aspect ratio or over 3 min | Renders are 1080x1920 and ~45s; check the URL contains `/shorts/` |
| Nothing publishes, no error | No channel accepts that category | **Channels** → tick more categories or set a catch-all |
