"""N2.4's analysis of the composite's frames (composite_check.py; offline tests in tests/test_native_core_composite.py).

A frame is the hidden host's Qt Quick target read back (``rendering.native.QuickFrame``), turned top-down here by the
fact the module reports (``y_up_in_framebuffer``: OpenGL's rows start at the scene's bottom). The composite's surface
holds each texel's own index (``pattern.frag``: r and g the low bytes of x and y, b their high nibbles), so a frame shows
which texel reached which window pixel:

* one to one: every pixel the composite covers shows exactly the texel the decided geometry maps there (the item's
  device pixel, turned by the quarter turn as ``presentation_orientation.logical_uv_from_physical_uv`` does), so no
  texel is skipped, repeated or blended;
* the coverage: a pixel inside the item is covered when the card's rounded rectangle's signed distance at its centre
  is <= 0 (``clip_host.py``'s rule); every other pixel is unchanged against the frame with the composite hidden.
Pixels whose centre lies within ``AMBIGUOUS_PX`` of the path (a float tie the shader's single precision may decide
either way) are left out of both requirements and counted.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

TOLERANCE = 2          # 8-bit levels per channel: an unchanged pixel (the contract's floor)
AMBIGUOUS_PX = 1e-3    # device pixels: a centre this close to the coverage path is not judged


def frame_rows(frame: Mapping[str, Any]) -> np.ndarray:
    """A read frame as top-down RGBA (H, W, 4) uint8."""
    width, height = int(frame["width"]), int(frame["height"])
    rows = np.frombuffer(frame["rgba"], dtype=np.uint8)[: width * height * 4].reshape(height, width, 4)
    return (rows[::-1] if frame["y_up_in_framebuffer"] else rows).copy()


def decode_texels(rgba: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The texel index each pixel shows (pattern.frag's encoding)."""
    r, g, b = (rgba[..., i].astype(np.int64) for i in range(3))
    return r | ((b & 15) << 8), g | ((b >> 4) << 8)


def geometry_px(rect: Sequence[float], pixel_size: Sequence[int], coverage: Any, quarters: int, dpr: float) -> dict:
    """A composite's decided geometry in window device pixels: the item's origin and size, its coverage (item-local
    rect and radius, or None when skipped), its quarter turns."""
    cover = None
    if coverage is not None:
        (cx, cy, cw, ch), radius = coverage
        cover = [cx * dpr, cy * dpr, cw * dpr, ch * dpr, radius * dpr]
    return {"origin_px": [int(round(rect[0] * dpr)), int(round(rect[1] * dpr))],
            "pixel_size": [int(pixel_size[0]), int(pixel_size[1])], "coverage_px": cover, "quarters": int(quarters) % 4}


def coverage_distance(geometry: Mapping[str, Any], shape: tuple[int, int]) -> np.ndarray:
    """Per window pixel: the signed distance (device pixels) of its centre to the coverage path, item-local; +inf
    outside the item; -inf inside the item when the coverage is skipped."""
    height, width = shape
    ox, oy = geometry["origin_px"]
    w, h = geometry["pixel_size"]
    ys, xs = np.mgrid[0:height, 0:width]
    px, py = xs - ox, ys - oy
    inside = (px >= 0) & (py >= 0) & (px < w) & (py < h)
    distance = np.full(shape, np.inf)
    cover = geometry["coverage_px"]
    if cover is None:
        distance[inside] = -np.inf
        return distance
    cx, cy, cw, ch, radius = (float(v) for v in cover)
    half_w, half_h = cw / 2.0, ch / 2.0
    radius = min(radius, half_w, half_h)
    qx = np.abs(px + 0.5 - (cx + half_w)) - (half_w - radius)
    qy = np.abs(py + 0.5 - (cy + half_h)) - (half_h - radius)
    d = (np.sqrt(np.maximum(qx, 0.0) ** 2 + np.maximum(qy, 0.0) ** 2) + np.minimum(np.maximum(qx, qy), 0.0) - radius)
    distance[inside] = d[inside]
    return distance


def expected_texels(geometry: Mapping[str, Any], shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    """Per window pixel: the texel the decided geometry maps there (meaningful inside the item only)."""
    height, width = shape
    ox, oy = geometry["origin_px"]
    w, h = geometry["pixel_size"]
    ys, xs = np.mgrid[0:height, 0:width]
    px, py = xs - ox, ys - oy
    turns = geometry["quarters"]
    if turns == 1:
        return py, w - 1 - px
    if turns == 2:
        return w - 1 - px, h - 1 - py
    if turns == 3:
        return h - 1 - py, px
    return px, py


def analyse_texels(drawn: np.ndarray, hidden: np.ndarray, geometry: Mapping[str, Any]) -> dict:
    """The one-to-one reading of a frame whose composite shows the texel pattern, against the frame with it hidden."""
    shape = drawn.shape[:2]
    distance = coverage_distance(geometry, shape)
    ambiguous = np.abs(distance) < AMBIGUOUS_PX
    covered = (distance <= 0.0) & ~ambiguous
    uncovered = (distance > 0.0) & ~ambiguous
    tx, ty = decode_texels(drawn)
    ex, ey = expected_texels(geometry, shape)
    mismatched = covered & ((tx != ex) | (ty != ey))
    seen = (tx[covered] << 16) | ty[covered]
    changed = np.abs(drawn[..., :3].astype(int) - hidden[..., :3].astype(int)).max(axis=2) > TOLERANCE
    escaped = uncovered & changed
    checks = {
        "covers_pixels": int(covered.sum()) > 0,
        "every_covered_pixel_shows_its_texel": int(mismatched.sum()) == 0,
        "no_texel_repeated": int(np.unique(seen).size) == int(seen.size),
        "nothing_changed_outside_the_coverage": int(escaped.sum()) == 0,
    }
    first = np.argwhere(mismatched)
    return {"checks": checks, "pass": all(checks.values()), "covered": int(covered.sum()),
            "mismatched": int(mismatched.sum()), "escaped": int(escaped.sum()), "ambiguous": int(ambiguous.sum()),
            "first_mismatch": ([int(v) for v in first[0]] + [int(tx[tuple(first[0])]), int(ty[tuple(first[0])]),
                                                             int(ex[tuple(first[0])]), int(ey[tuple(first[0])])])
            if first.size else None}


def changed_outside(read: np.ndarray, hidden: np.ndarray, rect_px: Sequence[int]) -> tuple[int, int]:
    """(pixels changed outside the device rect [x, y, w, h], pixels changed inside it)."""
    changed = np.abs(read[..., :3].astype(int) - hidden[..., :3].astype(int)).max(axis=2) > TOLERANCE
    inside = np.zeros(changed.shape, bool)
    x, y, w, h = (int(v) for v in rect_px)
    inside[max(0, y):max(0, y + h), max(0, x):max(0, x + w)] = True
    return int((changed & ~inside).sum()), int((changed & inside).sum())


def oriented_marker(rows: np.ndarray, colour: Sequence[int], size: int) -> bool:
    """The scene's top-left marker reads at the top-left: the frame is the right way up."""
    corner = rows[:size, :size, :3].astype(int)
    return bool(np.abs(corner - np.asarray(colour[:3])).max() <= TOLERANCE)


__all__ = ["AMBIGUOUS_PX", "TOLERANCE", "analyse_texels", "changed_outside", "coverage_distance", "decode_texels",
           "expected_texels", "frame_rows", "geometry_px", "oriented_marker"]
