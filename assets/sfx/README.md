# assets/sfx/

Empty on purpose — same reasoning as `assets/music/README.md`.

`audio_mixer.py` and `script_generator.py`'s scene `sfx` field expect short
one-shot sound effect files named to match: `whoosh.mp3`, `digital_pop.mp3`,
`riser.mp3`, `glitch.mp3`, `impact.mp3` (see `SFX_MAP`-style lookups in
`engine/audio_mixer.py` for the exact expected names). Missing files are
handled gracefully — that scene's SFX cue is just skipped, not an error.

## What to add
Short (under 1s, usually) royalty-free UI/whoosh/impact sounds. Free sources:
- [Pixabay Sound Effects](https://pixabay.com/sound-effects/) — check the license per clip
- [Freesound.org](https://freesound.org/) — filter by CC0 / license you're comfortable with
