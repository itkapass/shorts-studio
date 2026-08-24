"""
engine.styles — pluggable background renderers.

Each style module exposes:
    build_background_clip(scene: dict, duration: float, video_w: int, video_h: int) -> moviepy clip

Adding a new style later means: create engine/styles/my_style.py with that
one function, then register it below. Nothing else in the pipeline needs to
change — video_compositor.py, script_generator.py, and the admin panel all
read this registry rather than hardcoding style names.
"""
from . import stock_footage, whiteboard_sketch, quote_card

STYLES = {
    "stock_footage": {
        "label": "Stock Footage",
        "description": "Real b-roll from Pexels with a Ken Burns zoom. The original plan for this project.",
        "build_background_clip": stock_footage.build_background_clip,
        "uses_icons": False,
    },
    "whiteboard_sketch": {
        "label": "Whiteboard Sketch",
        "description": "Hand-drawn-style line icons that draw themselves on a paper background — the explainer-video look.",
        "build_background_clip": whiteboard_sketch.build_background_clip,
        "uses_icons": True,
    },
    "quote_card": {
        "label": "Quote Card",
        "description": "Minimal drifting gradient, no footage or icons — just big bold captions carrying the whole video.",
        "build_background_clip": quote_card.build_background_clip,
        "uses_icons": False,
    },
}

DEFAULT_STYLE = "stock_footage"


def available_styles():
    return list(STYLES.keys())


def get_style(name: str):
    """Never crashes on an unrecognized style name — falls back to the default."""
    return STYLES.get(name, STYLES[DEFAULT_STYLE])
