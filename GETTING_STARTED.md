# 🚀 Getting Started: Step-by-Step Guide

Welcome! You have a complete, production-ready **AI Video & Content Automation Studio** designed to generate high-retention, monetization-optimized YouTube Shorts and Instagram Reels for **$0/month**.

---

## ⚡ Quick Navigation
You can run this app in 3 simple stages:
1. **Stage 1: Launch the Web Studio (Takes 2 minutes)** — Explore the UI, generate prompts, test trending topics.
2. **Stage 2: Connect Supabase Database (Takes 3 minutes)** — Enable persistent storage, video queues, and live settings.
3. **Stage 3: Run Video Render Engine (Takes 2 minutes)** — Render full 1080x1920 videos with voiceover, b-roll, and subtitles.

---

## 🛠️ Stage 1: Launch the Web Studio Locally (2 Minutes)

The web dashboard is already built and ready to launch on your computer.

### Step 1: Open PowerShell / Terminal in the project folder
```powershell
cd path\to\this\project\admin-panel
```

### Step 2: Start the Web App
```powershell
npm run dev
```

### Step 3: Open your browser
Visit: **`http://localhost:5173`**
You will see:
* **Custom Prompt Video Studio (`/create`)**: Type any idea, pick a visual style, and
  generate a real storyboard via Gemini (needs the `generate-storyboard` Edge
  Function deployed — see `docs/04`, Step 4). A "Copy Render Command" button then
  renders exactly that storyboard.
* **Trending Radar (`/trending`)**: Real YouTube search results for what's getting
  views this week (needs the `discover-trends` Edge Function — same doc). No
  invented scores — just actual titles, channels, and view counts.
* **Video Queue (`/queue`)**: Review and approve drafts.
* **Topic Studio (`/studio`)**: Add custom niches and prompt presets.

---

## 🔑 Stage 2: Free API Keys & Supabase Database (5 Minutes)

To store your videos, settings, and topics permanently, set up the free backend:

### 1. Free Supabase Database (Free Tier)
1. Sign up at [supabase.com](https://supabase.com) (100% free, no credit card).
2. Create a new project (e.g., `shorts-studio`).
3. Click **SQL Editor** on the left menu $\rightarrow$ Click **New query**.
4. Copy all content from `supabase/schema.sql`, paste it into the editor, and click **Run**.
5. Create a Storage Bucket for video files:
   * Go to **Storage** $\rightarrow$ **New bucket**.
   * Name: `shorts-videos`
   * Toggle **Public bucket** to **ON** $\rightarrow$ Click **Save**.

### 2. Free AI & Video API Keys
* **Google Gemini API Key (Free)**: Get from [aistudio.google.com](https://aistudio.google.com) (Generates scripts & storyboards).
* **Pexels API Key (Free)**: Get from [pexels.com/api](https://www.pexels.com/api/) (Fetches HD video b-roll footage).

### 3. Connect Keys to your Project
1. In the project root (wherever you cloned/extracted this project), copy `.env.example` to `.env`:
   ```powershell
   copy .env.example .env
   ```
2. Open `.env` and fill in your keys:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   PEXELS_API_KEY=your_pexels_api_key_here
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_ANON_KEY=your_anon_key
   SUPABASE_SERVICE_KEY=your_service_role_key
   ```
3. In `admin-panel/`, copy `admin-panel/.env.example` to `admin-panel/.env`:
   ```powershell
   copy admin-panel\.env.example admin-panel\.env
   ```
   Add your `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`.

---

## 🎬 Stage 3: Render Your First AI Video Locally

Once your `.env` has your API keys, you can render a full video with a single command!

### Render from a Custom Prompt:
```powershell
python -m engine.orchestrator --prompt "How EUV lithography carves transistors smaller than a virus" --style whiteboard_sketch
```
`--style` picks the visual style: `stock_footage` (default), `whiteboard_sketch`, or
`quote_card` — see `CHANGES.md` for what each looks like. Omit it to use
`stock_footage`.

### Render a storyboard you built in the Create Video page:
If you generated and saved a storyboard from `/create` in the Admin Panel, the page
gives you this instead — it renders the *exact* storyboard you reviewed/edited, not a
freshly regenerated one:
```powershell
python -m engine.orchestrator --render-job <job_id>
```

What happens automatically:
1. 🧠 **Gemini** writes a script with genuine retention hooks (real generation — see `CHANGES.md` for what changed here).
2. 🎙️ **TTS Voice Engine** records the voiceover and extracts millisecond word timestamps.
3. 🎨 **Style renderer** builds the background — real b-roll (`stock_footage`), hand-drawn icons (`whiteboard_sketch`), or a gradient (`quote_card`).
4. 📝 **Subtitle Engine** renders animated captions.
5. 🎵 **Audio Mixer** balances background music + sound effects, with real smoothed ducking.
6. 🎞️ **Video Compositor** renders the completed 1080x1920 MP4, uploads it to Supabase Storage, and registers it in your web dashboard — for real, from every entry point (this used to only work when triggered via GitHub Actions; see `CHANGES.md`).

---

## ☁️ Stage 4: 100% Autonomous 24/7 Cloud Pipeline ($0/Month)

If you want the pipeline to run automatically every day on GitHub Actions without keeping your computer on:
* Follow `docs/04_AUTONOMOUS_YOUTUBE_PUBLISHING.md` — this is the current version;
  `DEVOPS_PLAYBOOK.md` is kept for reference but has an outdated YouTube auth section.

## 🌍 Stage 5: Access It From Anywhere (No Local Computer Needed)

Stage 1 above runs the dashboard on *your* machine (`npm run dev`). To get a real URL
you can open from your phone or any browser, any time — and to render on-demand
videos without your computer being on at all — see
`docs/05_DEPLOY_THE_DASHBOARD.md`. Short version: deploy `admin-panel/` to Vercel
(free), and the scheduled generation/publishing from Stage 4 already runs in GitHub's
cloud with no further setup either way.
