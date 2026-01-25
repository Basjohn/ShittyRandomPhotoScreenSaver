# 2.6 Action Plan (Full Detail Edition)

> This is the single authoritative plan that merges **every** item from the active Sanity Audit and **all** sections of `Docs/Feature_Investigation_Plan.md` (0–12). Nothing has been shortened—each entry retains its goals, research notes, references, module callouts, checklists, and pitfalls. Work proceeds phase-by-phase; do not skip ahead unless explicitly approved. Status legend: `[ ]` pending, `[~]` in progress, `[x]` complete.

---

## Phase Ordering & Conflict Review

- **Phase 0 prerequisites every other phase.** Logging/ThreadManager/ResourceManager fixes must land before UI phases so later timers, GL resources, and overlays have deterministic cleanup paths. No downstream tasks re-introduce raw managers; each phase references centralized modules explicitly.
- **Phase 1 (StyledPopup + timer policy) feeds Phase 3 widget work.** All widget/shadow/fade initiatives assume dialogs already share the same chrome and that inline QTimers have been migrated to ThreadManager helpers. Phase 3 checklists point back to the same modules to avoid duplicate cleanup.
- **Phase 2 (sources/RSS guard) must finish before Phase 5 (media/RSS extensions).** Items like Reddit priority or AlphaCoders feed reuse the same queue + dedupe improvements introduced in 2.2–2.4, so Phase 5 explicitly depends on the completed groundwork.
- **Phase 3 precedes Phase 4 purposely.** WidgetManager/shadow/visualizer stability comes before adding new transition controls or GL-heavy presets so we do not regress overlay fade ordering.
- **Phase 6/7 remain trailing documentation/monitoring passes.** Every phase now references Spec/Index/TestSuite touchpoints to prevent documentation drift; audits are updated after each phase per Usage Note #3.

No contradictory instructions remain: each checklist cites a single owning module set, and downstream phases reference upstream deliverables (e.g., Phase 5.3 explicitly “after Phase 2’s UI priority work”). If scope changes introduce new dependencies, add them here before modifying lower phases.

---

## Phase 0 – Core & Infrastructure Hardening

Stabilize logging, threading, resource ownership, settings/schema alignment, and event plumbing so downstream features are built on solid ground.

### 0.1 Logging & Diagnostics
**Goal:** Make logging lifecycle predictable and documented so repeated init/shutdown cycles do not leak handlers or write logs to phantom directories.  
**Current State / Findings:**  
- `setup_logging()` is re-entrant but only partially tears down handlers, causing duplicated file descriptors when toggled.  
- `_FORCED_LOG_DIR` / `_ACTIVE_LOG_DIR` semantics are unclear (see `@core/logging/logger.py#45-67`), leading to discrepancies when logging is disabled.  
- Colored console formatter assumes TTY, spamming escape codes in redirected logs.  
- `.perf.cfg` and `.logging.cfg` files produced by build scripts are undocumented in Spec/Style guides.  
**Modules:** `@core/logging/logger.py#45-67`, `@core/logging/logger.py#632-680`, build scripts writing cfg files, `Docs/Spec.md`, `Docs/STYLE_GUIDELINES.md`, `Index.md`, `/logs`, `/audits`, `/Docs` ad-hoc leaf files.  
**Checklist:**  
- [x] Tear down existing handlers before reinitializing and clearly document lifecycle.
  - **AC:** No duplicate file descriptors after 3 setup/teardown cycles
  - **Test:** `tests/test_logging_lifecycle.py::test_repeated_setup_teardown`  
- [x] Clarify forced/active log dir semantics and raise/log when logging is disabled but helpers are invoked.  
- [x] Auto-disable ANSI coloring when `stdout` is not a terminal.  
- [x] Describe `.perf.cfg` / `.logging.cfg` generation and expected values in Spec + Style guide.  
- [ ] Ensure build outputs reference the same contract (ties to Phase 6 tooling tasks).  
- [ ] Cull redundant high-volume logs (e.g., `[PERF][MEDIA_FEEDBACK]`, widget paint spam) and gate remaining diagnostics behind `SRPSS_PERF_METRICS` so normal runs stay quiet while still allowing synchronized-event instrumentation.  
**Pitfalls:** Avoid double-writing logs or silently discarding them; ensure documentation covers frozen builds vs dev builds.

### 0.2 ThreadManager & ResourceManager
**Goal:** Guarantee every thread-related resource is tracked, cancellable, and observable.  
**Current State / Findings:**  
- `_UiInvoker` and futures/timers are instantiated without ResourceManager registration.  
- Mutation queue silently drops entries without counter metrics.  
- `cleanup_all()` runs even when invoked off the UI thread, risking deadlocks.  
**Modules:** `@core/threading/manager.py`, `@core/resources/manager.py`, `@core/threading/types.py`, `@core/resources/types.py`, `@tests/test_thread_manager.py`, `@tests/test_resource_manager.py`.  
**Checklist:**  
- [x] Register UI thread dispatch futures returned by `invoke_in_ui_thread()` with ResourceManager so cancellation propagates; unregister when complete.  
  - **Code Reference:** `@core/threading/manager.py#_UiInvoker class`  
- [x] Surface queue drop counts via `inspect_queues()` returning `Dict[str, Dict[str, int]]` with keys `{pool_name: {dropped: N, pending: M}}` and expose to tests/logs.  
  - **AC:** Emit WARNING when drops exceed threshold (>10/minute)  
- [x] Enforce UI-thread cleanup: marshal `cleanup_all()` to the main thread via `ThreadManager.invoke_in_ui_thread(blocking=True, timeout=5s)` or warn + abort when called elsewhere.  
  - **AC:** Deadlock prevention - timeout after 5s and log ERROR if cleanup incomplete  
