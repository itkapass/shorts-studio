# 07 — Connecting your YouTube channel

Do these in order. Don't skip ahead — each step needs the one before it.

---

## Before you start: what "the dashboard" means

Where you read **dashboard** in any of these docs, it means **your admin panel —
the website you deployed to Vercel**. It's your own site, something like
`https://your-project.vercel.app`. It is not the Vercel control panel itself.

If you open it and don't see a **Channels** page in the left sidebar, you
haven't run the database migration yet. Do that first:

1. Supabase → your project → **SQL Editor** → **New query**
2. Open `supabase/migrations/002_channels_and_concepts.sql`, copy everything, paste
3. **Run**. You should see `Success. No rows returned.`
4. Redeploy the Vercel site (Vercel → your project → **Deployments** → **⋯** → **Redeploy**)

---

## Part 1 — Decide how you want to publish

There are two ways. Pick one now, because it changes what you do next.

### Option A — Manual posting (start here)

The app renders videos and packages each one into a zip with the video, a
thumbnail, the title, description, hashtags and subtitles. You upload it to
YouTube yourself.

- **Setup time: zero.** No Google Cloud, no OAuth, nothing.
- Works today.
- You post each video by hand.

**If you're just getting started, use this.** Get videos you're happy with
first. Automating uploads of videos you haven't seen yet is the wrong order.

### Option B — Automatic posting

The app uploads to your channel by itself. This needs Google Cloud setup, and
there's a catch explained in Part 3.

---

## Part 2 — Set up manual posting (5 minutes)

1. Open your dashboard (your Vercel site).
2. Click **Channels** in the left sidebar.
3. Click **Add channel**.
4. Fill in:
   - **Channel name** — anything, e.g. `My Channel`
   - **Publishing** — leave on **Manual**
   - **Categories** — tick the content types you want
   - Tick **Catch-all**
5. **Save channel**.

Done. You never touch Google Cloud.

**How you get videos:** open **Video Queue**, watch a video, and if you like it,
mark it for manual posting. On the next publish run it becomes a downloadable
zip with a `POST_THIS.md` checklist inside telling you exactly what to click on
YouTube.

You can stop reading here if that's all you need.

---

## Part 3 — Automatic posting, and the honest problem with it

### The 7-day problem

Google gives every app a "publishing status". New apps start in **Testing**.
While an app is in Testing, **Google expires its login every 7 days.** Your
uploads work for a week, then stop with no error.

**In my earlier version of this document I said switching to Production was a
two-minute click. That was wrong, and it's why you're stuck.** To switch an
External app to Production, Google requires three public web pages first:

- an app home page
- a privacy policy
- a terms of service page

That's what the yellow warning on your Audience page means by "OAuth
configuration is incomplete". Your Branding page has App name, support email
and developer email filled in — but the three **App domain** URL fields are
still empty, and those are the ones blocking you.

So you have two real choices:

| | Effort | Result |
|---|---|---|
| **Path 1** — publish those three pages, then switch to Production | ~20 min, once | Login never expires again |
| **Path 2** — stay in Testing | 2 min every 7 days | You re-run one command weekly |

Path 1 is worth doing. It's below, and I've already written the three pages for
you — you only have to host them.

---

## Part 4 — Path 1: publish the three pages with GitHub Pages (free)

Your repository is already on GitHub, so hosting is free and takes ten minutes.

### Step 1 — Push the pages

The zip includes a folder called `docs-site` with three ready files:
`index.html`, `privacy.html`, `terms.html`. Read them once — they describe what
your app does and what it does with your data. They're accurate for this app.

Commit and push them:

```
git add docs-site
git commit -m "Add app pages for OAuth"
git push
```

### Step 2 — Turn on GitHub Pages

1. Your repo on GitHub → **Settings** (the repo's tab, not your account's)
2. Left sidebar → **Pages**
3. Under **Source**, choose **Deploy from a branch**
4. Branch: **main** · Folder: **/docs-site** — if `/docs-site` isn't offered,
   pick **/ (root)** and instead move the three files into a folder named
   `docs`, then choose **/docs**
5. **Save**

Wait about a minute, then reload the page. GitHub shows your live URL at the
top, like:

```
https://YOUR-USERNAME.github.io/YOUR-REPO/
```

### Step 3 — Check it actually loads

Open all three in a browser. They must load **without logging in**:

```
https://YOUR-USERNAME.github.io/YOUR-REPO/
https://YOUR-USERNAME.github.io/YOUR-REPO/privacy.html
https://YOUR-USERNAME.github.io/YOUR-REPO/terms.html
```

If you get a 404, wait two more minutes — first deploys are slow. If it's still
404, your folder setting in Step 2 doesn't match where the files actually are.

### Step 4 — Fill in the Branding page

Back in Google Cloud → **Google Auth Platform** → **Branding**.

**Do the Authorized domain FIRST.** Google rejects the URLs if the domain isn't
registered yet, and the error message doesn't tell you that's the reason.

