# R-185 | A worker being torn down still read as running, so a crashed engine worker turned the worker off for the run

**Status:** fixed 11 Nov 2026 (native-core lane, found while working the phase-boundary audit's L4). The supervisor
reads a worker's exit status as well as its process handle (`core/process/supervisor.py: process_has_exited`).
Regression bars: `tests/test_visualizer_ordered_control_delivery.py`
(`test_a_worker_being_torn_down_is_not_running_and_a_send_to_it_never_raises`, with its negative control, and
`test_a_send_whose_target_dies_during_the_handle_transfer_is_not_running_not_an_error`) and the existing real-process
test `tests/test_visualizer_owner_engine_worker_liveness.py::test_a_killed_worker_is_seen_by_its_pipe_end_and_the_owner_recovers_on_a_fresh_worker`,
which failed in 3 of 3 runs before this fix, with the traceback below (the synchronous handle transfer of `9c1bd9b3`,
9 Nov 2026; that commit itself was not re-run). Silent in the product: the Visualizer kept running, in process, and
only the log said why.

## Symptom

The engine worker's process dies (a crash, a kill). The owner fades out, tries its one reconfigure and logs:

```
Ordered control serialization refused before queue admission ... PermissionError: [WinError 5] Access is denied
vis_configure could not be sent: [WinError 5] Access is denied
[ENGINE_WORKER] Off for the rest of the run: second failure: vis_configure: the request could not be sent
```

The contract (design doc, slice 5.5) is one recovery onto a fresh worker. Instead a single worker death cost the run
its worker path: the tick was back on the GUI process's GIL until the next start.

## Cause

1. **`Process.is_alive()` is late on Windows.** It waits on the process handle, which the kernel signals only when
   teardown has finished. The handle table is closed first. Measured on a killed child
   (`.artifacts/evidence/native_core/20261111_dying_worker_window/teardown_window.txt`): the exit status is set within
   0.1 ms, `DuplicateHandle` into the process is refused (access denied) from about 1.4 ms, and `is_alive()` stays True
   until 4.9 ms (50 MB child), 13 ms (300 MB) or 34 ms (800 MB).
2. **The owner reacts inside that window.** The session's wake pipe ends when the handle table goes, the listener
   thread queues the owner's failure event, and the owner's reconfigure asks `ProcessSupervisor.is_running`: True. So
   the replacement's `VIS_CONFIGURE` is sent to the dying process instead of waiting for a fresh one.
3. **Since `9c1bd9b3` the send duplicates the wake handle into the target at once** (`control_messages.EncodedControl`,
   audit L1: ordered controls are serialised before queue admission). Into a dying process that raises, the link
   reports "could not be sent", and that is a failure: the second one. Before `9c1bd9b3` the same send sat in the queue
   of the dead process until the heartbeat retired it, which cancels the correlation, and the link's
   `_respawn_unconfigured` sent it again to a restarted worker. The window was always there; the synchronous transfer
   turned it from a detour into a failure.

## Fix

- `process_has_exited(process)`: not alive, or (Windows) an exit status other than `STILL_ACTIVE`. The exit status is
  set when termination begins, before the handles go, so by the time the owner can see the pipe end the role already
  reads as gone.
- Used wherever the supervisor asks whether a role's process is there: `is_running`, `send_message`, `_start_role`,
  `_retire_dead_role` and the heartbeat's judgement. The link then takes its ordinary start path (`_ensure_worker` ->
  `supervisor.start`), which retires the dead role first. `_retire_dead_role` waits for the teardown to finish (on the
  role's lifecycle lock, an IO task, never the GUI thread or the state lock), so the dead process's handle is closed
  with the role.
- `send_message` answers None, as documented for a worker that is not running, when the target dies between its check
  and the handle transfer. An `OSError` from a live target still propagates.
- `control_messages.py` (the Windows child-owned duplication) is unchanged.

## Why it hid

- The real-process test that covers it was red, but nobody ran that file after `9c1bd9b3`: the L1 slice ran the new
  ordered-control tests and the supervisor tests, and the kill test lives with the owner's liveness tests.
- The product outcome is a contained fallback, which is itself a designed path: nothing vanishes, nothing crashes.

## Lessons

1. On Windows "alive" by the process handle lags "dead" by tens of milliseconds, and event-driven code arrives inside
   that gap. Ask for the exit status when the question is "can I still hand this process anything".
2. Moving work from a queue's feeder to the caller turns every asynchronous detour through that queue into a
   synchronous outcome. Re-run the tests of the failure paths that relied on the detour (here: every test that kills or
   hangs a worker), not only the tests of the new path.
