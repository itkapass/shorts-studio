"""
storage_r2.py — video file storage, on Cloudflare R2 or Supabase.
=================================================================

WHY R2 INSTEAD OF SUPABASE STORAGE
Supabase's free tier gives 1 GB. At 5-25 MB per rendered Short that is roughly
40-200 videos before everything stops, and "everything stops" here means renders
succeed and then fail to upload, which is the most annoying possible failure
because you have already paid the compute.

Cloudflare R2's free tier gives 10 GB of storage, 1 million writes/month, and —
the part that actually matters — zero egress fees. Every other object store
charges for downloads, and this pipeline downloads every video again at publish
time. R2 makes that free.

10 GB with automatic deletion after publish is effectively unlimited for this
use case: you would need to be sitting on 400+ unreviewed videos to fill it.

BACKEND SELECTION IS AUTOMATIC
Configure R2 credentials and R2 is used. Leave them unset and it falls back to
Supabase Storage, unchanged, so an existing setup keeps working with no edits.
Both backends implement the same three functions, so nothing upstream cares
which one is active.

R2 IS S3-COMPATIBLE
It speaks the S3 API, so boto3 talks to it directly with an endpoint override.
No Cloudflare-specific SDK, and if you ever outgrow R2 the same code points at
Backblaze B2 or S3 by changing one URL.
"""
import os
import time

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

from engine.config import get

BUCKET_DEFAULT = "shorts-videos"
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2

# Free-tier ceilings, used for the storage-pressure alert and the render brake.
R2_FREE_LIMIT_MB = 10 * 1024
SUPABASE_FREE_LIMIT_MB = 1024
PAUSE_RENDERS_ABOVE_PCT = 90


def backend_name() -> str:
    if get("R2_ACCOUNT_ID") and get("R2_ACCESS_KEY_ID") and get("R2_SECRET_ACCESS_KEY"):
        return "r2"
    return "supabase"


def storage_limit_mb() -> int:
    return R2_FREE_LIMIT_MB if backend_name() == "r2" else SUPABASE_FREE_LIMIT_MB


# ── R2 (S3-compatible) ───────────────────────────────────────────────────────


def _r2_client():
    import boto3
    from botocore.config import Config

    account = get("R2_ACCOUNT_ID")
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account}.r2.cloudflarestorage.com",
        aws_access_key_id=get("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=get("R2_SECRET_ACCESS_KEY"),
        # R2 ignores regions but boto3 requires one to be set.
        region_name="auto",
        config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
    )


def _r2_public_url(key: str) -> str:
    """Public URL for an object.

    R2_PUBLIC_BASE is the r2.dev subdomain (or your custom domain) that
    Cloudflare gives you when you enable public access on the bucket. Without
    it, objects exist but nothing can read them — including YouTube, which
    needs to fetch the file at publish time.
    """
    base = (get("R2_PUBLIC_BASE") or "").rstrip("/")
    if not base:
        raise RuntimeError(
            "R2_PUBLIC_BASE is not set. In the Cloudflare dashboard open your bucket -> "
            "Settings -> Public access -> 'R2.dev subdomain' -> Allow, then copy the "
            "https://pub-....r2.dev URL into R2_PUBLIC_BASE. See docs/06."
        )
    return f"{base}/{key}"


def _r2_upload(local_path: str, key: str, bucket: str) -> str:
    client = _r2_client()
    with open(local_path, "rb") as f:
        client.put_object(Bucket=bucket, Key=key, Body=f, ContentType="video/mp4")
    return _r2_public_url(key)


def _r2_delete(key: str, bucket: str) -> bool:
    _r2_client().delete_object(Bucket=bucket, Key=key)
    return True


def _r2_usage_mb(bucket: str) -> float:
    client = _r2_client()
    total, token = 0, None
    while True:
        kwargs = {"Bucket": bucket, "MaxKeys": 1000}
        if token:
            kwargs["ContinuationToken"] = token
        resp = client.list_objects_v2(**kwargs)
        for obj in resp.get("Contents", []):
            total += obj.get("Size", 0)
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")
    return total / (1024 * 1024)


# ── Supabase Storage (fallback) ──────────────────────────────────────────────


def _sb():
    from supabase import create_client
    url, key = get("SUPABASE_URL"), get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_KEY not configured")
    return create_client(url, key)


def _sb_upload(local_path: str, key: str, bucket: str, db=None) -> str:
    db = db or _sb()
    with open(local_path, "rb") as f:
        db.storage.from_(bucket).upload(
            key, f, file_options={"content-type": "video/mp4", "upsert": "true"}
        )
    return db.storage.from_(bucket).get_public_url(key)


