# Tool 2: Free AI & Video Footage API Keys Guide

You only need **2 free API keys** for the AI Video Engine to write scripts and fetch HD stock video clips.

---

## 1. Google Gemini API Key (For AI Script & Storyboard Generation)
*Cost: Free ($0/month)*

1. Go to [https://aistudio.google.com/](https://aistudio.google.com/)
2. Sign in with any Google account.
3. Click the blue button **Get API key** (top left).
4. Click **Create API key** $\rightarrow$ Select your Google Cloud project (or create one automatically).
5. Copy the generated API key (starts with `AIzaSy...`).
6. Paste it into `.env` (in project root):
   ```env
   GEMINI_API_KEY=AIzaSy...
   ```

---

## 2. Pexels API Key (For Automatic HD Video B-Roll Downloads)
*Cost: Free (200 requests/hour, 20,000 requests/month)*

Only needed for the `stock_footage` render style — `whiteboard_sketch` and
`quote_card` don't fetch any footage, so you can skip this key entirely if
you're only using those. See `CHANGES.md` for what the three styles look like.

1. Go to [https://www.pexels.com/api/](https://www.pexels.com/api/)
2. Click **Get Started** and create a free account.
3. Once logged in, click **Your API Key** on the dashboard.
4. Fill in the short 2-question form:
   * *What is your application?* $\rightarrow$ "Short-form video creation tool"
   * *Website/URL?* $\rightarrow$ "Personal project"
5. Copy the generated API key.
6. Paste it into `.env` (in project root):
   ```env
   PEXELS_API_KEY=your_pexels_key_here
   ```

---

## Summary of `.env` File
Once completed, your root `.env` file should look like this:
```env
GEMINI_API_KEY=AIzaSy...
# GEMINI_MODEL=gemini-3.5-flash   # optional override — see .env.example for why this exists
PEXELS_API_KEY=your_pexels_key_here
SUPABASE_URL=https://xyz.supabase.co
SUPABASE_ANON_KEY=ey...
SUPABASE_SERVICE_KEY=ey...
YOUTUBE_CLIENT_ID=...
YOUTUBE_CLIENT_SECRET=...
YOUTUBE_REFRESH_TOKEN=...
OUTPUT_DIR=output
ASSETS_DIR=assets
```
(YouTube values come from Step 2 of `docs/04_AUTONOMOUS_YOUTUBE_PUBLISHING.md`.)
