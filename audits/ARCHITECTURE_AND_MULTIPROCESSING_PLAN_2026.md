# Architecture & Multiprocessing Execution Plan (2026 Refresh)

_This document supersedes ALL documentation created before it. It is the ordered, single-source execution plan for multiprocessing, GL reliability, widgets/settings modularity, and documentation discipline. Keep this live and update statuses as work lands._
Document first and last policy, follow phase order unless explicitly told otherwise.


## 1) Sources of Truth & Standing Policies
- **Index.md** – live module map/ownership; consult before touching any subsystem.
- **Spec.md** – architectural decisions, runtime variants, pipelines, transitions, widgets, perf policy.
- **Docs/TestSuite.md** & **Docs/PERFORMANCE_BASELINE.md** – mandatory updates when tests or perf-sensitive code change.
- **Core Policies** – ThreadManager/ResourceManager/SettingsManager/AnimationManager usage, overlay guidelines (Docs/10_WIDGET_GUIDELINES.md), transition fallback policy (Group A→B→C), **no raw Qt timers**, centralized logging.

## 2) Non-Negotiable Guardrails
1. **UI Process Responsibilities**
   - Render, interpolate, apply prepared transitions, schedule work, drop frames if inputs are late.
   - Must **never** decode images, hit disk, perform FFT/beat analysis, traverse large buffers, allocate unpredictable large objects, or block on I/O.
2. **Worker Processes**
   - Started at boot, persistent, never touch UI state, own heavy work (image decode/prescale, RSS parse/cache, FFT/beat processing, transition precompute).
3. **Communication**
   - Multiprocessing `Queue`/`Pipe` only; small immutable messages; QImage/QPixmap never cross processes.
   - Shared memory allowed for RGBA/FFT buffers with sequence numbers; UI polls non-blocking and reuses last good frame if empty.
4. **Thread/Resource Discipline**
   - ThreadManager for all business logic; ResourceManager for Qt lifecycle; AnimationManager for UI timing; centralized overlay fade raising; **no raw Qt timers** (only documented weather fallback registered with ResourceManager).
   - Prefer lock-free/atomic patterns routed through ThreadManager; only introduce locks where impossible to avoid. Minimizing lock contention is a primary lever to reduce dt_max spikes.
5. **Fallback & Error Handling**
   - Shader failures demote the entire session (Group A→B→C). Worker stalls/crashes trigger restart without blocking UI. No per-transition silent fallback.
6. **Testing & Documentation**
   - Every completed phase updates `Index.md`, `Spec.md`, `Docs/TestSuite.md`, `Docs/PERFORMANCE_BASELINE.md` (when perf touched), and this audit. Tests must cover new paths before merging.
7. **Backups & Parity**
   - Every important module touched gets a `/bak` snapshot at start and after major progress. Feature parity must be documented **before** and **after** work for each major component.
8. **Visualizer Synthetic Baseline (Mandatory)**
   - The Spotify visualizer must have saved synthetic test results **before any visualizer-related work**. These results must be double-verified (no variance that could mislead) and any mapping/smoothing changes must be re-verified with an updated synthetic test.

## 3) Ordered Phases (single set)
| Phase | Objective | Key Deliverables | Depends On | Status |
| --- | --- | --- | --- | --- |
| **0** | Baseline readiness (thread safety & instrumentation) | Thread-safety audit, timer/event hardening, telemetry baselines, backups started | None | ✅ Complete |
| **1** | Process isolation foundations | Worker contract RFC, queue/backpressure rules, supervisor skeleton, shared-memory schema | 0 | ☐ Not started |
| **2** | Image & audio pipeline offload | Image decode/prescale worker, RSS worker, FFT/beat worker, transition precompute offload, shared-memory handoff | 1 | ☐ Not started |
| **3** | GL compositor & transition reliability | GLStateManager rollout, TransitionFactory parity, watchdog + fallback hardening, visualizer state alignment | 0–2 | ☐ Not started |
| **4** | Widget & settings modularity | WidgetManager slim-down, typed settings end-to-end, overlay timer unification, guideline compliance | 0–3 | ☐ Not started |
| **5** | Observability, performance, documentation | Perf baselines, regression tests, doc/audit upkeep, backups per phase | Runs alongside | ☐ Ongoing |

