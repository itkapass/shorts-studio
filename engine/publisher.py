"""
publisher.py
------------
MODULE 7 — YouTube Data API v3 Uploader

Uploads a rendered video to YouTube as a Short.
Handles:
  - OAuth 2.0 authentication with persistent refresh tokens
  - Correct metadata (title, description, tags, category)
  - #Shorts classification (required for YouTube Shorts feed)
  - Resumable upload (handles large files and network interruptions)

IMPORTANT: You must complete the one-time OAuth setup first.
Run: python engine/publisher.py --setup

AUTH, FIXED: config.py has always declared YOUTUBE_CLIENT_ID,
YOUTUBE_CLIENT_SECRET, and YOUTUBE_REFRESH_TOKEN — but this file never
actually read them; it only ever used a local pickle file
(engine/youtube_token.pickle) + an interactive browser flow, which cannot
run on a headless CI runner at all. The workflow (.github/workflows/
publish.yml) worked around that by base64-encoding the pickle file into a
GitHub secret and decoding it back to that exact path before each run —
functional, but a roundabout, hard-to-inspect way to move three plain
strings around. get_authenticated_service() now tries the env vars FIRST
(works identically in GitHub Actions, Docker, or a local .env — no pickle,
no base64), and only falls back to the local pickle file for the
convenience of not re-running --setup on every local test. --setup now
prints the refresh token directly so you can paste it into
YOUTUBE_REFRESH_TOKEN (alongside YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET,
which are already in your downloaded OAuth client JSON) as plain GitHub
secrets instead.

REMINDER (this is a Google policy, not something this code can fix): if
your OAuth consent screen is still in "Testing" status, the refresh token
above expires after 7 days regardless of which auth path you use. See
docs/04_AUTONOMOUS_YOUTUBE_PUBLISHING.md.
"""

import os
import json
import argparse
import pickle

import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

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


# ─── YouTube API Constants ─────────────────────────────────────────────────────
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
API_SERVICE = "youtube"
API_VERSION = "v3"

# Local pickle cache — dev convenience only, not required (see module docstring).
TOKEN_FILE = "engine/youtube_token.pickle"
CLIENT_SECRETS_FILE = "engine/youtube_client_secrets.json"

# YouTube category IDs
# 28 = Science & Technology (best for tech explainers → highest RPM)
# 27 = Education
# 22 = People & Blogs (sarcasm / advice content)
CATEGORY_MAP = {
    "tech":      "28",
    "education": "27",
    "lifestyle": "22",
    "default":   "28",
}


# ─── Authentication ────────────────────────────────────────────────────────────

def get_authenticated_service(creds_override: dict = None):
    """Returns an authenticated YouTube API service object.

    Tries, in order:
      1. YOUTUBE_CLIENT_ID + YOUTUBE_CLIENT_SECRET + YOUTUBE_REFRESH_TOKEN
         env vars — the path CI/Docker should use.
      2. The local engine/youtube_token.pickle cache, if present.
      3. The interactive browser flow (only works with a real local browser).
    """
    credentials = _credentials_from_env(creds_override) or _credentials_from_pickle()

    if credentials and credentials.expired and credentials.refresh_token:
        print("[publisher] Refreshing expired OAuth access token...")
        credentials.refresh(Request())
        if os.path.exists(os.path.dirname(TOKEN_FILE) or "."):
            _save_token(credentials)  # keep the local cache warm, if we're using one

    if not credentials or not credentials.valid:
        credentials = _run_interactive_setup()

    return googleapiclient.discovery.build(API_SERVICE, API_VERSION, credentials=credentials)


