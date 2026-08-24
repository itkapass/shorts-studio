# Tool 3: Web Studio & Local Video Rendering Guide

This guide covers running the interactive Web Dashboard and generating high-retention AI videos from your computer.

---

## 🖥️ 1. Running the Web Studio Dashboard

1. Open PowerShell or Command Prompt.
2. Navigate to the `admin-panel` folder inside wherever you cloned this project
   (an earlier version of this doc had one specific person's Windows desktop path
   hardcoded here — use your own project path instead):
   ```powershell
   cd path\to\this\project\admin-panel
   ```
3. Install dependencies (only needed once):
   ```powershell
   npm install
   ```
4. Start the dev server:
   ```powershell
   npm run dev
   ```
5. Open your browser to: **`http://localhost:5173`**

### What you can do in the Web Dashboard:
* **Create Video (`/create`)**: Input any topic, pick a visual style and tone, and
  generate a real AI storyboard (needs the `generate-storyboard` Edge Function
  deployed — see `docs/04`).
* **Trending Radar (`/trending`)**: Real YouTube search results for what's getting
  views this week (needs the `discover-trends` Edge Function — same doc).
* **Video Queue (`/queue`)**: Preview generated videos, inspect scene subtitles, and approve drafts.
* **Topic Studio (`/studio`)**: Add or edit content categories, tones, and each topic's default visual style.

---

## 🎬 2. Rendering Videos with Python Engine

### Prerequisites:
Make sure you installed Python packages once, from the project root:
```powershell
pip install -r requirements.txt
```

### Option A: Render from a Custom Prompt (On-Demand)
```powershell
python -m engine.orchestrator --prompt "Titan Company creation and evolution from Tata watches to an $18 Billion jewelry and lifestyle empire"
```

### Option B: Render from Active Topic Queue (Batch)
```powershell
python -m engine.orchestrator
```

### Where to find your finished videos:
Generated videos, voiceovers, subtitle files, and mixed audio are saved in the **`output/<job_id>/`** directory:
* `output/<job_id>/<job_id>_final.mp4` $\rightarrow$ Complete 1080x1920 video with captions & music.
* `output/<job_id>/<job_id>.srt` $\rightarrow$ Timed subtitle file for YouTube.
* `output/<job_id>/storyboard.json` $\rightarrow$ Full scene breakdown and metadata.