1. Scroll to **Authorized domains** → **+ Add domain**
2. Enter exactly: `github.io`
3. Now fill the three **App domain** fields:

| Field | Value |
|---|---|
| Application home page | `https://YOUR-USERNAME.github.io/YOUR-REPO/` |
| Application privacy policy link | `https://YOUR-USERNAME.github.io/YOUR-REPO/privacy.html` |
| Application terms of service link | `https://YOUR-USERNAME.github.io/YOUR-REPO/terms.html` |

4. Click **Save**.

> If Google refuses `github.io` as an authorized domain, use Vercel instead:
> copy the three files into your admin panel's `public/` folder, push, and use
> your `https://your-project.vercel.app/privacy.html` URLs with the authorized
> domain `vercel.app`.

### Step 5 — Publish

1. Left sidebar → **Audience**
2. The yellow "configuration is incomplete" warning should now be gone
3. Click **Publish app** → **Confirm**

Status now reads **In production**.

### Step 6 — About the verification warning

Google will say your app isn't verified. **This does not stop you.**

- Your app works. Uploads work.
- When you log in, you'll see a screen saying "Google hasn't verified this app".
  Click **Advanced** → **Go to YT autoposter app (unsafe)**.
- That warning exists to protect *strangers* from *your* app. You are not a
  stranger to your own app.
- Unverified production apps allow up to 100 users. You are one.

Verification only matters if you want other people to use your app.

### Step 7 — Get a fresh login

Your old token still has the 7-day clock on it. From your project folder:

```
python -m engine.publisher --setup
```

Copy the refresh token it prints into your `YOUTUBE_REFRESH_TOKEN` GitHub
secret. **This one does not expire.**

---

## Part 5 — Path 2: stay in Testing

Perfectly workable. Every 7 days:

```
python -m engine.publisher --setup
```

and paste the new token into your `YOUTUBE_REFRESH_TOKEN` secret.

The daily health check emails or Telegrams you the morning it expires, so you
won't lose more than a day.

---

## Part 6 — Setting up automatic posting

Only after Part 4 or Part 5.

### Step 1 — Get your OAuth credentials

1. Google Cloud → **APIs & Services** → **Library** → search
   **YouTube Data API v3** → **Enable**
2. **APIs & Services** → **Credentials** → **Create Credentials** →
   **OAuth client ID**
3. Application type: **Desktop app** → **Create**
4. Copy the **Client ID** and **Client Secret**

### Step 2 — Log in with the right account

Open an **incognito window** first. If you're signed into several Google
accounts, the browser silently picks one and you can authorise the wrong
channel.

In your project folder:

```
set YOUTUBE_CLIENT_ID=your-client-id
set YOUTUBE_CLIENT_SECRET=your-client-secret
python -m engine.publisher --setup
```

(On Mac/Linux use `export` instead of `set`.)

A browser opens. Sign in with the account that owns your YouTube channel, click
through the unverified warning, allow access. It prints a refresh token.

### Step 3 — Add three GitHub secrets

Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

| Name | Value |
|---|---|
| `YOUTUBE_CLIENT_ID` | from Step 1 |
| `YOUTUBE_CLIENT_SECRET` | from Step 1 |
| `YOUTUBE_REFRESH_TOKEN` | from Step 2 |

### Step 4 — Switch the channel to automatic

Dashboard → **Channels** → edit your channel → **Publishing: Automatic** →
**Uploads per day: 5** → Save.

### Step 5 — Confirm

Repo → **Actions** → **Health Check** → **Run workflow**. Look for:

```
✓ YouTube auth [My Channel]: token refreshed OK
```

---

## Part 7 — Why "uploads per day: 5"

Google gives each Cloud project 10,000 API units a day. One upload costs 1,600.

```
10,000 ÷ 1,600 = 6 uploads per day
```

Set it to 5, not 6. A retried upload consumes quota twice, and going over
returns a 403 that *still* burns quota — so the next run starts further behind.

**This limit is per Google Cloud project, not per channel.** Five channels
sharing one project get 6 uploads a day between them. For a full budget each,
create a separate Cloud project per channel and give each channel its own
secret suffix (`YOUTUBE_CLIENT_ID_SCIENCE`, etc.) in the Channels page.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'engine'` | Use `python -m engine.publisher --setup`, not `python engine/publisher.py`. Run it from the project folder — the one containing `engine`, not inside it |
| "Publish app" is greyed out / "configuration is incomplete" | The three App domain URLs are empty. Part 4 |
| Google won't accept my domain | Add the authorized domain **before** the URLs. If `github.io` is refused, use Vercel |
| No **Channels** page in the sidebar | Migration not run, or site not redeployed. See top of this doc |
| `invalid_grant` | Token expired (Testing mode) or wrong account. Re-run setup |
| Publishing stopped after a week | Testing mode. Part 4 |
| Nothing publishes, no error | No channel accepts that category. Channels → tick more categories or set Catch-all |
