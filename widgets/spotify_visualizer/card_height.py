"""Reusable card height expansion for Spotify visualizer modes.

Some visualizer modes (blob, starfield, helix) benefit from a taller card
than the default spectrum strip (~80 px).  This module provides a
centralised way to compute the preferred height for any mode and a
user-configurable growth factor so the expansion scales well on
different screen sizes.

The default height for spectrum is whatever the widget already has
(typically set by ``position_spotify_visualizer`` in widget_manager).
For expanded modes the height is multiplied by a per-mode growth
factor that the user can tune via settings.

Usage
-----
>>> from widgets.spotify_visualizer.card_height import preferred_height
>>> h = preferred_height("blob", base_height=80, growth_factor=2.5)
160   # 80 * 2.0 (clamped by MAX)
"""
from __future__ import annotations

from core.logging.logger import get_logger

logger = get_logger(__name__)

# Hard bounds to prevent absurd card sizes
MIN_HEIGHT: int = 40
MAX_HEIGHT: int = 600

# Default growth factors per mode (multiplied against base_height)
DEFAULT_GROWTH: dict[str, float] = {
    "spectrum": 2.0,
    "oscilloscope": 2.0,
    "starfield": 3.0,
    "blob": 3.5,
    "helix": 3.0,
    "sine_wave": 2.0,
    "bubble": 3.0,
}


def preferred_height(
    vis_mode: str,
    base_height: int = 80,
    growth_factor: float | None = None,
    max_available: int | None = None,
) -> int:
    """Return the ideal card height for *vis_mode*.

    Parameters
    ----------
    vis_mode:
        One of ``spectrum``, ``oscilloscope``, ``starfield``, ``blob``,
        ``helix``.
    base_height:
        The widget's default (spectrum) height in logical pixels.
    growth_factor:
        User-configurable multiplier.  ``None`` means use the built-in
        default for that mode.
    max_available:
        If provided, the result is clamped so the card does not exceed
        this many pixels (e.g. remaining screen space above the media
        widget).

    Returns
    -------
    int
        Clamped height in logical pixels.
    """
    if growth_factor is None:
        growth_factor = DEFAULT_GROWTH.get(vis_mode, 1.0)

    growth_factor = max(0.5, min(5.0, float(growth_factor)))
    raw = int(base_height * growth_factor)
    clamped = max(MIN_HEIGHT, min(MAX_HEIGHT, raw))

    if max_available is not None and max_available > 0:
        clamped = min(clamped, max_available)

    return max(MIN_HEIGHT, clamped)