def _sb_delete(key: str, bucket: str, db=None) -> bool:
    db = db or _sb()
    db.storage.from_(bucket).remove([key])
    return True


def _sb_usage_mb(bucket: str, db=None) -> float:
    db = db or _sb()
    total = 0
    files = db.storage.from_(bucket).list()
    for f in files or []:
        total += (f.get("metadata") or {}).get("size", 0) or 0
    return total / (1024 * 1024)


# ── Public API ───────────────────────────────────────────────────────────────


def upload_video(local_path: str, job_id: str, db=None) -> str | None:
    """Uploads a rendered video and writes its URL to videos.storage_url.

    Returns the public URL, or None on failure. Never raises — a failed upload
    should cost you one video, not the rest of the batch.
    """
    if not os.path.exists(local_path):
        print(f"[storage] ⚠ File not found, cannot upload: {local_path}")
        return None

    bucket = get("STORAGE_BUCKET", BUCKET_DEFAULT)
    key = f"{job_id}.mp4"
    backend = backend_name()
    db = db or _sb()

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            url = _r2_upload(local_path, key, bucket) if backend == "r2" \
                else _sb_upload(local_path, key, bucket, db=db)
            db.table("videos").update({
                "storage_url": url,
                "storage_backend": backend,
            }).eq("job_id", job_id).execute()
            size_mb = os.path.getsize(local_path) / (1024 * 1024)
            print(f"[storage] ✓ Uploaded {job_id} ({size_mb:.1f} MB) to {backend} -> {url}")
            return url
        except Exception as e:
            last_error = e
            print(f"[storage] ⚠ Upload attempt {attempt}/{MAX_RETRIES} failed for {job_id}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)

    try:
        db.table("videos").update({
            "status": "failed",
            "error_log": f"Storage upload failed after {MAX_RETRIES} attempts: {last_error}",
        }).eq("job_id", job_id).execute()
    except Exception as log_error:
        print(f"[storage] ⚠ Could not even record the upload failure: {log_error}")
    return None


def delete_video(job_id: str, db=None) -> bool:
    """Deletes a video's file and clears its URL.

    Called the moment a video reaches a terminal state (published, rejected,
    or exported for manual posting). This is what keeps a small free tier
    permanently sufficient: files exist only during the review window.
    """
    bucket = get("STORAGE_BUCKET", BUCKET_DEFAULT)
    key = f"{job_id}.mp4"
    backend = backend_name()
    try:
        if backend == "r2":
            _r2_delete(key, bucket)
        else:
            _sb_delete(key, bucket, db=db)
        try:
            (db or _sb()).table("videos").update(
                {"storage_url": None, "storage_freed_at": "now()"}
            ).eq("job_id", job_id).execute()
        except Exception:
            pass
        print(f"[storage] ✓ Freed storage for {job_id}")
        return True
    except Exception as e:
        print(f"[storage] ⚠ Could not delete {job_id}: {e}")
        return False


def usage_mb() -> float:
    bucket = get("STORAGE_BUCKET", BUCKET_DEFAULT)
    try:
        return _r2_usage_mb(bucket) if backend_name() == "r2" else _sb_usage_mb(bucket)
    except Exception as e:
        print(f"[storage] ⚠ Could not measure usage: {e}")
        return 0.0


def check_storage_pressure(alert_fn=None) -> dict:
    """Returns storage state and whether rendering should pause.

    Pausing BEFORE rendering rather than failing during upload is deliberate:
    a render is 5+ minutes of compute, and discovering the bucket is full after
    paying that is pure waste.
    """
    used = usage_mb()
    limit = storage_limit_mb()
    pct = (used / limit * 100) if limit else 0
    should_pause = pct >= PAUSE_RENDERS_ABOVE_PCT

    if pct >= 75 and alert_fn:
        try:
            alert_fn(used, limit)
        except Exception:
            pass

    return {
        "used_mb": round(used, 1), "limit_mb": limit, "percent": round(pct, 1),
        "backend": backend_name(), "should_pause_renders": should_pause,
    }


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Storage utilities")
    p.add_argument("--usage", action="store_true", help="Report storage usage")
    p.add_argument("--upload", help="Local file to upload")
    p.add_argument("--job-id", help="Job id for --upload / --delete")
    p.add_argument("--delete", action="store_true", help="Delete a job's file")
    a = p.parse_args()

    if a.usage:
        print(check_storage_pressure())
    elif a.upload and a.job_id:
        print(upload_video(a.upload, a.job_id))
    elif a.delete and a.job_id:
        print(delete_video(a.job_id))
    else:
        p.print_help()
