"""
rig.py — the drawing engine for 2D characters.
================================================

WHY THIS EXISTS (read before replacing it with an image API):
The reference videos this style imitates (cute-animal 2-panel jokes, talking
head comedians, stick-figure gags) all depend on ONE thing: the same character
looking identical in every frame of every video, forever. That is exactly what
image-generation models are worst at. Ask any of them for "the same cat again"
and you get a different cat.

So characters here are DRAWN, not generated: each one is parametric vector data
(circles, rounded rects, polygons, bezier curves) rendered with PIL. That buys:
  - Perfect consistency. Frame 1 and frame 9000 are pixel-identical.
  - $0 forever. No API, no rate limit, no key, no model deprecation.
  - Original artwork. Nothing here is traced, scraped, or derived from anyone
    else's character, so there is no copyright exposure and nothing to attribute.
  - Instant renders. A frame draws in ~15ms, versus seconds-per-image via an API.

The trade-off, stated honestly: this is clean flat-vector cartooning, the
"cute minimal mascot" register. It will not produce painterly or highly
detailed illustration. That is a real ceiling, and it is the right ceiling for
short-form comedy, where readability at thumbnail size beats detail anyway.

COORDINATE SYSTEM
Every part is defined in a 0..100 square (x right, y down), then scaled to the
target box at draw time. That means a character is resolution-independent: the
same definition renders crisp at 200px or 2000px.

LAYERING
Parts draw in the order listed in a character's `parts` list. Back-to-front:
tail -> body -> arms -> head -> face features -> accessories.
"""
import math
from PIL import Image, ImageDraw

# ── Geometry helpers (all in 0..100 space) ───────────────────────────────────


def _pt(x, y):
    return (float(x), float(y))


def circle(cx, cy, r, n=48):
    """Closed polygon approximating a circle."""
    return [
        _pt(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n))
        for i in range(n)
    ]


def ellipse(cx, cy, rx, ry, n=48, squash_top=1.0):
    """Ellipse with optional flattening of the upper half (squash_top < 1
    makes an egg/blob shape, which reads friendlier than a pure ellipse)."""
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        x = cx + rx * math.cos(a)
        y = cy + ry * math.sin(a)
        if y < cy:
            y = cy - (cy - y) * squash_top
        pts.append(_pt(x, y))
    return pts


