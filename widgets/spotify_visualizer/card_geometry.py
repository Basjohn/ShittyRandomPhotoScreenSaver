"""Outer card geometry policy for the Spotify visualizer.

This module intentionally owns only the *outer* card contract:
- mode-driven preferred height
- blob-specific width reduction
- media-relative card placement

It does *not* own painted-card stencil math or per-mode inner render
adaptation. Those remain separate so future edit-mode/custom-resize work
can reason about outer geometry without disturbing the GL card shell.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from PySide6.QtCore import QRect

# Hard bounds to prevent absurd card sizes
MIN_HEIGHT: int = 40
MAX_HEIGHT: int = 600

# Default growth factors per mode (multiplied against base_height)
DEFAULT_GROWTH: dict[str, float] = {
    "spectrum": 2.0,
    "oscilloscope": 2.0,
    "blob": 3.5,
    "sine_wave": 2.0,
    "bubble": 3.0,
    "devcurve": 3.5,
}

_SHRINK_TO_BASE_ALLOWED_MODES = frozenset({"spectrum", "oscilloscope", "sine_wave", "devcurve"})
_TOP_ANCHORS = ("TOP_LEFT", "TOP_CENTER", "TOP_RIGHT")


@dataclass(frozen=True)
class VisualizerCardMetrics:
    mode_id: str
    base_height: int
    growth_factor: float
    preferred_height: int
    force_base_height: bool


@dataclass(frozen=True)
class VisualizerCardPlacement:
    x: int
    y: int
    width: int
    height: int
    place_below_media: bool


def build_growth_map_from_widget(widget) -> dict[str, float]:
    """Return the live per-mode growth map from *widget*."""
    return {
        "spectrum": float(getattr(widget, "_spectrum_growth", DEFAULT_GROWTH["spectrum"])),
        "oscilloscope": float(getattr(widget, "_osc_growth", DEFAULT_GROWTH["oscilloscope"])),
        "blob": float(getattr(widget, "_blob_growth", DEFAULT_GROWTH["blob"])),
        "sine_wave": float(getattr(widget, "_sine_wave_growth", DEFAULT_GROWTH["sine_wave"])),
        "bubble": float(getattr(widget, "_bubble_growth", DEFAULT_GROWTH["bubble"])),
        "devcurve": float(getattr(widget, "_devcurve_growth", DEFAULT_GROWTH["devcurve"])),
    }


def resolve_card_metrics(
    mode_id: str,
    base_height: int,
    growth_by_mode: Mapping[str, float] | None = None,
    *,
    max_available: int | None = None,
) -> VisualizerCardMetrics:
    """Resolve the preferred outer card height contract for a mode."""
    growth_map = growth_by_mode or DEFAULT_GROWTH
    growth_factor = float(growth_map.get(mode_id, DEFAULT_GROWTH.get(mode_id, 1.0)))
    growth_factor = max(0.5, min(5.0, growth_factor))
    raw_height = int(int(base_height) * growth_factor)
    preferred_height = max(MIN_HEIGHT, min(MAX_HEIGHT, raw_height))

    if max_available is not None and max_available > 0:
        preferred_height = min(preferred_height, int(max_available))

    preferred_height = max(MIN_HEIGHT, preferred_height)
    force_base_height = mode_id in _SHRINK_TO_BASE_ALLOWED_MODES and growth_factor <= 1.0
    if force_base_height:
        preferred_height = max(MIN_HEIGHT, int(base_height))

    return VisualizerCardMetrics(
        mode_id=mode_id,
        base_height=int(base_height),
        growth_factor=growth_factor,
        preferred_height=int(preferred_height),
        force_base_height=force_base_height,
    )


def should_place_below_media(position_name: str) -> bool:
    normalized = str(position_name or "").upper()
    return any(anchor in normalized for anchor in _TOP_ANCHORS)


def resolve_relative_card_placement(
    *,
    media_rect: QRect,
    parent_width: int,
    parent_height: int,
    mode_id: str,
    card_height: int,
    position_name: str,
    blob_width: float = 1.0,
    gap: int = 20,
) -> VisualizerCardPlacement:
    """Resolve media-relative card geometry for the visualizer."""
    full_width = media_rect.width()
    width = full_width
    x = media_rect.left()

    if mode_id == "blob":
        blob_width = max(0.1, min(1.0, float(blob_width)))
        if blob_width < 1.0:
            width = max(40, int(full_width * blob_width))
            x = media_rect.left() + (full_width - width) // 2

    place_below = should_place_below_media(position_name)
    if place_below:
        y = media_rect.top() + media_rect.height() + gap
    else:
        y = media_rect.top() - gap - int(card_height)

    y = max(0, y)
    x = max(0, x)
    width = min(width, max(10, int(parent_width) - x))

    return VisualizerCardPlacement(
        x=int(x),
        y=int(y),
        width=int(width),
        height=int(card_height),
        place_below_media=place_below,
    )
