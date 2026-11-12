# R-192 | The display's scene was stretched vertically by an overscan that was not a whole logical pixel

**Status:** fixed 12 Nov 2026 (found by the lead's Display 1 run for plan 1C.4). The R-63 overscan is now the
smallest amount after which the overscanned axis is a whole number of logical pixels:
`rendering/quick/device_geometry.py` (`is_whole_logical`, `overscan_amount`). On the development machine's Display 1
(3840 × 2160 at 150 %) the window went from `(2560,-2)` 3840 × 2162 device pixels to `(2560,-3)` 3840 × 2163.
Regression bar: `tests/test_qtquick_window.py`
(`test_native_compat_window_overscans_one_exterior_edge_in_device_pixels`, and the durability sweep over every layout
and DPR, which now requires the overscanned axis to be whole whenever the monitor's own axis is; red on the old rule).

## Symptom

After 1C.4 put the Visualizer card on whole device pixels, the card's left and right borders on Display 1 were exact
(8 solid border pixels, nothing blended either side), but the bottom border still had a blended pixel on both sides,
so the content's edge read as touching the frame. No off-screen render showed it.

## Cause

Since 289270ae (24 Sep 2026, R-63's device-exact window) the overscan was the smallest amount for which Qt's rounding
maps back to the same device extent (`survives_logical_rounding`). At 150 % that was 2 device pixels: 2162 device
pixels, which Qt holds as 1441 logical. Qt Quick projects the window's logical size onto its surface's device size,
so the scene was drawn at 2162 / 1441 = 1.50035 device pixels per logical pixel vertically instead of 1.5: every
coordinate lower on the display drifted further off the device grid (about 0.1 px at the card's top, 0.39 px at its
bottom). Every horizontal edge on the display, card borders, widget edges and text included, was drawn between two
device pixels and blended. Horizontally nothing changed (2560 × 1.5 is exactly 3840).

## Why it stayed hidden

It was silent: no log line, no off-screen render (off-screen targets have no overscan), and a sub-pixel softness
reads as "slightly soft" rather than broken. Only a crop of the real window's back buffer at native pixels showed
the asymmetry between vertical and horizontal edges.

## Fix

`overscan_amount` first looks for the smallest amount (up to four logical pixels) that makes the axis a whole number
of logical pixels; the older rounding rule applies only when none exists. A whole logical extent is also exactly
representable by Qt, the overscan is then a whole device-pixel shift of the scene, and the monitor's pixels map 1:1.
Lead's D1 runs on Display 1, 12 Nov: before, the bottom edge read `91789e d2b2ff ×7 655265` (a blend on both sides);
after, every edge of the card reads 8 solid border pixels with nothing blended, in the saver's own frame and in the
DWM composite (`.artifacts/evidence/display/d1_run/20261112_devcurve_card_edge_after/` and
`20261112_devcurve_card_edge_whole_logical/`).

## Still open

A monitor whose *non*-overscanned axis is not a whole number of logical pixels at its DPR (for example 1366 px at
125 %) is still stretched on that axis; the fix there is a second exterior-edge overscan, recorded in the plan.

## Lesson

Qt Quick's scale is logical size to surface size, not the DPR: a window whose device extent is not a whole number of
logical pixels is a resampled scene. Judge edges on a real display at native pixels, in both axes.