- [x] Provide deterministic single-shot helper that respects QApplication lifecycle (per audit).  
  - **API:** `ThreadManager.single_shot_ui(delay_ms, callback)` helper
  - **Behavior:** Cancellable, respects QApplication lifecycle, auto-cleanup
  - **AC:** Callback not invoked after QApplication.quit()
  - **Test:** `tests/test_thread_manager_phase02.py::test_single_shot_ui_*`  
**Pitfalls:** Do not rely on GC finalizers; explicit unregister is required to avoid zombie entries.

### 0.3 Settings Authority
**Goal:** Align defaults, schema, and runtime manager to prevent cache blow-ups and key drift.  
**Current State:**  
- Cache keys use `id(default)`, resulting in misses and unbounded growth.  
- Flattened defaults reintroduce conflicting key paths (e.g., `display.mode`).  
- `set_many` emits change signals for each key, overwhelming UI.  
- SettingsManager never registers with ResourceManager; repeated instantiations leak QSettings handles.  
**Modules:** `@core/settings/defaults.py`, `@core/settings/schema.py`, `@core/settings/settings_manager.py`, docs referencing settings.  
**Checklist:**  
- [x] Remove `id(default)` cache keying; adopt per-key sentinel strategy with eviction.  
- [x] Align schema names with defaults and ensure flattening respects canonical path. Document in Spec/Index.  
- [x] Add batch update context that emits a single aggregated signal.  
- [x] Register SettingsManager with ResourceManager and clean change handlers on destruction.  
**Pitfalls:** Ensure Presets and Spec tables are updated simultaneously; mismatched docs create regressions.

### 0.4 Event System
**Goal:** Prevent subscription leaks and clamp history/recursion depth reliably.  
**Findings:** Subscriptions never auto-unsubscribe, `_publish_depth` grows per-thread, and history cannot be disabled (privacy risk).  
**Modules:** `@core/events/event_system.py`.  
**Checklist:**  
- [x] Provide RAII/context-managed subscription objects that auto unsubscribe.  
  - **API:** `EventSystem.scoped_subscription()` returns `ScopedSubscription` context manager
- [x] Purge `_publish_depth` entries even when exceptions occur; use `try/finally`.  
  - Already implemented in existing code
- [x] Add option to disable history or redact payloads; document in Spec.  
  - **API:** `EventSystem(history_enabled=False, redact_payloads=True)`
  - **API:** `set_history_enabled()`, `set_redact_payloads()` runtime toggles
**Pitfalls:** Ensure thread safety when modifying subscription map while publishing.

### 0.5 Engine / Rendering Foundations
**Goals:** Clean teardown and GL resource tracking.  
**Findings:**  
- ScreensaverEngine double-emits `stopped`, keeps ProcessSupervisor alive during settings dialog, and doesn’t store subscription IDs.  
- DisplayManager creates ad-hoc ResourceManagers, leaving hotplug signals connected post-cleanup.  
- GL compositor and DisplayWidget instantiate GL managers/textures without ResourceManager tracking.  
**Modules:** `@engine/screensaver_engine.py`, `@engine/display_manager.py`, `@rendering/gl_compositor.py`, `@rendering/display_widget.py`.  
**Checklist:**  
- [x] Capture subscription IDs, unsubscribe on cleanup, ensure timers/workers shut down once.  
  - **Implementation:** `_subscription_ids` list in ScreensaverEngine, `_unsubscribe_all_events()` method
- [x] Inject ResourceManager/ThreadManager dependencies; disconnect Qt signals and document lifetimes.  
  - **Implementation:** `_disconnect_monitor_signals()` in DisplayManager, signal disconnects in `_unsubscribe_all_events()`
- [x] Register GL resources (program caches, textures, geometry) with ResourceManager and free deterministically.  
**Pitfalls:** Avoid raw `QTimer` usage inside engine; align with ThreadManager policy.

---

## Phase 1 – UI Shell, Dialog Consistency, and QuickNotes Governance

Enforce a single popup chrome (StyledPopup), remove raw timers, sync QSS + Style Guide, and document deferred widgets.

### 1.1 StyledPopup Adoption
**Goal:** Every dialog (settings, toasts, popups, tooling) uses the frameless StyledPopup that mimics “Export Complete”.  
**Current State:** Custom classes (`NoSourcesPopup`, `ResetDefaultsDialog`) duplicate drop shadows/title bars, diverging from spec.  
**Modules:** `@ui/settings_dialog.py`, `@ui/tabs/*`, `@widgets/*`, `@main.py`, tooling dialogs, `@ui/styled_popup.py`.  
**Checklist:**  
- [x] Replace bespoke dialogs and any `QMessageBox` remnants with `StyledPopup.show_*` helpers.  
  - **Implementation:** Removed `ResetDefaultsDialog` class, replaced with `StyledPopup.show_success`
  - **Implementation:** Removed unused `reset_notice_label` and QTimer for auto-dismiss
- [x] Centralize button definitions (labels, values, defaults) so confirmations share copy and layout.  
- [x] Update doc references banning `QMessageBox` and ad-hoc dialog frames.  
**Pitfalls:** Ensure popups triggered from background threads marshal via ThreadManager to UI thread.

### 1.2 Timer Policy
**Goal:** No raw `QTimer.singleShot` in UI code; timers should either be registered with ResourceManager or scheduled via ThreadManager.  
**Modules:** `@ui/settings_dialog.py` (toast auto-dismiss, RSS helpers), `@ui/tabs/sources_tab.py` (folder scan debounce), `@widgets/media_widget.py`, `@widgets/spotify_visualizer_widget.py` (ghost timers), `@rendering/widget_manager.py`.  
**Checklist:**  
- [x] Replace toast/auto-dismiss timers with ThreadManager helpers; register any remaining QTimers.  
  - **Implementation:** Replaced settings_dialog reset notice with StyledPopup (has internal auto-close)
  - **Status:** sources_tab.py has no QTimer usages; media_widget.py uses OverlayTimerHandle for registration