def _credentials_from_env(creds_override: dict = None):
    """Loads OAuth credentials.

    `creds_override` lets a specific channel supply its own client id, secret
    and refresh token (see engine/channels.py). Each channel gets its own
    Google Cloud project so each gets its own 10,000-unit daily API budget —
    quota is per project, not per channel, so sharing one project across five
    channels would cap all five at 6 uploads a day between them.
    """
    if creds_override:
        client_id = creds_override.get("client_id")
        client_secret = creds_override.get("client_secret")
        refresh_token = creds_override.get("refresh_token")
    else:
        client_id = get("YOUTUBE_CLIENT_ID")
        client_secret = get("YOUTUBE_CLIENT_SECRET")
        refresh_token = get("YOUTUBE_REFRESH_TOKEN")
    if not (client_id and client_secret and refresh_token):
        return None

    creds = google.oauth2.credentials.Credentials(
        token=None,  # no cached access token — force an immediate refresh below
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    try:
        creds.refresh(Request())
    except Exception as e:
        msg = str(e).lower()
        if "invalid_grant" in msg:
            raise RuntimeError(
                "The YouTube refresh token was rejected (invalid_grant).\n\n"
                "The usual cause: your Google OAuth consent screen is still in 'Testing' "
                "status, and Google expires refresh tokens after 7 days in that state.\n\n"
                "PERMANENT FIX (do this once, takes 2 minutes): set the consent screen to "
                "'In production'. Tokens then stop expiring on the 7-day clock. Step-by-step "
                "in docs/07_YOUTUBE_AND_CHANNELS.md section 3.\n\n"
                "TEMPORARY FIX: re-run `python engine/publisher.py --setup` and update the "
                "secret — but you will be back here in 7 days."
            ) from e
        raise
    return creds


def _credentials_from_pickle():
    if not os.path.exists(TOKEN_FILE):
        return None
    with open(TOKEN_FILE, "rb") as f:
        return pickle.load(f)


def _run_interactive_setup():
    """Real, one-time browser-based OAuth grant. Only works locally (needs
    an actual browser) — this is exactly why the env-var path above exists
    for everywhere else."""
    if not os.path.exists(CLIENT_SECRETS_FILE):
        raise FileNotFoundError(
            f"YouTube client secrets not found at: {CLIENT_SECRETS_FILE}\n"
            f"Download it from Google Cloud Console \u2192 Credentials \u2192 OAuth 2.0 Client IDs \u2192 Download JSON\n"
            f"Rename it to: {CLIENT_SECRETS_FILE}"
        )
    print("[publisher] Opening browser for YouTube authorization (one-time setup)...")
    flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES
    )
    credentials = flow.run_local_server(port=0)
    _save_token(credentials)

    print("\n[publisher] \u2713 Authorization complete.")
    print("[publisher] For CI/Docker (recommended), add these as plain GitHub secrets — no")
    print("[publisher] base64/pickle step needed — instead of YOUTUBE_TOKEN_B64:")
    print(f"    YOUTUBE_CLIENT_ID     = {credentials.client_id}")
    print(f"    YOUTUBE_CLIENT_SECRET = {credentials.client_secret}")
    print(f"    YOUTUBE_REFRESH_TOKEN = {credentials.refresh_token}")
    print("[publisher] (Also cached locally at engine/youtube_token.pickle for local runs.)\n")
    return credentials


def _save_token(credentials):
    """Saves OAuth credentials to disk for local reuse (optional convenience)."""
    with open(TOKEN_FILE, "wb") as f:
        pickle.dump(credentials, f)
    print(f"[publisher] Token cached locally at {TOKEN_FILE}")


# ─── Core Upload Function ──────────────────────────────────────────────────────

