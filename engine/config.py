"""
config.py
---------
Loads and validates environment variables for each module.
Each engine module calls require() with only the vars IT needs.
This prevents crashes when one script is missing another script's credentials.

THE BUG THIS FILE'S get() USED TO HAVE, THREE TIMES

_env below is a hand-maintained list. get(key) used to return ONLY what was
in that list — so a real environment variable, correctly set in GitHub
Actions or a local .env file, could still be completely unreachable if
whoever added the FEATURE that reads it forgot to also add a line here.
That is not hypothetical: it happened to YOUTUBE_API_KEY (silently killed
trending discovery), and — found in the same audit that caught this —
TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, SMTP_HOST/USER/PASSWORD,
ALERT_EMAIL_TO, all three R2 storage credentials, PIPER_MODEL_PATH, and
GEMINI_TEMPERATURE. Email and Telegram alerts, Cloudflare R2 storage, the
offline Piper voice fallback, and a temperature override had ALL been
structurally unreachable this entire time — not because anyone configured
them wrong, but because this dict never had a line for them.

get() now falls back to a raw os.getenv() for anything not explicitly
listed below. _env stays as a readable "these are the keys this project
knows about" reference — genuinely useful for anyone skimming this file —
but it can no longer be the reason a correctly-set secret goes unseen. This
whole class of bug is now closed, not just today's known instances of it.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# All available configuration keys (loaded lazily — no crash if unused).
# See the module docstring above for why this list no longer being
# perfectly exhaustive is safe — get() falls through to os.getenv() too.
_env = {
    "GEMINI_API_KEY":           os.getenv("GEMINI_API_KEY"),
    "GEMINI_MODEL":             os.getenv("GEMINI_MODEL"),
    "GEMINI_TEMPERATURE":       os.getenv("GEMINI_TEMPERATURE"),
    "GROQ_API_KEY":             os.getenv("GROQ_API_KEY"),
    "GROQ_MODEL":               os.getenv("GROQ_MODEL"),
    "HUGGINGFACE_API_KEY":      os.getenv("HUGGINGFACE_API_KEY"),
    "HUGGINGFACE_IMAGE_MODEL":  os.getenv("HUGGINGFACE_IMAGE_MODEL"),
    "VAPID_PRIVATE_KEY":        os.getenv("VAPID_PRIVATE_KEY"),
    "VAPID_PUBLIC_KEY":         os.getenv("VAPID_PUBLIC_KEY"),
    "VAPID_CLAIM_EMAIL":        os.getenv("VAPID_CLAIM_EMAIL"),
    "PEXELS_API_KEY":           os.getenv("PEXELS_API_KEY"),
    "YOUTUBE_API_KEY":          os.getenv("YOUTUBE_API_KEY"),
    "SUPABASE_URL":             os.getenv("SUPABASE_URL"),
    "SUPABASE_ANON_KEY":        os.getenv("SUPABASE_ANON_KEY"),
    "SUPABASE_SERVICE_KEY":     os.getenv("SUPABASE_SERVICE_KEY"),
    "YOUTUBE_CLIENT_ID":        os.getenv("YOUTUBE_CLIENT_ID"),
    "YOUTUBE_CLIENT_SECRET":    os.getenv("YOUTUBE_CLIENT_SECRET"),
    "YOUTUBE_REFRESH_TOKEN":    os.getenv("YOUTUBE_REFRESH_TOKEN"),
    "OUTPUT_DIR":               os.getenv("OUTPUT_DIR", "output"),
    "ASSETS_DIR":               os.getenv("ASSETS_DIR", "assets"),
    # Alerting (engine/alerts.py, engine/health_check.py) — Telegram + email.
    # These specific seven were the ones found completely unreachable.
    "TELEGRAM_BOT_TOKEN":       os.getenv("TELEGRAM_BOT_TOKEN"),
    "TELEGRAM_CHAT_ID":         os.getenv("TELEGRAM_CHAT_ID"),
    "SMTP_HOST":                os.getenv("SMTP_HOST"),
    "SMTP_PORT":                os.getenv("SMTP_PORT"),
    "SMTP_USER":                os.getenv("SMTP_USER"),
    "SMTP_PASSWORD":            os.getenv("SMTP_PASSWORD"),
    "ALERT_EMAIL_TO":           os.getenv("ALERT_EMAIL_TO"),
    # Cloudflare R2 storage (engine/storage_r2.py) — optional alternative to
    # Supabase Storage.
    "R2_ACCOUNT_ID":            os.getenv("R2_ACCOUNT_ID"),
    "R2_ACCESS_KEY_ID":         os.getenv("R2_ACCESS_KEY_ID"),
    "R2_SECRET_ACCESS_KEY":     os.getenv("R2_SECRET_ACCESS_KEY"),
    "R2_PUBLIC_BASE":           os.getenv("R2_PUBLIC_BASE"),
    "STORAGE_BUCKET":           os.getenv("STORAGE_BUCKET"),
    # Offline TTS fallback (engine/voice_engine.py), below gTTS in the chain.
    "PIPER_MODEL_PATH":         os.getenv("PIPER_MODEL_PATH"),
}


def require(keys: list[str]) -> dict:
    """
    Call this at the top of each engine module to declare what it needs.
    Only crashes if a REQUIRED key for THAT module is missing.
    """
    result = {}
    missing = []
    for key in keys:
        # _env first (keeps the ".env with a default" behavior for the few
        # keys that have one, e.g. OUTPUT_DIR), then a raw env lookup for
        # anything real that simply isn't in the hand-maintained list above
        # — see the module docstring for why that fallback exists.
        val = _env.get(key) or os.getenv(key)
        if not val:
            missing.append(key)
        else:
            result[key] = val
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            f"Please check your .env file."
        )
    return result


def get(key: str, default=None):
    """Get any config value optionally (no crash if missing).

    Checks the curated _env dict first, then falls through to a raw
    os.getenv() for anything not explicitly listed there. That fallback is
    the actual fix for a bug that hit this project three times: a real,
    correctly-set environment variable was still invisible to every module
    that read it through this function, only because nobody had also added
    a matching line to _env above. See the module docstring for the full
    list of what that silently broke.
    """
    return _env.get(key) or os.getenv(key) or default
