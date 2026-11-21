# R-247 | Clicking into the saver resized its display window twice (a black flicker on every activation)

**Status:** fixed 21 Nov 2026 (operator report the same day). `QuickDisplayWindow._apply_screen_geometry` leaves a
shown window that already sits at its placement alone (`_placement_is_current`, `rendering/quick/window.py`).
Regression bar: `tests/test_qtquick_window_activation_placement.py` (red on the old code with exactly the trace's two
sizes, 3840 × 2162 then 3840 × 2163; an over-wide guard that skips every shown window fails its displaced-window case).

## Symptom

Clicking into the running saver (the operator runs it on Display 1 only and works on Display 0) gave a slight black
flicker; clicking out and back in repeated it, about every second try. Seen with logging on.

## Cause

`DisplayManager._on_application_state_changed` treats every return to `ApplicationActive` as a resume edge and
schedules a monitor reconcile; with an unchanged screen signature its settled pass calls each window's
`revalidate_bound_screen_geometry`, which re-ran `_apply_screen_geometry`. That re-applied Qt's logical R-63 rect
(`(2560,-1)` 2560 × 1441 on Display 1). Since R-192 (bdf9b2464, 12 Nov) the window's device-exact rect is 3840 × 2163
(a whole 1442 logical rows), which Qt reads back as 1442 logical, so the logical 1441 rect is not a no-op: Qt resized
the native window to 3840 × 2162, then `_apply_native_compat_geometry` resized it back to 2163. Two resizes of a
GL/Vulkan surface per click, each a swap-chain resize, and a black frame. Before R-192 the overscan survived Qt's
rounding (2162 device = 1441 logical), so `QWindow::setGeometry` returned early and the revalidation cost nothing:
this is inferred from that rounding, not re-run.

Evidence: the operator's 21 Nov logs pair every `[DISPLAY_MANAGER] Monitor reconcile no-op
reason=applicationStateChanged` (verbose log) with a `[QUICK_GEOMETRY]` and `[QUICK_NATIVE_GEOMETRY]` pair at the same
second (geometry log; 17 activations between 12:59 and 13:04 during one saver generation). A hidden-window trace
(`.artifacts/evidence/display/focus_flicker/20261121_activation_double_resize/native_resize_trace.py` and `.json`;
never shown) replays the revalidation on each screen of this machine: two `WM_SIZE` per edge on both displays.

## Why it stayed hidden

Nothing failed: the window ended at the correct rect, the log lines looked like routine placement, and the flash is one
frame. The resize happened only while the saver was running beside other work, so only a multi-display user saw it.

## Fix

The revalidation still exists for its purpose (a resume that leaves a window displaced), but a shown window whose
target rect is the one it was last placed for, whose Qt geometry is one of that placement's logical rects and whose
native rect equals `compat_native_rect` is not placed again. A work-area edge (`availableGeometryChanged`, which also
re-applied the geometry) is covered by the same guard. A hidden window (the show path) is always placed.

## Lesson

A logical `setGeometry` is not idempotent on a window placed in device pixels at a fractional DPR. A repair that runs on
a frequent edge must first check whether anything needs repairing.
