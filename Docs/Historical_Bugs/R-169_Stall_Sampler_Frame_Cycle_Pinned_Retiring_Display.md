# R-169 | GUI stall sampler's frame map pinned a retiring display (Settings-open barrier timeout)

**Status:** fixed 2026-10-25 (`core/performance/gui_stall_sampler.py`), regression test with negative control. Supersedes
nothing; the strict barrier and GC policy are unchanged (no sweep: see
`Docs/Audits/Retirement_GC_Sweep_Assessment_2026-10-25.md`).

## Symptom

Opening Settings after framed 3D use sometimes timed out the lifecycle barrier with every QObject gone but
`QuickDisplayUnit` + `QuickDisplayVisualizerOwner` alive; the saver then exited (code 1) instead of opening Settings.
Intermittent, worse in long sessions. Only the first retirement after the 45 s freeze survived it (its thaw sweep).

## Evidence

The 2026-10-25 21:37 run's `[LIFECYCLE_BARRIER][PYTHON_OWNER_REFS]` named only **frame objects** as referrers: the
`view_orbit_finished` route `live_unit_route` → lambda → `_route_quick_visualizer_input` →
`_persist_quick_visualizer_view` (paused at its closing `logger.info`), all long returned. `gui_stall_stacks.log` had
sampled the GUI thread inside that very orbit-finish emit (21:37:20). Both preserved timeout runs ran with
`--gui-stall-stacks`.

## Cause

`sys._current_frames()` returns a dict that also holds the sampler thread's own running `_describe` frame, whose
local `frames` is that dict: a reference cycle. The cycle keeps every sampled frame object, and through `f_back`
each caller frame and its locals, alive until a gen2 collection, which the RUN GC policy runs about once a session.
A sampled frame that held the display unit or visualizer owner pinned the retiring generation. Reproduced in
isolation on Python 3.14.8 (the locals survive refcount release; `gc.collect()` frees them).

## Fix and proof

`_describe` pops its own thread's entry before formatting, so nothing references the map after return.
`tests/test_gui_stall_sampler.py::test_a_sampled_stall_never_pins_the_gui_threads_locals` (real sampler, cyclic GC
disabled, R-154's refcount-only standard) fails without the fix and passes with it.

## Lesson

Any diagnostic that takes frame objects (`sys._current_frames`, `_getframe`, tracebacks) must not let them reach a
cycle: they pin whole call chains, including product owners, for as long as the cycle lives. Not seen yet: a timeout
in a run without `--gui-stall-stacks`; if one appears, its snapshot names a different holder.

## Different Settings-open failure, 28 October

`F:/Programming/Apps/logs0e66768ed8.zip` is not another retention timeout: lifecycle line 2064 records the
Settings barrier completing in 516 ms. Main log lines 392–414 instead report `ImportError: cannot import name
'Gradient'` while lazily importing Settings. The saver had loaded the earlier settings module before the source
UI integration changed on disk. This mixed-source process exited through `settings_dialog_failed`; its cached
module cannot acquire a newly added type merely because the file changed. The coherent committed source opens
the native Settings dialog in a fresh isolated process. No GC sweep, barrier relaxation, hot reload or import
fallback is warranted by this evidence. Avoid interdependent source edits against a running development saver;
validate a fresh process at the completed checkpoint.
