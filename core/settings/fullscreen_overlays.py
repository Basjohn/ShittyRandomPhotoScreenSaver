"""Expanded Visualizer overlays (plan 01 §G, M3b): their one canonical setting and its normaliser.

``widgets.spotify_visualizer.fullscreen_overlays`` holds every option of the two full-display overlays (the preset
toast and Now Playing) and their shared font. It is a **global Visualizer setting with a canonical default**, one
value per settings profile, like ``expanded_display_requested``: it has no mode prefix, so mode presets and the Custom
snapshot exclude it by construction (no preset repair fill; the completeness guard is unaffected), and preset
application or the runtime preset transaction never touches it. Settings' Visualizers → Fullscreen Mode pill edits it.

Each overlay's placement is its anchor corner plus an offset and a scale relative to the expanded display's safe area
(``offset_x``/``offset_y`` are fractions of the safe area's width/height in screen axes, ``scale`` multiplies the
overlay's size; zero offset and unit scale are the defaults). Now Playing's artwork has its own size factor
(``now_playing.artwork_scale``, on top of the overlay's scale; the artwork stays beside its text). Fullscreen Edit (M3c)
edits exactly these placement values: the offsets and the two scales. The corner is Settings' (the anchor); changing it
rebases the offset (:func:`rebase_offset_for_corner`).

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
#: The size factors (each clamped to SCALE_MIN..SCALE_MAX).
SCALE_KEYS = ("scale", "artwork_scale")
#: The placement members Fullscreen Edit writes, per overlay (the corner is Settings').
PLACEMENT_KEYS = {"preset": ("offset_x", "offset_y", "scale"),
                  "now_playing": ("offset_x", "offset_y", "scale", "artwork_scale")}

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
            elif key in SCALE_KEYS:
                target[key] = _number(item, float(default), SCALE_MIN, SCALE_MAX)
    return result


def rebase_offset_for_corner(options: Mapping[str, Any], corner: str) -> dict[str, Any]:
    """One overlay's options with its anchor moved to ``corner`` (Settings' Corner choice), its offset rebased.

    The offset is relative to the anchor corner, so a new corner reinterprets it. Each axis keeps its offset when it
    still points into the display from the new corner (right of a left corner, left of a right corner, below a top
    corner, above a bottom corner; zero always does): the overlay stays in bounds, the same distance in from the new
    anchor's edge. An axis whose offset would push the overlay out past the new anchor's edge resets to zero, so the
    overlay sits at the new corner instead of against the far side. Pure; everything but the offset is unchanged.
    """

    result = dict(options)
    corner = str(corner)
    if corner not in CORNERS:
        return result
    result["corner"] = corner
    inward_x = 1.0 if corner.endswith("_left") else -1.0
    inward_y = 1.0 if corner.startswith("top_") else -1.0
    for key, inward in (("offset_x", inward_x), ("offset_y", inward_y)):
        value = result.get(key, 0.0)
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = 0.0
        if not math.isfinite(number) or number * inward < 0.0:
            number = 0.0
        result[key] = number
    return result


__all__ = [
    "CORNERS",
    "FONT_SIZE_MAX",
    "FONT_SIZE_MIN",
    "FULLSCREEN_OVERLAYS_KEY",
    "OFFSET_MAX",
    "OFFSET_MIN",
    "OVERLAY_IDS",
    "PLACEMENT_KEYS",
    "SCALE_KEYS",
    "SCALE_MAX",
    "SCALE_MIN",
    "canonical_fullscreen_overlays",
    "normalize_fullscreen_overlays",
    "rebase_offset_for_corner",
]
