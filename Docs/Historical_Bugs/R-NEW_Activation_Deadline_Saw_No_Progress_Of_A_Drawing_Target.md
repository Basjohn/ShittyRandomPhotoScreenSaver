# R-NEW | The activation deadline saw no progress of a target that was drawing, so slow runs reloaded a live switch

**Status:** fixed 14 Nov 2026 (Current_Plan N2.5 leftovers, the two side-defect boxes). The owner's slow-but-alive
read counts the target's frames as well as its preparation units. Regression bars: `tests/test_visualizer_prepared_reveal.py`
(a worker target publishing before its commit reply, a bound target whose admitted frames advance, the outgoing
activation's frames as the control; the first two red on the pre-fix owner) and
`tests/test_visualizer_owner_render_parity.py::test_a_drawn_run_does_not_depend_on_the_wall_time_it_takes` (red on
the pre-fix owner: `deadline:fading_in` and every later frame moved).

## Symptom

`test_visualizer_owner_render_parity[devcurve]` failed once under concurrent load with `deadline:waiting_target` for
Neon Lake on the worker path and passed 7 of 7 runs after. Rule (a)'s parity run (`owner_render_parity --native`)
slowed by 30 ms a frame failed the same way in process, at input 497 of 549, and every frame from there moved on both
paths, so two runs of one commit were hash-identical only when the machine was idle.

## Cause

`QuickDisplayVisualizerOwner._on_transition_deadline` is a 6 s wall-clock single-shot (`_ACTIVATION_TRANSACTION_
DEADLINE_MS`); since R-180 it is extended (at most `_SLOW_TARGET_DEADLINE_EXTENSIONS` times) only when
`_target_preparation_progress` advanced: the preparation units the owner's own scene item reports. That read is 0 on
the worker until the commit's reply arrives (the session has already applied the commit and is drawing the target), and
0 for a target whose scene has not drawn (in the replay rigs the owner's own scene is unshown; the drawn scene is the
mirror's). The target's reveal meanwhile runs on the owner's transition clock (the prepared-reveal bound, 1.5 s), so a
run whose wall time outpaced its clock (load, a busy GUI) failed a target that was publishing every frame.

## Fix and evidence

`_slow_target_alive` takes the target's progress as (preparation units, newest frame revision): before the worker's
reply the session's newest frame when it is the target mode's and not the outgoing activation's
(`logical_mailbox.peek()`), after the commit the render bridge's newest admitted revision for the bound identity
(`VisualizerSnapshotBridge.last_revision`, new). Either advancing extends the deadline; the bound on extensions and the
failure of a silent target are unchanged. Evidence `.artifacts/evidence/native_core/n2_5_leftovers/`.

## Lesson

A liveness bound must read the progress edges of the thing it bounds, from the place that progresses: the engine's
frames of the target, not only one renderer's report from one scene.