- [ ] Document pattern in Style Guide and enforce via tests.  
**Pitfalls:** Many modules create timers before QApplication exists—add guards or no-ops with warnings to avoid crashes. Avoid sprinkling per-widget timers; prefer shared `ThreadManager.invoke_in_ui_thread(delay=...)` helpers tied into ResourceManager groups so widget teardown automatically cancels them.

### 1.3 Theming & Documentation
**Goal:** Align `themes/dark.qss` and Style Guide with StyledPopup + shared palette.  
**Checklist:**  
- [ ] Clean up duplicate selectors, add StyledPopup-specific rules, convert hard-coded RGBA values into shared tokens.  
- [ ] Expand Style Guide section 5 with concrete selectors, layout margins, icon glyph references, and behavior rules.  
- [ ] Cross-reference in Feature Plan so future requests cite this canonical implementation.  
**Pitfalls:** Keep theme changes scoped; avoid regressing other widgets by touching unrelated selectors.

### 1.4 Tests & QuickNotes
- [ ] Extend `tests/test_settings_dialog.py` (and other UI suites) to ensure StyledPopup usage, asynchronous operations, and ResourceManager cleanup.  
- [ ] Document QuickNotes widget deferral (Feature Plan §0): status 🚫, revisit trigger “storage/hover backlog reduced”. Keep note visible so future phases know it remains intentionally deferred.

---

## Phase 2 – Sources Tab Responsiveness, RSS Priority & Dedupe, “5 Images” START UP ONLY (Including from Settings GUI) Guard

Implement the in-depth plan from Feature Investigation §8 while resolving audit issues in sources modules.

### 2.1 Responsive Sources Tab
**Goal:** Folder scans, cache clears, RSS refreshes must not block the settings dialog.  
**Checklist:**  
- [x] Move heavy operations to ThreadManager IO pool; surface progress via EventSystem (with optional progress modal).  
  - **Implementation:** `_on_clear_rss_cache_clicked` uses async file counting and deletion
  - **Implementation:** `_on_just_make_it_work_clicked` uses async cache clear before applying feeds
  - **Implementation:** Buttons show progress state ("Counting...", "Clearing...", "Setting up...")
- [x] Keep buttons enabled/disabled appropriately and allow cancellation when possible.  
  - **Implementation:** Buttons disabled during async operations, re-enabled on completion
**Pitfalls:** Ensure ThreadManager single-shot is not invoked before QApplication instantiation.

### 2.2 Priority Display (Multi-select CANCELLED per user)
**Goal:** Priority = list order; display "Priority #" labels. Multi-select batch operations are cancelled - "Remove All" button handles this.  
**Details:**  
- Priority equals list order; label rows with "Priority #".
- Keep numbering current after reorder/add/remove.
- Reddit sources: priority applies within Reddit feeds only (rate-limit aware), not across source types  
**Modules:** `@ui/tabs/sources_tab.py`, `@engine/screensaver_engine.py`, `@core/settings/settings_manager.py`, `Spec.md`.  
**Checklist:**  
- [x] Display priority numbers in the UI (delegate or suffix).  
  - **Implementation:** `[1]`, `[2]` prefixes via `_load_sources()`, `_refresh_list_priorities()`
- [x] Persist ordering in settings; ensure "Just Make It Work" writes feeds sorted by desired priority.  
- [x] Update tooltips/docs to explain priority semantics.  
**Note:** Reddit source can gain priority over other Reddit sources but not non-Reddit sources due to rate limiting.

### 2.3 Cache & Dedupe Unification
**Goal:** Consolidate the multiple dedupe layers (engine queue, `RSSPipelineManager.record_images`, worker cache, disk cache).  
**Modules:** `@core/rss/pipeline_manager.py`, `@engine/screensaver_engine.py`, `@sources/rss_source.py`  
**Checklist:**  
- [x] Map all dedupe checkpoints and pick a single owner (likely pipeline manager).  
  - **Implementation:** `RSSSource._download_image()` now uses `_pipeline.record_keys()` 
  - **Implementation:** `RSSSource._load_cached_images()` tracks via central `_pipeline`
  - **Status:** `RssPipelineManager` is now the single dedupe authority
- [x] Broadcast generation tokens on cache clears so workers stop referencing stale `_cached_urls`.  
  - **Implementation:** `_generation` counter in `RssPipelineManager`, incremented in `clear_cache()`
  - **Implementation:** `generation` property for workers to check staleness
- [x] Instrument dedupe decisions (per feed) for diagnostics.  
  - **Implementation:** `is_duplicate(log_decision=True)` parameter for verbose logging  
**Pitfalls:** Do not expand manifest size; consider probabilistic filters only if measured collision risk is low. All resets must run through ThreadManager (no UI blocking).  

### 2.4 "5 Images" Startup Guard (START UP ONLY - Including from Settings GUI)
**Details:** Screensaver must not launch in RSS-only mode until at least five images are downloaded; once guard is satisfied, downloads continue asynchronously. Hybrid mode may fall back to local sources. This guard applies at startup AND when triggered from Settings GUI operations.  
**Modules:** `@engine/screensaver_engine.py`, `@core/rss/pipeline_manager.py`, UI actions ("Clear Cache", "Remove All", "Just Make It Work").  
**Checklist:**  
- [x] Implement RSSStartupGuard class with target=5, pause/resume hooks
  - **Status:** `_wait_for_min_rss_images()` implements guard; default updated to 5
- [x] When guard active, UI-triggered operations should only fetch five synchronous images before returning control.  
- [x] Emit guard start/stop events and add telemetry for startup latency.  
  - **Status:** `RSS_GUARD_SATISFIED` event emitted with elapsed time
- [x] Tests: extend `tests/test_screensaver_engine_rss_seed.py` to assert guard behavior and hybrid bypass.  
**Pitfalls:** Ensure guard cooperates with cache clears mid-download; resets should keep the 5-image limit. Avoid raw timers; rely on ThreadManager scheduling.  

