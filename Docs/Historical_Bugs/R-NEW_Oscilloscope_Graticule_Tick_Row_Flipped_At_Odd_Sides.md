# R-NEW: the Oscilloscope graticule's fourth tick row flipped at odd sides

**21 November 2026. Fixed in the shared graticule shader (ff9c255c5). Status: FIXED.**

## Observed failure

The N5.1 turned-card proof (`native/core/python/oscilloscope_check.py --rounds turned`, odd item sides 421 x 281 and
633 x 423) failed rule (a) on 18 of 21 sampled frames at every quarter turn, quarter 0 included: 200 to 330 pixels a
frame off by up to 180 levels, on two rows (or columns) exactly four pixels either side of the graticule's centre axes.
Python drew the minor ticks on one of those rows and the native core on the other. Nothing reported it before: every
earlier proof used even-sided items.

## Root cause

`widgets/spotify_visualizer/shaders/oscilloscope_graticule_body.glsl` limited the minor ticks to a band along the
centre axes with a hard cut, `step(toAxis, 4.0)`, where `toAxis` is a pixel centre's distance from the axis in pixels.
On an even-sided screen the axis lies on a pixel edge, so the centres sit at half-pixel distances and none is near the
cut. On an odd-sided screen the axis lies on a pixel centre, the fourth row's centre sits exactly at 4.0, and whether
that row's ticks are drawn depends on float rounding of the interpolated coordinate and its derivative. Two renderers,
or one renderer through two placements, round it apart, and the whole row appears or vanishes.

## Repair

The band ends on a half-pixel ramp, `1 - smoothstep(3.75, 4.25, toAxis)`: the fourth row of an odd-sided screen is drawn
at half its tick weight on every renderer, and centres at half-pixel distances (even-sided screens) get exactly what
they got before. The packs were baked again (`tools/regen_qrc.py --shaders`).

## Validation boundary

- Negative control seen failing: the same turned round with the old shader (`20261121_n51_turned_abi29/`, and quarter
  0 alone in `20261121_n51_turned_abi29_q0/`) fails at all eight quarter and ratio pairs.
- With the ramp, the turned round passes at quarters 0 to 3 at both ratios (rule (a) at most 2 levels;
  `20261121_n51_turned_abi29_band/`). The even-sided pixels round is hash-identical to ABI 28 on both APIs, and so are
  its Python references (126 of 126 frames each).
- Only these sizes and the harness's even sizes were measured. A screen whose centre lies at another fraction of a pixel
  had no exact tie to begin with, and the ramp changes it only where a centre lies between 3.75 and 4.25 pixels.

## Lesson

A hard threshold on a pixel distance ties exactly whenever geometry puts pixel centres on whole distances, which odd
sizes do on purpose. Parity proofs need odd and even sides alike, and a band edge in a shader needs a ramp at least
half a pixel wide.
