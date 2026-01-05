# SRPSS v2.0 Development Roadmap (Live Checklist)

**Status**: Active development roadmap integrating Minor Tasks, AAMP2026 phases, and architectural improvements.

**Policy**: Document-first, test-driven, centralized managers, no regressions. Follow checkbox order unless explicitly redirected.

---

## Phase 0: Foundation & Quick Wins (Completed Jan 2026)
- [x] **0.1 Visualizer Gating**: Halted FFT processing when Spotify != PLAYING; preserved dynamic floor logic. (Tests: `tests/test_spotify_visualizer_integration.py`).
- [x] **0.2 Positioning Audit**: Verified all 9 anchors; fixed TOP_CENTER/MIDDLE missing coverage. (Tests: `tests/test_widget_positioning_comprehensive.py`).
- [x] **0.3 Settings Persistence**: Implemented multi-monitor aware geometry save/restore in `SettingsDialog`.
- [x] **0.4 Double-Click Nav**: Added double-click "Next Image" to `InputHandler` with interaction gating. (Tests: `tests/test_double_click_navigation.py`).
- [x] **0.5 Volume Passthrough**: System volume keys now pass through to OS in MC mode. (Tests: `tests/test_media_keys.py`).
- [x] **0.6 Smart Positioning**: Visualizer auto-aligns below MediaWidget when both use TOP anchors. (Tests: `tests/test_visualizer_smart_positioning.py`).
- [x] **0.7 Regression Fixes**: Fixed `MediaWidget` position normalization (coerce logic) and resolved model/GUI string mismatches.

## Phase 1: Process Isolation Foundations (Week 3-4)

### 1.1 Architecture Design & Contracts
**Priority**: High (Foundation for multiprocessing)
**Dependencies**: Phase 0 complete
**Reference**: `audits/AAMP2026_Phase_1_Detailed.md`
**Related Modules**: `core/threading/manager.py`, `core/resources/manager.py`, `core/events/event_system.py`

- [x] **Worker Contract RFC**: Finalize worker roles and responsibilities ✅ _2026-01-05_
  - [x] ImageWorker: decode/prescale with `path|scaled:WxH` cache keys
    - Integrates with: `utils/image_cache.py`, `utils/image_prefetcher.py`, `rendering/image_processor.py`
  - [x] RSSWorker: fetch/parse/mirror with validated ImageMetadata
    - Integrates with: `sources/rss_source.py`, `sources/base_provider.py`
  - [x] FFTWorker: loopback ingest + smoothing + ghost envelopes
    - Integrates with: `widgets/beat_engine.py`, `widgets/spotify_visualizer_widget.py`
  - [x] TransitionPrepWorker: CPU precompute payloads
    - Integrates with: `rendering/transition_factory.py`, `transitions/base_transition.py`
- [x] **Message Schemas**: Define immutable request/response formats ✅ _2026-01-05_
  - [x] Common fields: seq_no, correlation_id, timestamps, payload_size
  - [x] Size caps per channel with rejection logic
  - [x] No Qt objects across process boundaries
- [x] **Shared Memory Schema**: RGBA/FFT headers with generation tracking ✅ _2026-01-05_
  - Coordinate with: `core/resources/types.py` for resource type definitions
- [x] **Process Supervisor Skeleton**: `core/process/` API surface ✅ _2026-01-05_
  - [x] start/stop/restart methods
  - [x] Health monitoring with heartbeat/backoff
  - [x] Settings gates for worker enable/disable
  - Integrates with: `core/resources/manager.py` for lifecycle tracking
- [x] **Queue & Backpressure Rules**: Non-blocking poll, drop-old policy ✅ _2026-01-05_
- [x] **Testing Strategy Design**: Worker simulators with failure injection ✅ _2026-01-05_

**Tests Required**:
- [x] `tests/test_process_supervisor.py` - Supervisor lifecycle, heartbeat, restart logic ✅ 33 tests passing
- [x] `tests/test_worker_contracts.py` - Message schema validation, size caps (integrated into test_process_supervisor.py)
- [x] `tests/test_shared_memory.py` - RGBA/FFT header generation tracking (integrated into test_process_supervisor.py)
- [ ] `tests/helpers/worker_sim.py` - Deterministic worker simulators (deferred to Phase 2)

### 1.2 Visualizer Logic Preservation
**Priority**: CRITICAL (No regression)
**Dependencies**: Phase 0.1 complete
**Reference**: `audits/VISUALIZER_DEBUG.md`, `audits/AAMP2026_Phase_2_Detailed.md` lines 25-94
**Related Modules**: `widgets/beat_engine.py`, `widgets/spotify_visualizer_widget.py`, `widgets/spotify_bars_gl_overlay.py`

