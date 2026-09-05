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

def get_authenticated_service(creds_override: dict = None, force_interactive: bool = False):
    """Returns an authenticated YouTube API service object.

    Tries, in order:
      1. YOUTUBE_CLIENT_ID + YOUTUBE_CLIENT_SECRET + YOUTUBE_REFRESH_TOKEN
         env vars — the path CI/Docker should use.
      2. The local engine/youtube_token.pickle cache, if present.
      3. The interactive browser flow (only works with a real local browser).

    force_interactive=True skips 1 and 2 entirely and always opens the browser.
    `--setup` uses this. It has to: the whole reason you run setup is that the
    saved token is dead, so loading it first and trying to refresh it just
    crashes on the dead token before setup can replace it.
    """
    if force_interactive:
        return googleapiclient.discovery.build(
            API_SERVICE, API_VERSION, credentials=_run_interactive_setup()
        )

    credentials = _credentials_from_env(creds_override) or _credentials_from_pickle()

    if credentials and credentials.expired and credentials.refresh_token:
        print("[publisher] Refreshing expired OAuth access token...")
        try:
            credentials.refresh(Request())
            if os.path.exists(os.path.dirname(TOKEN_FILE) or "."):
                _save_token(credentials)  # keep the local cache warm
        except Exception as e:
            # A dead refresh token must not crash with a raw traceback. On a
            # local machine we can just re-authorise; in CI there is no browser,
            # so say plainly what to do instead of dumping a stack trace.
            print(f"[publisher] \u26a0 Stored token is no longer valid: {e}")
            credentials = None
            if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
                raise RuntimeError(
                    "The stored YOUTUBE_REFRESH_TOKEN has expired or been revoked.\n"
                    "Run this on your own computer:  python -m engine.publisher --setup\n"
                    "then update the YOUTUBE_REFRESH_TOKEN secret in GitHub with the new value."
                ) from e
            print("[publisher] Starting a fresh authorization instead...")

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
    # Drop any stale cache first, so a dead token from a previous run cannot
    # interfere with the new grant.
    try:
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
            print("[publisher] Removed the old cached token.")
    except OSError:
        pass

    env_id = get("YOUTUBE_CLIENT_ID")
    env_secret = get("YOUTUBE_CLIENT_SECRET")

    if os.path.exists(CLIENT_SECRETS_FILE):
        flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
            CLIENT_SECRETS_FILE, scopes=SCOPES
        )
    elif env_id and env_secret:
        # Build the client config in memory from environment variables, so you
        # never have to download and rename a JSON file just to authorise.
        flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_config(
            {"installed": {
                "client_id": env_id,
                "client_secret": env_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }},
            scopes=SCOPES,
        )
    else:
        raise FileNotFoundError(
            "No OAuth client credentials found. Do EITHER of these:\n\n"
            "  A) Put YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in your .env file, or\n\n"
            f"  B) Google Cloud Console -> APIs & Services -> Credentials -> your OAuth\n"
            f"     client -> Download JSON, then save it as: {CLIENT_SECRETS_FILE}\n"
        )

    print("[publisher] Opening your browser for YouTube authorization...")
    print("[publisher] Sign in with the account that owns the YouTube channel.")
    print("[publisher] If you see 'Google hasn't verified this app', click")
    print("[publisher]   Advanced -> Go to <app name> (unsafe). It is your own app.\n")
    # prompt="consent" forces Google to issue a refresh token. Without it,
    # Google omits the refresh token on re-authorisation of an app you have
    # already approved once — and a grant with no refresh token is useless
    # for unattended publishing.
    credentials = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    _save_token(credentials)

    if not credentials.refresh_token:
        print("\n[publisher] \u26a0 Google did not return a refresh token.")
        print("[publisher] Revoke this app at https://myaccount.google.com/permissions")
        print("[publisher] and run --setup again.\n")
    else:
        print("\n" + "=" * 64)
        print("  AUTHORIZATION COMPLETE")
        print("=" * 64)
        print("\n  Add these three as GitHub repository secrets:")
        print("  (Repo -> Settings -> Secrets and variables -> Actions)\n")
        print(f"  YOUTUBE_CLIENT_ID\n     {credentials.client_id}\n")
        print(f"  YOUTUBE_CLIENT_SECRET\n     {credentials.client_secret}\n")
        print(f"  YOUTUBE_REFRESH_TOKEN\n     {credentials.refresh_token}\n")
        print("=" * 64)
        print("  Copy the REFRESH TOKEN now. It is not shown again.")
        print("=" * 64 + "\n")
    return credentials


