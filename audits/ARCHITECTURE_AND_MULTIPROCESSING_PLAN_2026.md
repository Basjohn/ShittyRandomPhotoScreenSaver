# Architecture & Multiprocessing Execution Plan (2026 Refresh)

_This document supersedes ALL DOCUMENTATION CREATED BEFORE IT. It consolidates architectural priorities, multiprocessing requirements, and live execution checklists guided by the current `Index.md` and `Spec.md`._

## 1. Source of Truth & Context
- **Index.md** – live module map, ownership, and extraction history (core managers, engine, rendering, widgets, UI, sources).
- **Spec.md** – architectural decisions, runtime variants, pipelines, transitions, widgets, performance policy.
- **Docs/TestSuite.md & Docs/PERFORMANCE_BASELINE.md** – required whenever tests or perf-sensitive code change.
- **Core policies** – ThreadManager + ResourceManager usage, overlay guidelines (Docs/10_WIDGET_GUIDELINES.md), transition fallback policy (Group A→B→C), no raw Qt timers, centralized logging.

## 2. Guardrails (Non-Negotiable)
1. **UI Process Responsibilities**
   - May render, interpolate, apply already-prepared transitions, schedule work, drop frames if inputs are late.
   - Must **never** decode images, hit disk, perform FFT/beat analysis, walk large buffers, allocate unpredictable large objects, or block on I/O.
2. **Worker Processes**
   - Started at boot, stay alive, never touch UI state, own all heavy work (image decode, scaling, RSS parsing, FFT, transition preprocessing).
3. **Communication**
   - Multiprocessing `Queue`/`Pipe` only, small immutable messages, QImage/QPixmap never cross processes. Shared memory allowed for large RGBA buffers with sequence numbers.
   - UI polls non-blocking; empty queue ⇒ keep rendering last good frame.
4. **Thread/Resource Discipline**
   - ThreadManager for all business logic tasks, ResourceManager for Qt object lifecycle, AnimationManager for UI timing, centralized overlay fade raising.
5. **Fallback & Error Handling**
   - Shader failures demote the entire session (Group A→B→C). Worker stalls/crashes trigger restart without blocking UI. No per-transition silent fallback.
6. **Testing & Documentation**
   - Every completed phase updates `Index.md`, `Spec.md`, `Docs/TestSuite.md`, and associated audits. Tests must cover new code paths before merging.

**Implementation Guidance**
- Threading, resource, and settings access must flow through the centralized managers enumerated in `Index.md` (ThreadManager, ResourceManager, SettingsManager, AnimationManager, WidgetManager) so lifecycle state is observable and testable @Index.md#18-217.
- Guardrails inherit the thread-safety policy defined in `Spec.md` (UI-thread widget updates, ThreadManager for IO/compute, overlay timers via helper APIs) @Spec.md#270-312.
- Transition fallback rules mirror the compositor group demotion flow in `Spec.md` — once shaders fail, the entire session downgrades to QPainter/CPU paths and transitions must finish on an artifact-free final frame @Spec.md#109-157 @Spec.md#4-27.
- Widget lifecycle, overlay fade synchronization, and GL overlay ordering must adhere to `Docs/10_WIDGET_GUIDELINES.md` references in both Index and Spec to avoid the historical flicker/regression set @Index.md#181-318 @Spec.md#288-354.
- Testing expectations (unit/integration/system/perf) and coverage targets are laid out in `Spec.md` Section 7 and should be re-affirmed before exiting any phase @Spec.md#819-888.

## 3. Execution Phases (Priority Order)
| Phase | Objective | Key Deliverables | Dependencies | Status |
| --- | --- | --- | --- | --- |
| **0** | Baseline readiness (thread safety & instrumentation) | Thread safety audit, event system hardening, telemetry baselines | None | ☐ Not started |
| **1** | Process isolation foundations | Worker API contract, queue/schema, health supervision | Phase 0 | ☐ Not started |
| **2** | Image & audio pipeline offload | Image decode/prescale workers, beat/FFT worker, shared-memory cache handoff | Phase 1 | ☐ Not started |
| **3** | GL compositor & transition reliability | Full GLStateManager integration, transition factory parity, watchdog + fallback hardening | Phases 0-2 | ☐ Not started |
| **4** | Widget & settings modularity | WidgetManager slim-down, typed settings adoption across UI/runtime, overlay timer unification | Phases 0-3 | ☐ Not started |
| **5** | Observability, performance, and documentation | Perf baselines, regression tests, doc refresh, live audit upkeep | Runs alongside phases | ☐ Ongoing |