- [x] **Create visualizer baseline test**: Capture current `_fft_to_bars` behavior ✅ exists
  - Document: `np.log1p`, `np.power(1.2)`, convolution kernel `[0.25, 0.5, 0.25]`
  - Document: Recommended sensitivity multiplier (0.285), resolution boost damping
  - Document: Profile template (15-element array), center-out gradient formula
- [x] **Document exact FFT pipeline**: Preserve all mathematical operations ✅ in VISUALIZER_DEBUG.md
  - Smoothing tau values: `tau_rise = base_tau * 0.35`, `tau_decay = base_tau * 3.0`
  - Alpha calculations: `1.0 - math.exp(-dt / tau)`
  - Dynamic floor: `floor_mid_weight`, `dynamic_floor_ratio`, headroom/hardness
- [ ] **Snapshot beat engine**: `/bak/widgets/beat_engine.py` before worker migration
- [x] **Verify synthetic test**: Ensure `tests/test_visualizer_distribution.py` passes ✅ exists
- [x] **Create preservation test**: Assert FFT output matches current implementation ✅ exists (needs worker init fix)

**Tests Required**:
- [ ] `tests/test_visualizer_baseline.py` - Capture exact `_fft_to_bars` output for known inputs
- [ ] `tests/test_visualizer_preservation.py` - Verify worker output matches baseline pixel-perfect
- [ ] `tests/test_beat_engine_math.py` - Unit tests for smoothing, floor, sensitivity calculations

---

## Phase 2: Pipeline Offload Implementation (Week 5-6)

### 2.1 Image Worker Implementation
**Priority**: High (Performance foundation)
**Dependencies**: Phase 1 complete
**Reference**: `audits/AAMP2026_Phase_2_Detailed.md`
**Related Modules**: `utils/image_cache.py`, `utils/image_prefetcher.py`, `rendering/image_processor.py`, `engine/image_queue.py`

- [x] **Port decode/prescale**: Move to worker with shared-memory output ✅ _2026-01-05_
  - Extract logic from: `ImagePrefetcher._prefetch_task()` (decode)
  - Extract logic from: `ImageProcessor.process_image()` (prescale)
  - Integrate with: `ImageCache` for `path|scaled:WxH` key insertion
- [x] **Preserve cache semantics**: Maintain `path|scaled:WxH` key strategy ✅ _2026-01-05_
  - Coordinate with: `ScreensaverEngine._load_image_task()` for cache lookup
- [ ] **Ratio policy enforcement**: Local vs RSS mix preserved
  - Respect: `ImageQueue.set_local_ratio()` and `has_both_source_types()`
- [ ] **Integration tests**: End-to-end latency validation
- [ ] **Performance baselines**: Record before/after metrics

**Tests Required**:
- [x] `tests/test_image_worker.py` - Worker decode/prescale correctness ✅ 11 tests passing
- [ ] `tests/test_image_worker_cache.py` - Cache key strategy parity
- [ ] `tests/test_image_worker_latency.py` - End-to-end latency < 100ms
- [ ] `tests/test_image_worker_ratio.py` - Local/RSS ratio enforcement

### 2.2 RSS Worker Implementation
**Priority**: High (Content pipeline)
**Dependencies**: Phase 1 complete
**Reference**: `audits/AAMP2026_Phase_2_Detailed.md`
**Related Modules**: `sources/rss_source.py`, `sources/base_provider.py`, `engine/screensaver_engine.py`

- [x] **Move fetch/parse**: RSS/JSON processing in worker ✅ _2026-01-05_
  - Extract logic from: `RSSSource.refresh()`, `_fetch_feed()`, `_parse_reddit_json()`
  - Preserve: Priority system (Bing=95, Unsplash=90, Wikimedia=85, NASA=75, Reddit=10)
  - Preserve: Per-source limits (8 images per source per cycle)
- [ ] **Disk mirror integration**: Maintain rotation rules and TTL
  - Preserve: `sources.rss_save_to_disk`, `sources.rss_save_directory` settings
  - Preserve: Cache cleanup (min_keep=20, rotating cache size)
- [ ] **Metadata validation**: Ensure ImageMetadata integrity
  - Validate: `ImageSourceType.RSS`, URL, title, timestamp, priority
- [ ] **Error handling**: Non-blocking with graceful degradation
  - Integrate with: `ScreensaverEngine._load_rss_images_async()` shutdown callback

**Tests Required**:
- [x] `tests/test_rss_worker.py` - Fetch/parse correctness for RSS/Atom/Reddit JSON ✅ 12 tests passing
- [ ] `tests/test_rss_worker_mirror.py` - Disk mirroring and rotation
- [ ] `tests/test_rss_worker_metadata.py` - ImageMetadata validation
- [ ] `tests/test_rss_worker_priority.py` - Priority system preservation

