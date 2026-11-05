"""Display <-> linear-light colour conversion shared by Studio instruments (sRGB transfer)."""
from __future__ import annotations

from typing import Iterable


def display_hex(linear_rgb: Iterable[float]) -> str:
    """Linear-light 0..1 RGB -> display sRGB hex."""
    values = []
    for v in linear_rgb:
        v = max(0.0, min(1.0, float(v)))
        s = 12.92 * v if v <= .0031308 else 1.055 * v ** (1 / 2.4) - .055
        values.append(max(0, min(255, round(s * 255))))
    return "#%02x%02x%02x" % tuple(values)


def linear_from_hex(text: str) -> list[float]:
    """Display sRGB hex -> linear-light 0..1 RGB."""
    text = str(text).strip().lstrip("#")
    if len(text) != 6:
        raise ValueError("Colour must be six hex digits")
    channels = [int(text[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in channels]


__all__ = ["display_hex", "linear_from_hex"]
