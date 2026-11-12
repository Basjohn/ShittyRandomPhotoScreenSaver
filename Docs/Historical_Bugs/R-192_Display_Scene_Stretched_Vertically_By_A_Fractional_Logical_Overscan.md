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

## Second axis (plan 1C.4 remainder, 12 Nov 2026)

A monitor whose *non*-overscanned axis was not a whole number of logical pixels at its DPR was still stretched on
that axis. `compat_native_rect` now gives that axis its own exterior-edge overscan, chosen by the same rule
(`overscan_amount`), whenever the monitor has an exterior edge on it: 1366 × 768 at 125 % gets a top and a left
overscan; the development machine's Display 0 (2560 × 1440 at 150 %, 1706.67 logical wide) was stretched
horizontally by 2560 / 1707 = 0.99980 and now goes from `(0,-3)` 2560 × 1443 to `(-2,-3)` 2562 × 1443 device pixels,
its shared right edge unchanged. Overscan still only goes past an edge on the virtual desktop's boundary, at most one
edge per axis. Regression bar: the durability sweep in `tests/test_qtquick_window.py` now requires every axis with an
exterior edge to be whole (red on the one-edge rule, first at `row 1280x720|1280x720 top` at 150 %), and
`test_native_compat_window_overscans_both_axes_when_neither_is_whole_logical`. Seen on the real Display 0 afterwards
(12 Nov, one bounded run by the lead with the operator's leave): window `(-2,-3)` 2562 × 1443 device pixels, every card
edge 8 solid border pixels with nothing blended, in the saver's frame and in the DWM composite (evidence
`.artifacts/evidence/display/d1_run/20261112_msi_second_axis_edges/`).

## Still open

An axis with no exterior edge cannot be overscanned without overdrawing a neighbour, so a monitor enclosed on that
axis (the middle of three in a row has no left or right exterior edge; the centre of a 3 × 3 grid has none at all)
keeps Qt Quick's stretch there when its extent is not whole at its DPR. A monitor with no exterior edge at all still
takes R-63's top fallback, which overscans into the display above it.

Decided 12 Nov 2026 (lead, plan 01 M3c display styles, decision 4): a Watchlist entry, not a blocker for the
Fullscreen Visualizer's Borders To Edge style. The layouts named: the middle of three in a row (no left or right
exterior edge) and the centre of a 3 × 3 grid (none at all). On such a display Qt Quick's stretch already softens
every edge; a frame on the display's edge adds no new defect. The stretch is recorded, never asserted away, by
`tests/test_expanded_display_styles.py` (`test_the_enclosed_axis_stretch_is_recorded_not_hidden`: three 1366 × 768
at 125 %, 1366 device pixels drawn as 1093 logical).

## Lesson

Qt Quick's scale is logical size to surface size, not the DPR: a window whose device extent is not a whole number of
logical pixels is a resampled scene. Judge edges on a real display at native pixels, in both axes.