### 2.3 FFT/Beat Worker Migration
**Priority**: CRITICAL (Preserve visualizer fidelity)
**Dependencies**: Phase 1 complete, visualizer baseline captured
**Reference**: `audits/VISUALIZER_DEBUG.md`, `audits/AAMP2026_Phase_2_Detailed.md` lines 25-94
**Related Modules**: `widgets/beat_engine.py`, `widgets/spotify_visualizer_widget.py`, `core/media/media_controller.py`

- [x] **Extract FFT pipeline**: Move `_SpotifyBeatEngine` compute to worker ✅ _2026-01-05_
  - Extract: `BeatEngine._process_audio_frame()`, `_fft_to_bars()`, `_apply_smoothing()`
  - Preserve: Noise floor subtraction (2.1), dynamic range expansion (2.5)
  - Preserve: Smoothing (0.3), decay rate (0.7), center-out gradient
- [x] **Preserve exact math**: All operations from VISUALIZER_DEBUG.md must match ✅ _2026-01-05_
  - Snapshot: `/bak/widgets/beat_engine.py` before changes
  - Document: All numpy operations (log1p, power, convolve)
  - Document: Sensitivity calculations (recommended vs manual)
- [ ] **Maintain smoothing**: Rise/decay tau, dynamic floor, adaptive sensitivity
  - Preserve: `tau_rise = base_tau * 0.35`, `tau_decay = base_tau * 3.0`
  - Preserve: Dynamic floor (ratio 1.05, alpha 0.05), manual override (0.12-4.00)
- [ ] **Triple buffer integration**: Non-blocking UI consumption
  - Use existing: `TripleBuffer` from `widgets/spotify_visualizer_widget.py`
- [ ] **Synthetic test rerun**: Verify worker output matches baseline exactly
- [ ] **Performance validation**: Ensure dt_max independence

**Tests Required**:
- [x] `tests/test_fft_worker.py` - Worker FFT processing correctness ✅ 13 tests passing
- [ ] `tests/test_fft_worker_preservation.py` - Exact math preservation vs baseline
- [ ] `tests/test_fft_worker_smoothing.py` - Tau, floor, sensitivity calculations
- [ ] `tests/test_fft_worker_latency.py` - Non-blocking UI consumption, dt_max < 100ms

### 2.4 Transition Precompute Worker
**Priority**: Medium (Transition performance)
**Dependencies**: Phase 1 complete
**Reference**: `audits/AAMP2026_Phase_2_Detailed.md`
**Related Modules**: `rendering/transition_factory.py`, `transitions/base_transition.py`, `rendering/gl_compositor.py`

- [x] **CPU precompute offload**: Lookup tables, block sequences ✅ _2026-01-05_
  - Target transitions: Diffuse (block sequences), BlockFlip (grid patterns), Crumble (Voronoi)
  - Extract from: CPU transition implementations in `transitions/` directory
- [ ] **Settings integration**: Honor duration/direction overrides
  - Respect: `transitions.durations` per-type overrides
  - Respect: `transitions.slide.direction`, `transitions.wipe.direction`
  - Respect: `transitions.diffuse.block_size`, `transitions.diffuse.shape`
- [ ] **Deterministic seeding**: Preserve randomization behavior
  - Preserve: `transitions.random_choice`, `transitions.pool` filtering
  - Preserve: Non-repeating direction selection logic

**Tests Required**:
- [x] `tests/test_transition_worker.py` - Precompute correctness for each transition type ✅ 11 tests passing
- [ ] `tests/test_transition_worker_settings.py` - Duration/direction override respect
- [ ] `tests/test_transition_worker_determinism.py` - Seeding and randomization preservation

---

## Phase 3: GL Compositor & Transition Reliability (Week 7-8)

### 3.1 GLStateManager Rollout
**Priority**: High (GL stability)
**Dependencies**: Phase 2 complete
**Reference**: `audits/GL_STATE_MANAGEMENT_REFACTORING_GUIDE.md`, `audits/AAMP2026_Phase_3_Detailed.md`
**Related Modules**: `rendering/gl_state_manager.py`, `rendering/gl_compositor.py`, `widgets/spotify_bars_gl_overlay.py`, `rendering/gl_error_handler.py`

- [x] **Apply to overlays**: `widgets/spotify_bars_gl_overlay.py`, GL warmup paths ✅ _2026-01-05_
  - Replace: `_gl_initialized` flags with `GLStateManager.transition(READY)` ✅
  - Gate: `paintGL()` and `resizeGL()` behind `self.is_gl_ready()` ✅
  - Register: All GL handles (programs, VAOs, VBOs, textures) with `ResourceManager`
- [ ] **State transitions**: READY→ERROR→DESTROYING validation
  - Implement: State change callbacks for telemetry
  - Track: Transition history for debugging
- [ ] **Centralized error handling**: GLStateManager emits, compositor responds
  - Integrate: `GLErrorHandler` singleton for session-level demotion
  - Implement: Group A→B→C fallback policy
- [ ] **Integration tests**: GL demotion scenarios (Group A→B→C)

