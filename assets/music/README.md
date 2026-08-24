# assets/music/

Empty on purpose — this build doesn't ship any audio files. Placeholder music
files would either be silently low-quality or a real copyright risk if sourced
carelessly; that's not something to fake.

`audio_mixer.py` picks a random `.mp3`/`.wav` from this folder for background
music. If it's empty, videos render with no background music (not an error —
just silence under the voiceover).

## What to add
Any royalty-free / properly-licensed instrumental tracks, a few minutes each,
lowish-energy (they sit under narration, not over it). Good free sources:
- [YouTube Audio Library](https://www.youtube.com/audiolibrary) — built for exactly this use case
- [Pixabay Music](https://pixabay.com/music/) — check the specific license per track
- Your own licensed music library, if you have one

Whatever you use, keep the license terms handy — if you ever get a Content ID
claim, you'll want to be able to show where the track came from and what its
license actually permits.