### Phase Status (single source)
| Phase | Status | Notes | Blockers | Next |
| --- | --- | --- | --- | --- |
| 0 | ✅ Complete | WeatherWidget ThreadManager-only; runtime `threading.Thread`/`QThread` absent outside tests/archive; overlay timers enforced via helper/ThreadManager; event system lock usage reviewed. See `audits/AAMP2026_Phase_2_Detailed.md` for the canonical Spotify visualizer snapshot preserved for Phase 2 workerization. | None | Proceed to Phase 1. |
| 1 | ☐ Not started | | | |
| 2 | ☐ Not started | | | |
| 3 | ☐ Not started | | | |
| 4 | ☐ Not started | | | |
| 5 | ☐ Ongoing | Perf/tests/docs/backups run per phase. | None | Keep docs/backups current. |

---

## 4) Detailed Phases & Ordered Checklists

### Phase 0 – Baseline Readiness (Thread Safety, Instrumentation)
**Objectives**
- Remove ThreadManager violations, raw Qt timers, cross-thread widget access.
- Validate EventSystem/thread safety invariants and telemetry coverage.
- Begin `/bak` snapshots for any touched modules.
- **Current state snapshot**: WeatherWidget now fetches exclusively via ThreadManager IO (no raw QThread); `/bak/widgets_weather_widget.py` holds the pre-change copy.

**Action Steps (order)**
1. **Inventory & Backups**
   - [x] List modules touched; `/bak/widgets_weather_widget.py` created before edits.
2. **Thread Safety Sweep**
   - [x] Traverse engine/rendering/widgets/media/sources for `threading.Thread`/`QThread` (none in runtime code; archive/tests only). WeatherWidget migrated to ThreadManager IO-only path.
   - [x] Add `_state_lock`/`RLock` only where unavoidable; prefer existing lock-free queues. (No new locks added.)
   - [x] Document lock-free coverage: ThreadManager mutation queue uses `SPSCQueue`, stats via `TripleBuffer`; Spotify visualizer shares data through `TripleBuffer` only.
3. **Timers & Events**
   - [x] Verify overlay timers use `widgets/overlay_timers.create_overlay_timer` or `ThreadManager.schedule_recurring`; documented ownership and ResourceManager cleanup via helper.
   - [x] Review `core/events/event_system.py` lock usage and async dispatch guarantees; lock released before callbacks, recursion guarded.
4. **Telemetry Baseline**
   - [x] `[PERF]` logs present for transitions/visualizer/AnimationManager; rotation tests remain valid; no new metrics needed.
5. **Tests & Docs**
   - [x] Thread-safety posture validated; existing threading tests cover UI dispatch/timer semantics; no new cases required this sweep.
   - [x] `python -m pytest tests/test_thread_manager.py tests/test_threading.py -q` (2026-01-01) to prove ThreadManager-only policy holds.
   - [x] Update `Index.md`, `Spec.md` with current state; `Docs/TestSuite.md` unchanged (coverage adequate for Phase 0 scope).
6. **Exit**
   - [x] All above green; post-change `/bak` snapshots captured; checklist updated.

### Phase 1 – Process Isolation Foundations
**Objectives**
- Define architecture and contracts without moving pipelines yet.

**Action Steps (order)**
1. **Worker Contract RFC (design-only)**
   - [ ] Define roles: ImageWorker (decode/prescale + cache keying), RSSWorker (fetch/parse/cache rotate), FFTWorker (loopback ingest + smoothing), TransitionPrepWorker (CPU precompute payloads).
   - [ ] Message schemas: requests/responses with minimal, immutable payloads; include seq_no, correlation_id, timestamps, pool hint, and max payload sizes.
   - [ ] Shared-memory schema: RGBA buffers (width/height/stride/format), FFT bins (len, window, smoothing metadata), ownership (producer_pid, generation).
   - [ ] Error/health contract: heartbeat interval, crash policy, degraded modes; logging format compatible with `[PERF]` tagging.
2. **Process Supervisor Skeleton (`core/process/`)**
   - [ ] API surface: start(worker_type), stop(worker_type), restart(worker_type), heartbeat monitor, structured logging hook, capability flags (supports_shared_mem, supports_gpu?).
   - [ ] Health model: missed-heartbeat threshold, exponential backoff restart, max restarts per window; metrics counters.
   - [ ] Integration points: settings for enabling/disabling workers; graceful shutdown path (ResourceManager-friendly).
3. **Queue & Backpressure Rules**
   - [ ] Non-blocking poll wrappers for UI: drop-old policy, queue length metrics, backpressure thresholds per channel (image, rss, fft, precompute).
   - [ ] Serialization choices: avoid pickling QImage/QPixmap; enforce small, immutable messages; include compression flag if used.