**Tests Required**:
- [x] `tests/test_gl_state_manager_overlay.py` - Overlay state transitions ✅ 21 tests passing
- [ ] `tests/test_gl_state_manager_demotion.py` - Group A→B→C fallback scenarios
- [ ] `tests/test_gl_resource_tracking.py` - ResourceManager GL handle registration
- [ ] `tests/test_gl_error_handler.py` - Session-level error handling

### 3.2 Transition Controller Alignment
**Priority**: High (Transition reliability)
**Dependencies**: Phase 3.1 complete
**Reference**: `audits/AAMP2026_Phase_3_Detailed.md`
**Related Modules**: `rendering/transition_controller.py`, `rendering/transition_state.py`, `rendering/gl_transition_renderer.py`

- [ ] **TransitionStateManager integration**: CPU + GL parity
  - Use: `TransitionStateManager` for all transition types
  - Integrate: State change notifications for overlay visibility
- [ ] **Enforce snap_to_new=True**: All cleanup paths
  - Audit: All `cleanup()` and `stop()` methods in `transitions/` directory
  - Ensure: `compositor.cancel_current_transition(snap_to_new=True)` everywhere
- [ ] **Watchdog standardization**: Per-transition telemetry
  - Integrate: `TransitionController` watchdog with `[PERF]` logging
  - Track: Transition type, duration, frames, dt_max per transition
- [ ] **Visual regression tests**: Final frame correctness
  - Verify: Final frame at progress=1.0 matches target image exactly
  - Test: All transition types (Crossfade, Slide, Wipe, Diffuse, etc.)

**Tests Required**:
- [ ] `tests/test_transition_state_manager.py` - State management for all transition types
- [ ] `tests/test_transition_snap_to_new.py` - Verify snap_to_new=True enforcement
- [ ] `tests/test_transition_watchdog.py` - Watchdog timeout handling
- [ ] `tests/test_transition_visual_regression.py` - Final frame correctness

### 3.3 Visualizer Smart Positioning
**Priority**: Medium (User experience)
**Dependencies**: Phase 0.2 complete
**Related Modules**: `rendering/widget_positioner.py`, `rendering/widget_manager.py`, `widgets/spotify_visualizer_widget.py`

- [x] **Detect top position conflicts**: Visualizer + media widget using top anchors
- [x] **Calculate smart offset**: Place visualizer below media with same padding
- [ ] **Handle edge cases**: Media disabled, different monitors
  - Test: Visualizer positioning when media widget disabled
  - Test: Different monitor selections for media vs visualizer
  - Test: Media widget position changes while visualizer active
- [x] **Update WidgetPositioner**: Integrate smart positioning logic
- [ ] **Test all combinations**: All position scenarios
  - Test: All 9 anchor positions for media widget
  - Test: Visualizer auto-positioning for each media anchor

**Tests Required**:
- [x] `tests/test_visualizer_smart_positioning.py` - Basic smart positioning
- [ ] `tests/test_visualizer_positioning_edge_cases.py` - Media disabled, monitor mismatches
- [ ] `tests/test_visualizer_positioning_comprehensive.py` - All anchor combinations

---

## Phase 4: Widget & Settings Modularity (Week 9-10)

### 4.1 WidgetManager Slim-Down
**Priority**: High (Architectural cleanup)
**Dependencies**: Phase 3 complete
**Reference**: `audits/AAMP2026_Phase_4_Detailed.md`
**Related Modules**: `rendering/widget_manager.py`, `rendering/widget_factories.py`, `rendering/widget_positioner.py`, `widgets/base_overlay_widget.py`

- [x] **Remove widget-specific logic**: Delegate to factories + positioner ✅ _2026-01-05_
  - Remove: Direct widget instantiation from `WidgetManager`
  - Use: `WidgetFactoryRegistry.create_widget()` for all widget types
  - Delegate: Positioning to `WidgetPositioner` with `PositionAnchor` enums
- [x] **Minimal API**: fade/raise/start/stop coordination only ✅ _2026-01-05_
  - Retain: `request_overlay_fade_sync()`, `invalidate_overlay_effects()`
  - Retain: `initialize_widget()`, `activate_widget()`, `deactivate_widget()`, `cleanup_widget()`
- [x] **Factory integration**: WidgetFactoryRegistry for creation ✅ _2026-01-05_
  - Use: `ClockWidgetFactory`, `WeatherWidgetFactory`, `MediaWidgetFactory`, etc.
  - Extract: Shadow config via `WidgetFactory.extract_shadow_config()`
- [x] **ResourceManager lifecycle**: Centralized cleanup ✅ _2026-01-05_
  - Register: All widgets with `ResourceManager` for deterministic cleanup
- [x] **Lock-free patterns**: Document any unavoidable locks ✅ _2026-01-05_
  - Review: `_lifecycle_lock` in `BaseOverlayWidget`
  - Document: QTimer.singleShot for UI-thread deferred execution (acceptable per Qt model)

