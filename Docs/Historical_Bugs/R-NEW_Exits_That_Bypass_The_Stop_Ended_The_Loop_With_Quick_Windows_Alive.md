# R-NEW | The exits that bypass the terminal stop ended the loop with their Quick windows alive

**Status:** fixed 14 Nov 2026 (Current_Plan item 8b, N2.7 leftovers, "Exits that bypass the stop"). The routes are
old; they crash only since N2.7 made Vulkan a product backend (`--graphics-backend=vulkan`, 14 Nov 2026). Owner:
`engine/runtime_destruction.py` (`release_quick_windows_then`, `exit_application_after_quick_release`) and
`engine/engine_lifecycle.py` (`stop`). Regression bars: `tests/test_quick_exit_routes.py` (one child process per
route on the native core's Vulkan device; each route's `bare` variant, the code before the fix, crashes) and
`tests/test_terminal_runtime_destruction.py::test_a_second_exiting_stop_during_the_terminal_drain_leaves_the_drain_to_quit`
(failed on the code before the fix). Precedent: R-207. Evidence: `.artifacts/evidence/native_core/n27_leftovers/20261114_exits/`.

## Symptom

On Vulkan, each of these routes ended the process with 0xC0000005 at interpreter exit. The window was still alive and
its native host was still open when `app.exec()` returned (hidden runs, one real `QuickDisplayRuntime`):

| Route | Before | After |
| --- | --- | --- |
| Replacement barrier timeout, window retirement stuck | exec 1, window alive, 0xC0000005 | exec 1, window gone, exit 0 |
| Replacement barrier timeout, a Python owner pinned (window already gone) | exec 1, exit 0 | unchanged |
| Settings teardown failed (`_exit_after_lifecycle_failure`) | exec 1, 0xC0000005 | exec 1, exit 0 |
| CUSTOM reload teardown failed | exec 1, 0xC0000005 | exec 1, exit 0 |
| Monitor-topology teardown failed | exec 1, 0xC0000005 | exec 1, exit 0 |
| Replacement continuation raised (a replacement with its window built) | exec 1, 0xC0000005 | exec 1, exit 0 |
| Terminal barrier timeout (its finalization quits) | exec 0, 0xC0000005 | exec 0, exit 0 |
| A second exiting stop during the terminal drain | exec 0, 0xC0000005 | exec 0, exit 0 |

On OpenGL the same routes exited without a crash.

## Cause

R-207 made every exiting stop wait for its terminal barrier before the quit. The failing routes never reach that
stop. They called `QCoreApplication.exit(1)` at once, and the terminal barrier's timeout ran its finalization's quit
at once. The loop ended with the generation's windows still alive, and on Vulkan a window that is alive at interpreter
exit crashes the process. A barrier timeout cannot wait on its own barrier, because the barrier is what failed.

A second exiting stop, for example the tray's Exit while `--exit-after`'s stop drained, treated the pending terminal
barrier like a replacement one. It cancelled the barrier, which dropped the quit continuation, and then finalized at
once. That quit ran before the windows retired.

## Fix

- One authority, `release_quick_windows_then(reason, continuation)`. It finds every live `QuickDisplayWindow`, queues
  its close (`queue_close`) and requests its deletion. The continuation runs from the last window's `destroyed`, with
  no timer and no wait on a barrier. With no windows alive, the continuation runs at once.
- `exit_application_after_quick_release(code, reason, engine=)` uses that authority to end the loop with `code`. It
  also marks the engine terminal so that no replacement starts while the windows go. Every former bare exit goes
  through it: the replacement barrier timeout, a failed replacement continuation, the Settings teardown failure, the
  Settings callback cancellation failure, the CUSTOM failure and the monitor failure.
- The terminal barrier's timeout releases the windows before it runs its finalization.
- `stop()` ignores an exiting stop while a terminal barrier is still draining (`RuntimeDestructionBarrier.is_terminal`).
  The first stop's drain then quits.

## Why it hid

- OpenGL tolerates a live Quick window at exit, and these routes run only when something else has already failed.
- R-207's fix and its tests covered the stops. The failure exits never pass through a stop.

## Lessons

1. Every way the loop can end must retire the windows first, not only the normal exit path. When an exit cannot
   wait on a barrier, it waits on the windows' own `destroyed` events.
2. A second request for the same terminal action must join the action that is already running, never cancel it.