def _save_token(credentials):
    """Saves OAuth credentials to disk for local reuse (optional convenience)."""
    with open(TOKEN_FILE, "wb") as f:
        pickle.dump(credentials, f)
    print(f"[publisher] Token cached locally at {TOKEN_FILE}")


# ─── Core Upload Function ──────────────────────────────────────────────────────

def upload_captions(video_id: str, srt_content: str, creds_override: dict = None,
                    language: str = "en") -> dict:
    """Uploads a real, native YouTube caption track for a video that already
    has one from subtitle_engine's export_srt().

    WHY THIS IS SEPARATE FROM THE BURNED-IN CAPTIONS: the word-highlight text
    baked into the video frames is for engagement — it's what makes someone
    stop scrolling. This is for the two things burned-in text can never do:
    screen readers can read it, and it's the transcript YouTube actually
    indexes for search. They render completely differently to a viewer —
    this track is OFF by default, the same as on any other YouTube video,
    and only appears if someone explicitly turns captions on. It never
    duplicates or fights with the on-screen animated text.

    Best-effort by design: this is called after the real video upload has
    already succeeded, so a caption failure must never look like the publish
    itself failed. Logs a warning and returns a failure marker instead of
    raising.
    """
    if not srt_content or not srt_content.strip():
        return {"status": "skipped", "reason": "no caption content on this video"}

    import tempfile

    try:
        youtube = get_authenticated_service(creds_override)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".srt", delete=False,
                                          encoding="utf-8") as f:
            f.write(srt_content)
            tmp_path = f.name

        try:
            media = MediaFileUpload(tmp_path, mimetype="application/octet-stream")
            request = youtube.captions().insert(
                part="snippet",
                body={
                    "snippet": {
                        "videoId": video_id,
                        "language": language,
                        "name": "",       # empty = the default/unnamed track, shown simply as the language
                        "isDraft": False,  # published immediately, not left as a hidden draft
                    }
                },
                media_body=media,
                # Timings already come from edge-tts's own ground truth (or a
                # syllable estimate as a fallback) — sync=True would tell
                # YouTube to try to re-align them itself, which is a step
                # backward from timing we already trust.
                sync=False,
            )
            response = request.execute()
            print(f"[publisher] \u2713 Real captions uploaded for {video_id} "
                  f"(track id: {response.get('id', '?')})")
            return {"status": "uploaded", "caption_id": response.get("id")}
        finally:
            os.unlink(tmp_path)

    except Exception as e:
        print(f"[publisher] \u26a0 Caption upload failed for {video_id} ({e}). "
              f"The video itself published fine — only the real caption track is missing. "
              f"Burned-in captions are unaffected.")
        return {"status": "failed", "error": str(e)}


