# R-172 | Offscreen Studio surface: GL context freed before its render control at interpreter exit

**Status:** fixed 2026-11-06 (`ui/studio/surface.py`, `OffscreenStudioSurface`). Regression tests with a negative
control in `tests/test_studio_exit_every_mode.py`. Production is not exposed (see below).

## Symptom

`tests/test_studio_exit_every_mode.py` passed every test, then the Python process exited with `0xC0000005` in about
a quarter of runs. `python -X faulthandler` showed an access violation with no Python frame, after "25 passed".
Measured before the fix: 3/12 and 2/10 runs of the whole file. Each half alone, the 9 forced-failure tests or the
other 16, gave 0/12. Other Studio lifecycle files (`test_waveform_studio_lifecycle.py`, `test_studio_exit_repaint.py`,
`test_studio_chrome.py`) gave 0/10.

## Evidence

- An exit census plugin (all live `QObject` wrappers at `pytest_unconfigure`) found 19 `OffscreenStudioSurface`s, 19
  `QOpenGLContext`s, and 9 live `QQuickRenderControl` / `QQmlEngine` trees. The 9 trees came from
  `test_a_failing_teardown_still_reveals_settings`, which stubs `surface.retire` to raise, so those surfaces are never
  retired. The closed `StudioController`s keep them all reachable.
- Logging `destroyed` during exit showed PySide's sweep at work. At interpreter exit PySide deletes every live
  Python-owned `QObject` one at a time, in binding-map (hash) order, and the crash fell inside that sweep.
- A probe that re-ran the sweep itself, in a seeded random order and logging each deletion before it happened,
  crashed on the deletion of an unretired `QQuickRenderControl`. That happened 3 times in 14 seeds. Each time the
  same surface's `QOpenGLContext` had already been deleted. The faulting frame was the probe's own
  `shiboken6.delete(control)`.

## Cause

`OffscreenStudioSurface` passes its own `QOpenGLContext` to the render control through
`QQuickGraphicsDevice.fromOpenGLContext`. The render control's RHI keeps a raw pointer to that context and makes it
current again in the control's destructor. Qt requires the context to outlive the control. Only `retire()` enforced
that order. The context and the control were two independent Python owners, so on any other path (a surface whose
retirement failed or never ran, GC of a cycle, the exit sweep) the context could be freed first. The control's
destructor then read freed memory. That only crashes when the freed block has been reused, which is why it was
intermittent and needed the whole file's heap churn.

## Fix and proof

The context and its offscreen surface are now Qt children of the render control (`setParent(control)`), so they are
no longer Python-owned. Whatever destroys the control destroys them afterwards. `retire()` deletes the window, then
the engine, then the control, which takes the context with it.

Two tests in `tests/test_studio_exit_every_mode.py` pin this:

- `test_an_unretired_surface_destroys_its_gl_context_only_after_its_render_control` leaves a surface unretired,
  replays the exit sweep context-first, and asserts the order control → context → offscreen surface. It fails on the
  old code at the plan check, before any illegal deletion runs.
- The negative control gives the context back its own Python owner and asserts the sweep check flags it.

After the fix: 0/24 whole-file runs, and 0/12 seeded-sweep runs.

## Production exposure

None from this mechanism. Production uses `StudioWindowSurface`, whose window's render loop creates and owns its GL
context internally, so there is no imported context. Only tests and `tools/` (`studio_drag_profile.py`,
`waveform_studio_capture.py`) construct `OffscreenStudioSurface`. When the app quits with a Studio open,
`close_for_quit` retires the surface from `aboutToQuit`. A probe showed that `QCoreApplication::exec`'s own cleanup
destroys the Studio window and engine before `exec()` returns, so nothing is left for the exit sweep.
`tools/onboarding_preview_foundry.py`'s hidden scene had the same structure: an imported context with its own Python
owner, and the control left to `deleteLater`. It got the same ownership on 6 Nov, and its `close()` now destroys the
window and then the control at once. `tests/test_onboarding_preview_capture_teardown.py` covers it, with a negative
control.

## Lesson

When a context is imported into a `QQuickRenderControl` (or any Qt object that keeps a raw pointer to it), make the
context a Qt child of the object that uses it. Do not leave the order to a `retire()` that some path may skip.
PySide's exit sweep deletes Python-owned `QObject`s in an order nobody controls. An intermittent exit-time access
violation with no Python frame means: replay that sweep yourself, seeded and logged, and look at the object it was
deleting.
