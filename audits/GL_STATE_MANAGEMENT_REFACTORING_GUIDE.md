# GL State Management Refactoring Guide (2026 Alignment)

_Role_: supplemental deep dive for **Phase 3 – GL Compositor & Transition Reliability** from `audits/ARCHITECTURE_AND_MULTIPROCESSING_PLAN_2026.md`. Use this when acting on GL-specific items; the consolidated plan remains the single source of truth for priorities, guardrails, and sequencing.

---

## 1. Purpose
- Keep GL lifecycle semantics consistent across compositor, overlays, and shader programs.
- Guarantee session-wide fallback behaviour (Group A→B→C) without per-transition hacks.
- Provide actionable checkpoints tied directly to current modules (`rendering/gl_compositor.py`, `widgets/spotify_bars_gl_overlay.py`, `rendering/gl_programs/*`, `transitions/*`).

---

## 2. Alignment With 2026 Execution Plan

| Consolidated Plan Phase | This Guide Covers | Key References |
| --- | --- | --- |
| Phase 0 | Thread safety groundwork (locking, watchdog logging) | `Spec.md` thread policy @Spec.md#270-312 |
| Phase 3 | GLStateManager rollout, compositor/overlay parity, watchdog + telemetry | `Spec.md` transitions @Spec.md#109-157, Index GL sections @Index.md#124-248 |
| Phase 5 | Tests, documentation, PERF baselines | `Docs/PERFORMANCE_BASELINE.md`, `Docs/TestSuite.md` |

---

## 3. Current Implementation Snapshot (Dec 2025)

- `rendering/gl_state_manager.py` already provides `GLStateManager`, transition validation, callbacks, and tests (`tests/test_gl_state_manager.py`).
- `GLCompositorWidget` uses `GLStateManager` for its own lifecycle but **SpotifyBarsGLOverlay** and legacy GL overlays still rely on ad‑hoc booleans (`_gl_initialized`, `_first_frame_drawn`, `_gl_disabled`).
- Transition watchdogs exist in `rendering/transition_controller.py` but aren’t yet wired to the state manager history/logs.
- `GLErrorHandler` manages capability demotion but lacks detailed context when an overlay triggers the downgrade.

**Goal:** extend the proven GLStateManager pattern across every GL consumer and wire telemetry/fallback flows into the consolidated plan’s Phase 3 checklist.

---

## 4. Action Plan

### 4.1 GLStateManager Coverage
1. **SpotifyBarsGLOverlay** (`widgets/spotify_bars_gl_overlay.py`)
   - Instantiate GLStateManager.
   - Mirror compositor lifecycle: `initializeGL` → INITIALIZING/READY, detect `paintGL` while not READY, transition to ERROR/CONTEXT_LOST when GL disables itself.
   - Reuse `_gl_initialized/_first_frame_drawn` booleans only as derived fields guarded by the manager.
2. **Legacy GL Overlays** (`transitions/*_gl_overlay.py` if any remain)
   - Either migrate to compositor-backed transitions or wrap state via GLStateManager when direct QOpenGLWidget usage is unavoidable.
3. **Shared Telemetry**
   - Every state change logs `[GL STATE] <component> old→new` and surfaces through `GLErrorHandler` so demotion decisions have per-component provenance.

### 4.2 Transition Controller Integration
- Ensure `rendering/transition_controller.py` or `GLCompositorWidget` always calls `self._state_manager.transition(..., snap_to_new=True)` during cleanup so widgets raise synchronously per overlay policy @Spec.md#288-354.
- Tie watchdog start/stop to GL state transitions so dt spikes can be correlated with state churn in `screensaver_perf.log`.

### 4.3 Recovery & Fallback
- `GLErrorHandler` should subscribe to GLStateManager callbacks (READY→CONTEXT_LOST/ERROR) and execute the session-level demotion (A→B→C) described in Spec; avoid per-transition fallbacks.
- When a Spotify overlay fails, propagate the demotion to the main compositor so transitions don’t continue requesting shaders after the overlay disabled GL.

---

## 5. Targeted Checklist (Use alongside consolidated master checklist)

### A. Coverage Audit
- [ ] List GL consumers still using raw flags (Spotify overlay, any residual per-transition GL widgets).
- [ ] Map where they allocate GL programs/VAOs without ResourceManager tracking.
- [ ] Document current fallback path when those overlays fail (should feed into GLErrorHandler).

### B. Implementation Tasks
- [ ] Inject `GLStateManager` into each overlay.
- [ ] Replace `_gl_initialized`/`_first_frame_drawn` gating with calls to `is_ready()` / state transitions.
- [ ] Emit `[GL STATE]` logs + history snapshots when transitions fail.
- [ ] Hook overlay state transitions into `GLErrorHandler` for capability demotion.
- [ ] Ensure `GLCompositorWidget.cleanup()` and overlay cleanup both transition to DESTROYING/DESTROYED after ResourceManager clears VAOs/programs.

### C. Telemetry & Watchdogs
- [ ] Extend `[PERF] [GL COMPOSITOR]` logs with queue latency once workers (Phase 2) feed textures; add overlay state to log context.
- [ ] Watchdog timeouts should capture `GLStateManager.get_transition_history()` to aid debugging.

### D. Tests & Documentation
- [ ] Expand `tests/test_gl_state_manager.py` with Spotify overlay fixtures (mocked `paintGL`, context loss events).
- [ ] Add integration tests verifying overlay + compositor demotion flows.
- [ ] Update `Docs/TestSuite.md` with new GL coverage entries.
- [ ] Cross-link results back into `audits/ARCHITECTURE_AND_MULTIPROCESSING_PLAN_2026.md` Phase 3 progress notes.

---

## 6. Success Criteria
- All GL components (compositor + overlays) rely on GLStateManager; no stray `_gl_initialized` flags drive logic.
- GLErrorHandler receives uniform state signals and enforces session-wide demotion.
- Watchdogs capture GL state history; `[PERF]` logs include overlay/compositor readiness info.
- Tests document READY/ERROR/CONTEXT_LOST transitions for every GL consumer.
- Documentation (Spec/Index/TestSuite + this guide) reflects the final architecture.

---

## 7. References
- `audits/ARCHITECTURE_AND_MULTIPROCESSING_PLAN_2026.md` – Phase 0/3/5 tasks.
- `Spec.md` – Transition policies, GL fallback semantics, telemetry toggles.
- `Index.md` – Module ownership for rendering and overlays.
- `Docs/PERFORMANCE_BASELINE.md` – Metrics to capture before/after GL changes.
- `Docs/10_WIDGET_GUIDELINES.md` – Overlay behaviour requirements tied to state readiness.
