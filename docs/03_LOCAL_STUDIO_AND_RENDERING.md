# Tool 3: Web Studio & Local Video Rendering Guide

This guide covers running the interactive Web Dashboard and generating high-retention AI videos from your computer.

---

## ⚠️ 0. System Requirement: ffmpeg (read this before you hit `[WinError 2]`)

Both Whisper (caption timing) and MoviePy (final rendering) shell out to the real
**ffmpeg program** — not a Python package, an actual executable on your system PATH.
`pip install -r requirements.txt` installs Python packages like `ffmpeg-python`, which
is just a wrapper — it does **not** install ffmpeg itself. Skipping this step is the
single most common way to hit this, deep in a Whisper traceback:
```
FileNotFoundError: [WinError 2] The system cannot find the file specified
```
That error means exactly one thing: ffmpeg isn't on PATH. Fix:

**Windows:**
```powershell
winget install ffmpeg
```
Then **open a brand new terminal window** — this is the part people miss. PATH
changes from an installer don't apply to a terminal that was already open before you
ran it; your existing PowerShell/Command Prompt window won't see it until you close
and reopen it (or restart your IDE's integrated terminal).

**macOS:**
```bash
brew install ffmpeg
```

**Linux:**
```bash
sudo apt-get install ffmpeg
```

**Verify it worked** (in whichever terminal you'll actually run the pipeline from):
```
ffmpeg -version
```
If that prints a version number, you're set. If it says "not recognized" / "command
not found", the install didn't complete or you're still in an old terminal session.

(GitHub Actions and Docker already install this automatically — `generate.yml`,
`publish.yml`, and the `Dockerfile` each have their own explicit ffmpeg install step.
This is specifically about running things directly on your own machine.)

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
