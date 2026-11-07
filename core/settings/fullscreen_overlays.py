"""Expanded Visualizer overlays (plan 01 §G, M3b): their one canonical setting and its normaliser.

``widgets.spotify_visualizer.fullscreen_overlays`` holds every option of the two full-display overlays (the preset
toast and Now Playing) and their shared font. It is a **global Visualizer setting with a canonical default**, one
value per settings profile, like ``expanded_display_requested``: it has no mode prefix, so mode presets and the Custom
snapshot exclude it by construction (no preset repair fill; the completeness guard is unaffected), and preset
application or the runtime preset transaction never touches it. Settings' Visualizers → Fullscreen Mode pill edits it.

Each overlay's placement is its anchor corner plus an offset and a scale relative to the expanded display's safe area
(``offset_x``/``offset_y`` are fractions of the safe area's width/height in screen axes, ``scale`` multiplies the
overlay's size; zero offset and unit scale are the defaults). Fullscreen Edit (M3c) edits those values.

Pure and Qt-free: the settings model, Settings and the display runtime all read it.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import math
from typing import Any

from core.settings.default_contract import require_canonical_default

FULLSCREEN_OVERLAYS_KEY = "widgets.spotify_visualizer.fullscreen_overlays"
#: The two overlays, in their canonical order.
OVERLAY_IDS = ("preset", "now_playing")
#: Anchor corners, in Settings' order.
CORNERS = ("top_left", "top_right", "bottom_left", "bottom_right")
FONT_SIZE_MIN, FONT_SIZE_MAX = 12, 72
OFFSET_MIN, OFFSET_MAX = -1.0, 1.0
SCALE_MIN, SCALE_MAX = 0.5, 3.0

_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})


def canonical_fullscreen_overlays(application: str | None = None) -> dict[str, Any]:
    """A fresh copy of the canonical default (fail-loud when the schema lacks it)."""

    value = require_canonical_default(FULLSCREEN_OVERLAYS_KEY, application)
    if not isinstance(value, Mapping):
        raise TypeError(f"canonical {FULLSCREEN_OVERLAYS_KEY} must be a mapping")
    return deepcopy(dict(value))


def _bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in _TRUE:
            return True
        if text in _FALSE:
            return False
    return default


def _number(value: Any, default: float, low: float, high: float) -> float:
    if isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if not math.isfinite(number):
        return default
    return max(low, min(high, number))


def normalize_fullscreen_overlays(value: Any, application: str | None = None) -> dict[str, Any]:
    """The stored value as the canonical shape: every key the canonical default declares, each admitted.

    Unknown keys are dropped; a missing or malformed member falls back to its canonical default (never to
    ``bool(value)``); numbers are clamped to their admitted ranges; a corner must be one of :data:`CORNERS`.
    """

    result = canonical_fullscreen_overlays(application)
    if not isinstance(value, Mapping):
        return result
    family = value.get("font_family")
    if isinstance(family, str) and family.strip():
        result["font_family"] = family.strip()
    if "font_size" in value:
        size = _number(value.get("font_size"), float(result["font_size"]), FONT_SIZE_MIN, FONT_SIZE_MAX)
        result["font_size"] = int(round(size))
    for overlay in OVERLAY_IDS:
        raw = value.get(overlay)
        if not isinstance(raw, Mapping):
            continue
        target = result[overlay]
        for key, default in tuple(target.items()):
            if key not in raw:
                continue
            item = raw[key]
            if key == "corner":
                if isinstance(item, str) and item.strip().lower() in CORNERS:
                    target[key] = item.strip().lower()
            elif isinstance(default, bool):
                target[key] = _bool(item, default)
            elif key in ("offset_x", "offset_y"):
                target[key] = _number(item, float(default), OFFSET_MIN, OFFSET_MAX)
            elif key == "scale":
                target[key] = _number(item, float(default), SCALE_MIN, SCALE_MAX)
    return result


__all__ = [
    "CORNERS",
    "FONT_SIZE_MAX",
    "FONT_SIZE_MIN",
    "FULLSCREEN_OVERLAYS_KEY",
    "OFFSET_MAX",
    "OFFSET_MIN",
    "OVERLAY_IDS",
    "SCALE_MAX",
    "SCALE_MIN",
    "canonical_fullscreen_overlays",
    "normalize_fullscreen_overlays",
]
