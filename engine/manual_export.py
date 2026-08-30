"""
manual_export.py — "I'll post this one myself" package builder.
===============================================================

WHAT IT DOES
Bundles everything needed to upload a video by hand into one folder and one zip:
    <job_id>/
      video.mp4              the render
      thumbnail.jpg          a frame pulled from the first third of the video
      title.txt              ready to paste
      description.txt        description + hashtags, already assembled
      hashtags.txt           hashtags alone, for platforms that want them apart
      captions.srt           subtitle file, uploadable to YouTube
      script.txt             the plain narration, for reference or reuse
      POST_THIS.md           a checklist with the exact steps and settings

WHY IT EXISTS
Two reasons, both practical. First, some videos belong on a channel the
pipeline does not own, or on TikTok/Instagram, or should go out at a moment of
your choosing. Second, it is an escape hatch: if YouTube auth breaks on a
Friday, publishing does not stop — you export and post manually while the
token gets fixed.

WHY THE CHECKLIST FILE
Uploading a Short by hand has settings that are easy to get wrong and matter a
lot: "Not made for kids" has to be set or the video loses monetisation and
comments, and the aspect ratio plus the #Shorts tag is what gets it into the
Shorts feed at all. Writing those into the package means the same decisions get
made whether the machine posts it or you do.

AFTER EXPORT
The video's storage file is deleted and its row is marked `exported`. It has
left the pipeline, so keeping the file costs space for no reason — that is the
same lifecycle rule that keeps a free storage tier permanently sufficient.
"""
import json
import os
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone

import requests

from engine.config import get

EXPORT_ROOT = os.path.join(get("OUTPUT_DIR", "output"), "manual_exports")


def _safe_name(text: str, limit: int = 60) -> str:
    keep = "".join(c if (c.isalnum() or c in " -_") else "" for c in (text or ""))
    return "_".join(keep.split())[:limit] or "video"


def _download(url: str, dest: str) -> bool:
    try:
        with requests.get(url, stream=True, timeout=180) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    f.write(chunk)
        return True
    except Exception as e:
        print(f"[manual_export] ⚠ Could not download video: {e}")
        return False


def _grab_thumbnail(video_path: str, dest: str, duration: float = None) -> bool:
    """Pulls a still for the thumbnail.

    Takes it at ~30% through rather than at 0s: the first frame is often a
    fade-in or an establishing beat, and a black or half-faded thumbnail costs
    real clicks.
    """
    at = max((duration or 20) * 0.3, 1.0)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(at), "-i", video_path,
             "-frames:v", "1", "-q:v", "2", dest],
            capture_output=True, timeout=90, check=True,
        )
        return os.path.exists(dest)
    except Exception as e:
        print(f"[manual_export] ⚠ Could not extract thumbnail: {e}")
        return False


def _checklist(row: dict, storyboard: dict) -> str:
    title = row.get("title", "")
    tags = row.get("hashtags") or []
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except Exception:
            tags = [t for t in tags.split() if t.startswith("#")]

    return f"""# Post this manually

**{title}**

Job: `{row.get('job_id')}`  ·  Style: `{row.get('render_style')}`  ·  Category: `{row.get('category') or 'unset'}`
Exported: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}

## Steps

1. Open YouTube Studio and click **Create -> Upload videos**.
2. Select `video.mp4` from this folder.
3. Paste the contents of `title.txt` into the title field.
4. Paste the contents of `description.txt` into the description field.
   The hashtags are already at the bottom of it. Do not add more than about
   15 — YouTube ignores all of them past that point.
5. Under **Audience**, choose **No, it's not made for kids**.
   This one is not optional. Getting it wrong disables comments, removes the
   video from recommendations, and blocks monetisation on it.
6. Leave **Age restriction** off unless the content genuinely warrants it.
7. On the **Video elements** screen, click **Upload subtitles** and select
   `captions.srt`. Captions measurably lift watch time on Shorts because most
   people watch muted.
8. On the **Visibility** screen, choose **Public** (or schedule it).
9. Publish.

## Confirm it registered as a Short

After publishing, open the video. The URL should contain `/shorts/`.
If it does not, the video was not classified as a Short. That happens when the
aspect ratio is not vertical or the length is over 3 minutes. This render is
1080x1920 and {row.get('duration') or '?'} seconds, so both should be fine.

## Files in this folder

| File | What it is |
|---|---|
| `video.mp4` | The finished video, 1080x1920 |
| `thumbnail.jpg` | A frame you can upload as a custom thumbnail |
| `title.txt` | Title, ready to paste |
| `description.txt` | Description with hashtags appended |
| `hashtags.txt` | Hashtags on their own, for other platforms |
| `captions.srt` | Subtitles, uploadable in step 7 |
| `script.txt` | The narration as plain text |

## Reusing this on other platforms

The same file works as-is on Instagram Reels and TikTok — both take 1080x1920.
Do not reuse the description verbatim across platforms; each one's search works
differently, and identical copy across accounts is one of the signals platforms
use to detect bulk-posted content.
"""


