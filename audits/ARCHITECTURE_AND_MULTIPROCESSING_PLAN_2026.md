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
| **5** | MC specialization & layering | Context menu layering, visibility detection, fully-automatic Eco Mode | 4 | ☐ Not started |
| **6** | Observability, performance, documentation | Perf baselines, regression tests, doc/audit upkeep, backups per phase | Runs alongside | ☐ Ongoing |

### Phase Status (single source)
| Phase | Status | Notes | Blockers | Next |
| --- | --- | --- | --- | --- |
| 0 | ✅ Complete | WeatherWidget ThreadManager-only; runtime `threading.Thread`/`QThread` absent outside tests/archive; overlay timers enforced via helper/ThreadManager; event system lock usage reviewed. See `audits/AAMP2026_Phase_2_Detailed.md` for the canonical Spotify visualizer snapshot preserved for Phase 2 workerization. | None | Proceed to Phase 1. |
| 1 | ☐ Not started | | | |
| 2 | ☐ Not started | | | |
| 3 | ☐ Not started | | | |
| 4 | ☐ Not started | | | |
| 5 | ☐ Not started | | | |
| 6 | ☐ Ongoing | Perf/tests/docs/backups run per phase. | None | Keep docs/backups current. |

---

**Phase 0 Accomplishments Summary:** Phase 0 established core thread safety and instrumentation. Key accomplishments include migrating WeatherWidget to ThreadManager, eliminating raw `threading.Thread`/`QThread` usage outside tests/archive, enforcing overlay timers via ThreadManager helpers, and reviewing event system lock usage. A canonical Spotify visualizer snapshot was also preserved for Phase 2 workerization.

## 4) Detailed Phases & Ordered Checklists


### Phase 1 – Process Isolation Foundations
**Objectives**
- Define architecture and contracts without moving pipelines yet.

**Related Modules**: `core/threading/manager.py`, `core/resources/manager.py`, `core/events/event_system.py`, `core/resources/types.py`

**Action Steps (order)**
1. **Worker Contract RFC (design-only)**
   - [ ] Define roles: ImageWorker (decode/prescale + cache keying), RSSWorker (fetch/parse/cache rotate), FFTWorker (loopback ingest + smoothing), TransitionPrepWorker (CPU precompute payloads).
     - ImageWorker integrates with: `utils/image_cache.py`, `utils/image_prefetcher.py`, `rendering/image_processor.py`
     - RSSWorker integrates with: `sources/rss_source.py`, `sources/base_provider.py`
     - FFTWorker integrates with: `widgets/beat_engine.py`, `widgets/spotify_visualizer_widget.py`
     - TransitionPrepWorker integrates with: `rendering/transition_factory.py`, `transitions/base_transition.py`
   - [ ] Message schemas: requests/responses with minimal, immutable payloads; include seq_no, correlation_id, timestamps, pool hint, and max payload sizes.
     - Coordinate with: `core/resources/types.py` for resource type definitions
   - [ ] Shared-memory schema: RGBA buffers (width/height/stride/format), FFT bins (len, window, smoothing metadata), ownership (producer_pid, generation).
     - Use pattern from: `ResourceManager` weak reference tracking
   - [ ] Error/health contract: heartbeat interval, crash policy, degraded modes; logging format compatible with `[PERF]` tagging.
     - Integrate with: `core/logging/logger.py` for structured logging
2. **Process Supervisor Skeleton (`core/process/`)**
   - [ ] API surface: start(worker_type), stop(worker_type), restart(worker_type), heartbeat monitor, structured logging hook, capability flags (supports_shared_mem, supports_gpu?).
     - Follow pattern from: `ThreadManager` for pool management
     - Register with: `ResourceManager` for lifecycle tracking
   - [ ] Health model: missed-heartbeat threshold, exponential backoff restart, max restarts per window; metrics counters.
     - Use: `EventSystem` for health state broadcasts
   - [ ] Integration points: settings for enabling/disabling workers; graceful shutdown path (ResourceManager-friendly).
     - Settings keys: `workers.image.enabled`, `workers.rss.enabled`, `workers.fft.enabled`, `workers.transition.enabled`
     - Shutdown: Coordinate with `ResourceManager.cleanup_all()` sequence
