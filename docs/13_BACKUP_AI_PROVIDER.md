# 13 — The free backup AI (never be stuck on one key again)

## What this is

When Gemini's daily quota is genuinely gone, the pipeline now automatically
tries **Groq** (groq.com — a hosting company, unrelated to xAI's "Grok")
before giving up. Groq's free tier hosts open models like Llama 3.3 70B on
its own hardware: no credit card, roughly **14,400 requests a day** at time
of writing — over 700x Gemini's free allowance — and its API is
OpenAI-compatible, so this project needed no new library to talk to it.

This is what turns "we can't test anything until midnight Pacific" into
"the emergency video still gets made, just by a different model."

## What it is not

It is **not** a replacement for Gemini, and it does not run by default.

- Gemini is tried first, always, on every single call.
- Groq is only ever reached after a **confirmed daily** 429 from Gemini — a
  momentary per-minute throttle just retries Gemini itself, because that
  clears in seconds on its own.
- Every result is honestly tagged with which model actually wrote it. A
  topic invented by the backup shows a distinct 🔁 badge in Topic Studio,
  never the same ✨ badge Gemini's topics get. A video whose script came
  from the backup shows a small badge in the Video Queue. Nothing pretends
  to be Gemini when it wasn't.
- Leave `GROQ_API_KEY` unset and none of this activates. The pipeline
  behaves exactly as it did before this file existed.

## Setting it up (about 2 minutes, genuinely free)

1. Go to **console.groq.com/keys** and sign in with any Google or GitHub
   account. No credit card anywhere in this flow.
2. Click **Create API Key**, name it anything, copy it.
3. Add it as a GitHub secret:
   - Repo → **Settings** → **Secrets and variables** → **Actions** → **New
     repository secret**
   - Name: `GROQ_API_KEY`
   - Value: the key you copied
4. Done. Nothing else to configure — the workflows in this zip already pass
   it through wherever `GEMINI_API_KEY` is passed.

## What it actually protects

| Step | Protected? |
|---|---|
| Topic invention (Add Topics) | Yes |
| Creative brief | Yes |
| Storyboard / script writing | Yes |
| Voice generation (edge-TTS) | No — unrelated to Gemini, already has its own fallback chain (edge-TTS → Piper → gTTS) |
| Video rendering (ffmpeg) | No — doesn't use any AI model |

So in practice: if Gemini is out of quota, you can still press **Add Topics
Now** and **Generate Video Now** and get a real result — written by Groq,
clearly labeled as such, rather than a "quota exhausted" error and nothing
to show for the attempt.

## Quality note

Gemini stays the default because it's tuned for this project's prompts and
generally produces stronger output for this specific job. Groq's models are
capable, fast, and free, but treat anything they write during a fallback as
"good enough to keep testing / keep the channel alive today," not
necessarily your best possible video. If a Groq-written video reads a little
different in tone, that's expected — it's a different model.

## If Groq's own free tier ever runs out too

It's generous enough that this should be rare, but if it happens you'll see
a clear message saying so — the pipeline never pretends a second failure is
the first one. At that point there's genuinely nothing free left to fall
back to for that request; wait for either allowance to reset, or add a
paid key to either provider.

## Overriding the model

Groq retires and adds free models on its own schedule, the same way Gemini
does. If `llama-3.3-70b-versatile` (this project's default) ever stops
resolving, set a GitHub secret named `GROQ_MODEL` to a current one — check
**console.groq.com/docs/models** for what's free right now.
