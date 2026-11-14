# R-213 | Spectrum's border band was lopsided: two units on the left and bottom, so the left border hid the rim glow

**Status:** fixed 14 Nov 2026 (plan item 1D.14, the operator's "bars glow, or show a gap, on their left side").
`widgets/spotify_visualizer/shaders/spectrum.frag` decides a bar's side border, its ghost's sides and a segment's
ring through one test, `spectrum_in_border_band`: one authored unit (never under one logical pixel, the bar top's
stroke rule) in from each edge, on the continuous coordinate of the fragment's pixel centre, the same on both edges.
Regression bar: `tests/test_spectrum_rim_glow.py` (the band as wide on the left as on the right for every bar; a
segment's ring as wide on every edge; the rim's lift equal on both sides within 10 %). Negative control: the old test
put back into the helper fails all three (left 2 against right 1 or 2; segment rows bottom 2 against top 1; rim lift
18,067 against 25,111).

## Symptom

On every Spectrum bar the left border was wider than the right, and the rim glow was dimmer on the left: its
brightest columns sat under the wider border. With a light border the left edge read as glow; with a dark or
translucent one, as a gap. Segmented bars had a ring two rows deep at the bottom and one at the top.

## Cause

The side test floored the coordinate and compared with `<=` on the low edge and `>=` against the floored width on
the high edge: `bx <= scale || bx >= floor(bar_width) - scale` with `bx = floor(bar_local_x)`. At scale 1 that is
two units on the left (`bx` 0 and 1) against one plus the width's fractional part on the right; the segment rows had
the same test. The rim glow is not drawn on border pixels, so the left border covered the rim's core there. The rim's
own arithmetic (the side distance, the `fwidth` feather) is symmetric; the bar layout (gaps, fractional origins) is
not the cause either: the bias was the same with no gap and on whole-pixel bars.

Measured before and after on the Python renderer offscreen and on the native item in the hidden host (OpenGL and
Vulkan, 33 bars at the canonical card, glow on, per bar: border columns, and the glow's lift summed over the six
outer columns):

| | border columns L / R | rim lift L / R (mean) | bars brighter L : R |
|---|---|---|---|
| dpr 1, before | 2 / 1-2 | 273 / 591 | 3 : 30 |
| dpr 1, after | 1 / 1 | 668 / 668 | 15 : 15 |
| dpr 1.5, before | 3 / 1-2 | 328 / 778 | 0 : 33 |
| dpr 1.5, after | 1-2 / 1-2 | 895 / 895 | 15 : 15 |
| dpr 2, before | 4 / 2-3 | 337 / 947 | 0 : 33 |
| dpr 2, after | 2 / 2 | 1102 / 1102 | 15 : 15 |

Native OpenGL equals the Python renderer byte for byte in every case; Vulkan equals native OpenGL (0 levels);
validation clean (Qt defect A only). What remains is pixel phase: a bar on a fractional position samples its two
edges at different distances (a centre exactly on the left edge is inside the half-open bar, one exactly on the right
edge is not), a few percent either way, not one side.

Evidence: `.artifacts/evidence/visualizers/spectrum/rim_glow/20261114_root_cause_before/` and `..._after/`.

## Lesson

A border is one rule applied to both edges of the same coordinate. Floor-and-compare tests on pixel indices are
asymmetric by construction (`<=` on one side, `>=` on the other, a floored extent); test the continuous coordinate
against a band of the same width from each edge, as the bar's top and bottom already did.
