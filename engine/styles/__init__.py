"""
engine.styles — pluggable background renderers.

Each style module exposes:
    build_background_clip(scene: dict, duration: float, video_w: int, video_h: int) -> moviepy clip

Adding a new style later means: create engine/styles/my_style.py with that
one function, then register it below. Nothing else in the pipeline needs to
change — video_compositor.py, script_generator.py, and the admin panel all
read this registry rather than hardcoding style names.
"""
from . import stock_footage, whiteboard_sketch, quote_card, character_skit

STYLES = {
    "stock_footage": {
        "label": "Stock Footage",
        "description": "Real b-roll from Pexels with a Ken Burns zoom. The original plan for this project.",
        "mode": "per_scene",
        "build_background_clip": stock_footage.build_background_clip,
        "uses_icons": False,
    },
    "whiteboard_sketch": {
        "label": "Whiteboard Sketch",
        "description": "One hand-drawn diagram that grows scene by scene, each idea connected to the last — the explainer-video look.",
        "mode": "whole_video",
        "build_whole_video_clip": whiteboard_sketch.build_whole_video_clip,
        "uses_icons": True,
    },
    "character_skit": {
        "label": "Character Skit",
        "description": (
            "Original 2D animated characters who talk, blink and react. Comedy, "
            "commentary and dialogue. Captions sit above the character, not over "
            "the face."
        ),
        "mode": "whole_video",
        "build_whole_video_clip": character_skit.build_whole_video_clip,
        "uses_icons": False,
        "uses_characters": True,
        # This style speaks its own dialogue per character, so the orchestrator
        # routes it to voice_engine.generate_multi_voice instead of the single
        # narrator path. Without this flag both characters share one voice.
        "multi_voice": True,
        # The animated face is already the moving thing on screen; a second
        # moving highlight in the captions competes with it for attention.
        "caption_highlight": False,
    },
    "quote_card": {
        "label": "Quote Card",
        "description": "Minimal drifting gradient, no footage or icons — just big bold captions carrying the whole video.",
        "mode": "per_scene",
        "build_background_clip": quote_card.build_background_clip,
        "uses_icons": False,
    },
}

DEFAULT_STYLE = "stock_footage"


def available_styles():
    return list(STYLES.keys())


def styles_using_characters():
    return [k for k, v in STYLES.items() if v.get("uses_characters")]


def is_multi_voice(name: str) -> bool:
    return bool(get_style(name).get("multi_voice"))


def get_style(name: str):
    """Never crashes on an unrecognized style name — falls back to the default."""
    return STYLES.get(name, STYLES[DEFAULT_STYLE])