3. **Queue & Backpressure Rules**
   - [ ] Non-blocking poll wrappers for UI: drop-old policy, queue length metrics, backpressure thresholds per channel (image, rss, fft, precompute).
   - [ ] Serialization choices: avoid pickling QImage/QPixmap; enforce small, immutable messages; include compression flag if used.
4. **Testing Hooks (design)**
   - [ ] `tests/helpers/worker_sim.py`: deterministic worker simulators for each worker type (canned images/FFT bins/transition payloads), controllable latency and failure injection.
     - Pattern: Similar to existing test helpers in `tests/` directory
   - [ ] Contract fixtures: schema validation helpers for requests/responses/shared-memory headers.
     - Tests: `tests/test_worker_contracts.py`, `tests/test_shared_memory.py`
   - [ ] Integration shims: stub supervisor for UI tests (no process spawn); verify UI drop-old semantics under delay.
     - Tests: `tests/test_process_supervisor.py`
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

**Related Modules**: `utils/image_prefetcher.py`, `utils/image_cache.py`, `sources/rss_source.py`, `widgets/beat_engine.py`, `widgets/spotify_visualizer_widget.py`, `rendering/image_processor.py`

**Action Steps (order)**
1. **Pre-flight & Backups**
   - [ ] Snapshot affected modules (`utils/image_prefetcher.py`, `utils/image_cache.py`, RSS sources, visualizer worker glue).
     - Backup to: `/bak/utils/`, `/bak/sources/`, `/bak/widgets/`
     - Include: Short README explaining pre-workerization state
2. **Image Worker**
   - [ ] Port decode/prescale to worker; populate shared-memory caches; UI swaps pointers into `ImageCache` (`path|scaled:WxH` key strategy preserved).
     - Extract from: `ImagePrefetcher._prefetch_task()` (decode logic)
     - Extract from: `ImageProcessor.process_image()` (prescale logic)
     - Coordinate with: `ScreensaverEngine._load_image_task()` for cache lookup
     - Tests: `tests/test_image_worker.py`, `tests/test_image_worker_cache.py`, `tests/test_image_worker_latency.py`
3. **RSS & Disk I/O**
   - [ ] Move RSS fetch/parse + disk mirroring to worker; UI receives validated `ImageMetadata` + handles.
     - Extract from: `RSSSource.refresh()`, `_fetch_feed()`, `_parse_reddit_json()`
     - Preserve: Priority system (Bing=95, Unsplash=90, Wikimedia=85, NASA=75, Reddit=10)
     - Preserve: Per-source limits (8 images per source per cycle)
     - Tests: `tests/test_rss_worker.py`, `tests/test_rss_worker_mirror.py`, `tests/test_rss_worker_metadata.py`
4. **Spotify FFT/Beat Worker**
   - [ ] Extract `_SpotifyBeatEngine` compute path into worker; UI consumes pre-smoothed bars + ghost envelopes via non-blocking poll.
     - Extract: `BeatEngine._process_audio_frame()`, `_fft_to_bars()`, `_apply_smoothing()`
     - Preserve: All math from `audits/VISUALIZER_DEBUG.md` (noise floor 2.1, expansion 2.5, smoothing 0.3, decay 0.7)
     - Preserve: Tau values (`tau_rise = base_tau * 0.35`, `tau_decay = base_tau * 3.0`)
     - Use: Existing `TripleBuffer` from `widgets/spotify_visualizer_widget.py`
   - [ ] **Prerequisite:** Visualizer synthetic test results saved and double-verified before any visualizer changes; rerun updated synthetic test after changes.
     - Baseline test: `tests/test_visualizer_baseline.py`
     - Preservation test: `tests/test_visualizer_preservation.py`
     - Math tests: `tests/test_beat_engine_math.py`
5. **Transition Precompute**
   - [ ] Offload CPU transition pre-bake (lookup tables/block sequences); UI only uploads results.
     - Target transitions: Diffuse (block sequences), BlockFlip (grid patterns), Crumble (Voronoi)
     - Extract from: CPU transition implementations in `transitions/` directory
     - Respect: `transitions.durations` per-type overrides, direction settings
     - Tests: `tests/test_transition_worker.py`, `tests/test_transition_worker_settings.py`
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

