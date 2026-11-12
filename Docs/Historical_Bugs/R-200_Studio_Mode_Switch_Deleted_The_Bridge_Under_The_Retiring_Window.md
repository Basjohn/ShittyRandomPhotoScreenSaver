# R-200 | A Studio mode switch deleted the `studio` bridge under the retiring window, and every binding of its shell failed

**Status:** fixed 12 Nov 2026 (13cc7745; the lane guard in 21ee4f8e). Reported from the operator's run of 12 Nov
(Visualizer Studio, spectrum -> sphere). Owner: `ui/studio/surface.py` (`StudioShellHost`), and the shell's shape
instrument in `ui/studio/qml/StudioShell.qml`. Regression bars:
`tests/test_studio_mode_switch_bindings.py::test_a_mode_switch_never_evaluates_a_shell_with_studio_missing` and
`tests/test_studio_shape_instrument.py::test_hovering_onto_a_lane_tag_from_nothing_reads_no_missing_lane`. Each failed on
the code before its fix (148 TypeErrors from the retiring window; 8 TypeErrors per shape instrument). Silent: log only,
nothing on screen. The switch path shipped with the first Studio (fb90ac39, 5 Nov) and failed on every switch once a
second Studio mode existed; the lane guard shipped with the shape instrument (3695f429, 11 Nov).

## Symptom

`screensaver_qml.log` on a mode switch: first `StudioShell.qml:1398` and `:870` "Cannot read property 'pinned' of
undefined"; then, between the controller's "open mode=sphere" and "shown", "Cannot read property X of null" on nearly
every binding of the shell (`studio.theme`, `capabilities`, `modes`, `presets`, `values`, `workspaces` ...), and more
of them after "shown". Nothing visible: the window that failed was already queued for hiding.

## Cause

1. **The retiring window's context object was deleted before the window.** `StudioWindowSurface.retire` queues the
   window's hide and `deleteLater` (never a Python `hide()`, see the GIL note there) and `release_engine` queues the
   engine's. `request_mode_switch` then calls `open()`, which assigns a new `StudioBridge` to `controller.bridge`. The
   old bridge, the retiring shell's `studio` context property (the context does not own it), lost its last Python
   reference and was deleted while that window and engine still waited for the event loop. QML re-evaluated every
   binding that read `studio` with `studio` null. Evidence: each Studio engine's own `warnings` signal attributes all
   148 errors to window 1 (the retiring shell), none to the new one; holding one extra reference to the old bridge
   across the switch made them all disappear.
2. **The new window was never the problem.** `StudioShellHost` sets `studio` before `component.create`, so the new
   shell's first evaluation already has it (0 errors from window 2).
3. **The lane guard had no lower bound.** The hover handler writes `hoverPart`, then `hoverIndex`. Arriving on a lane tag
   from empty space, the hint (870) and cursor (1398) bindings ran with part "lane" and the previous index -1, and
   `hoverIndex < lanes.length` let `lanes[-1].pinned` through. Unrelated to the switch; it appeared in the same log
   because the pointer crossed a lane tag on its way to the mode picker.

## Fix

- `StudioShellHost` holds its bridge; `release_engine` hands it to the module's retiring set until the engine's
  `destroyed` (the window, with the shell's items, is destroyed before it), then drops it. No timer, no deferral, no
  rebuild; the bridge is gone once the engine is (the test asserts it, so this is not a leak).
- The shape instrument reads a hovered lane's pin through one guarded property, `hoverPinned`
  (`hoverPart === "lane" && 0 <= hoverIndex < lanes.length`).

## Why it hid

- The failing window was queued for hiding, so nothing changed on screen; only the QML sidecar log showed it.
- Every mode-switch test ran on `OffscreenStudioSurface`, whose `retire` destroys window and engine synchronously, so
  the bridge was never replaced under a live engine. The production surface defers destruction to the event loop.

## Lessons

1. A QML context object must live as long as the engine that reads it. When an owner replaces it while the old engine's
   destruction is queued, the old engine's retirement holds it, not the caller.
2. Test a lifecycle on the surface that has the production's destruction timing; a test surface that destroys
   synchronously proves a different order.
3. A guard of an index written separately from its kind must check both bounds.
