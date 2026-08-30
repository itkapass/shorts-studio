"""
publish_approved.py
-------------------
PUBLISH SCRIPT — Publishes approved videos to YouTube

Called by the separate GitHub Actions "publish" workflow (runs every 30 min).
Queries Supabase for videos with status='approved', publishes them one at a time
(to avoid hitting YouTube API quota limits), then updates status to 'published'.

Deliberately throttled: publishes ONE video per run by default. Change via
the Admin Panel Settings page (publish_per_run) — this used to only read a
PUBLISH_PER_RUN env var that the settings-table value had no effect on;
FIXED so the dashboard setting is the real source of truth, with the env
var still available as an explicit CI override if you want one.
"""

import os
import json
import tempfile
import requests
from datetime import datetime, timezone
from supabase import create_client

from engine.config import require, get
from engine.publisher import upload_video
from engine import channels as channels_mod
from engine import concept_memory
from engine import storage_r2
from engine import alerts


def _load_publish_per_run(db) -> int:
    env_override = os.environ.get("PUBLISH_PER_RUN")
    if env_override:
        try:
            return int(env_override)
        except ValueError:
            pass
    try:
        row = db.table("settings").select("value").eq("key", "publish_per_run").single().execute()
        return int(row.data["value"])
    except Exception:
        return 1


def run_publish_pipeline():
    """Fetches the oldest approved video(s) and publishes them to YouTube."""
    cfg = require(["SUPABASE_URL", "SUPABASE_SERVICE_KEY"])
    db  = create_client(cfg["SUPABASE_URL"], cfg["SUPABASE_SERVICE_KEY"])

    publish_per_run = _load_publish_per_run(db)

    # Multi-channel routing. Each channel carries its own credentials and its
    # own daily cap, because YouTube's 10,000-unit budget is per Google Cloud
    # project — see engine/channels.py.
    all_channels = channels_mod.load_channels(db=db)
    if all_channels:
        print(f"[publish] {len(all_channels)} channel(s) configured:")
        for ch in all_channels:
            print(f"[publish]   - {channels_mod.describe(ch)}")

    rows = (
        db.table("videos")
        .select("*")
        .eq("status", "approved")
        .order("approved_at", desc=False)  # Oldest first
        .limit(publish_per_run)
        .execute()
        .data
    )

    if not rows:
        print("[publish] No approved videos to publish. Exiting.")
        return

    print(f"[publish] Found {len(rows)} approved video(s). Publishing...")
    published_count = 0

    for row in rows:
        job_id = row["job_id"]
        print(f"\n[publish] Publishing: '{row['title']}' (job_id: {job_id})")
        tmp_path = None

        try:
            # ── Pick the destination channel ─────────────────────────────
            channel = None
            creds = None
            if all_channels:
                channel = channels_mod.route(row.get("category") or row.get("archetype") or "",
                                             channels=all_channels)
                if not channel:
                    print(f"[publish] \u26a0 No channel accepts category "
                          f"'{row.get('category')}'. Leaving for manual export.")
                    _update_status(db, row["id"], "needs_manual",
                                   error="No channel configured for this category")
                    continue

                if channel.get("publish_mode") != "auto":
                    print(f"[publish] Channel '{channel.get('name')}' is set to manual. "
                          f"Marking for export instead of publishing.")
                    _update_status(db, row["id"], "needs_manual",
                                   error="Channel is set to manual posting")
                    continue

                cap = channels_mod.daily_cap_for(channel)
                sent = channels_mod.published_today(channel.get("id"), db=db)
                if sent >= cap:
                    # Stop BEFORE the API call. Pushing past the cap returns a
                    # 403 that also burns quota, so the next run starts even
                    # further behind.
                    print(f"[publish] Channel '{channel.get('name')}' hit its daily cap "
                          f"({sent}/{cap}). Skipping.")
                    alerts.daily_quota_reached(sent, cap)
                    continue

                creds = channels_mod.credentials_for(channel)
                if not creds:
                    alerts.youtube_auth_broken(
                        channel.get("name", "?"),
                        "The channel's YOUTUBE_* secrets are missing or incomplete.",
                    )
                    _update_status(db, row["id"], "publish_failed",
                                   error="Channel credentials missing")
                    continue

            video_url = row.get("storage_url")
            if not video_url:
                print(f"[publish] \u26a0 No storage URL for job {job_id}. Skipping.")
                _update_status(db, row["id"], "failed", error="No storage URL")
                continue

            print(f"[publish] Downloading video from storage...")
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                tmp_path = tmp.name
                resp = requests.get(video_url, stream=True, timeout=120)
                resp.raise_for_status()
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    tmp.write(chunk)

            hashtags = row.get("hashtags") or []
            if isinstance(hashtags, str):
                hashtags = json.loads(hashtags)

            result = upload_video(
                video_path=tmp_path,
                title=row["title"],
                description=row.get("description", ""),
                hashtags=hashtags,
                category="tech",
                privacy="public",
                notify_subscribers=False,
                creds_override=creds,
            )

            db.table("videos").update({
                "status":       "published",
                "youtube_id":   result["video_id"],
                "youtube_url":  result["url"],
                "channel_id":   (channel or {}).get("id"),
                "published_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", row["id"]).execute()

            # Commit the concept to the permanent ledger only now, on the way
            # out. Recording it at generation time would burn the idea even
            # when the video was rejected, slowly starving the topic pool.
            try:
                storyboard = row.get("storyboard")
                if isinstance(storyboard, str):
                    storyboard = json.loads(storyboard)
                if storyboard:
                    concept_memory.record_concept(storyboard, job_id, db=db)
            except Exception as e:
                print(f"[publish] \u26a0 Could not record concept: {e}")

            # The file has done its job. Deleting immediately is what keeps a
            # free storage tier permanently sufficient.
            storage_r2.delete_video(job_id, db=db)

            published_count += 1
            print(f"[publish] \u2713 Published: {result['url']}")

        except Exception as e:
            error_msg = _explain_error(e)
            print(f"[publish] \u2717 Failed to publish job {job_id}: {error_msg}")
            _update_status(db, row["id"], "publish_failed", error=error_msg)
            # An auth failure stops EVERY future upload, not just this one, so
            # it is the one error worth interrupting someone about.
            if "invalid_grant" in str(e).lower() or "refresh token" in error_msg.lower():
                alerts.youtube_auth_broken((channel or {}).get("name", "default"), error_msg)

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)


