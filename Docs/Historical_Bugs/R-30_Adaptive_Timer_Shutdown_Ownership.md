# R-30 — 2026-07-01 — Adaptive Timer Ownership Drop Left Python Process Alive After App Exit (Resolved In Code, Runtime Validation Pending)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [x] AWAITING VALIDATION
- [ ] SOLVED

- **Observed failure pattern:** a run reached `ShittyRandomPhotoScreenSaver Exiting (code=0)`, but the terminal never returned to the command prompt until Python was manually killed.
- **Evidence:** the same exit window logged `Cancelling 2 active tasks before shutdown`, then `ThreadManager shutdown timed out after 5.0s with 1 active tasks: ['adaptive_timer_1952220335120']`, followed by `Pool compute has 2 pending tasks during shutdown`. That timer was started at `10:09:34`, while later settings/display rebuilds had already started newer adaptive timers, making it an orphaned earlier display-generation task.
- **Root cause:** adaptive timer stop ownership was not a real loop-completion handshake. `AdaptiveRenderStrategyManager.stop()` forced `exit_immediate`, and `AdaptiveTimerStrategy.stop()` cleared local task ownership without waiting for `_timer_loop()` to exit. A second ThreadManager race could also register a very fast task as active after it had already completed.
- **Fix:** adaptive timers now own a loop-stopped event that is cleared on start, set from `_timer_loop()` in a `finally` block, and awaited briefly during stop before ownership is dropped. Render-strategy manager stop no longer forces the old immediate-drop path. `ThreadManager.submit_task()` now registers active-task truth before submitting to the executor and unregisters if submit fails.
- **Bars:** `tests/test_adaptive_timer.py` proves render-strategy stop waits for loop completion and leaves no mock timer thread alive. `tests/test_thread_manager.py` uses a synchronous executor to prove instant task completion cannot leave stale active-task bookkeeping.
- **Runtime validation target:** the next exit should show no `ThreadManager shutdown timed out`, no pending `adaptive_timer_*` task at shutdown, and no `[PERF][ADAPTIVE_TIMER][FALLBACK] Stop timed out before loop acknowledged shutdown...` warning. If that fallback fires, the next root cause is whichever display/compositor cleanup path still blocks the timer loop from acknowledging stop.

## Record Provenance

This standalone file preserves the complete former inline `R-30` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.
