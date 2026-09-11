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
models — this project uses OpenAI's open-weight gpt-oss-120b, with gpt-oss-20b
as a second try if that one is ever unavailable. Its free tier needs no card.
Real current allowance per Groq's own docs: 1,000 requests and 200,000
tokens per day, PER MODEL — so the two models used here give roughly double
that combined, since each has its own separate budget. (An earlier version
of this file quoted "~14,400 requests/day," which is real but belongs to a
different, now-deprecated model — corrected here after that mismatch showed
up as a live failure. See docs/13 for current numbers, since Groq's own
limits and model lineup change over time.) Its API is OpenAI-compatible, so
no new SDK: this is a single `requests.post`.

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
import time
import requests

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

# Free on Groq at the time this was written. Providers retire and add free
# models on their own schedule (the same reason engine/model_registry.py
# auto-discovers the current Gemini model rather than hardcoding one) —
# override with the GROQ_MODEL env var if this name stops resolving. Current
# list: https://console.groq.com/docs/models
# llama-3.3-70b-versatile (this project's original default) was deprecated
# by Groq on 2026-06-17 and fully shut down 2026-08-16 — confirmed directly
# against console.groq.com/docs/deprecations, and confirmed as the actual
# live cause of every recent generation failure via the app's own error
# message ("Groq model 'llama-3.3-70b-versatile' was not found"). Updated to
# Groq's own official recommended replacement for general-purpose/reasoning
# workloads. If THIS one is ever retired too, override with the GROQ_MODEL
# env var rather than waiting for another zip — check
# console.groq.com/docs/models for whatever is current.
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"

TIMEOUT_SECONDS = 60
PROVIDER_NAME = "groq"


def available() -> bool:
    """True if a Groq key is configured. Callers should check this before
    trying the fallback, so a missing key produces a clear 'no backup is
    set up' message instead of a confusing request failure."""
    return bool(os.environ.get("GROQ_API_KEY"))


# If the configured model (DEFAULT_GROQ_MODEL, or GROQ_MODEL if set) turns
# out to be retired, one automatic retry against this candidate happens
# before giving up entirely. This is what the original single-hardcoded-name
# design was missing: llama-3.3-70b-versatile's retirement (see
# DEFAULT_GROQ_MODEL's comment) took the ENTIRE backup offline until a human
# noticed and shipped a fix. A second, independent name means one model's
# retirement no longer disables the whole safety net on its own.
FALLBACK_GROQ_MODEL = "openai/gpt-oss-20b"


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

    primary_model = os.environ.get("GROQ_MODEL", DEFAULT_GROQ_MODEL)
    try:
        return _call_model(primary_model, system_prompt, user_prompt, temperature, api_key)
    except _TryNextModel as e:
        if primary_model == FALLBACK_GROQ_MODEL:
            raise RuntimeError(str(e)) from e  # already on the fallback, nothing left to try
        print(f"[backup_provider] \u26a0 {e} Retrying once against "
              f"'{FALLBACK_GROQ_MODEL}' before giving up.")
        try:
            return _call_model(FALLBACK_GROQ_MODEL, system_prompt, user_prompt, temperature, api_key)
        except _TryNextModel as e2:
            # Both models hit a wall. _TryNextModel is an internal signal
            # meaning "a different model is worth trying" — with no model
            # left to try, it must not leak out as itself; convert to a
            # plain RuntimeError so callers only ever see this module's two
            # public exception shapes (a plain failure, or success).
            raise RuntimeError(str(e2)) from e2


class _TryNextModel(RuntimeError):
    """Distinct from other RuntimeErrors so call() retries with a second
    model ONLY for the two situations where that can actually help — a
    missing/retired model name, or a rate limit on THIS specific model.

    THE BUG THIS FIXES: the fallback used to trigger only on a 404 (model
    genuinely doesn't exist). A 429 rate-limit raised immediately with no
    retry — but Groq's limits are enforced PER MODEL, not shared across an
    account (confirmed directly against console.groq.com/docs/rate-limits:
    gpt-oss-120b and gpt-oss-20b each get their own separate 1,000
    requests/day and 200,000 tokens/day). Hitting the ceiling on the primary
    model says nothing about whether the fallback model's own, separate
    budget is also spent — so refusing to even try it was leaving real,
    unused capacity on the table on exactly the day it mattered most.
    A bad API key or a genuine network failure should never trigger this —
    only these two specific, second-model-might-actually-work cases should.
    """


def _parse_retry_seconds(text: str, default: int = 25) -> int:
    """Pulls a suggested wait time out of Groq's error text if it gives one
    (e.g. '...try again in 21.5s'), otherwise a reasonable fixed default.
    Mirrors api_budget.retry_delay_seconds's same reasoning for Gemini:
    obeying the server's own number beats guessing."""
    import re
    m = re.search(r"try again in (\d+(?:\.\d+)?)\s*s", text, re.IGNORECASE)
    if m:
        return min(int(float(m.group(1))) + 2, 60)
    return default


def _call_model(model: str, system_prompt: str, user_prompt: str, temperature: float,
                api_key: str, _minute_retries: int = 0) -> str:
    # Caps same-model retries for a per-minute limit at 3 (roughly 25s each
    # = up to ~75s waited here) before giving up on this model entirely —
    # a limit that hasn't cleared after that long is behaving more like a
    # sustained problem than a genuine 60-second window, and this must
    # never be the thing that hangs a GitHub Actions job indefinitely.
    MAX_MINUTE_RETRIES = 3
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
        # Groq returns 429 for BOTH a per-minute limit (self-resolving in
        # under a minute) and a genuine per-day limit (nothing left until
        # tomorrow) — the same fork Gemini's 429s need (see
        # api_budget.is_per_minute_limit). Real current limits per Groq's
        # own docs: gpt-oss-120b and gpt-oss-20b each get 1,000
        # requests/day, 200,000 tokens/day, AND 8,000 tokens/minute,
        # separately per model. THE BUG THIS FIXES: a per-minute hit used
        # to immediately burn the fallback model instead of just waiting
        # the ~20-30 seconds it actually needed — wasting the fallback's
        # separate daily budget on a problem that was never really about
        # the daily budget at all.
        if "per minute" in resp.text.lower() or "tpm" in resp.text.lower() or "rpm" in resp.text.lower():
            if _minute_retries >= MAX_MINUTE_RETRIES:
                raise _TryNextModel(
                    f"Groq model '{model}' is still per-minute rate-limited after "
                    f"{MAX_MINUTE_RETRIES} waits — trying the other model instead "
                    f"of waiting further: {resp.text[:200]}"
                )
            wait = _parse_retry_seconds(resp.text)
            print(f"[backup_provider] \u26a0 Groq model '{model}' hit its per-MINUTE limit "
                  f"(self-resolving) — waiting {wait}s and retrying the SAME model "
                  f"(attempt {_minute_retries + 1}/{MAX_MINUTE_RETRIES}), not burning "
                  f"the fallback's separate daily budget on this.")
            time.sleep(wait)
            return _call_model(model, system_prompt, user_prompt, temperature, api_key,
                              _minute_retries=_minute_retries + 1)

        raise _TryNextModel(
            f"Groq model '{model}' hit its own daily limit (1,000 requests / "
            f"200,000 tokens per day, separate per model): {resp.text[:200]}"
        )
    if resp.status_code == 404 or "model_not_found" in resp.text.lower():
        raise _TryNextModel(
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
