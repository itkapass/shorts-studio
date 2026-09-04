"""
backup_provider.py — a free, independent fallback for when Gemini's daily
allowance is genuinely gone.
==============================================================================

WHY THIS EXISTS

Gemini's free tier gives ~20 requests/day. That comfortably covers six
videos on the normal schedule — but it is exactly zero help during the one
situation you actually asked for: a manual test right after code changed, or
an urgent video that has to happen NOW, landing on a day the allowance is
already spent. Waiting for midnight Pacific is not an acceptable answer to
"I need to test this right now."

Groq (groq.com — a hosting company, unrelated to xAI's "Grok") runs open
models like Llama 3.3 70B on its own chips. Its free tier needs no card and
allows roughly 14,400 requests a day — see docs/13 for the exact current
numbers, since both providers change these over time. Its API is
OpenAI-compatible, so no new SDK: this is a single `requests.post`.

THIS IS A SAFETY NET, NOT A REPLACEMENT

  - Gemini is tried FIRST on every call, always. This module is only ever
    reached from script_generator._call_model_with_clear_errors, and only
    after Gemini has returned a genuine PER-DAY 429 — never on a per-minute
    throttle (that clears itself in seconds and should just be retried), and
    never as a first choice on an ordinary day.
  - Every response is honestly tagged with WHICH provider actually served
    it — script_generator wraps both providers' output in the same
    `_ModelResponse(text, provider)` shape, and callers (topic invention,
    creative brief, storyboard writing) record that tag in the database.
    This project already has a strong opinion about never letting a
    fallback masquerade as the real thing (see how `persona-auto` vs
    `persona-seed-fallback` topics are tagged) — this extends that same
    honesty to a second axis: which MODEL wrote it, not just whether it was
    freshly invented.
  - Leave GROQ_API_KEY unset and this module is simply never called.
    Nothing breaks, nothing changes, the pipeline behaves exactly as it did
    before this file existed.

GETTING A KEY (about 2 minutes, no credit card)
  1. console.groq.com/keys -> sign in with any Google/GitHub account
  2. Create API Key -> copy it
  3. Add it as a GitHub secret named GROQ_API_KEY (same place as the others)

That's the whole setup. See docs/13_BACKUP_AI_PROVIDER.md for more.
"""
import os
import requests

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

# Free on Groq at the time this was written. Providers retire and add free
# models on their own schedule (the same reason engine/model_registry.py
# auto-discovers the current Gemini model rather than hardcoding one) —
# override with the GROQ_MODEL env var if this name stops resolving. Current
# list: https://console.groq.com/docs/models
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"

TIMEOUT_SECONDS = 60
PROVIDER_NAME = "groq"


def available() -> bool:
    """True if a Groq key is configured. Callers should check this before
    trying the fallback, so a missing key produces a clear 'no backup is
    set up' message instead of a confusing request failure."""
    return bool(os.environ.get("GROQ_API_KEY"))


def call(system_prompt: str, user_prompt: str, temperature: float = 0.9) -> str:
    """Sends one chat completion request to Groq and returns the raw text.

    Deliberately mirrors what Gemini's response_mime_type='application/json'
    gives callers: a text blob that MIGHT be wrapped in markdown fences,
    which is exactly what this project's existing _extract_json /
    _extract_json_array helpers (brief.py, topic_synthesizer.py) already
    handle — no new parsing logic needed on the caller's side.

    Raises on any failure. Callers decide what "no fallback available"
    means for their situation; this function never silently returns
    nothing, because a silent empty fallback is worse than a loud one that
    tells you it also failed.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set, so there is no backup provider configured. "
            "Get a free key at https://console.groq.com/keys (no card needed) "
            "and add it as a GitHub secret named GROQ_API_KEY. See docs/13."
        )

    model = os.environ.get("GROQ_MODEL", DEFAULT_GROQ_MODEL)

    try:
        resp = requests.post(
            GROQ_ENDPOINT,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": user_prompt
                        + "\n\nRespond with ONLY the JSON. No markdown fences, "
                          "no commentary before or after it.",
                    },
                ],
                "temperature": temperature,
            },
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException as e:
        raise RuntimeError(f"Could not reach Groq (network error): {e}") from e

    if resp.status_code == 401:
        raise RuntimeError(
            "Groq rejected the API key (401). Double-check the GROQ_API_KEY "
            "secret was pasted correctly at https://console.groq.com/keys."
        )
    if resp.status_code == 429:
        # Groq's free tier is generous (~14,400/day at time of writing) but
        # not infinite. If even THIS is exhausted, there is genuinely
        # nothing left to fall back to today.
        raise RuntimeError(
            f"Groq's free tier is also exhausted for today ({resp.status_code}): "
            f"{resp.text[:200]}"
        )
    if resp.status_code == 404 or "model_not_found" in resp.text.lower():
        raise RuntimeError(
            f"Groq model '{model}' was not found — it may have been retired. "
            f"Check https://console.groq.com/docs/models for a current free "
            f"model name and set GROQ_MODEL to override the default."
        )
    if not resp.ok:
        raise RuntimeError(f"Groq returned {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected response shape from Groq: {data}") from e
