"""
whiteboard_sketch.py — 'whole_video' background builder for the
'whiteboard_sketch' render style.

REDESIGNED after reviewing real generated output: the previous version gave
each scene a fresh paper background with 1-3 independently-positioned
icons, reset every scene. Feedback on actual rendered video was blunt and
correct: icons didn't relate to each other, nothing connected, and it read
as random shapes flashing rather than a diagram being drawn. A real
whiteboard explainer keeps everything it draws on screen and visibly
connects each new idea to the last.

This version draws ONE diagram for the entire video: one node per scene,
laid out in a top-to-bottom zigzag, each new node connected to the previous
one with a hand-drawn line as its scene begins. Earlier nodes stay on
screen for the rest of the video — nothing is erased — so the canvas
visibly grows exactly the way a real whiteboard does.

Because this needs to see every scene at once (to know the full layout and
which nodes are "already drawn" vs "still upcoming"), it's a 'whole_video'
style: engine/video_compositor.py calls build_whole_video_clip() ONCE with
the full scene list, instead of calling a per-scene function once per
scene the way stock_footage and quote_card do. See engine/styles/__init__.py.
"""
import random
import numpy as np
from PIL import Image, ImageDraw
from moviepy.editor import VideoClip

from .icon_library import get_icon_strokes

PAPER_BG = (250, 248, 240)   # warm off-white "paper"
DOT_COLOR = (225, 222, 208)  # faint grid dots
INK = (32, 32, 38)           # "marker" color
LINE_COLOR = (90, 90, 100)   # connecting lines — slightly lighter than icon ink

# Layout: nodes flow top-to-bottom in this vertical band, zigzagging left/right.
# Bounded well above the caption safe zone (captions sit around y=0.62).
Y_TOP, Y_BOTTOM = 0.10, 0.54
X_LEFT, X_RIGHT = 0.30, 0.70
NODE_BOX_RATIO = 0.15  # icon box size, as a fraction of min(video_w, video_h)


def _paper_texture(w, h, seed=0):
    img = Image.new("RGB", (w, h), PAPER_BG)
    draw = ImageDraw.Draw(img)
    rnd = random.Random(seed)
    step = 46
    for y in range(0, h, step):
        for x in range(0, w, step):
            jx, jy = rnd.randint(-3, 3), rnd.randint(-3, 3)
            draw.ellipse([x + jx - 1, y + jy - 1, x + jx + 1, y + jy + 1], fill=DOT_COLOR)
    return img


def _jitter_stroke(pts, seed, amount=1.6):
    rnd = random.Random(seed)
    return [(x + rnd.uniform(-amount, amount), y + rnd.uniform(-amount, amount)) for (x, y) in pts]


def _stroke_length(pts):
    return sum(
        ((pts[i + 1][0] - pts[i][0]) ** 2 + (pts[i + 1][1] - pts[i][1]) ** 2) ** 0.5
        for i in range(len(pts) - 1)
    )


def _partial_stroke(pts, progress):
    if progress >= 1:
        return pts
    if progress <= 0 or len(pts) < 2:
        return pts[:1] if progress > 0 else []
    target = _stroke_length(pts) * progress
    out, acc = [pts[0]], 0.0
    for i in range(len(pts) - 1):
        seg = ((pts[i + 1][0] - pts[i][0]) ** 2 + (pts[i + 1][1] - pts[i][1]) ** 2) ** 0.5
        if acc + seg >= target:
            t = (target - acc) / seg if seg > 1e-6 else 0
            out.append((pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t,
                        pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t))
            return out
        acc += seg
        out.append(pts[i + 1])
    return out


def _draw_icon(draw, name, cx, cy, size, progress, seed):
    """Draws one icon centered at (cx, cy), strokes revealed in sequence as
    progress climbs 0->1. progress >= 1 draws it fully, instantly — used
    for nodes from completed earlier scenes."""
    strokes = get_icon_strokes(name)
    n = len(strokes) or 1
    for i, stroke in enumerate(strokes):
        stroke_progress = 1.0 if progress >= 1 else min(max((progress * n) - i, 0.0), 1.0)
        if stroke_progress <= 0:
            continue
        scaled = [(cx + (p[0] - 50) / 100 * size, cy + (p[1] - 50) / 100 * size) for p in stroke]
        jittered = _jitter_stroke(scaled, seed=seed * 97 + i)
        partial = _partial_stroke(jittered, stroke_progress)
        if len(partial) == 1:
            r = max(size * 0.012, 2)
            x, y = partial[0]
            draw.ellipse([x - r, y - r, x + r, y + r], fill=INK)
        elif len(partial) >= 2:
            width = max(int(size * 0.018), 3)
            draw.line(partial, fill=INK, width=width, joint="curve")