> **Live Action Checklist Snapshot** (detailed lists per phase below)
> - [ ] Complete thread safety + event audit (Phase 0)
> - [ ] Ratify worker messaging contract + health supervision (Phase 1)
> - [ ] Ship image/FFT worker handoff with shared memory (Phase 2)
> - [ ] Finish GL compositor migration + watchdog parity (Phase 3)
> - [ ] Finalize widget/settings modularization (Phase 4)
> - [ ] Lock perf + docs, keep audit current (Phase 5)

---

## 4. Phase Detail & Checklists

### Phase 0 – Baseline Readiness (Thread Safety, Instrumentation)
**Objectives**
- Eliminate remaining ThreadManager violations, raw Qt timers, and cross-thread widget access.
- Validate EventSystem/thread safety invariants and logging coverage for diagnostics.

**Action Steps**
1. **Thread Safety Audit**
   - [ ] Traverse all modules highlighted in `Index.md` (engine, rendering, widgets, media, sources) for ThreadManager usage.
   - [ ] Replace lingering `threading.Thread`/`QThread` usages with ThreadManager pools or documented fallbacks (Weather widget already noted).
   - [ ] Add `_state_lock`/`RLock` guards for shared state (GL overlays, widget lifecycle caches).
2. **Event & Timer Consolidation**
   - [ ] Confirm overlay timers use `widgets/overlay_timers.create_overlay_timer` or ThreadManager.schedule_recurring.
   - [ ] Document timer ownership + clean-up via ResourceManager.
3. **Telemetry Baseline**
   - [ ] Ensure `[PERF]` logs exist for transitions, Spotify visualizer, AnimationManager loops.
   - [ ] Extend `screensaver_perf.log` rotation tests if new metrics added.
4. **Exit Criteria**
   - Thread safety unit tests (`tests/test_thread_manager.py`, new targeted tests) pass locally and in CI.
   - Docs updated: `Docs/TestSuite.md` (new tests), `Spec.md` (thread safety guarantees), `Index.md` (audit entry per module touched).

**Guidance & Pitfalls**
- Confirm `rendering/display_widget.py` only mutates Qt widgets via UI-thread helpers and that overlay timers route through `widgets/overlay_timers.py`; raw `QTimer` is allowed only inside the documented weather fallback and must be registered with ResourceManager @Index.md#124-318.
- The EventSystem in `core/events/event_system.py` should be reviewed for lock usage and subscriber lifecycle so worker callbacks never dispatch UI work synchronously; update docs if additional thread guarantees are codified @Index.md#27-38.
- Logging throttling (`core/logging/logger.py`) already exists; leverage it when adding new instrumentation to keep `screensaver_perf.log` actionable @Index.md#70-79 @COMPREHENSIVE_ARCHITECTURE_AUDIT_2025.md#556-603.

### Phase 1 – Process Isolation Foundations
**Objectives**
- Design top-level worker architecture without moving yet.
- Define message schema, sequencing, and health management.

**Action Steps**
1. **Worker Contract RFC**
   - [ ] Draft worker responsibilities (ImageWorker, FFTWorker) + payload schemas (requests/responses) referencing `engine/image_queue.py`, `utils/image_cache.py`, `widgets/spotify_visualizer_widget.py`.
   - [ ] Define shared `ProcessSupervisor` located under `core/process/` (new module) with: start, monitor, restart, health ping, structured logging hooks.
   - [ ] Specify sequence numbers + shared memory layout for large buffers (RGBA, FFT bins) using `multiprocessing.shared_memory` with copy-on-read semantics for UI.
2. **Queue & Backpressure Rules**
   - [ ] Implement non-blocking `Queue` access wrapper for UI (poll, drop-old policy, metrics counters).
   - [ ] Set caps per queue; overflow policy = drop oldest (latest-state semantics).
