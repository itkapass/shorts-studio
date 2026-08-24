# Tool 4: Autonomous YouTube Publishing & GitHub Actions ($0/Month)

This guide sets up automated video publishing to your YouTube channel on a schedule
using GitHub Actions, a real login-gated Admin Panel, and the two AI features that
now actually call real services instead of showing hardcoded data.

---

## Step 1: Google Cloud OAuth Setup (YouTube API)
1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create a Project (e.g. `YouTube Shorts AutoPoster`).
3. Enable the **YouTube Data API v3**: search for it → **Enable**.
4. Configure the OAuth Consent Screen:
   * Select **External** → fill in App Name and your email.
   * Add your Google account email as a **Test User**.
5. Create OAuth Credentials:
   * **Credentials** → **Create Credentials** → **OAuth client ID**.
   * Application Type: **Desktop App**. Name it whatever you like.
   * **Create** → **Download JSON** → save it as `engine/youtube_client_secrets.json`.

**Read this before you move on:** while your consent screen is in **Testing** status
(the default — the vast majority of solo projects never leave it), Google expires
your refresh token after **7 days**. After that, publishing fails until you redo the
setup below and update your secrets. This is a Google policy, not something this
project's code can work around. If you want a token that doesn't expire on a
schedule, you'd need to move the consent screen to "In production," which for the
`youtube.upload` scope requires Google's app verification review (budget real time —
this can take a couple of weeks, sometimes longer, and may ask for a demo video).
Most people building this as a personal/hobby project just accept the weekly re-auth
instead — that's a legitimate choice, just go in knowing which one you're making.

---

## Step 2: One-Time Local YouTube Authorization
```bash
python engine/publisher.py --setup
```
A browser window opens — sign in and grant permission. Unlike before, this now
**prints the three values you need directly to your terminal**:
```
YOUTUBE_CLIENT_ID     = ...
YOUTUBE_CLIENT_SECRET = ...
YOUTUBE_REFRESH_TOKEN = ...
```
Copy all three into your local `.env` and into GitHub Secrets (next step). This
replaced a previous base64-encode-a-pickle-file dance — same three underlying values,
much less error-prone to move around.

---

## Step 3: Supabase Auth (the Admin Panel now requires logging in)
This is new, and matters: the previous version of this project's database policies
let anyone with your public anon key read and write everything, and the Admin Panel
had no login screen at all. Both are fixed, but fixing them means you now need an
actual account:
1. Supabase Dashboard → **Authentication** → **Users** → **Add user**.
2. Create yourself an email + password. This is the only account you need — this
   project is built for a single owner, not multi-tenant use.
3. You'll use these to log into the Admin Panel at `/login`.

---

## Step 4: Deploy the Edge Functions (powers Create Video & Trending Radar)
Both pages used to show hardcoded/fake data. They now call two real Supabase Edge
Functions. Install the [Supabase CLI](https://supabase.com/docs/guides/cli) if you
haven't, then from the project root:
```bash
supabase login
supabase link --project-ref your-project-id
supabase functions deploy generate-storyboard
supabase functions deploy discover-trends

# Secrets these functions need (separate from your .env — these live on Supabase):
supabase secrets set GEMINI_API_KEY=your_gemini_api_key_here
supabase secrets set GEMINI_MODEL=gemini-3.5-flash   # optional, same override as the Python side
supabase secrets set YOUTUBE_API_KEY=your_youtube_api_key_here
```
`YOUTUBE_API_KEY` is a **separate, simpler credential** from the OAuth client you set
up in Step 1 — a plain API key, not OAuth. Same Google Cloud project: **APIs &
Services → Credentials → Create Credentials → API Key**, then restrict it to the
YouTube Data API v3. This is read-only search, costs very little quota, and is safe
to use this way (unlike the OAuth credentials, an API key can't upload video on your
behalf).

If a function's secret isn't set, that page shows a clear error explaining what's
missing — it won't silently fall back to fake data.

---

## Step 5: Enable Automated GitHub Actions Workflows
1. Push to a **public** GitHub repository (public repos get unlimited free Actions
   minutes; private repos have a monthly cap).
2. Repository → **Settings** → **Secrets and variables** → **Actions** → add:
   * `GEMINI_API_KEY`
   * `GEMINI_MODEL` (optional)
   * `PEXELS_API_KEY`
   * `SUPABASE_URL`
   * `SUPABASE_ANON_KEY`
   * `SUPABASE_SERVICE_KEY`
   * `YOUTUBE_CLIENT_ID`
   * `YOUTUBE_CLIENT_SECRET`
   * `YOUTUBE_REFRESH_TOKEN`

That's it — no `YOUTUBE_TOKEN_B64`, no `YOUTUBE_CLIENT_SECRETS_JSON` secret needed
anymore; `publisher.py` reads the three plain values above directly, the same way
locally, in Docker, or in Actions.

---

## Result
* `generate.yml` generates new video drafts on schedule (default: daily) and uploads
  them to Storage as it goes — including retries, not a silent best-effort.
* `publish.yml` publishes approved videos every 30 minutes, throttled by the
  `publish_per_run` setting in the Admin Panel (Settings page — this now actually
  does something).
* If a publish fails because your refresh token expired, the error log in the Video
  Queue will say so plainly instead of showing a raw OAuth error.
* $0 in hosting or compute cost, same as before — none of this changes that.
