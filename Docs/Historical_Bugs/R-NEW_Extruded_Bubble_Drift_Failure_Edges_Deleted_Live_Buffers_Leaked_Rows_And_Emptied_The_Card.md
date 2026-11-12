# R-NEW | Extruded Bubble's drift failure edges deleted live buffers, leaked rows and emptied the card

**Status:** fixed 12 Nov 2026 (Current_Plan item 8b, "D3 now, in the OpenGL renderer" and N1's drift program box;
contract D3 in `Docs/Future_Work/Native_Core_P3_Decisions.md`, "Residency and release"). Regression bars in
`tests/test_extruded_bubble_drift_solver.py` (failed allocation, dispatch raise at a geometry edit, a carried history
whose target allocation fails, a handoff whose fence wait fails, a drift output that cannot be allocated),
`tests/test_extruded_bubble_drift_gpu.py::test_a_drift_program_that_fails_to_compile_is_logged_once_and_the_mode_draws_without_drift`
and `tests/test_scene3d_resources.py::test_a_program_that_fails_to_compile_is_cached_logged_once_and_settles_the_warm_up`;
each red on the code before its fix.

## Symptom

None reported: every edge needs a GL failure (an allocation the driver refuses, a raise inside a dispatch) or a device
whose compiler refuses a drift program. On such a machine: drift drawn from deleted (or recycled) buffer names after a
failed allocation, GPU memory leaked at each failed geometry edit, and with a refused drift program an empty Extruded
Bubble card for the whole run while the program was compiled again on every drifting frame.

## Cause

`DriftSolver._advance` released a family's old buffers before `_allocate` made the new ones; `_allocate` can raise
(a geometry/capacity mismatch, a GL error), which left `_families` holding deleted names (the next frame dispatched and
drew from them) and, since the error escaped the frame, retried the same allocation on every frame. At a geometry edit
the old rows were deleted after the continuing dispatch, so a raise inside it skipped the delete and leaked them. The
drift output buffer had the same delete-before-allocate order. `MeshResources.compute_program` cached only successes:
a failed compile raised out of the warm-up (which then never completed) and out of every drifting frame, recompiling
each time, and the frame drew nothing. All of this was silent in the sense that matters: nothing told a user, and the
logs showed at most a repeated compile error.

## Fix

A family's new state is allocated before the old is released (`DriftSolver._replace`); a failure leaves the current
state current and drawn, is logged once and its (revision, capacity) is not tried again (a new key is); partial
allocations release what they made; the output is allocated first too. The geometry edit releases the old rows in a
`finally`. The display-move handoff (1C.2) keeps the same contract: a failed fence wait releases the carried history
exactly once and keeps the target's own, and failed keys travel with the history. `MeshResources` caches a failed
program (`ProgramUnavailable`, one error per program and context, cleared at release), `warm_programs` treats it as
settled, and the drift solver asks for both drift programs before it allocates anything: unavailable, it has no
output and Extruded Bubble draws without drift.

## Lesson

A replacement allocates before it releases, on every edge, and a failure edge is cached by key at its owner: never
an exception left to escape a frame, which turns one failure into a per-frame retry and an empty picture.