**Related Modules**: `rendering/gl_state_manager.py`, `rendering/gl_compositor.py`, `widgets/spotify_bars_gl_overlay.py`, `rendering/gl_error_handler.py`, `rendering/transition_controller.py`, `rendering/transition_state.py`

**Action Steps (order)**
1. **Backups**
   - [ ] Snapshot GL compositor/overlays/transition controller modules.
     - Backup to: `/bak/rendering/`, `/bak/widgets/`
     - Include: README documenting pre-GLStateManager integration state
2. **GLStateManager Rollout**
   - [ ] Apply to `widgets/spotify_bars_gl_overlay.py`, GL warmup paths, legacy overlays; validate READY→ERROR→DESTROYING transitions.
     - Replace: `_gl_initialized` flags with `GLStateManager.transition(READY)`
     - Gate: `paintGL()` and `resizeGL()` behind `self.is_gl_ready()`
     - Register: All GL handles (programs, VAOs, VBOs, textures) with `ResourceManager`
     - Follow: 12-phase plan in `audits/GL_STATE_MANAGEMENT_REFACTORING_GUIDE.md`
     - Tests: `tests/test_gl_state_manager_overlay.py`, `tests/test_gl_resource_tracking.py`
3. **Transition Controller Alignment**
   - [ ] Ensure `rendering/transition_controller.py` uses TransitionStateManager for CPU + GL; enforce `snap_to_new=True` cleanup.
     - Use: `TransitionStateManager` from `rendering/transition_state.py`
     - Audit: All `cleanup()` and `stop()` methods in `transitions/` directory
     - Ensure: `compositor.cancel_current_transition(snap_to_new=True)` everywhere
     - Tests: `tests/test_transition_state_manager.py`, `tests/test_transition_snap_to_new.py`
4. **Watchdog & Telemetry**
   - [ ] Standardize watchdog hooks; correlate `[PERF] [GL COMPOSITOR]` with worker queue latency once shared-memory feeds textures.
5. **Failure Paths & Visual Regression**
   - [ ] Tests for shader compile fail, lost context, demotion (Group A→B→C).
     - Integrate: `GLErrorHandler` singleton for session-level demotion
     - Implement: Group A→B→C fallback policy (shader → compositor → software)
     - Tests: `tests/test_gl_state_manager_demotion.py`, `tests/test_gl_error_handler.py`
   - [ ] Snapshot/visual regressions confirming final frame correctness.
     - Verify: Final frame at progress=1.0 matches target image exactly
     - Test: All transition types (Crossfade, Slide, Wipe, Diffuse, BlockFlip, etc.)
     - Tests: `tests/test_transition_visual_regression.py`
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

**Related Modules**: `rendering/widget_manager.py`, `rendering/widget_factories.py`, `rendering/widget_positioner.py`, `widgets/base_overlay_widget.py`, `ui/settings_dialog.py`, `core/settings/settings_manager.py`, `core/settings/models.py`

**Action Steps (order)**
1. **Backups**
   - [ ] Snapshot widget manager/factories/positioner/settings UI modules.
     - Backup to: `/bak/rendering/`, `/bak/widgets/`, `/bak/ui/`, `/bak/core/settings/`
     - Include: README documenting pre-modularization state
2. **WidgetManager Slim-Down**
   - [ ] Remove widget-specific conditionals; rely on factories + positioner enums; centralize fade/raise API to DisplayWidget.
     - Remove: Direct widget instantiation from `WidgetManager`
     - Use: `WidgetFactoryRegistry.create_widget()` for all widget types
     - Delegate: Positioning to `WidgetPositioner` with `PositionAnchor` enums
     - Target: < 600 LOC, no widget-specific conditionals
     - Tests: `tests/test_widget_manager_slim.py`, `tests/test_widget_factory_integration.py`