def _explain_error(e: Exception) -> str:
    """Turns the most common opaque OAuth failure into an actionable message
    instead of a raw SDK error, since this specific failure mode is a real,
    documented Google policy (not a bug) that this project has no code-level
    fix for: unless your Google Cloud OAuth consent screen has been moved to
    'In production' (requires Google's verification for the sensitive
    youtube.upload scope), refresh tokens for apps left in 'Testing' status
    expire after 7 days, and every publish attempt after that fails until
    you redo the local `--setup` step and update YOUTUBE_TOKEN_B64."""
    msg = str(e)
    lower = msg.lower()
    if "invalid_grant" in lower or "token has been expired or revoked" in lower:
        return (
            f"{msg}\n"
            f"This usually means your Google OAuth refresh token is no longer valid. If your "
            f"OAuth consent screen is still in 'Testing' status, Google expires refresh tokens "
            f"after 7 days — see docs/04_AUTONOMOUS_YOUTUBE_PUBLISHING.md. Fix: re-run "
            f"`python engine/publisher.py --setup` locally and update the YOUTUBE_TOKEN_B64 "
            f"GitHub secret, or move the consent screen to 'In production' for a token that "
            f"doesn't expire on a schedule."
        )
    return msg


def _update_status(db, row_id: int, status: str, error: str = None):
    update = {"status": status}
    if error:
        update["error_log"] = error[:1000]
    db.table("videos").update(update).eq("id", row_id).execute()


if __name__ == "__main__":
    run_publish_pipeline()
