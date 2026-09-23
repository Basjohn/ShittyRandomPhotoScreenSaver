# R-95 — Prepared Transition Geometry Never Matched Under R-63 Overscan

Date: 2026-09-24  
Status: SOLVED IN CODE — the next ordinary `--frame-trace` run confirms Glass's first moving frame

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

## Observed Failure

The operator felt Glass had become slow since collisions and second cracks were added. The 2026-09-23 23:47
frame trace showed every Glass run's first moving frame at 82–141 ms (2560×1440 display) and 43–72 ms
(3840×2160 display), all inside the render pass, after TX-01 had been accepted as fixed. Steady Glass frames
matched every other transition.

## Root Cause

TX-01 prepares fracture geometry on COMPUTE when the batch's transition resolves, keyed by the exact float
aspect. The preparation took its aspect from `display_bounds()` (the monitor rectangle, 1707×960 logical);
the renderer takes it from the frame's logical size, which is the background item's size — the R-63
compatibility window, one logical pixel taller (1707×961). The keys never matched, so the prepared bytes
were never used and the in-flight wait never engaged: both displays' render threads built the geometry
themselves at the same moment, contending for the GIL with the GUI and Visualizer threads. Collisions made
that build about 2.5× more expensive (≈8 → ≈19 ms isolated, ≈27 ms with second cracks), which is why it
became noticeable then.

## Why It Was Hard To Find

Every test fed both sides the same aspect, so the prepare → hit path was green; the cache failed silently
into a correct-looking rebuild. The fix for TX-01 was accepted on a trace taken before that fix landed. The
one-pixel R-63 overscan is deliberate and invisible, and only the native geometry log line shows the window
is larger than the monitor.

## Fix

`QuickDisplayUnit.transition_logical_size()` returns the background item's logical size; the manager keys
preparation on it. R-63 overscan unchanged.

## Regression Coverage

- `tests/test_transition_run_geometry.py::test_display_manager_prepares_geometry_once_per_batch_on_compute`
  models the R-63 window and asserts the key the renderer asks for is prepared (fails on the old path).
- `tests/test_qtquick_display_unit.py::test_transition_size_is_the_background_items_not_the_monitor_rect`
  shows a real unit and pins the accessor to the background item, not `display_bounds`.

## Guardrail

Work prepared off the render thread must key on the renderer's own inputs, and a test must prove a hit rather
than a build (`Docs/Guardrails.md`, Qt Quick hot paths).