**Tests Required**:
- [x] `tests/test_widget_manager.py` - Lifecycle suite (20 tests) ✅ _2026-01-05_
- [ ] `tests/test_widget_factory_integration.py` - All widgets created via registry
- [ ] `tests/test_widget_lifecycle_coordination.py` - Initialize/activate/deactivate/cleanup flow

### 4.1b Overlay Geometry & Padding Alignment
**Priority**: High (Widget consistency)
**Dependencies**: Phase 4.1 in progress
**Reference**: `audits/WIDGET_LIFECYCLE_REFACTORING_GUIDE.md` (Phase 5b), `Docs/10_WIDGET_GUIDELINES.md`
**Related Modules**: `widgets/base_overlay_widget.py`, `widgets/weather_widget.py`, `widgets/media_widget.py`, `widgets/reddit_widget.py`

- [x] Add BaseOverlayWidget visual-padding helpers + padding-aware `_update_position()`. ✅ _2026-01-05_
  - Implement: `set_visual_padding(top, right, bottom, left)` method
  - Implement: `_compute_visual_offset()` for all 9 anchor positions
  - Add: Padding-aware positioning in `_update_position()` before pixel shift
- [x] Migrate WeatherWidget first, validating all anchors with pixel shift and stacking. ✅ _2026-01-05_
  - Migrated: `_update_position()` now delegates to base class
  - Set: Visual padding via `set_visual_padding()` in constructor
  - Removed: Custom horizontal_margin adjustment logic
- [ ] Extend helper usage to Media/Reddit/Spotify widgets or document justified exceptions.
  - Document: Why certain widgets don't need visual offset (e.g., no chrome)
  - Update: `Docs/10_WIDGET_GUIDELINES.md` with visual offset patterns

**Tests Required**:
- [x] `tests/test_widget_visual_padding.py` - Visual offset calculations ✅ 15 tests passing
- [ ] `tests/test_widget_layouts.py` - All anchors with pixel shift and stacking
- [ ] `tests/test_widget_alignment_consistency.py` - Cross-widget margin alignment

### 4.2 Modal Settings Conversion
**Priority**: High (User experience)
**Dependencies**: Phase 4.1 complete
**Reference**: `audits/AAMP2026_Phase_4_Detailed.md`, `audits/setting manager defaults/Setting Defaults Guide.txt`
**Related Modules**: `ui/settings_dialog.py`, `core/settings/settings_manager.py`, `core/settings/defaults.py`, `core/settings/models.py`

- [ ] **Canonical defaults sweep**: Apply SST guide checklist
  - [ ] Import both SST files and verify SettingsManager parity
    - Files: `audits/setting manager defaults/SRPSS_Settings_Screensaver.sst`, `SRPSS_Settings_Screensaver_MC.sst`
    - Verify: `get_default_settings()` covers all SST values
  - [ ] Ensure MC defaults fall back to available monitor
    - Logic: When display 2 unavailable, MC defaults to display 1
  - [ ] Confirm auto geo detection for weather location
    - Default: `_get_default_image_folders()` pattern for weather geo
  - [ ] Add "no sources" popup with Just Make It Work/Ehhhh as options. Ehhhh closes application.
    - Popup: `ui/styled_popup.py` dark glass theme
    - Logic: Validate sources on startup, show popup if empty
- [ ] **Convert to modal workflow**: Preserve custom title bar/theme
  - Maintain: Custom title bar from existing `SettingsDialog`
  - Ensure: Can be launched from both SRPSS and MC builds
- [ ] **Live updates integration**: SettingsManager signals for instant changes
  - Wire: `settings_changed` signal to `DisplayWidget` refresh
  - Wire: Widget config updates (Spotify VIS, media, reddit)
- [ ] **Non-destructive refresh**: Monitor toggles without engine restart
  - Ensure: `DisplayWidget` handles monitor changes without teardown
- [ ] **Profile separation**: MC vs Screensaver isolation maintained
  - Verify: `SettingsManager` application name mapping ("Screensaver" vs "Screensaver_MC")

**Tests Required**:
- [ ] `tests/test_settings_defaults_parity.py` - SST vs SettingsManager defaults
- [ ] `tests/test_settings_modal_workflow.py` - Modal open/close, live updates
- [ ] `tests/test_settings_no_sources_popup.py` - Popup behavior and choices
- [ ] `tests/test_settings_profile_separation.py` - MC vs Screensaver isolation


