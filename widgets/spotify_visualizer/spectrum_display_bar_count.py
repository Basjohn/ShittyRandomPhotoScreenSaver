"""The one rule for how many bars Spectrum draws on the card as shown.

Operator, 8 Nov 2026: "Spectrum needs to scale still more bars when fullscreen, 20% more if fullscreen and
horizontal." The authored bar count (Settings / preset) is what the audio engine computes and what the ordinary card
draws. While the Visualizer is expanded (its display-wide record, ``ResolvedVisualizerPresentation.expanded_display``)
and its content is horizontal (not turned a quarter), Spectrum draws 20% more bars, rounded half up and capped at the
shader's 64. A quarter-turned card, the ordinary card and every other mode draw the authored count.

The extra bars are a presentation of the same logical frame: ``resample_levels`` spreads the authored bars and their
peaks over the drawn count (linear between neighbours, both ends kept), so the engine, the logical frames and their
digests are identical ordinary and expanded. The count changes only with the record the card is drawn from: the
expand/collapse fade-through swaps records at its midpoint, where the card is invisible, so it never pops.
"""
from __future__ import annotations

from typing import Sequence

SPECTRUM_EXPANDED_HORIZONTAL_BAR_GAIN = 1.2
SPECTRUM_MAX_DISPLAY_BARS = 64          # widgets/spotify_visualizer/shaders/spectrum.frag: u_bars[64]


def resolve_display_bar_count(
    mode_id: str, authored_bar_count: int, *, expanded: bool, content_rotation_quarters: int,
) -> int:
    """Bars ``mode_id`` draws for ``authored_bar_count`` on the card as shown (expanded or not, turned or not)."""

    authored = max(1, int(authored_bar_count))
    if str(mode_id) != "spectrum" or not expanded or int(content_rotation_quarters) % 2:
        return authored
    return max(authored, min(SPECTRUM_MAX_DISPLAY_BARS,
                             int(authored * SPECTRUM_EXPANDED_HORIZONTAL_BAR_GAIN + 0.5)))


def resample_levels(values: Sequence[float], count: int) -> list[float]:
    """``values`` spread over ``count`` bars: linear between neighbours, first and last kept exactly."""

    source = [float(value) for value in values]
    count = max(0, int(count))
    if count == len(source) or not source:
        return source[:count] + [0.0] * max(0, count - len(source))
    if count == 1 or len(source) == 1:
        return [source[0]] * count
    step = (len(source) - 1) / (count - 1)
    out = []
    for index in range(count):
        position = index * step
        low = min(int(position), len(source) - 2)
        t = position - low
        out.append(source[low] + (source[low + 1] - source[low]) * t)
    return out


__all__ = ["SPECTRUM_EXPANDED_HORIZONTAL_BAR_GAIN", "SPECTRUM_MAX_DISPLAY_BARS", "resample_levels",
           "resolve_display_bar_count"]
