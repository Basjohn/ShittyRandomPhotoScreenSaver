---
[SOLVED!]

# Hangingplan: Strict ThreadManager & RSS Shutdown Compliance

> **Zero tolerance:** Any deviation from ThreadManager / ResourceManager policy, ThreadPoolExecutor hacks, or RSS shutdown hygiene is considered a regression. Every step below must be executed exactly as written.

## Objective
Guarantee clean exit without `taskkill` by:
1. **Thread discipline** – single engine-owned ThreadManager, no hacks (DONE)
2. **RSS hygiene** – downloads abort instantly, cache stays intact (DONE)
3. **Transition shutdown** – adaptive render timers + GL transitions must collapse immediately when exit begins (NEW FOCUS)

All fixes must preserve hybrid adaptive timers, lock-free queues, and ResourceManager ownership.

## Policies That May *Never* Be Violated
1. **Centralized managers only** – ThreadManager, ResourceManager, EventSystem, SettingsManager, AnimationManager. No ad-hoc managers, no singletons hidden inside widgets.
2. **No ThreadPoolExecutor hacks** – Never swap executors, never mutate daemon flags, never touch private `_threads`. Shutdown must rely on documented APIs only.
3. **No raw threads for business logic** – `threading.Thread`, `ThreadPoolExecutor`, `asyncio`, etc., are forbidden unless explicitly allowed for a minimal daemon helper with documented cleanup.
4. **SRPSS_PERF_METRICS gating** – All instrumentation must use `is_perf_metrics_enabled()`.
5. **RSS integrity** – Downloads must abort the instant `_shutting_down` flips true; partially written files must be discarded before cache insert.

## Live Plan (All steps mandatory)
1. **Reproduction baseline** — `[x]`
   - *Done 2026-02-01:* Verified clean exit occurs when no transitions run.
   - Insight: exit hang only reproduces once any GL/software transition (adaptive timer active) runs.

2. **Instrument adaptive timer + transitions** — `[x]`
   - *Done 2026-02-01:* Added `describe_state()` methods to `AdaptiveTimerStrategy`, `AdaptiveRenderStrategyManager`, `TransitionController`, `GLCompositorWidget`, and `DisplayWidget`.
   - Added perf-gated logging in `AdaptiveRenderStrategyManager.stop/pause/resume` and `GLCompositorWidget.stop_rendering`.
   - Added `FrameState.describe()` for frame interpolation state capture.
   - Added `ScreensaverEngine.stop()` instrumentation to aggregate display states pre-shutdown.
   - All logs gated behind `SRPSS_PERF_METRICS` as per policy.

3. **Guarantee render timers halt immediately** — `[x]`
   - *Done 2026-02-01:* Added `DisplayWidget.shutdown_render_pipeline()` to synchronously stop transitions and render timers.
   - `DisplayManager.cleanup()` now calls `shutdown_render_pipeline("cleanup")` for each display before `clear()`.
   - `GLCompositorWidget.stop_rendering()` invokes `_stop_frame_pacing()` and `_stop_render_strategy()` with perf logging.
   - No destructor reliance; all stops are explicit and synchronous.

4. **Force transitions to complete/cancel on exit** — `[x]`
   - *Done 2026-02-01:* Enhanced `TransitionController.stop_current()` with `reason` parameter and perf-gated instrumentation.
   - Added `AnimationManager.cancel_all()` call during transition stop with logging.
   - Added `get_current_animation_info()` to `GLCompositorWidget` for tracking `_current_anim_id` during shutdown.
   - Updated `DisplayWidget.shutdown_render_pipeline()` to pass reason to `stop_current()`.

5. **Quiesce adaptive timers without regressing performance** — `[x]`
   - *Done 2026-02-01:* Added `exit_immediate` flag to `AdaptiveTimerConfig` for fast-path shutdown.
   - `AdaptiveTimerStrategy.stop()` checks `exit_immediate` and skips thread wait when set.
   - `AdaptiveRenderStrategyManager.stop()` sets `exit_immediate=True` before calling timer stop.
   - No performance regression during normal operation; fast-path only activates during shutdown.

6. **Regression tests & verification loop** — `[x]`
   - *Done 2026-02-01:* Ran `$env:SRPSS_PERF_METRICS='1'; python main.py` with transitions.
   - Logs show `exit_immediate=True` in all adaptive timer configs during shutdown.
   - `shutdown_render_pipeline` called with reasons "cleanup" and "clear".
   - `stop_rendering` invoked with reasons "display:cleanup" and "display:clear".
   - AnimationManager and ImageCache metrics logged successfully.
   - Workers exited normally; no hangs observed.

## Deliverables
- Updated code for ThreadManager and RSS pipeline per steps above.
- Updated tests (unit or integration) proving RSS abort behavior.
- This plan checked off with concrete log excerpts showing compliance.

## Latest Observations (Feb 1, 2026 16:18)
- Application exits cleanly with all instrumentation firing correctly.
- `exit_immediate=True` propagates through adaptive timer configs during shutdown.
- All render pipelines stop with documented reasons: "cleanup", "clear", "display:cleanup", "display:clear".
- AnimationManager cancels and ImageCache metrics log properly.
- Workers (IMAGE, FFT) exit normally without hangs.

## Known Issues (Pending)
- `transitions/overlay_manager.py:schedule_raise_when_ready()` uses static `ThreadManager.single_shot()` calls (lines 402, 404). This should be refactored to accept injected ThreadManager but is lower priority as it's not blocking shutdown (short timeouts).

## Forbidden Shortcuts
- No daemon-thread tweaks, no private attribute mutation.
- No suppression of errors instead of fixing the root cause.
- No TODOs in place of actual shutdown handling.

## Status Tracking (start unchecked)
- [x] Executor revert + cleanup handler
- [x] Shutdown logging & instrumentation
- [x] Dependency injection enforcement
- [x] RSS abort safeguards & cache integrity
- [x] Threading audit write-up
- [x] Transition hang reproduction baseline logged
- [x] Transition instrumentation added
- [x] Render timers halt instantly on shutdown
- [x] Transitions cancelled & GL compositors quiesced (via shutdown_render_pipeline)
- [x] Adaptive timer exit fast-path implemented
- [x] Clean-exit validation run (logs attached)

## Key Constraints to Maintain
- Hybrid adaptive timer, lock-free SPSC queues, and ResourceManager lifecycles stay intact.
- Single ThreadManager per engine instance; all consumers reuse it via DI.
- ResourceManager remains the sole owner of timers/executors for cleanup.
- RSS cache never contains partially downloaded files.

---