3. **Typed Settings Adoption**
   - [x] Replace ad-hoc `settings.get` with models; helper to/from dot-notation; update UI tabs respecting MC vs Screensaver profile separation. ✅ _2026‑01‑01_: WidgetManager + Widgets tab now consume `MediaWidgetSettings`, `RedditWidgetSettings`, and `SpotifyVisualizerSettings`.
   - [x] Capture live-setting reaction requirements (Spotify VIS/Sensitivity) inside the typed model contract so UI sliders always affect running widgets. ✅ _2026‑01‑01_: `WidgetManager._handle_settings_changed` pushes live refresh for Spotify VIS/media/reddit; regression tests cover VIS replay and scrollwheel volume.
   - [x] Document display/monitor toggles as non-destructive updates in typed profiles. ✅ _2026‑01‑01_: Typed models carry monitor selectors; refresh path applies without tearing down DisplayWidget; notes added to Spec/Phase doc.
   - [ ] Audit settings end to end for stragglers, make sure subwidgets inherit style settings where appropriate (when they lack their own exposed in the GUI) check positioning settings for any issues with placement, especially regarding middle/center and stacking.
4. **Overlay Geometry & Padding Alignment**
   - [ ] Implement BaseOverlayWidget visual-padding helpers and padding-aware `_update_position()` as outlined in `audits/WIDGET_LIFECYCLE_REFACTORING_GUIDE.md` (Phase 5b).
   - [ ] Migrate WeatherWidget first, validate pixel shift + stacking in all anchors, and add regression coverage.
   - [ ] Roll the helper out to Media/Reddit/Spotify widgets (or document exceptions) with guideline + Index updates.
4. **Modal Settings Conversion**
   - [ ] **Canonical defaults sweep (pre-modal work):** Apply the checklist in `audits/setting manager defaults/Setting Defaults Guide.txt` to ensure Screensaver vs MC SST exports map cleanly into SettingsManager defaults. Confirm reset-to-defaults adheres to the guide before the modal dialog rework.
     - Files: `audits/setting manager defaults/SRPSS_Settings_Screensaver.sst`, `SRPSS_Settings_Screensaver_MC.sst`
     - Verify: `core/settings/defaults.py` `get_default_settings()` covers all SST values
     - Tests: `tests/test_settings_defaults_parity.py`
   - [ ] Convert the existing settings dialog workflow into the modal version referenced in Spec.md, ensuring it can be launched from both SRPSS and MC builds without forcing an engine restart.
     - Maintain: Custom title bar from existing `SettingsDialog`
     - Add: "no sources" popup with Just Make It Work/Ehhhh options (uses `ui/styled_popup.py`)
     - Tests: `tests/test_settings_modal_workflow.py`, `tests/test_settings_no_sources_popup.py`
   - [ ] Wire modal lifecycle to `SettingsManager` signals so changes apply live; document how Just Make It Work/Ehhhh flow integrates with the modal dialog.
     - Wire: `settings_changed` signal to `DisplayWidget` refresh
     - Wire: Widget config updates (Spotify VIS, media, reddit) via `WidgetManager._handle_settings_changed`
   - [ ] Verify that monitor toggles, widget enablement, and queue/source changes raised through the modal path keep DisplayWidget running (no teardown/re-init).
     - Ensure: `DisplayWidget` handles monitor changes without teardown
     - Verify: `SettingsManager` application name mapping ("Screensaver" vs "Screensaver_MC")
     - Tests: `tests/test_settings_profile_separation.py`
5. **Overlay Guidelines Audit**
   - [ ] Verify alignment/fade/resource registration per Docs/10_WIDGET_GUIDELINES.md across all widgets and `ui/widget_stack_predictor.py`.
6. **Tests & Docs**
   - [ ] Expand `tests/test_widget_factories.py`, `tests/test_widget_positioner.py`, add lifecycle/UI binding integration tests.
   - [ ] Update `Spec.md`, `Index.md`, `Docs/TestSuite.md`; capture post-change `/bak`.
7. **Exit**
   - [ ] WidgetManager < 600 LOC, no widget-specific logic; guideline compliance documented.

### Phase 5 – MC Specialization & Layering (Eco Mode)
**Objectives**
- Add window layering control for MC builds and automatic performance gating.

**Related Modules**: `rendering/display_widget.py`, `widgets/context_menu.py`, `main_mc.py`, `rendering/transition_controller.py`, `widgets/beat_engine.py`