def export_for_manual_posting(job_id: str, db=None, delete_after: bool = True) -> dict:
    """Builds the package. Returns {"ok", "folder", "zip", "error"}."""
    from engine import storage_r2

    if db is None:
        from supabase import create_client
        db = create_client(get("SUPABASE_URL"), get("SUPABASE_SERVICE_KEY"))

    row = db.table("videos").select("*").eq("job_id", job_id).single().execute().data
    if not row:
        return {"ok": False, "error": f"No video found with job_id={job_id}"}
    if not row.get("storage_url"):
        return {"ok": False, "error": "This video has no stored file (already published, exported, or cleaned up)."}

    folder = os.path.join(EXPORT_ROOT, f"{job_id}_{_safe_name(row.get('title'))}")
    os.makedirs(folder, exist_ok=True)

    video_path = os.path.join(folder, "video.mp4")
    if not _download(row["storage_url"], video_path):
        return {"ok": False, "error": "Download from storage failed."}

    storyboard = row.get("storyboard")
    if isinstance(storyboard, str):
        try:
            storyboard = json.loads(storyboard)
        except Exception:
            storyboard = {}
    storyboard = storyboard or {}

    tags = row.get("hashtags") or []
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except Exception:
            tags = []
    hashtag_line = " ".join(tags)

    title = (row.get("title") or "").strip()
    description = (row.get("description") or "").strip()
    script = " ".join(s.get("voice_text", "") for s in storyboard.get("scenes", []))

    writes = {
        "title.txt": title,
        "description.txt": f"{description}\n\n{hashtag_line}".strip(),
        "hashtags.txt": hashtag_line,
        "script.txt": script,
        "POST_THIS.md": _checklist(row, storyboard),
        "storyboard.json": json.dumps(storyboard, indent=2, ensure_ascii=False),
    }
    for name, content in writes.items():
        with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
            f.write(content)

    # The .srt is regenerated from the storyboard rather than copied, because
    # the render's own .srt lives in a temp dir that is long gone by now.
    _write_srt(storyboard, os.path.join(folder, "captions.srt"))
    _grab_thumbnail(video_path, os.path.join(folder, "thumbnail.jpg"), row.get("duration"))

    zip_path = f"{folder}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(folder):
            for name in files:
                full = os.path.join(root, name)
                z.write(full, os.path.relpath(full, folder))

    try:
        db.table("videos").update({
            "status": "exported",
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }).eq("job_id", job_id).execute()
    except Exception as e:
        print(f"[manual_export] ⚠ Could not update status: {e}")

    if delete_after:
        storage_r2.delete_video(job_id, db=db)

    print(f"[manual_export] ✓ Package ready: {zip_path}")
    return {"ok": True, "folder": folder, "zip": zip_path}


def _write_srt(storyboard: dict, path: str):
    """Scene-level SRT. Word-level timings are not persisted after render, so
    this is per-scene rather than per-word — still fully usable as an upload,
    just less granular than the burned-in captions."""
    def fmt(sec):
        h, m = int(sec // 3600), int((sec % 3600) // 60)
        s, ms = int(sec % 60), int((sec % 1) * 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    lines, idx = [], 1
    for scene in storyboard.get("scenes", []):
        text = (scene.get("voice_text") or "").strip()
        if not text:
            continue
        start = float(scene.get("time_start", 0))
        end = float(scene.get("time_end", start + 3))
        lines += [str(idx), f"{fmt(start)} --> {fmt(end)}", text, ""]
        idx += 1

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Build a manual-posting package for a video.")
    p.add_argument("--job-id", required=True)
    p.add_argument("--keep-storage", action="store_true",
                   help="Do not delete the stored file after exporting")
    a = p.parse_args()
    result = export_for_manual_posting(a.job_id, delete_after=not a.keep_storage)
    raise SystemExit(0 if result.get("ok") else 1)