4. **Testing Hooks (design)**
   - [ ] `tests/helpers/worker_sim.py`: deterministic worker simulators for each worker type (canned images/FFT bins/transition payloads), controllable latency and failure injection.
   - [ ] Contract fixtures: schema validation helpers for requests/responses/shared-memory headers.
5. **Documentation & Backups Plan**
   - [ ] Maintain Phase 1 detailed plan in `audits/AAMP2026_Phase_1_Detailed.md`; keep audit in sync.
   - [ ] Spec.md stays current-state (no planning).
   - [ ] Index.md: add/adjust entries for worker modules when implemented.
   - [ ] `/bak`: snapshots pre/post for modules touched in Phase 1.
6. **Exit (for planning phase)**
   - [ ] RFC content finalized in this document; no code written.
   - [ ] Schemas, health rules, and testing approach captured here and mirrored into Spec/Index.

### Phase 2 – Image & Audio Pipeline Offload
**Objectives**
- Move heavy work to workers while preserving cache/promote semantics.

**Action Steps (order)**
1. **Pre-flight & Backups**
   - [ ] Snapshot affected modules (`utils/image_prefetcher.py`, `utils/image_cache.py`, RSS sources, visualizer worker glue).
2. **Image Worker**
   - [ ] Port decode/prescale to worker; populate shared-memory caches; UI swaps pointers into `ImageCache` (`path|scaled:WxH` key strategy preserved).
3. **RSS & Disk I/O**
   - [ ] Move RSS fetch/parse + disk mirroring to worker; UI receives validated `ImageMetadata` + handles.
4. **Spotify FFT/Beat Worker**
   - [ ] Extract `_SpotifyBeatEngine` compute path into worker; UI consumes pre-smoothed bars + ghost envelopes via non-blocking poll.
   - [ ] **Prerequisite:** Visualizer synthetic test results saved and double-verified before any visualizer changes; rerun updated synthetic test after changes.
5. **Transition Precompute**
   - [ ] Offload CPU transition pre-bake (lookup tables/block sequences); UI only uploads results.
6. **Tests & Perf**
   - [ ] End-to-end latency tests (worker delay still keeps dt_max bounded).
   - [ ] Perf baselines before/after with `SRPSS_PERF_METRICS=1`; record in `Docs/PERFORMANCE_BASELINE.md`.
7. **Documentation & Backups**
   - [ ] Maintain Phase 2 detailed plan in `audits/AAMP2026_Phase_2_Detailed.md`; keep audit in sync.
   - [ ] Spec.md stays current-state (no planning).
   - [ ] Index.md: add worker modules when implemented.
   - [ ] `/bak`: snapshots pre/post for modules touched in Phase 2.

### Phase 3 – GL Compositor & Transition Reliability
**Objectives**
- Unify GL state management, watchdogs, and fallback behaviour; align visualizer overlays.

**Action Steps (order)**
1. **Backups**
   - [ ] Snapshot GL compositor/overlays/transition controller modules.
2. **GLStateManager Rollout**
   - [ ] Apply to `widgets/spotify_bars_gl_overlay.py`, GL warmup paths, legacy overlays; validate READY→ERROR→DESTROYING transitions.
3. **Transition Controller Alignment**
   - [ ] Ensure `rendering/transition_controller.py` uses TransitionStateManager for CPU + GL; enforce `snap_to_new=True` cleanup.
4. **Watchdog & Telemetry**
   - [ ] Standardize watchdog hooks; correlate `[PERF] [GL COMPOSITOR]` with worker queue latency once shared-memory feeds textures.
5. **Failure Paths & Visual Regression**
   - [ ] Tests for shader compile fail, lost context, demotion (Group A→B→C).
   - [ ] Snapshot/visual regressions confirming final frame correctness.
6. **Documentation & Backups**
   - [ ] Maintain Phase 3 detailed plan in `audits/AAMP2026_Phase_3_Detailed.md`; keep audit in sync.
   - [ ] Spec.md stays current-state (no planning).
   - [ ] Index.md: add/adjust entries for GL state manager + overlays when implemented.
   - [ ] `/bak`: snapshots pre/post for GL compositor/overlay modules touched.

### Phase 4 – Widget & Settings Modularity
**Objectives**
- Make WidgetManager a coordinator; typed settings end-to-end; overlay guideline compliance.
- Ensure modal Settings (dialog + future overlays) apply changes live without forcing engine restarts; widget configs (Spotify VIS sensitivity/floor, etc.) must subscribe to settings signals.
- Prevent Settings-driven display toggles (e.g., primary monitor disable) from inadvertently tearing down the running engine; DisplayWidget must handle the refresh non-destructively.