### 2.5 Reddit Rate Limits & Research
**From Feature Plan:** Document current Reddit activity windows and rate limits (8 req/min confirmed). Ensure UI priority interplay doesn't stall entire queue when Reddit feeds are throttled. Add research notes to Spec.  
**Modules:** `@core/reddit_rate_limiter.py` (if exists), `@sources/rss_source.py`  
**Checklist:**  
- [x] Document current 8 req/min limit in Spec.md Sources section
  - **Implementation:** Added Reddit Rate Limiting section with all constants and behavior
- [x] Test backoff behavior when limit exceeded
  - **Status:** `tests/test_reddit_rate_limiter.py` covers rate limit enforcement, backoff, thread safety
- [x] Verify priority processing doesn't block non-Reddit sources
  - **Status:** Reddit priority=10 (lowest), non-Reddit sources fetched first  

---

## Phase 3 – Widgets, Shadows, Fade Coordination, Weather & Reddit Options, Pixel Shift

Implement Feature Plan sections 3–7 alongside audit findings.

### 3.1 Drop Shadow System Review (Feature Plan §3)
**Goal:** Migrate to central `ShadowFadeProfile`, reduce QGraphicsEffect overhead, and document canonical shadow profiles.  
**Modules:** `@widgets/shadow_utils.py`, `@widgets/shadow_utils_old.py`, `@widgets/reddit_widget.py`, `@widgets/media_widget.py`, `@widgets/spotify_visualizer_widget.py`, `@widgets/weather_widget.py`, `@ui/settings_dialog.py`, `@Docs/10_WIDGET_GUIDELINES.md`, `@Docs/STYLE_GUIDELINES.md`.  
**Checklist:**  
- [ ] Enumerate all `QGraphicsDropShadowEffect` usages (including `shadow_utils_old`).  
- [ ] Define card vs badge profiles (radius 8px/4px, offsets, alpha).  
- [ ] Prototype GL overlay shadow strips (Spotify card) to avoid effect corruption; cache strips as 9-slice textures rather than per-frame QGraphicsEffect blur.  
- [ ] Update Docs/10_WIDGET_GUIDELINES.md + Style Guide with diagrams, offset values, and references to Qt performance research [^1][^2][^9].  
- [ ] Capture before/after perf metrics (paint cost, FPS) to prove new profiles do not regress overlay budgets.  
**Pitfalls:** Keep fade-sync logic intact; ensure new profiles integrate with `ShadowFadeProfile`. Qt’s own docs note that `QGraphicsDropShadowEffect` re-blurs every frame in device coordinates, so sharing a cached pixmap or shader-generated strip is mandatory on low-power GPUs. When integrating with GL overlays, register the new textures with ResourceManager to avoid leaks.

### 3.2 WidgetManager Reliability
**Modules:** `@rendering/widget_manager.py`, `@rendering/display_widget.py`, `@widgets/base_overlay_widget.py`, `@widgets/spotify_volume_widget.py`, `@widgets/spotify_visualizer_widget.py`.  
- [ ] Register/unregister widgets, timers, and fade callbacks with ResourceManager; disconnect compositor signals on teardown.  
- [ ] Document expected overlay/fade handshake so widgets know when to register (Widget Guidelines §10, Spec Overlay chapter).  
- [ ] Ensure `WidgetManager.request_overlay_fade_sync()` order is deterministic so Phase 3.3 tests have a stable contract.  

### 3.3 Spotify Volume Widget Fade Coordination (Feature Plan §4)
**Checklist:**  
- [ ] Add guarded log verifying `request_overlay_fade_sync("spotify_volume")` is invoked before fade start.  
- [ ] Ensure `add_expected_overlay()` happens before anchor widget triggers the fade.  
- [ ] Add regression test (`tests/test_widget_fade_sync.py`) simulating volume/visualizer handshake.  

### 3.4 Spotify Visualizer Enhancements (Feature Plan §5)
**Goal:** Ship new GLSL visualizer modes (morphing waveform ribbon, DNA helix, radial bloom, spectrogram ribbon, phasor particle swarm) without altering the existing Spectrum mode implementation or performance envelope.  
**Requirement:** Spectrum bar mode remains untouched; all new work layers on top of the current FFT pipeline and widget plumbing.  

**Shared Constraints & Defaults:**  
- Maintain the current card footprint (width/height, padding, chrome) unless the user toggles the new “Vertical orientation,” in which case geometry rotates and DisplayWidget repositions the overlay.  
- Reuse existing settings infrastructure @widgets/spotify_visualizer_widget.py#1-948, overlay chrome @widgets/spotify_bars_gl_overlay.py#1-151, and FFT plumbing @widgets/spotify_visualizer/beat_engine.py#1-314.  
- Introduce `spotify_visualizer.mode` (default `spectrum`). Presets: `Cinematic` → helix, `Artistic` → waveform. Each mode gains scoped defaults (e.g., `helix.twist=1.0`, `waveform.ribbon_thickness=0.35`, `phasor.particle_count=128`).  
- Add per-mode settings for thickness, twist, history depth, particle count, etc., surfaced in Widgets tab along with a vertical orientation toggle and any auxiliary controls (opacity multipliers, ribbon offset).  

**Performance Considerations vs Spectrum:**  
- Morphing Waveform Ribbon: ~parity (reuse existing VBO, single strip; CPU overhead negligible).  
- DNA Helix: ~1.2× shader cost due to dual curve calculations but still within present shader complexity.  
- Radial Bloom: Equal when clamped to semicircle; full radial (vertical orientation) is ~1.1× fragment load.  
- Spectrogram Ribbon: Heavier (history buffer). Limit stored frames to ≤32 and auto-degrade to 16 under GPU pressure.  
- Phasor Particle Swarm: Comparable if particle count = bar count × 4; default 128 particles to match current fill rate.  