def _draw_connector(draw, p_from, p_to, progress, seed, node_size):
    """Hand-drawn connecting line from one node toward the next, with a
    small arrowhead once it arrives — this is the piece that was entirely
    missing before: visible proof that idea A leads to idea B."""
    if progress <= 0:
        return
    # Shrink the line so it starts/ends at each node's edge, not its center
    # (a line stopping just short of the icon reads more like a diagram).
    edge = node_size * 0.42
    dx, dy = p_to[0] - p_from[0], p_to[1] - p_from[1]
    dist = max((dx ** 2 + dy ** 2) ** 0.5, 1e-6)
    ux, uy = dx / dist, dy / dist
    start = (p_from[0] + ux * edge, p_from[1] + uy * edge)
    end = (p_to[0] - ux * edge, p_to[1] - uy * edge)

    line_pts = _jitter_stroke([start, end], seed=seed, amount=2.2)
    partial = _partial_stroke(line_pts, min(progress, 1.0))
    if len(partial) >= 2:
        draw.line(partial, fill=LINE_COLOR, width=3, joint="curve")

    if progress >= 1.0 and len(partial) >= 2:
        # Small arrowhead at the arrival end, pointing along the line.
        ax, ay = partial[-1]
        back_x, back_y = ax - ux * 14, ay - uy * 14
        perp_x, perp_y = -uy, ux
        left = (back_x + perp_x * 6, back_y + perp_y * 6)
        right = (back_x - perp_x * 6, back_y - perp_y * 6)
        draw.line([left, (ax, ay), right], fill=LINE_COLOR, width=3, joint="curve")


def _node_positions(n_nodes, video_w, video_h):
    """Top-to-bottom zigzag layout — one position per scene/node."""
    positions = []
    for i in range(n_nodes):
        frac = i / max(n_nodes - 1, 1)
        y = video_h * (Y_TOP + (Y_BOTTOM - Y_TOP) * frac)
        x = video_w * (X_LEFT if i % 2 == 0 else X_RIGHT)
        positions.append((x, y))
    return positions


def build_whole_video_clip(scenes: list, total_duration: float, video_w: int, video_h: int):
    """
    One continuous clip for the entire video. Each scene contributes exactly
    one node (its first chosen icon), connected to the previous scene's node.
    Nodes from completed scenes stay fully drawn; the current scene's node
    (and the line leading to it) draws progressively; future nodes aren't
    drawn at all yet.
    """
    n = len(scenes)
    icons = [(s.get("icons") or ["lightbulb"])[0] for s in scenes]
    positions = _node_positions(n, video_w, video_h)
    node_size = min(video_w, video_h) * NODE_BOX_RATIO

    seed_source = "|".join(icons) + str(n)
    base_seed = abs(hash(seed_source)) % 100000
    base = _paper_texture(video_w, video_h, seed=base_seed)
    node_seeds = [abs(hash(f"{icons[i]}{i}")) % 10000 for i in range(n)]

    # Precompute each scene's [start, end) in the global timeline.
    bounds = [(s.get("time_start", 0.0), s.get("time_end", total_duration)) for s in scenes]

    def scene_index_at(t):
        for i, (start, end) in enumerate(bounds):
            if t < end or i == n - 1:
                return i
        return n - 1

    # Performance: without this, every frame redrew every node and connector
    # drawn so far from scratch — cheap early on, increasingly wasteful by
    # the last scene once several nodes have accumulated, for work whose
    # result doesn't even change frame to frame once a scene is finished.
    # Cache the fully-drawn state once per scene boundary instead; each
    # frame then only has to draw the ONE scene currently in progress on
    # top of that cached image.
    completed_cache = [base.copy()]  # index i+1 = state after scene i is fully drawn
    running = base.copy()
    for i in range(n):
        d = ImageDraw.Draw(running)
        if i > 0:
            _draw_connector(d, positions[i - 1], positions[i], 1.0, seed=node_seeds[i] + 500, node_size=node_size)
        _draw_icon(d, icons[i], positions[i][0], positions[i][1], node_size, 1.0, seed=node_seeds[i])
        completed_cache.append(running.copy())

    def make_frame(t):
        current = scene_index_at(t)
        img = completed_cache[current].copy()  # everything before `current` is already drawn in here
        draw = ImageDraw.Draw(img)

        start, end = bounds[current]
        dur = max(end - start, 0.1)
        local_t = max(t - start, 0.0)

        if current == 0:
            connector_progress, icon_progress = 1.0, min(local_t / (dur * 0.6), 1.0)
        else:
            connector_span = dur * 0.35
            connector_progress = min(local_t / connector_span, 1.0)
            icon_progress = min(max(local_t - connector_span, 0.0) / (dur - connector_span), 1.0)

        if current > 0:
            _draw_connector(draw, positions[current - 1], positions[current], connector_progress,
                             seed=node_seeds[current] + 500, node_size=node_size)
        _draw_icon(draw, icons[current], positions[current][0], positions[current][1], node_size,
                   icon_progress, seed=node_seeds[current])

        return np.array(img)

    return VideoClip(make_frame, duration=total_duration)
