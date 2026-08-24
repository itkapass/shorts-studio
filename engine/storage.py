"""
storage.py
----------
MODULE 7 — Supabase Storage upload

FIXED A REAL GAP: orchestrator.py's own docstring always promised step 8,
"Upload to Supabase Storage", and publish_approved.py has always hard-required
row["storage_url"] to publish anything — but no Python code anywhere actually
called Storage's upload API. The only place this ever happened was a separate,
unguarded `python -c "..."` block bolted onto the end of .github/workflows/
generate.yml, with no error handling and no retry. That meant:
  - Scheduled GitHub Actions runs: worked, as long as that one step didn't
    fail partway through a batch (if it did, later videos in that run were
    silently orphaned — local files gone the moment the runner tears down,
    DB row stuck at "pending" with no storage_url, forever).
  - Local runs, Docker runs, and the --prompt CLI path: never uploaded
    anything, because that logic didn't exist outside the GitHub Actions
    YAML at all.

This module is the one real implementation, called directly from
orchestrator.py so upload behavior is identical everywhere the pipeline runs.
generate.yml now just calls `python -m engine.storage --job-id <id>` (see
__main__ below) instead of duplicating this logic inline.
"""
import os
import time
import argparse

from engine.config import get

BUCKET_NAME = "shorts-videos"
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2


def _get_db():
    from supabase import create_client
    url = get("SUPABASE_URL")
    key = get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_KEY not configured")
    return create_client(url, key)


def upload_video_to_storage(local_path: str, job_id: str, db=None) -> str | None:
    """
    Uploads a rendered video file to Supabase Storage and writes the
    resulting public URL back to videos.storage_url for the matching job_id.

    Returns the public URL on success, or None on failure (never raises —
    callers get a clear return value to branch on, and the DB row is left
    however it was, so a failed upload here doesn't stop the rest of a batch
    or corrupt existing state).
    """
    if not os.path.exists(local_path):
        print(f"[storage] \u26a0 File not found, cannot upload: {local_path}")
        return None

    db = db or _get_db()
    storage_path = f"{job_id}.mp4"

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with open(local_path, "rb") as f:
                db.storage.from_(BUCKET_NAME).upload(
                    storage_path,
                    f,
                    file_options={"content-type": "video/mp4", "upsert": "true"},
                )
            public_url = db.storage.from_(BUCKET_NAME).get_public_url(storage_path)

            db.table("videos").update({"storage_url": public_url}).eq("job_id", job_id).execute()

            print(f"[storage] \u2713 Uploaded {job_id} -> {public_url}")
            return public_url

        except Exception as e:
            last_error = e
            print(f"[storage] \u26a0 Upload attempt {attempt}/{MAX_RETRIES} failed for {job_id}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)

    # All retries exhausted — record the failure on the row itself so it's
    # visible in the dashboard instead of silently staying "pending" forever
    # with no explanation.
    try:
        db.table("videos").update({
            "status": "failed",
            "error_log": f"Storage upload failed after {MAX_RETRIES} attempts: {last_error}",
        }).eq("job_id", job_id).execute()
    except Exception as log_error:
        print(f"[storage] \u26a0 Could not even record the upload failure to DB: {log_error}")

    return None


def upload_all_pending_in_dir(output_dir: str) -> dict:
    """
    Scans output_dir for {job_id}_final.mp4 files (the layout orchestrator.py
    writes) and uploads each one. Used by generate.yml right after a batch —
    see engine/storage.py __main__ below.
    """
    import glob
    results = {"uploaded": [], "failed": []}
    db = _get_db()

    pattern = os.path.join(output_dir, "**", "*_final.mp4")
    for mp4_path in glob.glob(pattern, recursive=True):
        job_id = os.path.basename(mp4_path).replace("_final.mp4", "")
        url = upload_video_to_storage(mp4_path, job_id, db=db)
        (results["uploaded"] if url else results["failed"]).append(job_id)

    print(f"[storage] Batch upload done: {len(results['uploaded'])} ok, {len(results['failed'])} failed")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload rendered video(s) to Supabase Storage.")
    parser.add_argument("--job-id", help="Upload a single job by ID (expects OUTPUT_DIR/<job_id>/<job_id>_final.mp4)")
    parser.add_argument("--all-pending", action="store_true", help="Scan OUTPUT_DIR for every *_final.mp4 and upload all of them")
    args = parser.parse_args()

    output_dir = get("OUTPUT_DIR", "output")

    if args.job_id:
        path = os.path.join(output_dir, args.job_id, f"{args.job_id}_final.mp4")
        ok = upload_video_to_storage(path, args.job_id)
        raise SystemExit(0 if ok else 1)
    elif args.all_pending:
        results = upload_all_pending_in_dir(output_dir)
        raise SystemExit(0 if not results["failed"] else 1)
    else:
        parser.print_help()