### 4.3 Volume Key Passthrough (MC Mode)
**Priority**: Medium (System integration)
**Dependencies**: Phase 4.1 complete
[DEFERRED UNTIL ALL OTHER TASKS COMPLETED AND VERIFIED]
Key related items below require their own extensive documentation Investigation
The cause is related to focus and shadow cache invalidation but most solutions break shadowing
See audits\mc_focus_weather_plan.md for current investigation, tackle this only after every thing else in the roadmap. Make backups, very risky task.
- [ ] Research task online for similiar issues, solutions and failures.
- [ ] **MC mode working keys: Currently MC mode on one display breaks ALL keyboard interaction unless a user opens the right click menu first and then loses it once the user swaps focus and swaps back in. ANY solution for this must not break shadow cache invalidiation mitigations as they are tighly connected. No keys in MC Mode is better than shadow cache corruption. 
- [ ] Add Spacebar Local Hotkey that trigers pause/play in media widget if present.
- [ ] **Spotify volume isolation**: Prevent interference
- [ ] **Test media players**: Various apps and states
- [ ] **Document behavior**: Build-specific differences

---

## Phase 5: MC Build Enhancements (Week 11-12)

### 5.1 Window Layering Control
**Priority**: Medium (MC feature)
**Dependencies**: Phase 4 complete
**Reference**: `audits/AAMP2026_Phase_5_Detailed.md`
**Related Modules**: `rendering/display_widget.py`, `widgets/context_menu.py`, `main_mc.py`

- [x] **Context menu item**: "On Top / On Bottom" (MC builds only) ✅ _2026-01-05_
  - Add: Menu entry in `ScreensaverContextMenu` with `is_mc_build` flag
  - Gate: Only visible when `is_mc_build=True` passed to constructor
  - Persist: Choice in MC-specific settings profile (`mc.always_on_top`)
- [x] **Window layering toggle**: Maintain Z-order hierarchy (preserve internal widget Z-index) ✅ _2026-01-05_
  - Implement: `_on_context_always_on_top_toggled()` in `DisplayWidget`
  - Preserve: Internal widget Z-order managed by `WidgetManager`
  - Use: Qt window flags (Qt.WindowStaysOnTopHint)
- [x] **Visibility detection**: implement 95% opacity/coverage threshold ✅ _2026-01-05_
  - Create: `EcoModeManager` in `core/eco_mode.py`
  - Use: Qt window geometry intersection for occlusion calculation
  - Log: Visibility state changes with `[MC] [ECO MODE]` prefix
- [x] **Eco Mode implementation**: pause transitions and visualizer updates when covered ✅ _2026-01-05_
  - Create: `EcoModeManager` to coordinate pausing
  - Pause: `TransitionController` (hold current frame)
  - Pause: `SpotifyBeatEngine` via `set_eco_mode(True)`
  - Pause: `ImageQueue` prefetching (optional via callbacks)
- [x] **Ensure isolation**: never trigger Eco Mode in "On Top" mode ✅ _2026-01-05_
  - Gate: `set_always_on_top(True)` disables Eco Mode
- [x] **Automatic recovery**: Restore all animations when visibility regained ✅ _2026-01-05_
  - Resume: All paused components via `_deactivate_eco_mode()`
  - Recovery delay: 100ms configurable
- [x] **Logging & Telemetry**: Track Eco Mode activation/deactivation effectiveness ✅ _2026-01-05_
  - Log: `[MC] [ECO MODE]` activation/deactivation events
  - Track: `EcoModeStats` with activations, deactivations, total_eco_time_ms
- [ ] **Multi-monitor testing**: Various configurations and overlap scenarios
  - Test: Partial occlusion on multi-monitor setups
  - Test: Window moved between monitors

**Tests Required**:
- [ ] `tests/test_mc_layering_mode.py` - Layering toggle, Z-order preservation
- [ ] `tests/test_mc_visibility_detection.py` - 95% threshold, multi-monitor
- [x] `tests/test_mc_eco_mode.py` - Pause/resume, isolation from "On Top" ✅ 21 tests passing
- [ ] `tests/test_mc_eco_mode_recovery.py` - No flicker, all animations restored

**Notes**:
- Disable in normal builds (grey out or hide option)
- Consider whether pausing saves more resources and resumes better than heavy fps throttling/limiting
- No GUI toggle for Eco Mode (fully automatic)
- Consider adding performance telemetry for Eco Mode effectiveness

### 5.2 System Tray Enhancements
**Priority**: Low (UX polish)
**Dependencies**: None
**Related Modules**: `ui/system_tray.py`

- [x] **CPU/GPU tooltip**: Show usage stats on hover ✅ _2026-01-05_
  - Implement: Lazy-loaded psutil for CPU, pynvml for GPU
  - Display: "SRPSS | CPU: X% | GPU: Y%" format
  - No perf penalty: Lazy init, only queries on tooltip update
- [ ] **Periodic refresh**: Optional timer-based tooltip updates
  - Consider: Only refresh when tray icon is visible/hovered

