"""Cut Guided Setup widget previews out of an operator screenshot sheet.

``tools/onboarding_sources/MEGASHEET.png`` (operator-owned, unshipped) is a
screenshot of real widgets on a real saver.  This tool finds each card's white frame, cuts the
card out along its rounded outer edge (everything outside becomes transparent)
and gives it a soft free-hanging shadow, so previews sit on any Settings theme.
Families shown as several cards are laid out together on one transparent
canvas.  Clocks stay with ``tools/onboarding_preview_foundry.py``.

Run after the foundry: ``python tools/onboarding_sheet_previews.py``.  It
rewrites the covered ``widget_*.png`` files and the manifest.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Final

import numpy
from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT: Final = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_SHEET: Final = ROOT / "tools" / "onboarding_sources" / "MEGASHEET.png"
DEFAULT_OUTPUT: Final = ROOT / "images" / "onboarding"

# Card frame lines located in the sheet (x0, y0, x1, y1, sheet pixels).  The
# tool walks outward from each line to the frame's true outer edge.
CARDS: Final = {
    "osd": (32, 46, 600, 145),
    "anime_news": (731, 959, 1566, 1696),
    "ar": (2824, 497, 3629, 1164),
    "friend_pulse": (1688, 26, 2997, 322),
    "weather": (3039, 28, 3776, 452),
    "games_you_follow": (1671, 746, 2446, 1396),
    "gmail": (1670, 1433, 2478, 1775),
    "system_stats": (2519, 1355, 2894, 1775),
    "spotify": (718, 1724, 1542, 2108),
    "spotify_volume": (1566, 1764, 1580, 2070),
    "reddit_all": (1652, 1804, 2307, 2109),
    "reddit_drama": (2336, 1804, 2892, 2108),
    "abandonment_issues": (3102, 1200, 3774, 1510),
    "achievement_pulse": (2925, 1542, 3776, 2108),
    "bubble": (0, 1662, 683, 2112),
}

# Family preview -> rows of cards.  Cards in one row share a top edge.
FAMILIES: Final = {
    "system_audio_osd": (("osd",),),
    "feeds": (("anime_news", "ar"),),
    "steam": (("friend_pulse",), ("achievement_pulse", "games_you_follow")),
    "weather": (("weather",),),
    "gmail": (("gmail",),),
    "system_stats": (("system_stats",),),
    "media": (("spotify", "spotify_volume"),),
    "reddit": (("reddit_all", "reddit_drama"),),
    "visualizers": (("bubble",),),
}

# Media's volume slider sits beside its card at the product's own spacing.
_ATTACHED_GAPS: Final = {("spotify", "spotify_volume")}

_GAP: Final = 26
_MAX_SIZE: Final = (820, 560)
_SHADOW_OFFSET: Final = (5, 6)      # the default SE card shadow
_SHADOW_BLUR: Final = 9
_SHADOW_OPACITY: Final = 0.62
_SHADOW_PAD: Final = 24


def _bright(pixels: numpy.ndarray) -> numpy.ndarray:
    return pixels.min(axis=2) > 150


def _outer_edges(pixels: numpy.ndarray, box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Walk outward from a frame line to the last bright frame pixel on each side."""

    height, width, _ = pixels.shape
    x0, y0, x1, y1 = box
    bright = _bright(pixels)
    mid_rows = slice(y0 + (y1 - y0) // 4, y1 - (y1 - y0) // 4)
    mid_cols = slice(x0 + (x1 - x0) // 4, x1 - (x1 - x0) // 4)

    def column_bright(x: int) -> bool:
        return 0 <= x < width and bright[mid_rows, x].mean() > 0.6

    def row_bright(y: int) -> bool:
        return 0 <= y < height and bright[y, mid_cols].mean() > 0.6

    left = x0
    while column_bright(left - 1):
        left -= 1
    right = x1
    while column_bright(right):
        right += 1
    top = y0
    while row_bright(top - 1):
        top -= 1
    bottom = y1
    while row_bright(bottom):
        bottom += 1
    # The outermost solid frame pixel; the rounded mask supplies the edge AA.
    return left, top, right, bottom


def _outer_radius(pixels: numpy.ndarray, edges: tuple[int, int, int, int]) -> float:
    """Corner radius from the first frame pixel along the top-right diagonal."""

    left, top, right, bottom = edges
    bright = _bright(pixels)
    for step in range(0, min(40, (right - left) // 2, (bottom - top) // 2)):
        if bright[top + step, right - 1 - step]:
            # A circle of radius r meets the diagonal r(1 - 1/sqrt2) in.
            return max(2.0, (step + 0.5) / (1.0 - 1.0 / numpy.sqrt(2.0)))
    return 10.0


def _rounded_mask(size: tuple[int, int], radius: float, inset: float = 0.0) -> Image.Image:
    scale = 4
    big = Image.new("L", (size[0] * scale, size[1] * scale), 0)
    edge = inset * scale
    ImageDraw.Draw(big).rounded_rectangle(
        (edge, edge, size[0] * scale - 1 - edge, size[1] * scale - 1 - edge),
        radius=max(1.0, (radius - inset) * scale), fill=255)
    return big.resize(size, Image.Resampling.LANCZOS)


def _frame_colour(card: Image.Image) -> tuple[int, int, int]:
    """Median of the frame's solid top edge (the card's own border colour)."""

    row = numpy.asarray(card.convert("RGB"))[1, card.width // 4: card.width * 3 // 4]
    bright = row[row.min(axis=1) > 150]
    source = bright if len(bright) else row
    return tuple(int(value) for value in numpy.median(source, axis=0))


def _apply_mask(card: Image.Image, radius: float) -> Image.Image:
    """Cut along the rounded outer edge without any screenshot background fringe.

    The outer ~1.5 px band (where the screenshot blends frame and wallpaper) is
    repainted in the frame's own colour; the mask supplies clean antialiasing.
    """

    frame = Image.new("RGBA", card.size, (*_frame_colour(card), 255))
    inner = _rounded_mask(card.size, radius, inset=1.5)
    card = Image.composite(card, frame, inner)
    card.putalpha(_rounded_mask(card.size, radius))
    return card


def _cut_card(sheet: Image.Image, pixels: numpy.ndarray, name: str) -> Image.Image:
    edges = _outer_edges(pixels, CARDS[name])
    left, top, right, bottom = edges
    radius = _outer_radius(pixels, edges)
    card = sheet.crop(edges).convert("RGBA")
    if left == 0:
        # The screenshot clipped this card's left frame; rebuild it from the
        # mirrored right frame so the cut-out has a complete border.
        strip = _frame_strip_width(pixels, edges)
        mirrored = card.crop((card.width - strip, 0, card.width, card.height)).transpose(
            Image.Transpose.FLIP_LEFT_RIGHT)
        visible = _visible_left_frame(pixels, edges)
        rebuilt = Image.new("RGBA", (card.width + strip - visible, card.height))
        rebuilt.paste(card, (strip - visible, 0))
        rebuilt.paste(mirrored, (0, 0))
        card = rebuilt
    return _apply_mask(card, radius)


def _frame_strip_width(pixels: numpy.ndarray, edges: tuple[int, int, int, int]) -> int:
    left, top, right, bottom = edges
    bright = _bright(pixels)
    row = (top + bottom) // 2
    width = 1  # the antialiased outer pixel
    while bright[row, right - 1 - width]:
        width += 1
    return width + 1


def _visible_left_frame(pixels: numpy.ndarray, edges: tuple[int, int, int, int]) -> int:
    left, top, right, bottom = edges
    row = (top + bottom) // 2
    visible = 0
    while pixels[row, left + visible].min() > 110:
        visible += 1
    return visible


def _layout(cards: dict[str, Image.Image], rows: tuple[tuple[str, ...], ...]) -> Image.Image:
    placed: list[tuple[Image.Image, int, int]] = []
    y = 0
    width = 0
    for row in rows:
        x = 0
        height = 0
        previous = None
        for name in row:
            image = cards[name]
            if previous is not None:
                x += _attached_gap(previous, name)
            placed.append((image, x, y))
            x += image.width
            height = max(height, image.height)
            previous = name
        width = max(width, x)
        y += height + _GAP
    canvas = Image.new("RGBA", (width, y - _GAP), (0, 0, 0, 0))
    for image, x, top in placed:
        canvas.alpha_composite(image, (x, top))
    return canvas


def _attached_gap(first: str, second: str) -> int:
    if (first, second) in _ATTACHED_GAPS:
        left = CARDS[first][2]
        right = CARDS[second][0]
        return max(4, right - left - 8)
    return _GAP


def _with_shadow(image: Image.Image) -> Image.Image:
    """Transparent canvas, the content, and a soft SE shadow hanging off it."""

    image.thumbnail(_MAX_SIZE, Image.Resampling.LANCZOS)
    pad = _SHADOW_PAD
    size = (image.width + 2 * pad, image.height + 2 * pad)
    shadow_alpha = Image.new("L", size, 0)
    shadow_alpha.paste(image.getchannel("A"), (pad + _SHADOW_OFFSET[0], pad + _SHADOW_OFFSET[1]))
    shadow_alpha = shadow_alpha.filter(ImageFilter.GaussianBlur(_SHADOW_BLUR))
    shadow_alpha = shadow_alpha.point(lambda value: int(value * _SHADOW_OPACITY))
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    canvas.putalpha(shadow_alpha)
    canvas.alpha_composite(image, (pad, pad))
    return canvas


def build(sheet_path: Path, output: Path) -> list[str]:
    sheet = Image.open(sheet_path).convert("RGB")
    pixels = numpy.asarray(sheet).astype(int)
    cards = {name: _cut_card(sheet, pixels, name) for name in CARDS}
    written = []
    for family_id, rows in FAMILIES.items():
        name = f"widget_{family_id}.png"
        _with_shadow(_layout(cards, rows)).save(output / name, "PNG", optimize=True)
        written.append(name)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sheet", type=Path, default=DEFAULT_SHEET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-manifest", action="store_true")
    args = parser.parse_args(argv)
    written = build(args.sheet.resolve(), args.output.resolve())
    print("\n".join(written))
    if not args.no_manifest:
        from tools.onboarding_preview_foundry import assemble_manifest
        assemble_manifest(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
