# R-215 | Spectrum's kick lane boosted the edge bars wherever the Bass lane was authored

**Status:** fixed 14 Nov 2026 (plan item 1B.10, side defect; commit 701302d5).
`widgets/spotify_visualizer/bar_computation.py` now picks the bars the kick express lane boosts with
`kick_lane_bars`: the bars whose lane position lies nearest the Bass lane's authored position, on the shape
instrument's lane axis (`lane_sample_positions`: 0 at the centre, 1 at the edge when mirrored). The count is the same
as before, taken per half in a mirrored layout, and each bar is paired with its mirror `bands - 1 - i`. With no Bass
lane, nothing is boosted. A linear layout with Bass at its start boosts the same first bars as before.
Regression bar: `tests/test_spectrum_kick_lane_position.py`, which drives the engine's real `fft_to_bars` with the
transient lane pinned high and then off:
- a centre Bass lane lifts the centre bars and not the edges;
- an edge Bass lane lifts the edges and not the centre;
- the lift is symmetric at 15 and 16 bars;
- the linear layout still lifts its first bars.

Negative control: the old loop, with the new helper merely present, fails three of the six cases: both centre-Bass
cases, and the edge-Bass case at 16 bars (the asymmetry).

## Symptom

On a kick, a mirrored Spectrum jumped at its outermost bars even when its Bass lane sat at the centre. Most curated
presets and Extruded Spectrum's default author the mirrored Bass lane there. The bars that carry the bass lane got no
kick help, so a kick read as a twitch at the card's sides. Nothing failed and nothing was logged; the operator saw only
a weaker, oddly placed kick response.

## Cause

The kick express lane (Approach A section 5) boosted bar indices `0 .. _agc_bass_split - 1`, then their mirror
`2 * center - i` in a mirrored layout. That is the left edge and the right edge, whatever the shape instrument's notch
positions said. `_agc_bass_split` is a frequency split, not a lane position. The rule was written when the mirrored
default put Bass at the edges, and it never followed the lane once the lanes became authored. Two more faults sat in
the mirror formula:
- With an even bar count, `2 * center - 0` is out of range, so the right side boosted one bar fewer than the left
  (an asymmetric kick).
- The odd-count arithmetic only happened to be right.

## Lesson

A kick, like any other band-specific response, belongs to the lane that carries the band, read from the same
authored lane axis the energy routing uses. It must never come from a fixed index range that was right for one
default layout. A mirror is `bands - 1 - i`; `2 * center - i` is right only for odd counts.
