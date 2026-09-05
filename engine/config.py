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
    "GROQ_API_KEY":             os.getenv("GROQ_API_KEY"),
    "GROQ_MODEL":               os.getenv("GROQ_MODEL"),
    "HUGGINGFACE_API_KEY":      os.getenv("HUGGINGFACE_API_KEY"),
    "HUGGINGFACE_IMAGE_MODEL":  os.getenv("HUGGINGFACE_IMAGE_MODEL"),
    "PEXELS_API_KEY":           os.getenv("PEXELS_API_KEY"),
    # This is the separate, simple YouTube Data API v3 key (distinct from
    # the YOUTUBE_CLIENT_* OAuth credentials below, which are for
    # publishing). It was missing from this dict entirely, which meant
    # engine/trending.py's get("YOUTUBE_API_KEY") always returned None even
    # when the secret WAS set correctly in GitHub Actions — the workflow
    # passed it into the environment just fine, but nothing here ever read
    # it back out. The whole trending-discovery path (the "Discover
    # Trending Topics" workflow, the --auto-add CLI, and topic_inspiration
    # below) was silently dead the entire time. Found by actually testing
    # the new topic_inspiration() wiring end-to-end rather than assuming
    # a green build meant it worked.
    "YOUTUBE_API_KEY":          os.getenv("YOUTUBE_API_KEY"),
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
