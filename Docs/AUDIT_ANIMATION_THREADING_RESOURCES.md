# Animation, Threading, and Resource Systems Audit

Status: Draft (live checklist)

This document reviews the current systems (AnimationManager, ThreadManager, ResourceManager, Display/Transitions) and lists targeted optimizations and cleanup opportunities. Optimizations must not reduce visual fidelity or reliability.

---

## Live Checklist

- [ ] Add unit tests for AnimationManager cadence changes (set_target_fps) and progress stability
- [ ] Register AnimationManager timer with ResourceManager for lifecycle tracking
- [ ] Validate all QTimers are tracked by ResourceManager (PanAndScan done)
- [ ] Ensure all Qt widgets created by transitions are cleaned via deleteLater and not set to None prematurely
- [ ] Add optional SW caps (documented) to avoid CPU spikes on SW transitions (leave default uncapped)
- [ ] Verify per-display target FPS reconfig at runtime when screen changes (manual test plan)
- [ ] Review GL overlay persistent widgets for deletion order and leak risk
- [ ] Confirm no background threads modify Qt widgets without UI-thread invocation
- [ ] Add watchdog logging around prewarm to detect stalls > 250ms per overlay
- [ ] Add CI-safe offscreen configuration guidance for GUI tests
- [ ] When Pan and Scan is enabled transitions should use the PanAndScanAnimator/Zoomlevel as the goal point of the transition to avoid jumps/zooms/flickers.
- [ ] When starting screensaver with Diffuse enabled there is init flicker. This ONLY happens with Diffuse enabled. Try to carefully analyze the cause of this and resolve said flicker.
---

## Findings

- Animation timing is centralized via AnimationManager with per-widget instances, wall-clock based updates, and easing.
- PanAndScan uses its own QTimer with DPR-safe image scaling; timer is registered with ResourceManager.
- Prewarm uses persistent overlay widgets to avoid first-use GL flicker; overlays are kept hidden and reused.
- Threading policy is adhered to for business logic; transitions and UI work execute on UI thread.

---

## Optimizations (no fidelity loss)

1. Animation cadence configuration
   - Add `set_target_fps` (done) for runtime cadence changes without restarting animations.
   - Consider a per-display AnimationManager shared among transitions on that display to reduce timer count.
     - [ ] Prototype behind a feature flag; measure timer wakeups and CPU usage.

2. Timer lifecycle tracking
   - AnimationManager uses a QTimer; not currently tracked by ResourceManager.
     - [ ] Register the timer with ResourceManager and verify deterministic cleanup.

3. Transition allocations
   - Slide and Wipe pre-fit pixmaps to widget size to avoid per-frame scaling and reduce allocations.
     - [ ] Audit other SW transitions for pre-fit consistency.

4. Logging and diagnostics
   - Add prewarm stall logging if an overlay is not ready within 250ms (best-effort without spamming logs).
     - [ ] Implement optional verbose logging flag for prewarm diagnostics.

5. Settings schema and caps
   - Support optional caps for SW transitions and PanAndScan max FPS to protect CPU on high-Hz panels.
     - [ ] Document the keys and defaults in Spec.md and Settings UI (future work).

---

## Potential Leak/Cleanup Risks

- Deleting timers and widgets:
  - Ensure `deleteLater()` is used and not immediately setting variables to None in a way that loses reference tracking.
- Persistent GL overlays:
  - Verify overlays are cleaned on DisplayWidget destruction and do not cross-reference parents after deletion.
    - [ ] Add a cleanup path when the display widget is closed.

---

## Threading Audit

- Business logic threading goes through ThreadManager; transitions avoid creating threads.
- UI updates occur on UI thread; transitions move QLabel positions or masks only from AnimationManager callbacks (UI context).
- No raw QThread usage detected in transitions.

---

## Test Coverage Gaps

- Lacks tests around prewarm behavior; created a deadlock safety test (offscreen GUI backend, fake GL overlay modules).
- Missing tests for `set_target_fps` correctness and continuity while animations are running.
  - [ ] Add unit tests with a small custom animation and assert update cadence changes mid-run.

---

## Recommendations Summary

- Short term (low risk):
  - Register AnimationManager timer with ResourceManager.
  - Keep per-widget AnimationManager but add monitoring (active timers count).
  - Maintain SW Diffuse in HW mode to avoid GL instability.

- Medium term (guarded by flag):
  - Explore per-display AnimationManager singleton to decrease timer count and improve sync.

- Long term:
  - Broaden test suite for cadence, prewarm stability, and screen-change reconfiguration.