| Mode | Description | External Inspiration |
| --- | --- | --- |
| Morphing Waveform Ribbon | Mirror waveform that morphs in place (no scrolling) while preserving card bounds. | TimArt/3DAudioVisualizers[^3] |
| DNA Helix | Dual helices twisting with amplitude and optional slow Z scroll (“growth”). | ShaderToy `dtl3Dr`[^4] |
| Radial Bloom | Clamp GLava’s radial shader into a semicircle (horizontal) or full circle (vertical orientation). | GLava radial module[^5] |
| Spectrogram Ribbon | Stack recent FFT frames as translucent ribbon layers above/below bars. | Stanford CCRMA OpenGL viz[^6] |
| Phasor Particle Swarm | Replace solid bars with particle emitters along the same x positions; swirling phasor trails capture beats. | PAV “Phasor”[^7] |

**Reference Assets & Docs:**  
- Morphing Waveform Ribbon – capture still from TimArt animated example, store interim PNG under `%TEMP%\visualizer_refs\waveform.png`, commit final asset to `Docs/assets/visualizer_modes/morph_waveform.png` with caption + link to TimArt GitHub README.  
- DNA Helix – ShaderToy `dtl3Dr` has both shader source and preview; save preview frame (`Docs/assets/visualizer_modes/dna_helix.png`) + include author credit + license snippet from ShaderToy.  
- Radial Bloom – GLava gallery screenshots (radial module) + official docs (https://github.com/wacossusca34/glava/wiki); capture semicircle frame for horizontal default and full radial for vertical mode.  
- Spectrogram Ribbon – Stanford CCRMA Sound Visualization lab posts include sample renders; capture single frame plus annotate color scale usage (store as `spectrogram_ribbon.png`).  
- Phasor Particle Swarm – PAV “Phasor” YouTube demo + GitHub README assets; capture top-down frame showing particle emitters; note particle counts + easing functions.  
All assets must be documented in `Docs/Spec.md` Appendix (visualizer references) with source URLs and image licensing notes. Until final images ship, keep raw references in `%TEMP%\visualizer_refs` and note TODO in Spec.

**FFT Worker & Data Flow:**  
- Existing `SpotifyVisualizerAudioWorker` already pushes mono frames through the ProcessSupervisor FFT worker; no new worker is required. Instead, extend the worker payload to return both magnitude bars and optional time-domain history (`history_buffer`, `phase_samples`).  
- Modes needing additional data: Spectrogram Ribbon (history of freq frames ≤32), Morphing Waveform (time-domain waveform), Phasor Swarm (phase differentials). Plan to reuse the same FFT worker by adding opt-in flags per mode so it emits cached FFT bins + raw waveform window in one message.  
- Update TripleBuffer schema to include `fft_bins`, `waveform_slice`, and `history_ring`. UI thread selects whichever subset each GLSL program needs. Keep ghosting/adaptive sensitivity logic centralized so Spectrum + new modes read the same normalization constants.  
- Document worker changes in `Docs/TestSuite.md` (headless FFT tests) and ensure the ProcessSupervisor budget covers slightly larger payloads (still under 64 KB per frame).

**Implementation Steps:**  
1. Add `spotify_visualizer.mode` enum + per-mode settings (thickness, twist, particle count, history depth) + vertical orientation toggle in Widgets tab UI; ensure config persists in `core/settings/defaults.py`, `core/settings/models.py`, and presets.  
2. Implement GLSL programs for each mode under `widgets/spotify_visualizer/*`, sharing buffers with Spectrum wherever possible; capability detection should fall back to Spectrum whenever GL requirements fail (session-scoped demotion only).  
3. Update DisplayWidget / overlay layout so card rotation + padding adjustments respect orientation toggle without breaching ShadowFadeProfile constraints.  
4. Update presets (`Cinematic` helix defaults, `Artistic` waveform) and document tables in Spec/Index.  

**Per-Mode Implementation Notes:**  
- Morphing Waveform Ribbon – Use mirrored triangle strip with dynamic thickness; drive vertical displacement from time-domain waveform while tinting via FFT-derived energy. Reference TimArt shader for morph math, but clamp vertex count to existing VBO (reuse 64 vertices).  
- DNA Helix – Two instanced helices rendered via geometry shader; amplitude maps to helix radius, twist factor driven by setting `helix.twist`. Add optional Z scroll uniform (0 = static).  
- Radial Bloom – Render using polar coordinates: sample FFT bins, convert to angle/length pairs; horizontal orientation clamps to 180° arc, vertical orientation unlocks full 360°.  
- Spectrogram Ribbon – Maintain history buffer texture (≤32 rows). Each frame uploads latest FFT magnitudes into a scrolling 2D texture for ribbon shader to sample. Provide degradation path (downsample to 16 frames) when GPU load detected.  
- Phasor Particle Swarm – Spawn particles anchored to bar centers; GPU instancing handles per-particle angular velocity derived from FFT phase. Cap default particle count at 128, allow up to 256 via settings if `SRPSS_PERF_METRICS` indicates sufficient headroom.  
Include external references (GLava wiki, ShaderToy source, CCRMA lab notes, PAV repo) directly in Spec footnotes for reproducibility.

**Testing & Telemetry:**  
- Headless GL smoke tests to initialize each mode (mock GL context) and assert no errors.  
- Config persistence tests covering mode switches + preset application (ensure `config.json` writing is stable).  
- GL uniform budget snapshot tests comparing each mode vs Spectrum to ensure no unexpected uniform uploads/VBO allocations.  
- Guard any new performance logging behind `SRPSS_PERF_METRICS`; reuse `screensaver_perf.log` pipeline.  

**Card Sizing & Layout:**  
- Keep default card width identical to Spectrum so existing placements stay valid, but allow per-mode Y-growth up to +25% (and X-growth in vertical orientation) via new settings `widgets.spotify_visualizer.additional_height` / `.additional_width_vertical`.  
- Extend `WidgetManager` layout helpers so card bounding boxes can expand while preserving anchor margins; update Widget Guidelines to call out maximum safe growth before overlapping other overlays.  
- Verify new orientation paths respect pixel shift + fade coordination: orientation toggle should trigger a layout recalculation before fade-in so the compositor never reveals partially clipped geometry.

**Modules / References:** `widgets/spotify_visualizer_widget.py`, `widgets/spotify_bars_gl_overlay.py`, `widgets/spotify_visualizer/*`, `ui/tabs/widgets_tab.py`, `core/settings/defaults.py`, `core/settings/models.py`, `Spec.md`, `Docs/Feature_Investigation_Plan.md`, `tests/visualizer/*`.  

**Pitfalls:** Maintain existing ghosting/adaptive sensitivity logic across modes (shared helpers); never mutate Spectrum shader/perf caps; capability detection must demote once per session (no per-call silent fallbacks); ensure vertical orientation keeps card bounds consistent with Widget Guidelines.  

### 3.5 Weather Widget – Animated SVG Icons (Feature Plan §6) 
**Goal:** Replace text-only widget with animated SVG icons using `QSvgRenderer`.  
**Checklist:**  
- [x ] Promote to QWidget + QHBoxLayout (text column + icon container) so layout alignment is reliable.  
- [x ] Load icons via `QSvgRenderer`, set `framesPerSecond`, and connect `repaintNeeded` to `update()` (no extra timers).  
- [x ] Add settings for `widgets.weather.icon_scale` and animation toggle (defaults documented).  
- [x ] Maintain small LRU cache (≤6 renderers) and pause animations during transitions.  
- [x ] Map provider condition codes to `images/weather/manifest.json`.  
- [x ] Tests: throttle repaint signal counts, ensure caching works, update `tools/download_weather_icons.py` if needed.  
**Pitfalls:** Do not spawn extra threads; rely on renderer’s animation driver. Document fallback to static icons when animation disabled.  
**Status/Notes (Jan 25):** Detail row now emits fallback metrics (cached or 0%) whenever the provider omits rain/humidity/wind, so the layout never collapses even under degraded data. Keep this behavior when the SVG overhaul lands so degraded payloads stay visually consistent (screenshots in §3 requirements).

### 3.6 Reddit Widget Options & Header Parity (Feature Plan §7 + §7.1) 
**Checklist:**  
- [x ] Rename “Exit when Reddit links opened” to “Open When Reddit Links Are Clicked”; add “Copy Clicked Reddit Links To Clipboard” checkbox.  
- [x ] Enforce mutual exclusivity except on MC builds (where both can be enabled); reuse `self._mc_build` gating.  
- [x ] Update click handler (`rendering/display_widget.py`) to set clipboard text before executing action.  
- [x ] Migrate settings key (`widgets.reddit.exit_on_click` → `widgets.reddit.open_on_click`) with `SettingsManager.validate_and_repair()` shim. Update presets + Spec tables.  
- [x ] Add header frame toggle/styling parity with Spotify widget; update Widget Guidelines to require header frame options for all widgets with headings/logo.  
- [x ] Tests: `tests/ui/test_widgets_tab.py` for mutual exclusivity + persistence.  
**Pitfalls:** Ensure tooltip text adheres to Style Guide (no inline QSS). Document MC vs normal builds difference.  
**Modules:** `ui/tabs/widgets_tab.py`, `widgets/reddit_widget.py`, `rendering/display_widget.py`, `core/settings/defaults.py`, `Spec.md`, `Docs/10_WIDGET_GUIDELINES.md`. Ensure settings migration touches `SettingsManager.validate_and_repair()` and `core/presets.py`.

### 3.7 Pixel Shift Boundary Enforcement (Feature Plan §7.2) 
- [x ] Audit `DisplayWidget._apply_pixel_shift()` to clamp overlay rects within `screen_geometry.adjusted(margins)`.  
- [x ] Provide per-widget bounding boxes via WidgetManager (notify overlays when geometry shifts).  
- [x ] Add regression test simulating max pixel shift deltas on multi-monitor setups to ensure widgets remain fully visible.  
- [x ] Update Widget Guidelines (positioning section) with pixel-shift constraints.  

### 3.8 Media Widget Feedback Sync & Fade (New)
**Goal:** Finish the EventSystem broadcast path so every MediaWidget (all screens) reacts in lockstep to hardware keys, and retune the highlight fade so it looks like a smooth, single animation rather than per-widget timers fighting.  
**Current Findings:**  
- WM_APPCOMMAND now publishes `EventType.MEDIA_CONTROL_TRIGGERED`, and MediaWidget clones share a single animation driver (class timer + shared event cache). Logging shows identical event IDs/timestamps per clone.  
- Auto/manual guard logic still needs verification when broadcast feedback lands during fade-in, but baseline highlight synchronization now matches across displays.  
**Checklist:**  
- [x ] Instrument `_publish_media_control_action` / `_handle_media_control_event` with shared event IDs + `[PERF][MEDIA_FEEDBACK]` grouping so logs confirm synchronized delivery (per Phase 0 logging cleanup).  
- [x ] Introduce a shared animation driver (single timer or ThreadManager callback) for all MediaWidget clones; store control feedback timestamps in a shared struct keyed by event ID instead of each widget keeping its own timer.  
- [x ] When hardware/manual triggers arrive, reuse the shared timestamp and skip `_controls_feedback.clear()` so repaint diffing doesn’t blank the card on one display.  
- [ ] Ensure fade-in/out state (`_fade_in_completed`, `_has_seen_first_track`) is updated atomically when broadcast feedback arrives so the secondary display doesn’t slip back into hidden state.  
- [x ] Add regression tests (`tests/test_media_widget.py`) to simulate hardware broadcasts and assert both widgets trigger `_trigger_controls_feedback` once, with identical timestamps.  
- [ ] Update Spec/Docs to describe the broadcast contract (hardware → EventSystem → shared driver) and mention the fade guard for multi-display setups.  
**Pitfalls:** Avoid spinning up new per-widget timers; use ThreadManager/ResourceManager so teardown stays deterministic. Verify logging stays gated by `SRPSS_PERF_METRICS`.

---

## Phase 4 – Transitions & Display Enhancements (Feature Plan §2)

Deliver all transition/UI enhancements plus DisplayWidget hygiene items.

### 4.1 Image Cache Slider (Feature Plan §2.1)
- [ ] Raise `cache.max_items` default to 30 (min 30, max 100). Add slider + spinbox near RSS cache controls, persist via SettingsManager, and trigger cache/prefetcher reinit without restart.  
- [ ] Update presets (Performance, Balanced) to 60/90 respectively and document in Spec/Index.  
- [ ] Ensure ThreadManager handles heavy reinit work to avoid UI freezes.  

### 4.1 Transition Controls
**Blinds Feather Control (§2.2):**  
- [ ] Slider (0–10) shown when Blinds selected; thread value through TransitionFactory to GL shader uniform.  
- [ ] Clamp for software renderer fallback; update presets and docs.  

**Particle Direction Disable (§2.3):**  
- [ ] `_update_particle_mode_visibility()` should disable direction combo when mode == Converge, preserving stored value for other modes.  
- [ ] Document in Spec preset table.  

**3D Block Spins Enhancements (§2.4):**  
- [ ] Extend direction enum for diagonal travel, add sheen toggle, axis blending, and random mode caching so repeated transitions honor user choice.  
- [ ] Update shader to support new directions and add capability gate for GL < 3.3.  
- [ ] Presets: Cinematic uses “Diagonal TL→BR” with high sheen.  

**Peel Transition Options (§2.5):**  
- [ ] Add slice-width slider, diagonal directions, motion-blur toggle; gate via `_refresh_hw_dependent_options()` so non-GL builds hide controls.  
- [ ] Update shader uniforms and documentation.  

**Block Puzzle Flip Direction Matrix (§2.6):**  
- [ ] Extend shared direction enum with `BlockPuzzleDirection` (Up/Down/Left/Right/Diagonal TL→BR/Diagonal TR→BL/Center Burst/Random).  
- [ ] Show direction combo only for Block Puzzle Flip; persist random choice per rotation, update TransitionFactory + GL shader uniforms, add CPU fallback for software renderer.  
- [ ] Tests: extend `tests/test_transition_state_manager.py` and related suites to cover new enumeration.  

### 4.2 Display/Rendering Hygiene
- [ ] Align documentation of `_render_strategy_manager` fallback with actual behavior; ensure software renderer downgrade path is deterministic.  
- [ ] Document (or plan) DisplayWidget refactor to separate input, overlay, and eco mode responsibilities as per audit.  

---

## Phase 5 – Input, Media Integration, RSS Extensions, QuickNotes Re-entry

Execute Feature Plan §1, §12, and remaining media/widget items after earlier phases are stable.

### 5.1 Global Media Key Passthrough (Feature Plan §1)
**Goal:** Media keys always invoke OS actions (play/pause/next/volume) across all builds; no suppression.  
**Current State:**  
- `InputHandler.handle_key_press()` returns `False` when `_is_media_key`, but `DisplayWidget.keyPressEvent()` still accepts the event, blocking OS passthrough.  
- Tests currently confirm suppression (behavior to invert).  
**Settings Defaults / Presets:**  
- Introduce `input.media_keys.passthrough_enabled = True` in defaults and ensure MC preset matches. Document in Spec keybinding table.  
**Modules:** `@rendering/display_widget.py`, `@rendering/input_handler.py`, `@core/engine/input_hooks.py`, `@core/settings/defaults.py`, `@tests/test_media_keys.py`, `Spec.md`.  
**Checklist:**  
- [ ] Update `DisplayWidget.keyPressEvent()` to `event.ignore()` when `_is_media_key` returns `False` so OS receives event.  
- [ ] Review `nativeEventFilter` (Index: `core/engine/input_hooks.py`) to ensure WM_APPCOMMAND isn’t consumed prematurely.  
- [ ] Add optional helper `platform/win32/media_passthrough.py` to replay WM_APPCOMMAND when fullscreen focus still blocks keys; gate fallback commands via setting.  
- [ ] Add default/preset entry + Spec table updates; ensure Standard, Minimal, MC builds align.  
- [ ] Extend `tests/test_media_keys.py` to assert passthrough and absence of unintended exits.  
**Pitfalls:** Avoid double-triggering actions; respect “exit on any key” logic and ensure MC vs Saver builds both behave correctly.

### 5.2 Spotify Volume Telemetry
- [ ] Ensure perf harness obeys `SRPSS_PERF_METRICS`; logging toggles should not spam production logs.  
- [ ] Add metrics summary to perf docs/harness as per audit.  

### 5.3 Reddit Priority Beyond RSS
- [ ] After Phase 2’s UI priority work, confirm Reddit widget + presets/docs reflect new ordering, especially for “Just Make It Work” and future priority-based features.  

### 5.4 AlphaCoders / RSS HTML Feeds (Feature Plan §12)
**Goal:** Determine feasibility of pulling curated AlphaCoders galleries into RSS/JSON pipeline.  
**Unknowns:** Endpoint availability, rate limits/ToS, API keys, CDN link resolution, attribution rules.  
**Checklist:**  
- [ ] Research AlphaCoders developer docs/forums for RSS/JSON endpoints; if none, prototype HTML parser (requests + selectolax) extracting `{title, image_url, source_url}`.  
- [ ] Decide whether to extend `RSSSource` (virtual feeds) or create `AlphaCodersSource`.  
- [ ] Evaluate caching impact (4K images) and ThreadManager budget for multi-MB downloads.  
- [ ] Document findings in Spec (Sources section) and update Feature Plan status.  
**Pitfalls:** Must respect licensing/attribution. Significant size may require adjusted cache policies.  

### 5.5 QuickNotes Re-entry
- [ ] Once Settings UI backlog shrinks and storage constraints are handled, revisit QuickNotes widget (Feature Plan §0). Document new scope, dependencies, and gating criteria.  

---

## Phase 6 – Documentation, Testing, and Tooling

Keep docs/tests/tools synchronized with implementation.

### 6.1 Documentation Sync
- [ ] Update `Docs/Spec.md`, `Index.md`, `Docs/Feature_Investigation_Plan.md`, and `audits/SanityAudit.md` whenever new settings/modules ship.  
- [ ] Refresh `Docs/10_WIDGET_GUIDELINES.md` and `Docs/STYLE_GUIDELINES.md` with: shadow profiles, header frame policy, tooltip conventions, pixel shift constraints, StyledPopup selectors, timer policy, Spotify/Weather widget instructions.  
- [ ] Maintain Feature Investigation doc as living record—sections should note when work moves into action plan or completes.  

### 6.2 TestSuite & New Suites
- [ ] `Docs/TestSuite.md` must catalog new suites: thread contention, fade coordination, weather SVG timing, visualizer mode snapshots, RSS guard tests, etc., plus PowerShell invocation snippets per policy.  
- [ ] Implement referenced test files (`tests/perf/test_thread_manager_contention.py`, `tests/ui/test_fade_coordination.py`, `tests/widgets/test_weather_icons.py`, `tests/visualizer/test_modes.py`, etc.).  

### 6.3 Tooling & Scripts
- [ ] **`scripts/build_nuitka.ps1`:** add venv awareness, `--skip-install` flag, helper payload checksum validation, doc references for `.perf.cfg`/`.logging.cfg`, safer SCR rename (warn before deleting signed binary).  
- [ ] **`tools/run_tests.py`:** limit `__pycache__` purges (scope by path or make opt-in), detect missing `tests/pytest.py`, lock log rotation for concurrent runs.  
- [ ] **`tools/perf_integration_harness.py`:** respect ResourceManager/ThreadManager policies, avoid global env mutations, share timer helpers with main app.  
- [ ] **Metrics parsers/log parser:** unify parsing/stat helpers between Spotify VIS & slide metrics scripts; allow config-driven keyword categories for overlay log parser; tie scripts to perf/log env docs.  
- [ ] **Visualizer/overlay harnesses:** expose public APIs (no poking private attributes), register widgets with ResourceManager, consolidate FFT/intensity helper code.  

---

## Phase 7 – Monitoring, Future Widgets, Continuous Auditing

Long-range coordination once core work is complete.

- [ ] **Future Widget Program:** Maintain `Docs/Future_Widget_Plans.md` for Imgur, Flickr, ArtStation, Tumblr, etc., ensuring prerequisites (shadow centralization, WidgetManager cleanup, perf harnesses) are satisfied before implementation.  
- [ ] **RSS HTML Scrape Feasibility:** Continue AlphaCoders/offline feed research, update plan with blockers or schedule once Phase 2 stabilizes.  
- [ ] **Audit Trail:** After finishing each phase, append findings/resolutions to `audits/SanityAudit.md` and track new risks.  

---

## References
[^1]: Qt Forum – “why program is so laggy after using QGraphicsDropShadowEffect.”  
[^2]: *Performance and Solutions for QWidget::setGraphicsEffect()* – warns against per-widget effects.  
[^3]: TimArt, *3D Audio Visualizers* (GitHub) – waveform inspiration.  
[^4]: ShaderToy `dtl3Dr` – DNA helix visualization.  
[^5]: GLava radial shader – basis for radial bloom mode.  
[^6]: Stanford CCRMA, *Sound Visualization with OpenGL* – spectrogram ribbon reference.  
[^7]: Processing Audio Visualization (PAV) “Phasor” – particle swarm inspiration.  
[^8]: Qt 6.8 `QSvgRenderer` docs – animated SVG guidance.  
[^9]: Qt Docs – *QGraphicsDropShadowEffect* (Qt 6.8) – notes per-frame blur cost and device-coordinate offsets, reinforcing the need for cached/custom shadows.  

---

### Usage Notes
1. Always pull work from the **lowest-numbered** phase with unfinished items.  
2. Update checklist status inline with notes when scope changes; never remove context.  
3. Mirror completions in Spec/Index/TestSuite + audits immediately.  
4. Treat this document as the single source of truth—new discoveries should be added to the appropriate phase or a new phase, not scattered elsewhere.

--------------------------------------------
SUGGESTIONS BOX 
--------------------------------------------
This special area below this patch of text will be known as the suggestions box.
You will be able to add suggestions freely for the developer/user/other agents to check as worth investigating/implementing'
and are encouraged to do so regularly. The user/developer will also place suggestions here.
All suggestions must have two checkboxes. Only once the user/developer checks at least one can it be removed from the box and placed into the action plan where appropriate.
2 checks means implement, 1 check means investigate and add to medium/low priority tasks if deemed valuable. Examine the box during every doc update. If any suggestions are made obviously redundant, remove them
Keep this box tidy and ordered. IT IS NOT A CHANGE LOG. Pre place checkboxes even without suggestions for convienence, in space allocated. If suggestions exist without check boxes, reformat them to have them.
##################################################################
## - [x] [ ] Examine that multiple visualizers do not do multiple work. Media is always a clone, central work to avoid performance issues is key.
## - [x] [ ] Check what visualizer FPS limitations/caps are, how they function with vsync, whether altering these would improve smoothness or performance.
## - [x] [ ] Many alignment issues in media card when on main_mc ONLY (ADDRESSED IN PHASE 3.8)
## - [x] [x] Clean up logging significantly! (ADDRESSED IN PHASE 0.1)
##
##
##
##
##
##
##
##
##
##
##
##
###################################################################