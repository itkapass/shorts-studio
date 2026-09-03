"""
storage.py — COMPATIBILITY SHIM.
================================

Storage moved to engine/storage_r2.py, which supports Cloudflare R2 (10 GB
free, no egress fees) as well as Supabase Storage (1 GB free) and picks
between them automatically based on which credentials are configured.

This file stays so that any existing command, workflow step, or note that
references `engine.storage` keeps working. Everything here forwards to the
new module. There is no separate implementation to drift out of sync.

New code should import engine.storage_r2 directly.
"""
import os
import sys

# Allow BOTH `python -m engine.publisher --setup` (correct) and
# `python engine/publisher.py --setup` (what people naturally type).
# Running a file directly puts engine/ on sys.path instead of the project root,
# so `from engine.config import ...` fails with ModuleNotFoundError. Adding the
# project root here makes the natural command work too, because telling a
# beginner "you typed it wrong" is a worse answer than making both work.
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.storage_r2 import (  # noqa: F401
    upload_video, delete_video, usage_mb, check_storage_pressure, backend_name,
)


def upload_video_to_storage(local_path: str, job_id: str, db=None):
    """Old name for upload_video(). Kept for backwards compatibility."""
    return upload_video(local_path, job_id, db=db)


def upload_all_pending(db=None):
    """Uploads any rendered file that has no storage_url yet.

    Rarely needed now that the orchestrator uploads inline, but it is the
    recovery path if a run is interrupted between rendering and uploading.
    """
    from engine.config import get
    from supabase import create_client

    db = db or create_client(get("SUPABASE_URL"), get("SUPABASE_SERVICE_KEY"))
    output_dir = get("OUTPUT_DIR", "output")
    rows = db.table("videos").select("job_id").is_("storage_url", "null").execute().data or []

    done = 0
    for row in rows:
        job_id = row["job_id"]
        path = os.path.join(output_dir, job_id, f"{job_id}_final.mp4")
        if os.path.exists(path) and upload_video(path, job_id, db=db):
            done += 1
    print(f"[storage] Uploaded {done} pending file(s).")
    return done


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Storage utilities (shim for storage_r2)")
    p.add_argument("--job-id")
    p.add_argument("--all-pending", action="store_true")
    p.add_argument("--usage", action="store_true")
    a = p.parse_args()

    if a.usage:
        print(check_storage_pressure())
    elif a.all_pending:
        upload_all_pending()
    elif a.job_id:
        import os
        from engine.config import get
        path = os.path.join(get("OUTPUT_DIR", "output"), a.job_id, f"{a.job_id}_final.mp4")
        print(upload_video(path, a.job_id))
    else:
        p.print_help()
