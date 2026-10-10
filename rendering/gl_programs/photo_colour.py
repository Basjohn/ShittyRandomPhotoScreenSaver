"""Colours read from a photograph: shared, import-safe helpers (no GL), cheap enough to run once per run.

* ``photo_dominant_colour``: the most used colour (Exploding Tiles' wall body);
* ``photo_accent_colour``: the most used *vivid* colour, weighted by chroma and brightness, so a
  mostly dark or grey picture still yields its characteristic hue;
* ``photo_glow_colour``: an accent made luminous for emitted light (full brightness, saturation
  kept in a glowing range; a near-grey picture glows cool white).

Both readers sample the same sparse 64 x 36 grid of the presentation image's RGBA8 bytes into a
coarse (3 bits per channel) histogram, vectorised (well under a millisecond on the render thread);
ties go to the bin seen first in row order.
"""

from __future__ import annotations

import colorsys

import numpy as np

_COLUMNS, _ROWS = 64, 36


def _grid(rgba8: bytes, pixel_size: tuple[int, int], row_stride: int) -> np.ndarray:
    """The sampled pixels, row by row, as an (N, 3) int array."""
    width, height = int(pixel_size[0]), int(pixel_size[1])
    data = np.frombuffer(rgba8, dtype=np.uint8)
    rows = ((2 * np.arange(_ROWS) + 1) * height // (2 * _ROWS)) * int(row_stride)
    columns = 4 * ((2 * np.arange(_COLUMNS) + 1) * width // (2 * _COLUMNS))
    index = (rows[:, None] + columns[None, :]).ravel()
    return np.stack((data[index], data[index + 1], data[index + 2]), axis=1).astype(np.int64)


def _heaviest_bin(pixels: np.ndarray, weights: np.ndarray) -> tuple[float, float, float] | None:
    keep = weights > 0.0
    if not keep.any():
        return None
    keys = (pixels[:, 0] >> 5) << 6 | (pixels[:, 1] >> 5) << 3 | pixels[:, 2] >> 5
    totals = np.bincount(keys[keep], weights[keep], minlength=512)
    best = np.flatnonzero(totals == totals.max())
    if len(best) > 1:      # the bin whose first sample comes first
        first = {int(key): position for position, key in reversed(list(enumerate(keys[keep])))}
        best = [min(best, key=lambda key: first[int(key)])]
    chosen = keep & (keys == best[0])
    total = float(totals[best[0]])
    rgb = (pixels[chosen] * weights[chosen, None]).sum(axis=0)
    return tuple(float(c) / (255.0 * total) for c in rgb)


def photo_dominant_colour(rgba8: bytes, pixel_size: tuple[int, int], row_stride: int) -> tuple[float, float, float]:
    """The photograph's most used colour, as 0..1 RGB: the fullest histogram bin, averaged within
    that bin, so a real majority colour rather than a muddy mean."""
    pixels = _grid(rgba8, pixel_size, row_stride)
    return _heaviest_bin(pixels, np.ones(len(pixels)))


def photo_accent_colour(rgba8: bytes, pixel_size: tuple[int, int], row_stride: int) -> tuple[float, float, float]:
    """The photograph's most used vivid colour, as 0..1 RGB: samples weigh by chroma times
    brightness, so greys and shadows count for little. A picture with no colour at all gives its
    dominant colour."""
    pixels = _grid(rgba8, pixel_size, row_stride)
    high, low = pixels.max(axis=1), pixels.min(axis=1)
    accent = _heaviest_bin(pixels, (high - low) * high / 65025.0)
    return accent if accent is not None else _heaviest_bin(pixels, np.ones(len(pixels)))


def photo_glow_colour(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    """``rgb`` made luminous for emitted light: full brightness, saturation between 0.45 and 0.9;
    a near-grey colour glows cool white."""
    hue, saturation, _value = colorsys.rgb_to_hsv(*(max(0.0, min(1.0, float(c))) for c in rgb))
    if saturation < 0.08:
        return 0.9, 0.94, 1.0
    return colorsys.hsv_to_rgb(hue, max(0.45, min(0.9, saturation * 1.4)), 1.0)
