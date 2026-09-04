# v5 — Caption sync fix + Groq diversity confirmed

No new migration.

## Caption sync — likely root cause found

edge-tts gives EXACT per-word timing. Its fallbacks (Piper, gTTS) only
ESTIMATE it. Your render most likely fell back to gTTS because Microsoft
rate-limits GitHub Actions' IPs — a known risk this codebase already
flagged in a comment, just never guarded against hard enough.

**Fixed:**
- edge-tts retries: 3 → 5 attempts, longer backoff + jitter (fewer fallbacks
  in the first place — the real fix).
- Every video now tagged with which engine voiced it (`_voice_engine`).
- Quality gates flag any non-edge-tts video as **warn** — review before
  approving instead of finding out from views/comments.
- Video Queue shows a ⚠ badge on any video with estimated captions.

Can't promise edge-tts never fails again (Microsoft's call, not ours) — but
failures are now rarer, and when one slips through, you'll see it before
publishing instead of after.

## Groq topic diversity — already inherited, confirmed

Groq runs through the exact same `synthesize_topics()` prompt as Gemini —
same 12 lenses forcing different question types, same avoid-list, same
house rules. Nothing extra needed. Duplicate detection (`concept_memory.py`)
also checks the finished script regardless of which AI wrote it.

## Files changed

```
engine/voice_engine.py      5 retries, backoff+jitter, docstring update
engine/orchestrator.py      tags storyboard._voice_engine
engine/quality_gates.py     warns on non-edge-tts timing
engine/step_summary.py      shows voice engine in the run summary
engine/audio_mixer.py       stale Whisper comment fixed
admin-panel/.../VideoQueue.jsx   ⚠ estimated-captions badge
tools/selfcheck.py          11th check: this wiring
```

Verified: `python3 tools/selfcheck.py` → 11/11. Frontend builds clean.
