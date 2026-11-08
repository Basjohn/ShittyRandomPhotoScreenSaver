# R-178 | The engine-worker owner's layout-metrics observer kept it alive: every Settings barrier timed out and the saver exited

**Status:** fixed 8 Nov 2026 (`e713dd74`): `QuickDisplayVisualizerOwner.retire()` sets its controller's
layout-metrics observer to None with the other early detaches. Regression bar:
`tests/test_visualizer_owner_engine_worker.py::test_a_retired_owner_leaves_no_callback_of_its_own_on_its_controller`
(failed on the parent commit `d9ee61f1` with `['_layout_metrics_observer']`). Found by native core P2 gate 4's first
live run (`Docs/Future_Work/Native_Core_P2_Engine_Design.md`, "Gate 4 record"). Only the engine-worker path
(`--viz-engine-worker`, default off since its introduction the same day) was affected.

## Symptom

The invisible live check with the engine worker admitted (`tools/visualizer_live_check.py --mode spectrum --preset 1
--settings-roundtrip 30,52 --app-arg=--viz-engine-worker`): the first Settings round trip never reached its dialog.
The `settings` destruction barrier timed out after 8,273 ms, the engine fell back to its event-loop exit backstop and
the saver exited with code 1. The same run with the admission off completed both round trips (barriers 423 / 427 ms).
Any display reload under the admission (Settings, a CUSTOM layout commit, a monitor topology change) goes through the
same barrier.

The barrier's own diagnostics named it: `python_owners={'QuickDisplayVisualizerOwner': 1}` still alive, one referrer,
a bound method `QuickDisplayVisualizerOwner._on_layout_metrics_written`.

## Cause

On the worker path the owner forwards the controller's layout metrics to the session (`VIS_SET_VIEW`), so
`_adopt_engine_worker_session` installs `controller.set_layout_metrics_observer(self._on_layout_metrics_written)` (work
order 5 slice 5.2). The owner holds the controller, so owner -> controller -> bound method -> owner is a reference
cycle. The destruction barrier judges a retiring generation's Python owners by reference counting (R-53/R-154; R-175
collects the cycles only after the barrier, in the replacement's continuation), and the RUN GC thresholds practically
never run a deep collection, so the owner never read as released. `retire()` already severed every other owner link
(the wake, the sync admission, the viewport sink, the presentation image listener, the runtime references) for exactly
this reason; this one was added later on the worker path only. The in-process fallback cleared it; retirement did not.

## Why nothing caught it

Every worker-path test drives the owner through the `owner_worker_gate` rig, whose teardown is an `ExitStack`, not the
engine's destruction barrier; the engine replacement suites (Settings round trips, display selection, S hotkey) run
the in-process owner or stand-ins. No test retired the real owner on the worker through the real barrier until the
live check could run the saver with the admission (gate 4 added `--app-arg`).

## Proof

- Before: the barrier timeout and exit above (evidence `smoke_on` was overwritten by the after-run; the first run's log
  lines are quoted here).
- After: the same command completes both round trips (barriers 456 / 426 ms, dialogs 1,499 / 1,501 ms, re-frozen),
  and gate 4's 20-round-trip run completes all 20 with the admission on (`settings` barriers 404-484 ms, every reveal
  re-frozen, the worker retired at each Settings open and respawned at its close; Gate 4 record).
- The test asserts the worker path installs an owner callback on the controller (so it cannot pass vacuously) and that
  none is left after `retire()`.

## Lesson

A callback an owner installs on an object it owns is a cycle; on a generation-scoped owner every such install needs
its removal in `retire()`, next to the others, whichever path installed it. Rig teardown is not the destruction
barrier: a lifecycle path is proven only through the engine's own barrier (the live check's `--settings-roundtrip`).

## Evidence

`.artifacts/evidence/architecture/native_core_p2/20261108_gate4_dormancy/` (`smoke_on`, `smoke_off`,
`settings20_flag_on`).
