"""
config.py
---------
Loads and validates environment variables for each module.
Each engine module calls require() with only the vars IT needs.
This prevents crashes when one script is missing another script's credentials.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# All available configuration keys (loaded lazily — no crash if unused)
_env = {
    "GEMINI_API_KEY":           os.getenv("GEMINI_API_KEY"),
    "GEMINI_MODEL":             os.getenv("GEMINI_MODEL"),
    "PEXELS_API_KEY":           os.getenv("PEXELS_API_KEY"),
    "SUPABASE_URL":             os.getenv("SUPABASE_URL"),
    "SUPABASE_ANON_KEY":        os.getenv("SUPABASE_ANON_KEY"),
    "SUPABASE_SERVICE_KEY":     os.getenv("SUPABASE_SERVICE_KEY"),
    "YOUTUBE_CLIENT_ID":        os.getenv("YOUTUBE_CLIENT_ID"),
    "YOUTUBE_CLIENT_SECRET":    os.getenv("YOUTUBE_CLIENT_SECRET"),
    "YOUTUBE_REFRESH_TOKEN":    os.getenv("YOUTUBE_REFRESH_TOKEN"),
    "OUTPUT_DIR":               os.getenv("OUTPUT_DIR", "output"),
    "ASSETS_DIR":               os.getenv("ASSETS_DIR", "assets"),
}


def require(keys: list[str]) -> dict:
    """
    Call this at the top of each engine module to declare what it needs.
    Only crashes if a REQUIRED key for THAT module is missing.
    """
    result = {}
    missing = []
    for key in keys:
        val = _env.get(key)
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
    """Get any config value optionally (no crash if missing)."""
    return _env.get(key) or default