3. **Testing Hooks**
   - [ ] Provide fake worker harness for unit tests (predictable data via `tests/helpers/worker_sim.py`).
4. **Exit Criteria**
   - RFC merged; `Spec.md` gains new "Process Isolation" section.
   - Supervisor skeleton checked in with basic spawn/heartbeat tests.

**Guidance & Pitfalls**
- Base worker APIs should mirror existing cache/prefetch semantics (`engine/image_queue.py`, `utils/image_prefetcher.py`) so UI callers do not require new synchronization primitives @Index.md#83-200 @Index.md#352-356.
- When defining queue schemas, capture the metadata already emitted by `sources/rss_source.py` (priorities, TTLs) to avoid duplicating logic in the UI thread @Index.md#258-271.
- Include health metrics/logging hooks inside the supervisor so `[PERF]` lines can correlate worker latency vs. compositor dt spikes; reuse `screensaver_perf.log` tagging conventions @Spec.md#158-185.

### Phase 2 – Image & Audio Pipeline Offload
**Objectives**
- Move deterministic heavy work to workers while preserving caching semantics.
- Ensure UI promotion paths (QImage→QPixmap, GL texture uploads) remain unchanged.

**Action Steps**
1. **Image Worker Implementation**
   - [ ] Port `utils/image_prefetcher.py` decode/prescale steps into worker process.
   - [ ] Workers populate shared-memory caches; UI updates `ImageCache` via pointer swap (no locks on UI thread).
   - [ ] Enforce ratio policy (local vs RSS) by queuing requests rather than inline decode.
2. **RSS & Disk I/O**
   - [ ] Move RSS fetch/parse + disk mirroring into worker; UI only receives validated `ImageMetadata` + buffer handles.
3. **Spotify Beat/FFT Worker**
   - [ ] Extract `_SpotifyBeatEngine` compute path into worker; UI consumes pre-smoothed bar magnitudes + ghost envelopes.
   - [ ] Maintain dt_max independence by ensuring UI polls non-blocking.
4. **Transition Precompute**
   - [ ] Offload CPU transition pre-bake (lookup tables, block sequences) so UI only uploads results.
5. **Testing & Metrics**
   - [ ] End-to-end tests verifying UI responsiveness when workers delayed (synthetic `time.sleep(0.02)` still leaves dt_max bounded).
   - [ ] Perf baselines captured with `SRPSS_PERF_METRICS=1` before/after.
6. **Exit Criteria**
   - Workers restart automatically on crash; UI logs degrade gracefully.
   - `Docs/PERFORMANCE_BASELINE.md` updated with new pipeline metrics.

**Guidance & Pitfalls**
- Preserve the cache key strategy in `ImageCache` (`path|scaled:WxH`) so prescaled/shared-memory buffers line up with existing promotion flows; any deviation risks duplicate uploads and memory churn @Spec.md#68-170.
- Ensure Spotify worker outputs feed directly into `SpotifyBarsGLOverlay`’s triple-buffer expectations, keeping `_shadowfade_progress` coordination intact @Spec.md#227-353.
- For transition precompute, respect direction/duration settings from `SettingsManager` models so per-type overrides continue to function (`transitions.durations`, direction history) @Spec.md#123-199.

### Phase 3 – GL Compositor & Transition Reliability
**Objectives**
- Finish GLStateManager rollout, ensure session-wide fallback handling, bring Spotify overlays onto same state machine.
- Simplify TransitionFactory + overlay coordination per `Spec.md` expectations.

**Action Steps**
1. **GLStateManager Integration**
   - [ ] Apply to `widgets/spotify_bars_gl_overlay.py`, GL widget warmup paths, and legacy overlays.
   - [ ] Validate state transitions (READY→ERROR→DESTROYING) with instrumentation.
2. **Transition Controller Alignment**
   - [ ] Ensure `rendering/transition_controller.py` uses TransitionStateManager for all transitions, CPU + GL.
   - [ ] Guarantee `snap_to_new=True` on every cleanup path to obey no-residual blending policy.
3. **Watchdog & Telemetry**
   - [ ] Standardize watchdog start/stop hooks per transition; integrate with supervisor metrics.
   - [ ] Expand `[PERF] [GL COMPOSITOR]` logs to include queue latency vs render time once workers feed textures.
