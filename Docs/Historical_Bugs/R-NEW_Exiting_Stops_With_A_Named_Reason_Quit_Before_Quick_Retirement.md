# R-NEW | An exiting stop with any reason but "application_exit" quit before its Quick windows retired

**Status:** fixed 14 Nov 2026 (Current_Plan item 8b, N2.7 leftovers, "Exit on Vulkan"). Present since `--exit-after`
gave its stop a reason (854df59b, 6 Oct 2026; the keying itself is H1b's, 47934cdf, 30 Aug 2026) and, for the failed
start's `no_display_shown`, since 2c6ceaee (7 Nov 2026). Owner: `engine/engine_lifecycle.py`
(`teardown_display_runtime`, `stop`). Regression bars: `tests/test_terminal_runtime_destruction.py::
test_every_exiting_stop_waits_for_its_quick_roots_before_the_quit` and `tests/test_quick_backend_owner.py::
test_an_exiting_stop_releases_the_vulkan_window_and_the_process_exits_cleanly`, both failing on the code before the
fix. Evidence: `.artifacts/evidence/native_core/n27_leftovers/20261114_exit/`.

## Symptom

The lead's first product run on Vulkan (14 Nov, `d1_run.py --app-arg=--graphics-backend=vulkan`) exited with
0xC0000005 at `--exit-after`. The log showed the terminal barrier armed and the application's quit requested in the
same millisecond: the loop ended with the Quick window still alive, and the process crashed during interpreter exit.
On OpenGL the same runs exited 0 with the same early quit.

## Cause

`teardown_display_runtime` armed the terminal-purpose destruction barrier (H1b: the quit waits until the retiring
generation's Quick roots are destroyed) only when the stop's reason was the string `"application_exit"`, the default
of an exiting `stop()`. An exiting stop given its own reason (`--exit-after`'s `"cli_exit_after"`, the failed start's
`"no_display_shown"`) armed a replacement-purpose barrier instead. A replacement barrier cancels itself when terminal
shutdown is requested (it must never admit a replacement), so `stop()` found it complete and finalized at once: worker
shutdown and `QCoreApplication.quit()` ran while the window's retirement was still queued. A live Vulkan window at
interpreter exit crashes the process (a real `QuickDisplayRuntime` closed and quit at once: exit 139; quit after its
window was destroyed: exit 0).

## Fix

The barrier's purpose follows the stop, not its reason: `stop()` passes `terminal=exit_app` to
`teardown_display_runtime`, which arms the terminal barrier for every exiting stop. `--exit-after` and a failed start
now wait for the Quick retirement (about 0.4 s in the hidden runs) before the quit, on both backends.

## Why it hid

- OpenGL tolerated a live Quick window at interpreter exit, so every `--exit-after` run (d1_run, the live checks)
  exited 0 and looked like a clean terminal stop.
- The barrier's own log line ("armed") was written either way; only the absence of "Terminal shutdown deferred" and
  of "barrier complete" before the quit showed it.

## Lessons

1. A lifecycle decision keyed on a free-text reason breaks when a caller names its reason. Key it on the fact
   (`exit_app`), and keep reasons for logs.
2. An exit that is clean on one backend is not proof of a clean teardown order: read the order in the log.