### 5.3 Performance Optimization
**Priority**: Medium (Performance refinement)
**Dependencies**: Phase 2 complete
**Reference**: `Docs/PERFORMANCE_BASELINE.md`
**Related Modules**: `core/threading/manager.py`, `rendering/gl_programs/texture_manager.py`, `core/resources/manager.py`

- [x] **Worker latency tuning**: Optimize queue sizes and backpressure ✅ _2026-01-05_
  - Created: `core/process/tuning.py` with per-worker configs
  - Tune: Per-channel caps (IMAGE=32, RSS=16, FFT=128, TRANSITION=8)
  - Optimize: DROP_OLD policy for IMAGE/RSS/FFT, DROP_NEW for TRANSITION
- [ ] **GL texture streaming**: PBO optimization if needed
  - Review: `GLTextureManager` PBO pooling efficiency
  - Measure: Texture upload time vs frame budget
  - Optimize: PBO size and pool depth if bottleneck identified
- [ ] **Memory pressure reduction**: Object pooling enhancements
  - Review: `ResourceManager` QPixmap/QImage pooling
  - Measure: GC pressure and allocation spikes
  - Optimize: Pool sizes and eviction policies
- [ ] **Perf baseline update**: Record final v2.0 metrics
  - Run: Full harness per `Docs/PERFORMANCE_BASELINE.md`
  - Record: dt_max, avg_fps, memory, VRAM per transition/backend
  - Compare: v1.x vs v2.0 improvements

**Tests Required**:
- [x] `tests/test_worker_latency_tuning.py` - Queue depth optimization ✅ 20 tests passing
- [ ] `tests/test_gl_texture_streaming.py` - PBO performance validation
- [ ] `tests/test_memory_pooling.py` - Object pool efficiency

---

## Phase 6: Integration & Polish (Week 13-14)

### 6.1 Comprehensive Testing
**Priority**: CRITICAL (Quality assurance)
**Dependencies**: All previous phases complete
**Reference**: `Docs/TestSuite.md`
**Related Modules**: All modules across `core/`, `rendering/`, `widgets/`, `transitions/`, `sources/`

- [ ] **Full integration tests**: End-to-end workflow validation
  - Test: Startup → image display → transitions → widget overlays → shutdown
  - Test: RSS feed loading → queue population → image cycling
  - Test: Spotify visualizer → FFT processing → bar rendering
- [ ] **Performance regression tests**: Ensure dt_max < 100ms maintained
  - Run: `tests/test_frame_timing_workload.py` with `FrameTimingHarness`
  - Verify: All transitions meet dt_max < 100ms target
  - Verify: Worker latency doesn't impact UI frame timing
- [ ] **Multi-monitor scenarios**: All display configurations
  - Test: 1, 2, 3 monitor setups
  - Test: Different resolutions and DPI scaling
  - Test: Monitor disconnect/reconnect while running
- [ ] **Widget interaction tests**: All widget combinations
  - Test: All widget types enabled simultaneously
  - Test: Widget positioning conflicts and stacking
  - Test: Pixel shift with all widgets active
- [ ] **Settings migration tests**: Legacy config compatibility
  - Test: v1.x settings upgrade to v2.0
  - Test: SST import compatibility
  - Test: Reset to defaults preserves user-specific keys
- [ ] **MC vs normal build tests**: Feature parity validation
  - Test: Settings profile separation
  - Test: MC-specific features (layering, Eco Mode)
  - Test: Normal build doesn't expose MC features

**Tests Required**:
- [ ] `tests/test_integration_full_workflow.py` - End-to-end scenarios
- [ ] `tests/test_performance_regression.py` - dt_max validation across all paths
- [ ] `tests/test_multi_monitor_comprehensive.py` - All display configurations
- [ ] `tests/test_widget_combinations.py` - All widget interaction scenarios
- [ ] `tests/test_settings_migration.py` - Legacy compatibility
- [ ] `tests/test_build_variants.py` - MC vs normal feature parity

### 6.2 Documentation Updates
**Priority**: High (Documentation discipline)
**Dependencies**: All code changes complete
**Reference**: `audits/AAMP2026_Phase_6_Detailed.md`

- [ ] **Update Spec.md**: Current architecture and features
  - Update: Worker process architecture (Phase 1-2)
  - Update: GLStateManager integration (Phase 3)
  - Update: Modal settings workflow (Phase 4)
  - Update: MC layering and Eco Mode (Phase 5)
- [ ] **Update Index.md**: Module map and ownership
  - Add: `core/process/` supervisor and worker modules
  - Update: Widget manager, factories, positioner changes
  - Update: GL state management modules
- [ ] **Update Docs/TestSuite.md**: Complete test coverage
  - Add: All new test files from Phases 1-6
  - Update: Test counts and categories
  - Document: Worker simulator usage
- [ ] **Update Docs/PERFORMANCE_BASELINE.md**: v2.0 baselines
  - Record: Final dt_max, avg_fps, memory, VRAM metrics
  - Document: Worker latency impact
  - Compare: v1.x vs v2.0 improvements