**Action Steps (order)**
1. **Window Layering Control**
   - [ ] Implement toggle for window Z-order layering in `rendering/display_widget.py`.
     - Implement: `set_always_on_top(bool)` method
     - Use: Qt window flags (Qt.WindowStaysOnTopHint)
     - Persist: Choice in MC-specific settings profile
   - [ ] Add context menu entry in `widgets/context_menu.py` (restricted to MC builds).
     - Gate: Only visible when `is_mc_build()` returns True
     - Menu: "On Top / On Bottom" toggle
   - [ ] Ensure internal widget Z-order is preserved across layering changes.
     - Preserve: Widget Z-order managed by `WidgetManager`
     - Tests: `tests/test_mc_layering_mode.py`
2. **Visibility Detection**
   - [ ] Implement coverage detection algorithm (threshold: 95% occlusion).
     - Create: `VisibilityMonitor` in `rendering/` directory
     - Use: OS-level window events (Win32 API or Qt screen intersection)
     - Log: Visibility state changes with `[MC]` prefix
   - [ ] Hook into OS-level window events to detect when SRPSS/MC is buried.
     - Tests: `tests/test_mc_visibility_detection.py`
3. **Eco Mode Implementation**
   - [ ] Implement automatic "Eco Mode" that pauses transitions and visualizer updates when covered.
     - Create: `EcoModeManager` to coordinate pausing
     - Pause: `TransitionController` (hold current frame)
     - Pause: `SpotifyBeatEngine` (halt FFT and bar updates)
     - Pause: `ImageQueue` prefetching (optional, measure benefit)
     - Resume: All paused components immediately when visibility > 5%
   - [ ] Ensure Eco Mode is strictly gated (never triggers when "On Top" is active).
     - Gate: Eco Mode only active when layering is "On Bottom"
     - Log: `[MC] [ECO MODE]` activation/deactivation events
     - Tests: `tests/test_mc_eco_mode.py`, `tests/test_mc_eco_mode_recovery.py`
4. **Tests & Telemetry**
   - [ ] Add `tests/test_mc_layering_mode.py` covering multi-monitor overlap.
   - [ ] Log activation/deactivation effectiveness in telemetry.

### Phase 6 – Observability, Performance, Documentation (Ongoing)
**Objectives**
- Keep telemetry, tests, docs, and backups current across phases.

**Related Modules**: All modules across `core/`, `rendering/`, `widgets/`, `transitions/`, `sources/`

**Action Steps (repeated each phase)**
1. **Perf Baselines**
   - [ ] Run harness per `Docs/PERFORMANCE_BASELINE.md`; record dt_max/avg_fps/memory per transition/backend.
     - Use: `SRPSS_PERF_METRICS=1` environment variable
     - Run: `tests/test_frame_timing_workload.py` with `FrameTimingHarness`
     - Record: dt_max, avg_fps, memory, VRAM per transition/backend
     - Compare: v1.x vs v2.0 improvements
2. **Regression Tests**
   - [ ] Add/adjust pytest for workers, GL demotion, widget lifecycle; maintain rotating pytest log per Windows guide.
     - Worker tests: `tests/test_*_worker.py` series
     - GL tests: `tests/test_gl_state_manager*.py`, `tests/test_gl_error_handler.py`
     - Widget tests: `tests/test_widget_manager*.py`, `tests/test_widget_lifecycle*.py`
     - Integration tests: `tests/test_integration_full_workflow.py`
3. **Documentation Hygiene**
   - [ ] Update `Index.md`, `Spec.md`, `Docs/TestSuite.md`, and this audit with status + feature parity before/after.
     - Index.md: Add `core/process/` supervisor and worker modules
     - Spec.md: Update worker process architecture, GLStateManager, modal settings, MC features
     - TestSuite.md: Add all new test files from Phases 1-6, update counts
     - PERFORMANCE_BASELINE.md: Record final v2.0 metrics
4. **Backups**
   - [ ] `/bak` snapshots for every important module touched; include short README per snapshot.
     - Backup structure: `/bak/<module_path>/` with README explaining pre-change state
     - Include: Timestamp and phase number in README
     - Example: `/bak/widgets/beat_engine.py` with README documenting pre-workerization FFT pipeline
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
