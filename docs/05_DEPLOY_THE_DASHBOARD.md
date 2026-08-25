# Tool 5: Deploy the Dashboard (Access It From Anywhere)

Short answer to "can I access this online any time, without my computer": **yes** —
that's what this doc sets up. Worth understanding *why* first, because it explains
what still needs your computer and what doesn't.

## The architecture, plainly

Three separate things run in three separate places. Mixing them up is the usual
source of "wait, do I need my laptop on for this?" confusion:

| Piece | Where it runs | Always-on? |
|---|---|---|
| **Admin Panel** (the dashboard you look at) | Vercel (static hosting) | Yes, once deployed — this doc |
| **Scheduled generation + publishing** | GitHub Actions, on a cron schedule | Yes, already — `generate.yml` / `publish.yml` need no setup beyond secrets |
| **Rendering a specific video** (ffmpeg + TTS + Whisper) | Either GitHub Actions (on demand, new) or your own machine | Your choice — see below |

The part that actually needs sustained compute — turning a script into an actual
`.mp4` — takes minutes, not seconds. That doesn't fit Vercel's serverless model
(built for requests that finish in seconds), which is why this project always used
GitHub Actions for it, not Vercel, even before this build. **You do not need to keep
your own computer running for the daily scheduled pipeline** — that already happens
in GitHub's cloud, for free, on the schedule in `generate.yml`.

The one place your own machine used to be required: rendering a specific storyboard
you built in the **Create Video** page on demand. That's now fixed too (see Step 3).

---

## Step 1: Deploy the Admin Panel to Vercel

1. Push this project to a GitHub repository (needed for both this and Actions).
2. Go to [vercel.com](https://vercel.com/) → **Add New** → **Project** → import your repo.
3. Set **Root Directory** to `admin-panel`.
4. Add Environment Variables:
   * `VITE_SUPABASE_URL` = your Supabase project URL
   * `VITE_SUPABASE_ANON_KEY` = your Supabase anon public key
5. **Deploy.** You'll get a URL like `your-project.vercel.app` — bookmark it, that's
   your dashboard from now on, from any device.
6. Log in with the account you created in `docs/01` (Authentication → Users).

Every push to your repo's main branch auto-redeploys — no manual redeploy step.

---

## Step 2: Confirm the scheduled pipeline needs nothing further

If you completed `docs/04`, `generate.yml` and `publish.yml` are already running on
their cron schedules in GitHub's cloud. Check: repo → **Actions** tab → you should
see past runs (or upcoming scheduled ones). Nothing here depends on Vercel or your
own computer being on.

---

## Step 3: On-demand rendering, without your computer

The Create Video page's storyboard generation already runs server-side (the
`generate-storyboard` Edge Function from `docs/04`). Actually *rendering* that
storyboard into a video used to only be possible by copying a command and running it
locally. There's now a second option: a **"Render in Cloud"** button that triggers
`.github/workflows/render-on-demand.yml` remotely, so it runs on GitHub Actions
instead — same free compute the scheduled pipeline already uses.

This needs one more credential: a GitHub token that's allowed to trigger workflow
runs. Scope it tightly:

1. GitHub → your profile picture → **Settings** → **Developer settings** →
   **Personal access tokens** → **Fine-grained tokens** → **Generate new token**.
2. **Repository access**: "Only select repositories" → pick just this one repo.
3. **Permissions** → **Actions**: set to **Read and write**. Leave everything else
   at no access.
4. Generate, copy the token (starts with `github_pat_...` — you won't see it again).
5. Set it as an Edge Function secret, along with which repo it applies to:
   ```bash
   supabase functions deploy trigger-render
   supabase secrets set GITHUB_PAT=github_pat_...
   supabase secrets set GITHUB_REPO=your-username/your-repo-name
   ```

Now, from the Admin Panel — on your phone, at a friend's computer, wherever —
Create Video → generate a storyboard → **Save Storyboard** → **Render in Cloud**. It
finishes in GitHub Actions in a few minutes; the video shows up in the Video Queue as
"Rendering," then "Pending Review" once done. "Or render locally instead" is still
there if you'd rather.

**On scope, honestly:** this fine-grained PAT can only dispatch workflow runs on the
one repo you scoped it to — it can't read your other repos, push code, or touch
account settings. Still a real credential though; same rule as every other key in
this project applies — never share it, and if it's ever exposed, revoke it from the
same Developer Settings page and issue a new one.

---

## What you can now do entirely from the dashboard, from anywhere

- Review, approve, or reject queued videos (Video Queue).
- Generate a new video from a prompt, in any of the three visual styles (Create Video).
- Pull real trending inspiration (Trending Radar).
- Trigger a render without touching your own machine (Step 3, above).
- Adjust topics, tones, and settings (Topic Studio / Settings).

What still runs on its own schedule, untouched by any of this: the daily generation
batch and the every-30-minutes publish check — both already cloud-native, no action
needed from you beyond the one-time setup in `docs/04`.