def upload_video(
    video_path: str,
    title: str,
    description: str,
    hashtags: list[str],
    category: str = "default",
    privacy: str = "public",
    notify_subscribers: bool = False,
    creds_override: dict = None,
    captions_srt: str = None,
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
        captions_srt:         Optional real .srt content (from subtitle_engine.export_srt,
                              stored on the video row). If given, uploaded as a REAL YouTube
                              caption track after the video itself is live — see
                              upload_captions() for why this is a separate, best-effort step
                              and how it differs from the burned-in on-screen captions.

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

    caption_result = None
    if captions_srt:
        caption_result = upload_captions(video_id, captions_srt, creds_override=creds_override)

    return {
        "video_id": video_id,
        "url":      url,
        "status":   "uploaded",
        "title":    title,
        "captions": caption_result,
    }


# ─── Configuration check ──────────────────────────────────────────────────────

def _check_config() -> bool:
    """Prints exactly what is and isn't set up, and what to do about it.

    This exists because setting this up involves Google Cloud, GitHub Secrets,
    a local .env, Supabase and a dashboard, and it is genuinely easy to lose
    track of which of those you have finished. Guessing wastes far more time
    than one command that just tells you.
    """
    print("\n" + "=" * 64)
    print("  YOUTUBE PUBLISHING - CONFIGURATION CHECK")
    print("=" * 64 + "\n")

    ok = True

    cid = get("YOUTUBE_CLIENT_ID")
    secret = get("YOUTUBE_CLIENT_SECRET")
    token = get("YOUTUBE_REFRESH_TOKEN")

    def show(label, value, hint):
        nonlocal ok
        if value:
            tail = value[-6:] if len(value) > 6 else value
            print(f"  [ok]      {label}  (...{tail})")
            return True
        print(f"  [MISSING] {label}")
        print(f"            {hint}")
        ok = False
        return False

    print("  Credentials in your local .env file")
    print("  " + "-" * 60)
    show("YOUTUBE_CLIENT_ID", cid,
         "Google Cloud -> APIs & Services -> Credentials -> your OAuth client")
    show("YOUTUBE_CLIENT_SECRET", secret,
         "Same screen as the client ID")
    has_token = show("YOUTUBE_REFRESH_TOKEN", token,
                     "Run: python -m engine.publisher --setup")

    print()
    print("  Local token cache")
    print("  " + "-" * 60)
    print(f"  {'[ok]     ' if os.path.exists(TOKEN_FILE) else '[none]   '} {TOKEN_FILE}")
    print("            (optional - only used for local runs)")

    if has_token and cid and secret:
        print()
        print("  Live connection test")
        print("  " + "-" * 60)
        try:
            # Verify by REFRESHING the token, not by calling a read API.
            #
            # The obvious check — channels().list(mine=True) to print the
            # channel name — needs youtube.readonly, and this app deliberately
            # requests only youtube.upload. Widening the scope just to make a
            # diagnostic prettier would mean asking for permission to read the
            # account when the app never reads it, and would contradict the
            # privacy policy. A successful refresh already proves the
            # credentials are live, which is what actually matters.
            creds = _credentials_from_env() or _credentials_from_pickle()
            creds.refresh(Request())
            print("  [ok]      Token is valid and refreshed successfully.")
            print("            Publishing will work.")

            # If a broader scope happens to have been granted, show the channel
            # name as a bonus. Never treat its absence as a failure.
            try:
                service = googleapiclient.discovery.build(
                    API_SERVICE, API_VERSION, credentials=creds
                )
                items = service.channels().list(part="snippet", mine=True).execute().get("items", [])
                if items:
                    print(f"  [ok]      Channel: {items[0]['snippet']['title']}")
            except Exception:
                print("            (Channel name not shown — this app only has upload")
                print("             permission, not read permission. That is by design.)")
        except Exception as e:
            msg = str(e)
            print(f"  [FAILED]  {msg[:180]}")
            if "invalid_grant" in msg:
                print()
                print("            Your refresh token is dead. Most likely it was created")
                print("            while your app was still in 'Testing' mode, which expires")
                print("            tokens after 7 days.")
                print()
                print("            Get a new one:  python -m engine.publisher --setup")
            elif "accessNotConfigured" in msg or "has not been used" in msg:
                print()
                print("            YouTube Data API v3 is not enabled on this Cloud project.")
                print("            Google Cloud -> APIs & Services -> Library ->")
                print("            search 'YouTube Data API v3' -> Enable")
            ok = False

    print()
    print("=" * 64)
    if ok:
        print("  All good. Add the same three values as GitHub secrets, then")
        print("  set your channel to Automatic in the dashboard.")
    else:
        print("  Fix the items marked MISSING or FAILED above, then run again.")
    print("=" * 64 + "\n")
    return ok


# ─── CLI Entry Point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YouTube Shorts Publisher")
    parser.add_argument("--setup", action="store_true",
                        help="Run OAuth browser authorization (always starts fresh)")
    parser.add_argument("--check", action="store_true",
                        help="Show what is configured and what is missing")
    parser.add_argument("--upload", type=str,
                        help="Path to .mp4 file to upload")
    parser.add_argument("--title", type=str, default="Test Video #Shorts")
    parser.add_argument("--privacy", type=str, default="private",
                        help="public | private | unlisted")
    args = parser.parse_args()

    if args.check:
        raise SystemExit(0 if _check_config() else 1)

    elif args.setup:
        print("[publisher] Running YouTube OAuth setup (fresh authorization)...")
        # force_interactive=True is essential here. Without it, setup loads the
        # OLD refresh token first and tries to refresh it — and since the whole
        # reason you are running setup is that the old token is dead, it crashes
        # on the dead token before it can ever open the browser.
        get_authenticated_service(force_interactive=True)

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
        print("Usage:\n"
              "  python -m engine.publisher --check    (what is configured?)\n"
              "  python -m engine.publisher --setup    (authorize YouTube)\n"
              "  python -m engine.publisher --upload path/to/video.mp4")
