# DevOps & Deployment Playbook: YouTube Shorts AI Pipeline

> **This file is kept for reference but is partly outdated — see `docs/01` through
> `docs/04` for the current setup steps.** Specifically, the YouTube auth section
> below (Phase 5, `YOUTUBE_TOKEN_B64` / `YOUTUBE_CLIENT_SECRETS_JSON`) describes the
> old base64-pickle approach; `publisher.py` now reads plain `YOUTUBE_CLIENT_ID` /
> `YOUTUBE_CLIENT_SECRET` / `YOUTUBE_REFRESH_TOKEN` secrets instead, which is what
> `docs/04_AUTONOMOUS_YOUTUBE_PUBLISHING.md` documents. The Supabase/database steps
> below (Phase 1) are still accurate, but `docs/01` additionally covers creating your
> Admin Panel login, which is new — see `CHANGES.md` for why.

This document is your step-by-step checklist to initialize version control, configure secrets, deploy the database, and launch your automated YouTube Shorts pipeline.

---

## 🛠️ Phase 1: Supabase Database Setup (3 Minutes)

1. Open your [Supabase Dashboard](https://supabase.com/dashboard).
2. Open your project $\rightarrow$ Click **SQL Editor** on the left menu.
3. Click **New Query** $\rightarrow$ Open the file `supabase/schema.sql` in your project (a relative path — an earlier version of this doc had a broken link that only worked on one specific machine), copy its entire contents, paste it into the Supabase SQL editor, and click **Run**.
4. Create the Storage Bucket for videos:
   * Click **Storage** on the left menu $\rightarrow$ Click **New bucket**.
   * Name: `shorts-videos`
   * Set **Public bucket** to **ON** (so YouTube and your admin panel can access the generated video URLs).
   * Click **Save**.

---

## 🔐 Phase 2: Local Environment Configuration (.env)

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Open `.env` and paste your actual keys:
   * `GEMINI_API_KEY`: From Google AI Studio.
   * `PEXELS_API_KEY`: From Pexels API dashboard.
   * `SUPABASE_URL`: From Supabase Project Settings $\rightarrow$ API.
   * `SUPABASE_ANON_KEY`: From Supabase Project Settings $\rightarrow$ API (`anon` public key).
   * `SUPABASE_SERVICE_KEY`: From Supabase Project Settings $\rightarrow$ API (`service_role` secret key).

3. Configure Admin Panel environment:
   * Copy `admin-panel/.env.example` to `admin-panel/.env`:
     ```bash
     cp admin-panel/.env.example admin-panel/.env
     ```
   * Set `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` inside `admin-panel/.env`.

---

## 🐙 Phase 3: Git & GitHub Setup (Unlimited Compute)

To get **unlimited free render minutes**, make your GitHub repository **Public** (your secrets will remain 100% private in GitHub Secrets and `.gitignore` protects your local `.env`).

Run the following commands in your project root:

```bash
# 1. Initialize git repository
git init

# 2. Add all files (secrets and node_modules are automatically excluded by .gitignore)
git add .

# 3. Create your initial commit
git commit -m "feat: complete automated zero-cost youtube shorts studio pipeline"

# 4. Set main branch
git branch -M main

# 5. Connect to your GitHub repository (replace with your repo URL)
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git

# 6. Push to GitHub
git push -u origin main
```

---

## 🔑 Phase 4: Configure GitHub Actions Secrets

Go to your repository on GitHub:
👉 **Settings** $\rightarrow$ **Secrets and variables** $\rightarrow$ **Actions** $\rightarrow$ Click **New repository secret** for each of the following:

| Secret Name | Value to Paste |
|---|---|
| `GEMINI_API_KEY` | Your Google Gemini API Key |
| `PEXELS_API_KEY` | Your Pexels API Key |
| `SUPABASE_URL` | Your Supabase Project URL (`https://xyz.supabase.co`) |
| `SUPABASE_ANON_KEY` | Your Supabase `anon` public key |
| `SUPABASE_SERVICE_KEY` | Your Supabase `service_role` secret key |
| `YOUTUBE_CLIENT_SECRETS_JSON` | Entire JSON content of your downloaded Google Cloud OAuth client secret file |
| `YOUTUBE_TOKEN_B64` | Base64 encoded `youtube_token.pickle` (see Phase 5 below) |

---

## 🎥 Phase 5: One-Time YouTube OAuth Authentication

To authorize automated publishing without entering your password every time:

1. Download your OAuth 2.0 Client Credentials JSON from Google Cloud Console $\rightarrow$ APIs & Services $\rightarrow$ Credentials.
2. Save the file in your project as: `engine/youtube_client_secrets.json`.
3. Run the one-time interactive login command:
   ```bash
   python engine/publisher.py --setup
   ```
4. A browser window will open $\rightarrow$ Sign in to the Google account connected to your YouTube channel $\rightarrow$ Click **Continue/Allow**.
5. This generates `engine/youtube_token.pickle`.
6. Convert this token to a Base64 string to store in GitHub Secrets:
   * **PowerShell (Windows):**
     ```powershell
     [Convert]::ToBase64String([IO.File]::ReadAllBytes("engine/youtube_token.pickle")) | Set-Clipboard
     ```
   * *The Base64 string is now in your clipboard! Paste it into GitHub Secret named `YOUTUBE_TOKEN_B64`.*

---

## 🐳 Phase 6: Running Locally via Docker (Optional)

If you want to run the whole stack or test a video render inside Docker:

```bash
# Build and start both the Python Video Engine and React Admin Panel
docker compose up --build

# Or run just the React Admin Panel on http://localhost:5173
cd admin-panel
npm run dev
```

---

## 🚀 Phase 7: Deploy Admin Panel to Vercel (100% Free)

1. Go to [Vercel](https://vercel.com/) and click **Add New** $\rightarrow$ **Project**.
2. Select your GitHub repository.
3. Set **Root Directory** to: `admin-panel`.
4. In **Environment Variables**, add:
   * `VITE_SUPABASE_URL` = Your Supabase Project URL
   * `VITE_SUPABASE_ANON_KEY` = Your Supabase anon public key
5. Click **Deploy**. Your Admin Dashboard is now live on the web!

---

## ⚡ Phase 8: Testing Your First Run

1. Open your GitHub Repository $\rightarrow$ Click the **Actions** tab.
2. Click **Generate Video Drafts** workflow on the left.
3. Click **Run workflow** $\rightarrow$ **Run workflow**.
4. Watch the pipeline run! In ~4 minutes, it will:
   * Call Gemini to write a high-retention 5-scene tech script
   * Generate neural audio with Edge-TTS
   * Run Whisper for word-level timestamps
   * Fetch matching HD B-roll clips from Pexels
   * Duck background music under the voice
   * Render dynamic word-by-word highlighted captions
   * Upload the draft to Supabase Storage and queue it in your Admin Panel!
5. Open your Admin Panel $\rightarrow$ Review the video draft $\rightarrow$ Click **Approve for YouTube**!