4. **Testing**
   - [ ] Synthetic failure tests (shader compile fail, lost context) verifying Group demotion.
   - [ ] Visual regression capture (snapshot comparisons) ensuring final frame matches target image.
5. **Exit Criteria**
   - GL overlays + compositor share one state flow; `Spec.md` updated; tests in `tests/test_gl_state_manager.py` extended for overlays.

**Guidance & Pitfalls**
- Align watchdog handling with `rendering/transition_controller.py` and `GLCompositorWidget` warmup to guarantee `snap_to_new=True` and synchronous widget raises after `transition.start()` per overlay policy @Spec.md#119-157 @Spec.md#289-354.
- When extending GLStateManager to Spotify overlays, reuse the `_gl_initialized` and `_first_frame_drawn` gating pattern documented in Spec so `paintGL` never executes early @Spec.md#110-154.
- Logging for fallback demotion should reuse `GLErrorHandler` capability levels so telemetry clearly shows when sessions drop from FULL_SHADERS → COMPOSITOR_ONLY → SOFTWARE_ONLY @Index.md#162-168.

### Phase 4 – Widget & Settings Modularity
**Objectives**
- Finish slimming WidgetManager into pure coordinator; push creation/config/positioning fully into factories and positioner.
- Enforce typed settings usage end-to-end, including UI binding.

**Action Steps**
1. **WidgetManager Refactor Completion**
   - [ ] Remove widget-specific logic from `rendering/widget_manager.py`; rely on factories + positioner enums.
   - [ ] Centralize overlay fade + raise logic and expose minimal API to DisplayWidget.
2. **Settings Model Adoption**
   - [ ] Replace ad-hoc `settings.get` calls with typed dataclasses across rendering + widgets.
   - [ ] Provide helper to convert typed models back to dot-notation for persistence.
   - [ ] Update UI tabs to consume models (ensuring MC vs screensaver profile separation remains).
3. **Overlay Guidelines Compliance**
   - [ ] Audit all overlay widgets against `Docs/10_WIDGET_GUIDELINES.md` (header/logo alignment, fade sync, ResourceManager registration).
4. **Testing**
   - [ ] Expand `tests/test_widget_factories.py` & `tests/test_widget_positioner.py` for new cases.
   - [ ] Add integration tests for multi-widget start/stop sequences verifying lifecycle ordering.
5. **Exit Criteria**
   - WidgetManager < 600 LOC, no widget-specific conditionals.
   - Settings models documented in Spec + UI binding instructions.

**Guidance & Pitfalls**
- Widget factories already encapsulate creation logic; keep future enhancements inside `rendering/widget_factories.py` and surface only declarative configs to WidgetManager to avoid relapsing into monolithic patterns @Index.md#181-207.
- Settings adoption must consider MC vs. Screensaver profile mapping already baked into `SettingsManager` so user separation persists @Index.md#31-39 @Spec.md#42-52.
- Overlay guideline compliance requires referencing `Docs/10_WIDGET_GUIDELINES.md`; ensure any new positioning/fade work updates both the runtime widget and predictive UI (`ui/widget_stack_predictor.py`) @Index.md#288-344.

### Phase 5 – Observability, Performance, Documentation (Ongoing)
**Objectives**
- Keep audits, Index, Spec, TestSuite, and PerformanceBaseline current.
- Ensure perf regression protection and documentation clarity for future contributors.

**Action Steps**
1. **Perf Baselines**
   - [ ] Run standard perf harness (per `Docs/PERFORMANCE_BASELINE.md`) after each major phase; record dt_max, avg_fps, memory per transition.
2. **Regression Tests**
   - [ ] Add targeted pytest modules for workers, GL demotion, widget lifecycle sequences.
   - [ ] Maintain rotating pytest log as per Windows guide when suites grow.
3. **Documentation Hygiene**
   - [ ] Update `Index.md` after each phase with module summaries + new ownership.
   - [ ] Update `Spec.md` for architectural decisions (process isolation, GL, widget settings).
   - [ ] Keep `Docs/TestSuite.md` synchronized with new/modified tests.
   - [ ] Append `audits/ARCHITECTURE_AND_MULTIPROCESSING_PLAN_2026.md` with progress notes (checklist state) instead of spawning side files.
