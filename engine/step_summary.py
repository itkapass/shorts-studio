"""
step_summary.py — answers "what actually happened?" without opening the app.

WHY THIS EXISTS

A workflow finishing green tells you it didn't crash. It tells you nothing
about what it actually DID — how many topics got invented, what they were,
which channel a new video belongs to, which AI wrote it. Finding that out
used to mean leaving GitHub, opening the dashboard, and clicking into Topic
Studio or the Video Queue. For a quick "did that just work?" check, that is
a lot of friction, and it's exactly the friction that makes a real emergency
feel worse than it needs to.

GitHub Actions renders a "Summary" tab on every workflow run — the same page
you land on after a run finishes — and any step can write markdown into it
by appending to a file path GitHub hands you in the GITHUB_STEP_SUMMARY
environment variable. Nothing needs installing; it is a built-in mechanic.

This module just makes that one line safe to call everywhere: it writes the
summary when running inside GitHub Actions, and quietly prints to the
console instead when it isn't (running locally, or during a test) — so the
exact same code path works in both places without an if-statement at every
call site.
"""
import os


def write(markdown: str):
    """Appends markdown to the current GitHub Actions run's Summary tab.

    Safe to call outside GitHub Actions (e.g. running locally): falls back
    to printing, and never raises — a broken summary write must never take
    down the actual pipeline it is trying to describe.
    """
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        print("\n--- (would appear on the GitHub Actions Summary tab) ---")
        print(markdown)
        print("--- end summary ---\n")
        return
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(markdown.rstrip() + "\n\n")
    except Exception as e:
        print(f"[step_summary] \u26a0 Could not write to GITHUB_STEP_SUMMARY: {e}")


def topics_added(results: dict):
    """One row per persona, one line per topic, right on the run's Summary
    tab. This is the direct answer to 'how do I know what topics got
    added and what they are' — no dashboard click required."""
    total = sum(r.get("added", 0) for r in results.values())
    lines = ["## \U0001f4a1 Topics added", ""]

    if total == 0:
        lines.append("Every persona's pool was already deep enough — nothing new was needed this run.")
        write("\n".join(lines))
        return

    lines.append(f"**{total} new topic(s)** across {len(results)} persona(s):")
    lines.append("")
    for key, r in results.items():
        added = r.get("added", 0)
        if not added:
            lines.append(f"- **{r.get('label', key)}** — pool already full, nothing added.")
            continue
        source_bits = []
        if r.get("from_gemini"):
            source_bits.append(f"{r['from_gemini']} \u2728 Gemini")
        if r.get("from_groq"):
            source_bits.append(f"{r['from_groq']} \U0001f501 Groq backup")
        if r.get("from_seed"):
            source_bits.append(f"{r['from_seed']} \U0001f331 seed fallback")
        lines.append(f"- **{r.get('label', key)}** — {added} added ({', '.join(source_bits)})")
        for t in r.get("topics", []):
            icon = {"gemini": "\u2728", "groq": "\U0001f501", "seed": "\U0001f331"}.get(t.get("source"), "")
            lines.append(f"    - {icon} {t.get('name')}")
    write("\n".join(lines))


def video_generated(title: str, persona_label: str, style: str, archetype: str,
                     provider: str, job_id: str, quality_verdict: str = None,
                     voice_engine: str = None):
    """One clean block confirming exactly what was made and by which AI,
    right where you already are (the workflow run page) after pressing
    'Generate Video Now'."""
    provider_note = {
        "gemini": "\u2728 Gemini (primary)",
        "groq": "\U0001f501 Groq backup — Gemini's daily quota was gone",
    }.get(provider, provider or "unknown")
    voice_note = {
        "edge-tts": "\U0001f3a4 edge-tts (exact caption timing)",
        "piper": "\U0001f3a4 Piper (offline, estimated timing)",
        "gtts": "\u26a0\ufe0f gTTS fallback — ESTIMATED timing, captions may drift, review before approving",
    }.get(voice_engine, voice_engine or "n/a")
    lines = [
        "## \U0001f3ac Video generated",
        "",
        f"**{title}**",
        "",
        f"| | |",
        f"|---|---|",
        f"| Channel / persona | {persona_label} |",
        f"| Format | {archetype or 'n/a'} |",
        f"| Visual style | {style} |",
        f"| Written by | {provider_note} |",
        f"| Voiced by | {voice_note} |",
        f"| Quality gates | {quality_verdict or 'n/a'} |",
        f"| Job ID | `{job_id}` |",
        "",
        "It is waiting in **Pending Review** in the dashboard.",
    ]
    write("\n".join(lines))