def rounded_rect(x0, y0, x1, y1, r, n=8):
    """Rounded rectangle as a polygon."""
    pts = []
    corners = [
        (x1 - r, y0 + r, -90, 0),
        (x1 - r, y1 - r, 0, 90),
        (x0 + r, y1 - r, 90, 180),
        (x0 + r, y0 + r, 180, 270),
    ]
    for cx, cy, a0, a1 in corners:
        for i in range(n + 1):
            a = math.radians(a0 + (a1 - a0) * i / n)
            pts.append(_pt(cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def arc(cx, cy, r, deg_start, deg_end, n=24):
    """Open arc — used for smiles, eyebrows, ear insides."""
    return [
        _pt(
            cx + r * math.cos(math.radians(deg_start + (deg_end - deg_start) * i / n)),
            cy + r * math.sin(math.radians(deg_start + (deg_end - deg_start) * i / n)),
        )
        for i in range(n + 1)
    ]


def bezier(p0, p1, p2, n=20):
    """Quadratic bezier — smooth organic curves (tails, hair, arms)."""
    out = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        out.append(
            _pt(
                u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1],
            )
        )
    return out


def teardrop(cx, cy, r, tip_x, tip_y, n=32):
    """Circle pulled to a point — ears, leaves, speech-bubble tails."""
    pts = circle(cx, cy, r, n)
    far = max(range(len(pts)), key=lambda i: (pts[i][0] - tip_x) ** 2 + (pts[i][1] - tip_y) ** 2)
    out = pts[:]
    out[(far + len(pts) // 2) % len(pts)] = _pt(tip_x, tip_y)
    return out


def translate(pts, dx, dy):
    return [_pt(x + dx, y + dy) for (x, y) in pts]


def scale_pts(pts, sx, sy=None, ox=50.0, oy=50.0):
    sy = sx if sy is None else sy
    return [_pt(ox + (x - ox) * sx, oy + (y - oy) * sy) for (x, y) in pts]


def rotate(pts, deg, ox=50.0, oy=50.0):
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    return [
        _pt(ox + (x - ox) * ca - (y - oy) * sa, oy + (x - ox) * sa + (y - oy) * ca)
        for (x, y) in pts
    ]


# ── Part definition ──────────────────────────────────────────────────────────


class Part:
    """One drawable shape.

    kind:    'fill'  — filled polygon with outline
             'line'  — open stroked polyline (smiles, brows, whiskers)
             'blank' — filled polygon with NO outline (blush, highlights)
    slot:    optional name. Parts whose slot matches a swap key get replaced
             at draw time — this is how mouth shapes and eye states work.
    bob:     if True, this part rides the idle bob animation (head + face
             move together; feet stay planted).
    """

    __slots__ = ("pts", "fill", "outline", "width", "kind", "slot", "bob")

    def __init__(self, pts, fill=None, outline="ink", width=2.2, kind="fill", slot=None, bob=True):
        self.pts = pts
        self.fill = fill
        self.outline = outline
        self.width = width
        self.kind = kind
        self.slot = slot
        self.bob = bob


# ── Renderer ─────────────────────────────────────────────────────────────────


def _resolve(color, palette):
    if color is None:
        return None
    if isinstance(color, str):
        return palette.get(color, color)
    return color


def draw_character(
    img: Image.Image,
    parts: list,
    palette: dict,
    box: tuple,
    bob_offset: float = 0.0,
    supersample: int = 3,
):
    """Draws a character's part list into `img` at `box` = (x, y, w, h).

    Rendering happens on a supersampled transparent layer and is then
    downscaled with LANCZOS before compositing. Without this, PIL's polygon
    edges are hard-aliased and the character reads as jagged clip-art at
    1080p; with it the linework is clean. 3x is the sweet spot — 4x costs
    ~1.8x the time for a difference that does not survive H.264 encoding.
    """
    bx, by, bw, bh = box
    S = supersample
    layer = Image.new("RGBA", (int(bw * S), int(bh * S)), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    def to_px(pts, dy=0.0):
        return [((x / 100.0) * bw * S, ((y + dy) / 100.0) * bh * S) for (x, y) in pts]

    for p in parts:
        dy = bob_offset if p.bob else 0.0
        px = to_px(p.pts, dy)
        if len(px) < 2:
            continue

        fill = _resolve(p.fill, palette)
        outline = _resolve(p.outline, palette)
        w = max(int(p.width * S * (bw / 300.0) * 1.2), 1)

        if p.kind == "line":
            if outline:
                d.line(px, fill=outline, width=w, joint="curve")
                # PIL's line joints leave gaps at sharp turns; capping the
                # endpoints with dots hides that on curves like smiles.
                r = w / 2.0
                for (ex, ey) in (px[0], px[-1]):
                    d.ellipse([ex - r, ey - r, ex + r, ey + r], fill=outline)
        elif p.kind == "blank":
            if fill:
                d.polygon(px, fill=fill)
        else:
            d.polygon(px, fill=fill, outline=outline)
            if outline and w > 1:
                # polygon()'s outline is always 1px; redraw the border as a
                # closed line to get real stroke weight.
                d.line(px + [px[0]], fill=outline, width=w, joint="curve")

    layer = layer.resize((int(bw), int(bh)), Image.LANCZOS)
    img.alpha_composite(layer, (int(bx), int(by)))
    return img


def apply_swaps(parts: list, swaps: dict) -> list:
    """Replaces slot-matched parts. `swaps` maps slot name -> list of Parts
    (or [] to hide that slot entirely).

    This is the whole animation mechanism: the mouth is a slot, and swapping
    it per frame from a viseme timeline is what produces lip sync.
    """
    out = []
    for p in parts:
        if p.slot and p.slot in swaps:
            continue
        out.append(p)
    for slot, replacement in swaps.items():
        out.extend(replacement or [])
    return out