def upload_video(
    video_path: str,
    title: str,
    description: str,
    hashtags: list[str],
    category: str = "default",
    privacy: str = "public",
    notify_subscribers: bool = False,
    creds_override: dict = None,
) -> dict:
    """
    Uploads a video to YouTube as a Short.

    Args:
        video_path:           Path to the rendered .mp4 file
        title:                Video title (max 100 chars, must include #Shorts)
        description:          Video description (max 5000 chars)
        hashtags:             List of hashtag strings (e.g., ["#Shorts", "#Technology"])
        category:             Content category key from CATEGORY_MAP
        privacy:              "public" | "private" | "unlisted"
        notify_subscribers:   Whether to notify subscribers (default False for batch uploads)
        creds_override:       Per-channel OAuth credentials from engine/channels.py.
                              None uses the default YOUTUBE_* environment variables.

    Returns:
        {"video_id": "...", "url": "https://youtube.com/shorts/...", "status": "uploaded"}

    Raises:
        FileNotFoundError: If video_path doesn't exist
        googleapiclient.errors.HttpError: On API quota or upload errors
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # ── Build metadata ─────────────────────────────────────────────────────────
    # Ensure #Shorts in title (required for YouTube Shorts classification)
    if "#Shorts" not in title and "#shorts" not in title.lower():
        title = title[:90] + " #Shorts"

    # Build description with hashtags at the end
    hashtag_string = " ".join(hashtags)
    full_description = f"{description}\n\n{hashtag_string}"

    # Category ID
    category_id = CATEGORY_MAP.get(category, CATEGORY_MAP["default"])

    body = {
        "snippet": {
            "title":       title[:100],     # YouTube max title length
            "description": full_description[:5000],
            "tags":        [tag.lstrip("#") for tag in hashtags[:15]],  # Max 15 tags
            "categoryId":  category_id,
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus":          privacy,
            "selfDeclaredMadeForKids": False,
            "notifySubscribers":      notify_subscribers,
        },
    }

    # ── Upload ─────────────────────────────────────────────────────────────────
    print(f"[publisher] Uploading: '{title}'")
    print(f"[publisher] File: {video_path} ({os.path.getsize(video_path) / 1024 / 1024:.1f} MB)")

    youtube = get_authenticated_service(creds_override)

    media = MediaFileUpload(
        video_path,
        chunksize=10 * 1024 * 1024,  # 10MB chunks (resumable upload)
        resumable=True,
        mimetype="video/mp4",
    )

    # NOTE: this used to also pass stabilize=False. Confirmed via YouTube's
    # own API revision history: "the videos.insert method's autoLevels and
    # stabilize parameters are now deprecated... their values are ignored."
    # Harmless, but does nothing — removed rather than leave dead code that
    # implies a behavior it doesn't have.
    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            progress = int(status.progress() * 100)
            print(f"[publisher] Upload progress: {progress}%", end="\r")

    video_id = response.get("id", "")
    url = f"https://www.youtube.com/shorts/{video_id}"

    print(f"\n[publisher] ✓ Uploaded successfully!")
    print(f"[publisher] Video ID: {video_id}")
    print(f"[publisher] URL: {url}")

    return {
        "video_id": video_id,
        "url":      url,
        "status":   "uploaded",
        "title":    title,
    }


# ─── CLI Entry Point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YouTube Shorts Publisher")
    parser.add_argument("--setup", action="store_true",
                        help="Run one-time OAuth browser authorization")
    parser.add_argument("--upload", type=str,
                        help="Path to .mp4 file to upload")
    parser.add_argument("--title", type=str, default="Test Video #Shorts")
    parser.add_argument("--privacy", type=str, default="private",
                        help="public | private | unlisted")
    args = parser.parse_args()

    if args.setup:
        print("[publisher] Running one-time YouTube OAuth setup...")
        get_authenticated_service()
        print("[publisher] ✓ Setup complete! You can now run automated uploads.")

    elif args.upload:
        result = upload_video(
            video_path=args.upload,
            title=args.title,
            description="Test upload from automated pipeline.",
            hashtags=["#Shorts", "#Technology", "#AI"],
            privacy=args.privacy,
        )
        print(json.dumps(result, indent=2))

    else:
        print("Usage:\n  python engine/publisher.py --setup\n  python engine/publisher.py --upload path/to/video.mp4")