4. **Audits & Backups**
   - [ ] Mirror critical .py files touched by each phase into `/bak` (per policy) with short README.
   - [ ] Keep `/audits/v1_2 ROADMAP.md` updated when GL or compositor behaviour changes.

**Guidance & Pitfalls**
- Performance baselines must use the metrics enumerated in `Docs/PERFORMANCE_BASELINE.md` (dt_max, avg_fps, memory) and reference the environment toggles described in `Spec.md` (`SRPSS_PERF_METRICS`, `SRPSS_PROFILE_CPU`) @Spec.md#158-187.
- When adding regression tests, cross-reference `Docs/TestSuite.md` to maintain the canonical registry; widget/transition tests should inherit fixtures from the existing suites listed in Section 3.2 of the 2025 audit @COMPREHENSIVE_ARCHITECTURE_AUDIT_2025.md#606-670.
- Every documentation update should reiterate the centralized module responsibilities from Index so new contributors can trace ownership quickly; treat `Index.md` as the authoritative file map, not a changelog @Index.md#1-347.

---

## 5. Live Master Checklist
> Update this section as work progresses; it is the canonical status tracker for the combined plan.

### Phase 0 – Baseline Readiness
- [ ] Complete ThreadManager compliance sweep (engine, rendering, widgets, media, sources).
- [ ] Replace residual raw Qt timers / QThreads with centralized overlays timers or ThreadManager scheduling.
- [ ] Add/verify locks for GL overlay state flags and widget lifecycle caches.
- [ ] Extend thread safety unit tests + document in Docs/TestSuite.md.

### Phase 1 – Process Isolation Foundations
- [ ] Publish worker contract RFC + ProcessSupervisor skeleton.
- [ ] Implement queue/backpressure helpers with metrics + logging.
- [ ] Land shared memory layout spec + helper utilities.
- [ ] Provide worker simulation harness for tests.

### Phase 2 – Image & Audio Pipeline Offload
- [ ] Port image decode/prescale to workers with shared memory handoff.
- [ ] Offload RSS/JSON fetch & caching.
- [ ] Move Spotify FFT/beat smoothing into worker process.
- [ ] Offload CPU transition precompute.
- [ ] Capture before/after perf baselines.

### Phase 3 – GL & Transition Reliability
- [ ] Apply GLStateManager to Spotify overlays + legacy GL widgets.
- [ ] Ensure all transitions route through TransitionStateManager + snap_to_new cleanup.
- [ ] Standardize watchdog instrumentation + `[PERF]` logging.
- [ ] Add failure-path tests (shader compile, lost context, demotion).

### Phase 4 – Widget & Settings Modularity
- [ ] Reduce WidgetManager to coordinator (factories + positioner do the rest).
- [ ] Enforce typed settings usage across runtime + UI.
- [ ] Audit overlay guidelines compliance for every widget.
- [ ] Expand widget lifecycle + UI binding tests.

### Phase 5 – Observability & Documentation
- [ ] Update Index, Spec, Docs/TestSuite, and audits after each phase.
- [ ] Maintain `/audits/v1_2 ROADMAP.md` + `/audits/ARCHITECTURE_AND_MULTIPROCESSING_PLAN_2026.md` progress log.
- [ ] Keep `/bak` snapshots for critical modules touched in each phase.
- [ ] Run PERF baseline + log rotation checks regularly.

---

## 6. Delivery Expectations & Reporting
- **Planning Discipline**: For complex subtasks (GL, multiprocessing, widget rewrites), spin up dedicated planning notes **before** writing code, per audit admonitions.
- **Coordination**: Use centralized managers (ThreadManager, ResourceManager, EventSystem, AnimationManager) for every new feature.
- **Testing Gate**: No task considered complete until tests + docs + audit updates land together.
- **Communication**: Log progress in this document (checkboxes, brief notes) and reference commit hashes when closing items.

> _By following this phased plan, the codebase moves toward deterministic UI workloads, predictable GL behaviour, and maintainable widget/settings systems while keeping documentation synchronized with reality._