**Action Steps (order)**
1. **Backups**
   - [ ] Snapshot widget manager/factories/positioner/settings UI modules.
2. **WidgetManager Slim-Down**
   - [ ] Remove widget-specific conditionals; rely on factories + positioner enums; centralize fade/raise API to DisplayWidget.
3. **Typed Settings Adoption**
   - [x] Replace ad-hoc `settings.get` with models; helper to/from dot-notation; update UI tabs respecting MC vs Screensaver profile separation. ✅ _2026‑01‑01_: WidgetManager + Widgets tab now consume `MediaWidgetSettings`, `RedditWidgetSettings`, and `SpotifyVisualizerSettings`.
   - [x] Capture live-setting reaction requirements (Spotify VIS/Sensitivity) inside the typed model contract so UI sliders always affect running widgets. ✅ _2026‑01‑01_: `WidgetManager._handle_settings_changed` pushes live refresh for Spotify VIS/media/reddit; regression tests cover VIS replay and scrollwheel volume.
   - [x] Document display/monitor toggles as non-destructive updates in typed profiles. ✅ _2026‑01‑01_: Typed models carry monitor selectors; refresh path applies without tearing down DisplayWidget; notes added to Spec/Phase doc.
   - [ ] Audit settings end to end for stragglers, make sure subwidgets inherit style settings where appropriate (when they lack their own exposed in the GUI) check positioning settings for any issues with placement, especially regarding middle/center and stacking.
4. **Modal Settings Conversion**
   - [ ] **Canonical defaults sweep (pre-modal work):** Apply the checklist in `audits/setting manager defaults/Setting Defaults Guide.txt` to ensure Screensaver vs MC SST exports map cleanly into SettingsManager defaults. Confirm reset-to-defaults adheres to the guide before the modal dialog rework.
   - [ ] Convert the existing settings dialog workflow into the modal version referenced in Spec.md, ensuring it can be launched from both SRPSS and MC builds without forcing an engine restart.
   - [ ] Wire modal lifecycle to `SettingsManager` signals so changes apply live; document how Just Make It Work/Ehhhh flow integrates with the modal dialog.
   - [ ] Verify that monitor toggles, widget enablement, and queue/source changes raised through the modal path keep DisplayWidget running (no teardown/re-init).
5. **Overlay Guidelines Audit**
   - [ ] Verify alignment/fade/resource registration per Docs/10_WIDGET_GUIDELINES.md across all widgets and `ui/widget_stack_predictor.py`.
6. **Tests & Docs**
   - [ ] Expand `tests/test_widget_factories.py`, `tests/test_widget_positioner.py`, add lifecycle/UI binding integration tests.
   - [ ] Update `Spec.md`, `Index.md`, `Docs/TestSuite.md`; capture post-change `/bak`.
7. **Exit**
   - [ ] WidgetManager < 600 LOC, no widget-specific logic; guideline compliance documented.

### Phase 5 – Observability, Performance, Documentation (Ongoing)
**Objectives**
- Keep telemetry, tests, docs, and backups current across phases.

**Action Steps (repeated each phase)**
1. **Perf Baselines**
   - [ ] Run harness per `Docs/PERFORMANCE_BASELINE.md`; record dt_max/avg_fps/memory per transition/backend.
2. **Regression Tests**
   - [ ] Add/adjust pytest for workers, GL demotion, widget lifecycle; maintain rotating pytest log per Windows guide.
3. **Documentation Hygiene**
   - [ ] Update `Index.md`, `Spec.md`, `Docs/TestSuite.md`, and this audit with status + feature parity before/after.
4. **Backups**
   - [ ] `/bak` snapshots for every important module touched; include short README per snapshot.
5. **Audit Continuity**
   - [ ] Keep this file and the per-phase detailed planners as the only live trackers (no duplicate roadmap docs).

---

## 5) Delivery Expectations & Reporting
- **Planning Discipline**: Draft sub-plans for complex work (GL, multiprocessing, widget rewrites) before coding.
- **Coordination**: Always route through centralized managers (ThreadManager, ResourceManager, EventSystem, AnimationManager, SettingsManager).
- **Testing Gate**: No task is done without tests + docs + audit updates together.
- **Documentation of Parity**: Record pre/post functionality for every major component touched.
- **Communication**: Update this document with checkbox status and brief notes; reference commit hashes when closing items.

> By following this ordered plan, UI workloads stay deterministic, GL behaviour remains predictable, and widget/settings systems remain maintainable—while docs, tests, perf baselines, and backups stay in lockstep.
