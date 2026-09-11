"""Pure-data colourization helpers for Settings About artwork.

The shipped About images intentionally keep their original pixels. Companion
liquid-mask PNGs identify only the chromatic liquid/background field. Theme
changes recolour that masked field while preserving its original shading and
all unmasked artwork exactly.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image

# Authored source-liquid colour. A theme may still choose this exact value to
# bypass recolouring and preserve the source pixels byte-for-byte.
ORIGINAL_ABOUT_LIQUID_RGB = (198, 133, 82)
_REFERENCE_LIGHTNESS = 0.55


@lru_cache(maxsize=8)
def _load_source_and_mask(source_path: str, mask_path: str) -> tuple[np.ndarray, np.ndarray]:
    source = np.asarray(Image.open(source_path).convert("RGBA"), dtype=np.uint8)
    mask = np.asarray(Image.open(mask_path).convert("L"), dtype=np.uint8)
    if source.shape[:2] != mask.shape:
        raise ValueError(
            f"About liquid mask size mismatch: source={source.shape[:2]} mask={mask.shape}"
        )
    source.setflags(write=False)
    mask.setflags(write=False)
    return source, mask


def recolor_liquid_rgba(
    source_rgba: np.ndarray,
    mask_u8: np.ndarray,
    target_rgb: Iterable[int],
) -> np.ndarray:
    """Return RGBA pixels with only the masked liquid recoloured.

    The source luminance remains the shading authority. The target colour owns
    the neutral/midpoint colour; darker source pixels shade toward black and
    lighter source pixels shade toward white. The mask may contain soft edge
    values so antialiasing around bubbles/text remains intact.
    """

    src = np.asarray(source_rgba, dtype=np.uint8)
    mask = np.asarray(mask_u8, dtype=np.uint8)
    if src.ndim != 3 or src.shape[2] != 4:
        raise ValueError("source_rgba must have shape (height, width, 4)")
    if mask.shape != src.shape[:2]:
        raise ValueError("mask_u8 shape must match source image dimensions")

    target = tuple(int(channel) for channel in target_rgb)
    if len(target) != 3 or any(channel < 0 or channel > 255 for channel in target):
        raise ValueError("target_rgb must contain three 0..255 channels")

    # Preserve any theme that explicitly chooses the authored source orange
    # byte-for-byte rather than passing it through an equivalent transform.
    if target == ORIGINAL_ABOUT_LIQUID_RGB:
        return src.copy()

    rgb = src[..., :3].astype(np.float32)
    luminance = (
        0.2126 * rgb[..., 0]
        + 0.7152 * rgb[..., 1]
        + 0.0722 * rgb[..., 2]
    ) / 255.0

    target_arr = np.asarray(target, dtype=np.float32)
    low_factor = np.clip(luminance / _REFERENCE_LIGHTNESS, 0.0, 1.0)[..., None]
    high_factor = np.clip(
        (luminance - _REFERENCE_LIGHTNESS) / (1.0 - _REFERENCE_LIGHTNESS),
        0.0,
        1.0,
    )[..., None]

    shaded = np.where(
        (luminance < _REFERENCE_LIGHTNESS)[..., None],
        target_arr * low_factor,
        target_arr * (1.0 - high_factor) + 255.0 * high_factor,
    )

    weight = (mask.astype(np.float32) / 255.0)[..., None]
    out = src.copy()
    out[..., :3] = np.clip(rgb * (1.0 - weight) + shaded * weight, 0.0, 255.0).astype(
        np.uint8
    )
    # Source alpha is intentionally untouched.
    return out


def themed_about_rgba(
    source_path: str | Path,
    mask_path: str | Path,
    target_rgb: Iterable[int],
) -> np.ndarray:
    """Load one cached source/mask pair and return themed RGBA pixels."""

    source, mask = _load_source_and_mask(str(Path(source_path)), str(Path(mask_path)))
    return recolor_liquid_rgba(source, mask, target_rgb)


__all__ = [
    "ORIGINAL_ABOUT_LIQUID_RGB",
    "recolor_liquid_rgba",
    "themed_about_rgba",
]