- [ ] **Update Docs/10_WIDGET_GUIDELINES.md**: Any positioning changes
  - Document: Visual offset patterns (Phase 4.1b)
  - Update: Widget lifecycle integration
- [ ] **Archive phase docs**: Move completed phase docs to archive/
  - Move: `audits/AAMP2026_Phase_*_Detailed.md` to `archive/v2_0/`
  - Keep: `v2_0_Roadmap.md` and `ARCHITECTURE_AND_MULTIPROCESSING_PLAN_2026.md` as reference

### 6.3 Release Preparation
**Priority**: High (Release readiness)
**Dependencies**: Phase 6.1-6.2 complete
**Related Modules**: `versioning.py`, `scripts/build_nuitka*.ps1`, `scripts/SRPSS_MediaCenter_Installer.iss`

- [ ] **Final backups**: `/bak` snapshots of all major modules
  - Backup: All modified modules from Phases 1-6
  - Include: Short README per backup explaining changes
- [ ] **Version bump**: Update versioning.py for v2.0
  - Update: Version string to "2.0.0"
  - Update: Build metadata and release date
- [ ] **Changelog preparation**: Summary of changes and improvements
  - Document: Multiprocessing architecture
  - Document: GL reliability improvements
  - Document: Widget and settings modularity
  - Document: MC enhancements (layering, Eco Mode)
  - Document: Performance improvements
- [ ] **Build testing**: Verify both normal and MC builds
  - Build: Normal screensaver (SRPSS.scr/SRPSS.exe)
  - Build: MC variant (SRPSS_Media_Center.exe via Nuitka)
  - Test: Both builds on clean Windows installation
- [ ] **Installation testing**: Fresh install and upgrade scenarios
  - Test: Fresh install on system without previous version
  - Test: Upgrade from v1.x to v2.0
  - Test: Settings migration and preservation

**Tests Required**:
- [ ] `tests/test_version_metadata.py` - Version string validation
- [ ] `tests/test_build_artifacts.py` - Build output verification
- [ ] Manual: Installation and upgrade testing on clean systems

---

## Testing Requirements Per Phase

### Unit Tests (Required for each phase)
- [ ] All new modules have comprehensive unit tests
- [ ] Existing tests still pass (no regressions)
- [ ] Coverage maintained or improved
- [ ] Performance tests for critical paths

### Integration Tests (Required for each phase)
- [ ] End-to-end workflow validation
- [ ] Multi-display scenarios tested
- [ ] Error handling and recovery verified
- [ ] Settings persistence and migration

### Performance Tests (Required for performance-sensitive changes)
- [ ] `SRPSS_PERF_METRICS=1` baselines recorded
- [ ] dt_max < 100ms maintained
- [ ] Memory usage within acceptable bounds, no leak potential
- [ ] VRAM usage < 1GB, no leak potential.
- [ ] No new blocking operations on UI thread

### Visual Regression Tests (Required for UI changes)
- [ ] Widget positioning verified
- [ ] Transition correctness validated
- [ ] Visualizer fidelity and calculation results maintained
- [ ] Settings dialog behavior consistent

---

## Success Criteria

### Performance Targets
- [ ] Visualizer CPU usage reduced by 70%+ when not playing
- [ ] dt_max < 100ms maintained across all operations
- [ ] Memory usage stable (no leaks)
- [ ] VRAM usage < 1GB, no leak potential
- [ ] Startup time < 3 seconds on typical hardware

### Feature Completeness
- [ ] All Minor Tasks implemented and tested
- [ ] AAMP2026 phases 1-6 complete
- [ ] MC build enhancements functional
- [ ] Settings modal workflow operational

### Quality Assurance
- [ ] All unit tests passing
- [ ] Integration test coverage complete
- [ ] Documentation updated and accurate
- [ ] No known regressions from v1.x

### Architecture Goals
- [ ] Centralized managers used throughout
- [ ] Thread safety violations eliminated
- [ ] Process isolation foundations in place
- [ ] Widget and settings modularity achieved

---

## Risk Mitigation

### High-Risk Items
1. **Visualizer FFT worker migration**: Risk of visual fidelity loss
   - **Mitigation**: Comprehensive synthetic tests, exact math preservation
2. **GLStateManager rollout**: Risk of GL instability
   - **Mitigation**: Extensive testing, fallback paths maintained
3. **Settings modal conversion**: Risk of configuration loss
   - **Mitigation**: Migration shims, extensive backup testing

### Rollback Plans
- [ ] `/bak` snapshots BEFORE all major changes
- [ ] Feature flags for critical new functionality
- [ ] Automated rollback testing
- [ ] Documentation of rollback procedures

---

**Last Updated**: 2026-01-03
**Next Review**: After Phase 0 completion
**Owner**: Development Team
**Status**: Ready for execution
