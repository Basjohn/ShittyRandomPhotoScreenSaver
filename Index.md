# Index

A living map of modules, purposes, and key classes. Keep this up to date.

- **Documentation Cross-References:**
  - **Canonical Specification**: `Spec.md`
  - **Detailed Module Docs**: See the sections below (condensed from the former `Docs/INDEX.md`)
  - **Test Documentation**: `Docs/TestSuite.md`
  - **Benchmark Harness Parity**: `Docs/Benchmark_Parity.md`
- **Active Audits & Roadmaps**:
  - `audits/FULL_CODEBASE_AUDIT_2026_01_06.md` (live checklist)
  - `audits/Audit_Consolidation_Jan10_2026.md` (current phased plan; supersedes prior audit files)

## Refactor Status
- audits/ARCHITECTURE_AND_MULTIPROCESSING_PLAN_2026.md (Main 2026 Execution Plan)
- audits/v2_0_Roadmap.md (Live Checklist)
- audits/GL_STATE_MANAGEMENT_REFACTORING_GUIDE.md (**REFRESHED**: 12-phase execution plan for Phase 3; mandates ResourceManager for VRAM safety)
- audits/WIDGET_LIFECYCLE_REFACTORING_GUIDE.md (Phase 4 Supplement)
- audits/COMPREHENSIVE_ARCHITECTURE_AUDIT_2025.md (Historical)
  - **Dec 2025**: Widget Lifecycle Management, GL State Management, Widget Factories, Settings Type Safety, Widget Positioning, Intense Shadows, Log Throttling, Core Manager Tests
  - 236 unit tests across 9 test files

## Active Audit Documents (Jan 2026)
- **audits/HaloAndFadeSyncAudit_Jan10.md** - ✅ **COMPLETED** (Jan 10, 2026)
  - Fixed control halo not appearing (double opacity application bug)
  - Fixed widgets appearing before compositor (added compositor ready signal)
  - 8 files modified across rendering and widgets
- **audits/FULL_CODEBASE_AUDIT_2026_01_06.md** - ✅ **LIVE CHECKLIST** (Jan 6, 2026)
  - Full codebase audit covering runtime, rendering, transitions, widgets, logging, threading, settings, tests, docs
  - P0-P3 prioritized tasks with difficulty/reward ratings
  - Documentation parity (SPEC logging v2, Index audits list, TestSuite counts)
  - Test coverage (transition endframe correctness, GL fallback policy, widget raise order, logging routing, render strategy)
  - VSync render thread lifecycle standardization
  - Cross-linking between Index.md, Docs/INDEX.md, and SPEC
- **audits/Audit_Consolidation_Jan10_2026.md** - ✅ **PRIMARY ROADMAP**
  - Collates remaining action items from Codebase Conflicts, Critical Regressions, Production Fixes, Static Element Paint Caching, Test Suite Improvements, and Widget Refactor audits.
  - Provides phased plan (P0–P3) with effort/reward/risk ratings and acceptance criteria.
  - All superseded audit documents now carry ARCHIVED headers pointing back to this file.
- **audits/VISUALIZER_DEBUG.md** - Visualizer debugging reference
- **Archived:** `bak/audits_archive_20260105/` - Completed audit documents (Full_Architectural_Audit_Jan_2026, Performance_Investigation, Solution_3, etc.)

- Phase 0 Improvements (Jan 2026)
  - **WidgetManager**: Robust position normalization (Enum/String/Coerce); Smart positioning logic for Visualizer (Top vs Bottom alignment).
  - **InputHandler**: Global media key passthrough; Double-click "Next Image" navigation.
  - **SettingsDialog**: Multi-monitor aware window state persistence (geometry clamping, screen-at detection).
  - **Clock Widgets**: Centralized shared tick driver wired through `WidgetManager` so every display cluster reuses a single ThreadManager-backed PreciseTimer (`widgets.clock.shared_tick`), matching the synthetic benchmark’s `--clock-shared-tick` design and eliminating duplicate overlay timers.

- v2.1 Production Integration (Jan 2026)
  - **ProcessSupervisor Integration**: Initialized in ScreensaverEngine with 4 worker factories (Image, RSS, FFT, Transition)
  - **ImageWorker Integration**: Wired into `_do_load_and_process` for decode/prescale in separate process
  - **RSSWorker Integration**: Wired into `load_rss_task` with fallback to RSSSource
  - **FFTWorker Integration**: Wired into SpotifyVisualizerAudioWorker with 15ms timeout and fallback
  - **TransitionWorker Integration**: Wired into TransitionFactory for precomputation offloading
  - **EcoModeManager Integration**: Instantiated in DisplayWidget for MC builds (auto-pause when occluded)
  - **ProcessSupervisor wiring**: Engine → DisplayManager → DisplayWidget → WidgetManager/TransitionFactory
  - **Particle Transition Random Mode**: Added "Random" mode that randomly selects between Directional/Swirl with random sub-options
  - **Settings Audit**: Fixed hardcoded defaults in UI to use canonical defaults from `defaults.py`
  - **Worker Settings**: Added `workers.*` and `mc.eco_mode.*` settings to `defaults.py`
  - **Tests**: Added 3 new tests for Particle Random mode, fixed 3 existing tests
  - **Performance Fixes (Jan 5, 2026)**:
    - Fixed ImageWorker timeout (500ms→1500ms) - eliminates timeout fallback to main thread
    - Implemented shared memory for large images (>5MB) - avoids queue serialization overhead
    - Implemented worker pool tuning (`workers.max_workers`: auto = half CPU cores, min 2, max 4)
    - Increased heartbeat tolerance (1s→3s interval, 3→5 missed threshold) - prevents false restarts
    - Added 10 real integration tests for worker processes (`tests/test_worker_integration.py`)
    - **Result**: FPS improved from 21.5 to 45-47 fps (+10-25 fps gain)
  - **Performance Deep Dive (Jan 5, 2026)**:
    - Added `WORKER_BUSY`/`WORKER_IDLE` message types for heartbeat skip during processing
    - Lowered shared memory threshold from 5MB to 2MB (catches 2560x1438 images)
    - Added `HealthStatus.is_busy` flag to skip heartbeat checks during long operations
    - Created `core/performance/frame_budget.py` with `FrameBudget` and `GCController` classes
    - Integrated GC tuning into `GLCompositor.paintGL()` (disable GC during render, idle-time collection)
    - Increased GC thresholds (10000, 50, 50) to reduce GC frequency
    - Removed RSS and Transition workers (use ThreadManager instead) - reduces process overhead
    - Fixed ImageWorker response handling (skip BUSY/IDLE messages in polling loop)
    - **Result**: Transition FPS improved to 52 fps, ImageWorker now using shared memory correctly
  - **Solution 3: Main Thread Blocking Fixes (Jan 5, 2026)**:
    - Moved prefetch `QPixmap.fromImage()` from UI thread to compute pool (`screensaver_engine.py`)
    - Added `AsyncShadowRenderer` class with thread-safe caching and corruption protection (`painter_shadow.py`)
    - Added cache size limits (MAX_SHADOW_CACHE_SIZE=50) with FIFO eviction
    - Updated `PainterShadow.render()` to use async cache as fallback
    - Added comprehensive tests for shadow cache corruption scenarios (`test_painter_shadow.py`)
    - Fixed eco mode bug: `set_always_on_top()` not called on toggle (`display_widget.py`)
    - Added eco mode worker control: stops ImageWorker/FFTWorker when window occluded (`eco_mode.py`)
    - **Audit Documents Created**:
      - `audits/Solution_3_Implementation_Plan.md` - Task breakdown for worker offloading ✅ COMPLETED
      - `audits/Main_Thread_Blocking_Audit.md` - Complete audit of blocking operations
      - `audits/Solution_1_VSync_Driven_Analysis.md` - Deep analysis of VSync-driven rendering
      - `audits/Full_Architectural_Audit_Jan_2026.md` - Comprehensive codebase audit ✅ P0-P2 COMPLETED
  - **Audit Implementation (Jan 5, 2026)**:
    - P0: Worker health diagnostics (`get_detailed_health()`, `log_all_health_diagnostics()`) in ProcessSupervisor
    - P1: Eco mode worker control - stops IMAGE/FFT workers when window occluded
    - P1: QImage lifecycle cleanup - 7 conversion sites fixed (50% memory reduction)
    - P2: Settings caching with invalidation on change in SettingsManager
    - P2: Exception logging improvements (bare except → logged) in screensaver_engine.py
    - Tests: `tests/test_eco_mode_worker_control.py` (8 tests)
    - Backup: `bak/architecture_snapshot_20260105_perf_audit/`
  - **Code Quality Improvements (Jan 5, 2026)**:
    - Created `core/constants/` package with `timing.py` and `sizes.py` for magic number extraction
    - Created `core/logging/tags.py` for standardized logging tags
    - Created `widgets/spotify_visualizer/` package (audio_worker.py, beat_engine.py) - partial refactor
    - PBO texture upload already implemented in `rendering/gl_programs/texture_manager.py`

- v2.0 Roadmap Progress (Jan 2026)
  - **Phase 4.2**: Modal Settings Conversion complete (no-sources popup, profile separation, live updates)
  - **Phase 4.1b**: Visual padding helpers complete (BaseOverlayWidget, WeatherWidget migration)
  - **Phase 5.1b**: GL State Management Phases 1-3b complete (ResourceManager GL tracking)
  - **Phase 5.3**: Performance optimization tests complete (GL texture streaming, memory pooling)
  - **Settings Validation**: Auto-repair for corrupted sensitivity values in `validate_and_repair()`
  - **Widget Margin Alignment** (Jan 5, 2026): Centralized positioning for all overlay widgets
    - Fixed BaseOverlayWidget MIDDLE_LEFT/MIDDLE_RIGHT positioning
    - Refactored RedditWidget, MediaWidget, ClockWidget to delegate to BaseOverlayWidget._update_position()
    - Fixed ClockWidget recursion bug (set_visual_padding calling _update_position)
    - Added 4 cross-widget margin alignment regression tests
    - Added 10 comprehensive stacking tests (33 total positioner tests)
  - **WidgetManager Factory Refactoring** (Jan 5, 2026): Delegated widget creation to factories
    - Enhanced `ClockWidgetFactory` with full settings inheritance (clock2/clock3 from clock)
    - Enhanced `WeatherWidgetFactory` with full settings support
    - Enhanced `MediaWidgetFactory` with MediaWidgetSettings model integration
    - Enhanced `RedditWidgetFactory` with full settings inheritance (reddit2 from reddit)
    - Refactored `setup_all_widgets()` to use `WidgetFactoryRegistry`
    - **Phase 2**: Removed legacy `create_*_widget` methods (2577→1926 LOC, ~650 lines removed)
    - Fixed `test_settings_no_sources_popup.py` to use isolated settings (prevents `/some/folder` corruption)
    - Added Eco Mode systray indicator (`set_eco_mode_callback()` in `ScreensaverTrayIcon`)
    - **Jan 8, 2026**: Canonical widget defaults synchronized with UI — Reddit `limit` key replaces legacy aliases, all widget "intense shadow" toggles default to **ON**, and SST snapshots regenerated via `tools/regenerate_sst_defaults.py`.
    - **Jan 8, 2026**: `tests/test_widget_manager_refresh.py` modernized to drive `WidgetManager.setup_all_widgets()` through the factory registry (media/clock/weather/reddit coverage, spotify widgets stubbed, QColor parsing mocked). Ensures the Reddit 20-item mode renders again and enforces the no-shims policy for widget tests.
  - **Bug Fixes** (Jan 5, 2026):
    - Fixed `RedditWidgetFactory` using wrong model attributes (`subreddits` → `subreddit`, `length` → `item_limit`)
    - Fixed MC mode On Top disable to lower window behind others (was raising)
    - Removed systray CPU polling after it introduced 100–160 ms UI stalls; tray now only shows GPU/Eco flags. **Rule:** never block the UI thread—diagnostics must run off-thread and post updates via `ThreadManager.invoke_in_ui_thread()`.
    - Created `tests/test_worker_consolidated.py` with 30 parameterized tests
    - **1348 tests collected** (150 widget/worker tests passing)

## Upcoming Work (_NOT YET IMPLEMENTED_)
- **Weather Widget SVG Refresh**: Adopt right-aligned `QHBoxLayout` container with animated SVGs sourced from the existing downloader cache. Requires updates to `widgets/weather_widget.py`, `widgets/weather_renderer.py`, and `Docs/Spec.md` once implementation begins.
- **Visualizer Mode Additions**: Add non-Spectrum modes (e.g., waveform morph, DNA helix, ribbon arcs) to `widgets/spotify_visualizer_widget.py` and `widgets/spotify_visualizer/` GLSL overlays while preserving Spectrum defaults. Document presets + defaults in Spec/Index when ready.
- **Reddit Widget Enhancements**: Add “copy link vs open browser” options and richer click behaviors under `ui/tabs/widgets_tab.py` + `widgets/reddit_widget.py`.
- **Imgur Widget Investigation**: Research feasibility, rate limiting, and scraping/API requirements for an Imgur overlay (`widgets/imgur_widget.py`, `sources/imgur_source.py`). Implementation deferred pending investigation outcomes captured in `Docs/Feature_Investigation_Plan.md`.
- **Cache Slider Default Increase**: Plan calls for bumping `cache.max_items` from 24 → 30 in `core/settings/defaults.py` plus UI/Spec updates. Do not update values until implementation lands.
- **Automation Hooks**: Add CI rule to block widgets importing `QThread`/`threading.Thread` directly (ties into Widget Guidelines §11). Awaiting tooling.
- **Transition Desync Settings**: Introduce configurable “desync window” (transition-safe quiet period) exposed via `transitions.desync_guard_ms` in Settings + Spec to enforce the policy described below.

### Transition Desync Policy (current state)
- `rendering/gl_compositor.py` applies a per-display random delay (0–500 ms) with compensated durations so GPU uploads and Transition start costs are staggered while visuals remain aligned. See `_apply_desync_strategy()` and `_desync_delay_ms`.
- `DisplayManager`/`TransitionController` wait for all displays to report ready via a lock-free SPSC queue before starting synchronized transitions, preventing large start spikes.
- _NOT YET IMPLEMENTED_: surface `transitions.desync_guard_ms` + UI controls so operators can tune/disable stagger windows explicitly; document the guard in Spec once the setting lands.

### Transition Guard (Jan 2026)
- **Mandatory 1000ms guard** between transitions enforced in `engine/screensaver_engine.py`
- `TRANSITION_GUARD_MS = 1000` constant defines minimum time between transition completions
- `_show_next_image()` checks two conditions before allowing new transition:
  1. If `_loading_in_progress` is True → defer (transition already running)
  2. If less than 1000ms since `_last_transition_complete_time` → defer
- If guard triggered, transition is **deferred** (not discarded) via `_on_deferred_transition()` callback
- **Timestamp source:** `DisplayWidget.transition_finished` signal → `DisplayManager.transition_finished` → `ScreensaverEngine._on_visual_transition_finished()`
- Timestamp updated when **visual transition animation ends** (not when image loads), ensuring 1000ms guard starts from END of visual effect
- Prevents GPU/compositor overload from rapid X-key presses, short rotation intervals, or programmatic bursts

### Cross-Display Weather Animation Driver (Jan 2026)
- Configured in `DisplayManager.configure_cross_display_weather_driver()` after all displays created
- Collects weather widgets from ALL `DisplayWidget` instances and shares single `QSvgRenderer`
- Uses `SharedWeatherAnimationDriver` with master/sink pattern: master widget drives animation, sinks relay with 3ms stagger
- Prevents duplicate animation drivers when weather widgets exist on multiple displays
- Log marker: `[WEATHER][CROSS_DISPLAY] Shared driver active`

### Media Widget Multi-Display Sync (Jan 2026)
- Class-level shared media info cache in `widgets/media_widget.py` prevents desync across displays
- `_shared_last_valid_info` / `_shared_last_valid_info_ts` cache most recent valid track info (5s TTL)
- `_get_shared_valid_info()` checks cache and other widget instances before allowing hide
- Fixes issue where one media widget hides due to GSMTC timing while another has valid data
- Log marker: `[MEDIA_WIDGET] Using shared info from another display`

### Image Cache Slider (Jan 2026 - Phase 4.1)
- `cache.max_items` default raised from 24 to 30
- UI slider in Display tab → Performance group: "Image Cache Size" (30-100 images)
- Setting persisted via SettingsManager, loaded/saved in `ui/tabs/display_tab.py`
- Affects `core/settings/models.py` → `CacheSettings.max_items`

### Blinds Feather Control (Jan 2026 - Phase 4.1)
- UI slider (0-10px) in Transitions tab → Blinds Settings group
- Setting flows: `transitions_tab.py` → `transition_factory.py` → `GLCompositorBlindsTransition`
- `feather` parameter controls edge softness of slat reveals (0 = sharp, 10 = soft)
- Stored in `transitions.blinds.feather` setting

## Core Managers
- core/threading/manager.py
  - ThreadManager, ThreadPoolType, TaskPriority
  - UI dispatch helpers: run_on_ui_thread, single_shot
  - IO/Compute pools, lock-free stats and mutation queues
- core/resources/manager.py
  - ResourceManager for Qt object lifecycle tracking (register_qt, cleanup_all)
- core/resources/types.py
  - Resource type definitions and enums
- core/events/event_system.py
  - EventSystem pub/sub (thread-safe)
- core/events/event_types.py
  - Event type definitions (ImageChanged, TransitionStarted, etc.)
- core/rss/pipeline_manager.py
  - RssPipelineManager: Singleton for RSS cache paths, deduplication, and cache hygiene
  - `build_url_key()`, `build_image_key()`: Generate dedupe keys from URLs/images
  - `record_keys()`, `has_key()`, `clear_dedupe()`: Manage dedupe state
  - `count_disk_cache_files()`, `clear_cache()`: Disk cache management
  - `generation` property: Cache invalidation token for staleness checks (Phase 2.3)
  - `is_duplicate(log_decision=True)`: Dedupe with optional diagnostics
- core/reddit_rate_limiter.py
  - RedditRateLimiter: Thread-safe singleton for Reddit API rate limiting
  - Enforces 8 req/min limit (Reddit allows 10, -2 safety margin)
  - `wait_if_needed()`, `record_request()`, `can_make_request()`
- core/performance/frame_budget.py
  - FrameBudget: Frame time budget allocation for GL render, visualizer, image loading
  - FrameBudgetConfig: Configuration for target FPS and budget allocation
  - GCController: Frame-aware garbage collection (disable during render, idle-time collection)
  - get_frame_budget(), get_gc_controller(): Global singleton accessors
- core/settings/settings_manager.py
  - SettingsManager (get/set, dot-notation, section helpers, JSON SST snapshot import/export)
  - Maps application name "Screensaver" to "Screensaver_MC" when running under the MC executable (e.g. `SRPSS MC`, `SRPSS_MC`, `main_mc.py`) so QSettings are isolated between the normal screensaver and MC profiles.
  - `validate_and_repair()`: Validates settings types and repairs corrupted values (lists, ranges, enums)
  - `backup_settings(path)`: Creates timestamped JSON backup of all settings
  - `_get_default_image_folders()`: Dynamic default folders (user's Pictures) instead of hardcoded paths
  - Normalizes QSettings nested Mapping values to plain dicts on read to prevent type confusion
  - Preserves user-specific keys (sources folders, RSS feeds, weather location/geo) during reset_to_defaults
- core/settings/defaults.py
  - **Single source of truth** for all default settings values
  - `get_default_settings()`: Returns canonical defaults dict used by SettingsManager and UI
  - `PRESERVE_ON_RESET`: Set of keys to preserve during reset (user-specific data)
  - `get_flat_defaults()`: Flattened dot-notation defaults for validation
  - **Dec 2025**: `analog_shadow_intense` now defaults to True for dramatic analogue clock shadows
- core/settings/models.py
  - **Type-safe settings dataclass models** for IDE autocompletion and validation
  - `DisplayMode`, `TransitionType`, `WidgetPosition`: Enums for type-safe settings values
  - `DisplaySettings`, `TransitionSettings`, `InputSettings`, `CacheSettings`, `SourceSettings`: Core settings models
  - `ShadowSettings`, `ClockWidgetSettings`, `WeatherWidgetSettings`, `MediaWidgetSettings`, `RedditWidgetSettings`, `SpotifyVisualizerSettings`: Widget settings models (media/reddit/Spotify use typed models for both creation and live refresh)
  - `AccessibilitySettings`, `AppSettings`: Accessibility and container models
  - Each model has `from_settings(SettingsManager)`, `from_mapping()`, and `to_dict()` methods so both `SettingsManager` and UI dictionaries share one schema
  - **36 unit tests** now cover serialization plus WidgetManager refresh + scrollwheel volume behaviour (`tests/test_settings_models.py`, `tests/test_widget_manager_refresh.py`, `tests/test_scrollwheel_volume.py`)
- core/animation/animator.py
  - AnimationManager and easing types
  - Animation class with optional FrameState for decoupled rendering
- core/animation/frame_interpolator.py
  - FrameState: timestamped progress samples for render-time interpolation
  - Decouples animation updates from rendering to eliminate timer jitter
- core/animation/easing.py
  - Easing function implementations (Linear, InOutCubic, InOutQuad, etc.)
- core/animation/types.py
  - Animation type definitions and enums
- core/media/media_controller.py
  - Centralized media playback state via Windows GSMTC (Global System Media Transport Controls)
  - GSMTC queries run via ThreadManager with a hard timeout so WinRT calls cannot stall the UI thread or test runner; on hard-timeout, media integration is disabled for the remainder of the session.
- core/media/spotify_volume.py
  - Spotify volume control via pycaw/Core Audio (Windows mixer session level)
  - Uses `ISimpleAudioVolume` to control per-application session volume, NOT Spotify's internal volume
  - **Limitation**: This controls the Windows mixer level, not Spotify's in-app volume slider. Spotify Web API (`PUT /v1/me/player/volume`) can control internal volume but requires OAuth + Premium subscription.
- core/logging/logger.py
  - Centralized logging with colorized output, suppression, and rotation
  - **3-tier logging system:**
    1. `screensaver.log` - Main log (INFO+, no PERF, console mirrors)
    2. `screensaver_verbose.log` - Full DEBUG/INFO without suppression (debug mode only)
    3. `screensaver_perf.log` - PERF metrics only
  - `VerboseLogFilter` - Captures all DEBUG/INFO for deep debugging
- core/logging/overlay_telemetry.py
  - Overlay telemetry logging for debugging widget behavior
- core/eco_mode.py
  - `EcoModeManager`: MC build resource conservation when window occluded
  - `EcoModeState`: DISABLED, MONITORING, ECO_ACTIVE states
  - `EcoModeConfig`: Occlusion threshold (95%), check interval, pause settings
  - `is_mc_build()`: Detect MC build entry point
  - **Jan 6, 2026**: FFT worker removed from eco mode stop list (causes visualizer stalls)
  - **21 unit tests** in `tests/test_mc_eco_mode.py`
- core/reddit_rate_limiter.py
  - `RedditRateLimiter`: Centralized Reddit API rate limiting (singleton)
  - Coordinates all Reddit API calls across RSS source and Reddit widget
  - Enforces 8 requests per minute (under Reddit's 10 req/min limit)
  - Thread-safe with `threading.Lock()` for concurrent access
  - Methods: `can_make_request()`, `record_request()`, `wait_if_needed()`, `reset()`
  - **Jan 9, 2026**: Created to fix rate limiting issues on startup
  - **10 unit tests** in `tests/test_reddit_rate_limiter.py`
- core/presets.py
  - `PresetDefinition`: Dataclass for preset configurations
  - `PRESET_DEFINITIONS`: Dict of all available presets (Purist, Essentials, Media, Full Monty, Custom)
  - `apply_preset()`: Apply a preset to SettingsManager
  - `get_ordered_presets()`: Get preset keys in slider order
  - `adjust_settings_for_mc_mode()`: Adjust placements for MC mode (display 2)
  - Custom preset saves/restores user's manual settings
  - **Jan 10, 2026**: Created for presets feature
  - See `audits/Presets_Feature_Plan.md` for implementation details
- core/process/__init__.py
  - Process isolation module for SRPSS v2.0 multiprocessing
  - Exports: WorkerType, WorkerState, MessageType, WorkerMessage, WorkerResponse, SharedMemoryHeader, RGBAHeader, FFTHeader, HealthStatus, ProcessSupervisor
- core/process/types.py
  - `WorkerType`: IMAGE, RSS, FFT, TRANSITION worker types
  - `WorkerState`: STOPPED, STARTING, RUNNING, STOPPING, ERROR, RESTARTING states
  - `MessageType`: Control (SHUTDOWN, HEARTBEAT) and worker-specific message types
  - `WorkerMessage`, `WorkerResponse`: Immutable request/response with seq_no, correlation_id, timestamps
  - `SharedMemoryHeader`, `RGBAHeader`, `FFTHeader`: Shared memory buffer headers with generation tracking
  - `HealthStatus`: Worker health monitoring with heartbeat tracking, restart backoff
  - **33 unit tests** in `tests/test_process_supervisor.py`
- core/process/supervisor.py
  - `ProcessSupervisor`: Worker lifecycle management (start/stop/restart)
  - Health monitoring via heartbeat with exponential backoff restart policy
  - Non-blocking message passing with drop-old backpressure policy
  - Integration with ResourceManager for cleanup, EventSystem for health broadcasts
  - Settings-based worker enable/disable via `workers.<type>.enabled` keys
- core/process/workers/__init__.py
  - Worker implementations for process isolation
  - Exports: BaseWorker, ImageWorker, RSSWorker, FFTWorker, TransitionWorker
- core/process/workers/base.py
  - `BaseWorker`: Base class for all workers with message loop, heartbeat, graceful shutdown
  - `setup_worker_logging()`: Per-worker log file setup
- core/process/workers/image_worker.py
  - `ImageWorker`: Decode/prescale images using PIL (no Qt in worker process)
  - `ImageWorker._fft_to_bars()`: Display modes (fill, fit, shrink), Lanczos scaling, sharpening
  - Cache key strategy: `path|scaled:WxH` for prescaled images
  - **11 unit tests** in `tests/test_image_worker.py`
- core/process/workers/rss_worker.py
  - `RSSWorker`: Fetch/parse RSS/Atom/Reddit JSON feeds
  - Priority ordering (Bing > NASA > Reddit for rate limiting)
  - Image download with cache/mirror directories
  - **12 unit tests** in `tests/test_rss_worker.py`
- core/process/workers/fft_worker.py
  - `FFTWorker`: FFT computation preserving exact math from VISUALIZER_DEBUG.md
  - `FFTConfig`: Preserves smoothing tau, decay rates, profile template, convolution kernel
  - log1p + power(1.2) normalization, center-out frequency mapping
  - **13 unit tests** in `tests/test_fft_worker.py`
- core/process/workers/transition_worker.py
  - `TransitionWorker`: Precompute transition data (block patterns, particles, etc.)
  - Supports Diffuse, BlockFlip, Particle, Warp, RainDrops, Crumble transitions
  - Cache key generation and result caching
  - **11 unit tests** in `tests/test_transition_worker.py`
- core/process/tuning.py
  - `WorkerTuningConfig`: Per-worker queue sizes, backpressure, latency targets
  - `BackpressurePolicy`: BLOCK, DROP_OLD, DROP_NEW policies
  - `LatencyMetrics`: Track min/max/avg latency per worker
  - `LatencyMonitor`: Centralized latency monitoring with alert callbacks
  - **20 unit tests** in `tests/test_worker_latency_tuning.py`

## v2.0 Roadmap Test Summary
- `tests/test_process_supervisor.py` - 33 tests for ProcessSupervisor, message schemas, shared memory
- `tests/test_image_worker.py` - 11 tests for ImageWorker decode/prescale
- `tests/test_rss_worker.py` - 12 tests for RSSWorker fetch/parse
- `tests/test_fft_worker.py` - 13 tests for FFTWorker math preservation
- `tests/test_transition_worker.py` - 11 tests for TransitionWorker precompute
- `tests/test_gl_state_manager_overlay.py` - 21 tests for GLStateManager overlay integration
- `tests/test_transition_state_manager.py` - 12 tests for transition state dataclasses
- `tests/test_widget_manager.py` - 20 tests for WidgetManager lifecycle
- `tests/test_mc_eco_mode.py` - 21 tests for MC Eco Mode
- `tests/test_worker_latency_tuning.py` - 20 tests for worker latency configuration
- `tests/test_mc_context_menu.py` - 12 tests for MC context menu features
- `tests/test_settings_defaults_parity.py` - 23 tests for settings defaults and SST parity
- `tests/test_widget_visual_padding.py` - 15 tests for BaseOverlayWidget visual padding helpers
- `tests/test_settings_no_sources_popup.py` - 10 tests for no-sources popup validation
- `tests/test_settings_profile_separation.py` - 9 tests for MC vs Screensaver profile isolation
- `tests/test_gl_texture_streaming.py` - 18 tests for GL texture streaming and PBO optimization
- `tests/test_memory_pooling.py` - 19 tests for ResourceManager object pooling efficiency
- `tests/test_spotify_visualizer_widget.py` - 12 tests for Spotify visualizer audio worker and widget
- `tests/test_integration_full_workflow.py` - 19 tests for end-to-end integration scenarios
- `tests/test_gl_state_and_error_handling.py` - 31 tests for GL state management and error handling (consolidated)
- **Total: 389 tests** for process isolation, GL state, widgets, MC features, settings, performance tuning, and integration (including widget factories/positioner)

## GL Resource Management (Jan 2026)
- `core/resources/manager.py` - ResourceManager GL cleanup hooks:
  - `register_gl_handle()` - Generic GL handle registration with custom cleanup
  - `register_gl_vao()` - VAO registration with glDeleteVertexArrays cleanup
  - `register_gl_vbo()` - VBO registration with glDeleteBuffers cleanup
  - `register_gl_program()` - Shader program registration with glDeleteProgram cleanup
  - `register_gl_texture()` - Texture registration with glDeleteTextures cleanup
  - `get_gl_stats()` - Statistics on registered GL handles
- **Integrated Modules** (all GL handles now tracked):
  - `widgets/spotify_bars_gl_overlay.py` - Program, VAO, VBO
  - `rendering/gl_programs/geometry_manager.py` - Quad/box VAO, VBO
  - `rendering/gl_programs/texture_manager.py` - Textures, PBOs
- `audits/GL_HANDLE_INVENTORY.md` - Full inventory of GL handle creation points

- **ARCHIVED**: Gmail modules moved to `archive/gmail_feature/` (Dec 2025)
  - Google OAuth verification requirements block unverified apps from using sensitive Gmail scopes
  - See `archive/gmail_feature/RESTORE_GMAIL.md` for restoration instructions

## Engine
- engine/screensaver_engine.py
  - Orchestrator: sources → ImageQueue → display → transitions
  - Caching/prefetch integration via ImageCache + ImagePrefetcher
  - Random transition/type selection with non-repeating logic (persisted)
  - **State Management (2025-12-14 refactor)**: Uses `EngineState` enum instead of boolean flags
    - States: UNINITIALIZED, INITIALIZING, STOPPED, STARTING, RUNNING, STOPPING, REINITIALIZING, SHUTTING_DOWN
    - `_running`, `_initialized`, `_shutting_down` are now derived properties from `_state`
    - Thread-safe `_transition_state()` method with validation and logging
    - CRITICAL: `_shutting_down` returns False for REINITIALIZING state (fixes RSS reload bug)
  - **RSS async loading**: `_load_rss_images_async()` loads RSS images in background without blocking startup
    - Uses `_shutting_down` property (derived from state) to distinguish actual shutdown from settings reinitialization
    - Pre-loads cached RSS images to queue before starting async download for immediate variety
    - Limits to 8 images per source per refresh cycle to prevent any single source from blocking
    - Sets shutdown callback on RSSSource objects so downloads abort immediately on exit
  - **Settings reinitialization**: `_on_sources_changed()` rebuilds sources and queue when settings change
    - Transitions to REINITIALIZING state (not STOPPING) so _shutting_down returns False
    - Restores to RUNNING state after reinitialization completes
- engine/display_manager.py
  - Multi-monitor DisplayWidget management, sync scaffolding
- engine/image_queue.py
  - ImageQueue with RLock, shuffle/history, wraparound
  - **Ratio-based source selection**: Separate pools for local and RSS images with configurable usage ratio (default 60% local / 40% RSS)
  - Automatic fallback: if selected pool empty, falls back to other pool
  - **Legacy single-source semantics**: When only one source type exists, `next()` consumes from the combined queue to preserve deterministic `peek()/size()/wraparound` behavior.
  - peek() and peek_many(n) for prefetch look-ahead
  - `set_local_ratio(ratio)` / `get_local_ratio()` for runtime ratio adjustment
  - `has_both_source_types()` to check if ratio control is applicable

## Entry Points & Variants
- main.py
  - Primary screensaver entry point used by SRPSS.scr/SRPSS.exe.
  - Uses SettingsManager with application name "Screensaver" for QSettings.
- main_mc.py
  - Manual Controller (MC) variant: same engine and widgets but launched as a normal app (PyInstaller `SRPSS MC` / Nuitka `SRPSS_MC`).
  - Uses a separate QSettings application name "Screensaver_MC" so MC settings never conflict with the normal screensaver profile.
  - MC-only runtime behaviour:
    - Forces `input.hard_exit=True` at startup so the saver cannot be exited accidentally by mouse movement unless explicitly reconfigured in the MC profile.
    - While Windows is configured to use SRPSS.scr as the active screensaver, calls `SetThreadExecutionState` to prevent the system screensaver/power idle from triggering while MC is running; normal screensaver builds never change system-wide idle behaviour.
    - Marks the fullscreen DisplayWidget window as a Qt.Tool window in MC builds, keeping it out of the taskbar and standard Alt+Tab while remaining top-most on all displays.

## Rendering
- rendering/display_widget.py
  - Borderless fullscreen (frameless, always-on-top per monitor) image presentation, DPR-aware scaling. In MC builds the same DisplayWidget also adds the Qt.Tool flag so the window is hidden from the taskbar/standard Alt+Tab while retaining fullscreen/top-most behaviour.
  - Creates transitions based on settings (CPU, legacy GL overlays, and compositor-backed GL variants, including GL-only Blinds when HW accel is enabled).
  - Injects shared ResourceManager into transitions; seeds base pixmap pre/post transition and on startup to avoid black frames (wallpaper snapshot seeding + previous-pixmap fallback)
  - Uses lazy GL overlay initialization via `overlay_manager.prepare_gl_overlay` instead of a global startup prewarm; manages widgets Z-order, logs per-stage telemetry, handles transition watchdog timers
 - rendering/gl_compositor.py
  - `GLCompositorWidget`: single per-display GL surface responsible for drawing the base image and all compositor-backed GL transitions (Crossfade, Slide, Wipe, Block Puzzle Flip, Blinds, Diffuse, plus the GL-only Peel, 3D Block Spins, Ripple, Warp Dissolve).
  - Hosts the Route 3 GLSL shader pipeline (OpenGL 4.1+ via PyOpenGL when available), including a shared card-flip program and geometry for both a fullscreen quad and a dedicated 3D box mesh. The pipeline currently powers the 3D Block Spins slab shader and the Warp Dissolve / Ripple / Shuffle effects; the BlockSpin shader path renders the image as a thin depth-tested slab (front/back/side faces) with neutral glass edges and specular highlights using this box mesh.
  - Owns the GLSL program/geometry state in a private pipeline container and exposes `cleanup()` to tear down programs, buffers, and Block Spins textures; `DisplayWidget` calls this from its destruction path so ResourceManager-driven shutdown leaves no dangling GL objects.
  - Maintains lightweight per-transition state dataclasses (CrossfadeState, SlideState, WipeState, BlockFlipState, BlockSpinState, BlindsState, DiffuseState, PeelState, WarpState) and exposes `start_*` helpers driven by the shared AnimationManager.
  - Legacy per-transition GL overlays remain supported but new GL-only transitions route through this compositor instead of creating additional `QOpenGLWidget` instances.
  - On `initializeGL`, logs the OpenGL adapter vendor/renderer/version and disables the shader pipeline for obvious software GL implementations (for example, GDI Generic, Microsoft Basic Render Driver, llvmpipe), keeping compositor QPainter transitions and CPU fallbacks as the safe paths on those stacks.
  - When PERF metrics are enabled (`core.logging.logger.is_perf_metrics_enabled()` / `PERF_METRICS_ENABLED`), emits `[PERF] [GL COMPOSITOR] <Name> metrics` summary lines for compositor-driven transitions and can optionally draw a small FPS/debug overlay based on the active transition's profiling state (Slide, Wipe, BlockSpin, Ripple, Warp Dissolve, Diffuse, Blinds, Peel); both metrics and HUD are disabled entirely when PERF metrics are turned off in retail builds. NOTE: Shuffle and Shooting Stars (Claws) transitions have been fully retired and removed.
- rendering/image_processor.py
  - Scaling/cropping for FILL/FIT/SHRINK, optional Lanczos via PIL
- rendering/display_modes.py
  - DisplayMode enum and helpers
- rendering/gl_programs/
  - Per-transition shader program helpers that encapsulate GLSL source, compilation, uniform caching, and draw logic.
  - `program_cache.py`: `GLProgramCache` singleton for centralized lazy-loading of shader programs. Replaces 10+ module-level globals with single cache class. Validates cached program IDs per-context via `glIsProgram()` and recompiles when IDs are stale.
  - `geometry_manager.py`: `GLGeometryManager` - **per-compositor instance** for VAO/VBO management. Handles quad and box mesh creation/cleanup. Changed from singleton because OpenGL VAOs are context-specific.
  - `texture_manager.py`: `GLTextureManager` - **per-compositor instance** for texture upload, caching (LRU), and PBO pooling. Changed from singleton because OpenGL textures are context-specific.
  - `base_program.py`: `BaseGLProgram` ABC with shared vertex shader and compilation helpers.
  - `peel_program.py`: `PeelProgram` for the Peel transition GLSL.
  - `blockflip_program.py`: `BlockFlipProgram` for the BlockFlip transition GLSL.
- rendering/gl_compositor_pkg/
  - **Jan 6, 2026**: Extracted metrics package from gl_compositor.py
  - `__init__.py`: Package exports for metrics dataclasses
  - `metrics.py`: `_GLPipelineState`, `_AnimationRunMetrics`, `_PaintMetrics`, `_RenderTimerMetrics`
- rendering/render_strategy.py
  - **Jan 6, 2026**: VSync infrastructure for future VSync-driven rendering
  - `RenderStrategy`: Abstract base class for render strategies
  - `RenderStrategyConfig`: Configuration (target_fps, vsync_enabled, fallback_on_failure)
  - `RenderMetrics`: Performance tracking (frame_count, min/max dt, avg_fps)
  - `TimerRenderStrategy`: QTimer-based rendering (current default)
  - `VSyncRenderStrategy`: VSync-driven via dedicated thread with automatic fallback
  - `RenderStrategyManager`: Runtime strategy switching
  - `crossfade_program.py`: `CrossfadeProgram` for the Crossfade transition GLSL.
  - `blinds_program.py`: `BlindsProgram` for the Blinds transition GLSL.
  - `diffuse_program.py`: `DiffuseProgram` for the Diffuse transition GLSL.
  - `slide_program.py`: `SlideProgram` for the Slide transition GLSL. Optimized with branchless bounds checking using `step()` and `mix()`.
  - `wipe_program.py`: `WipeProgram` for the Wipe transition GLSL. Optimized with direction vector approach instead of mode branching.
  - `warp_program.py`: `WarpProgram` for the Warp Dissolve transition GLSL.
  - `raindrops_program.py`: `RaindropsProgram` for the Raindrops/Ripple transition GLSL.
  - `crumble_program.py`: `CrumbleProgram` for the Crumble transition GLSL (Voronoi crack pattern with falling pieces).
- rendering/gl_transition_renderer.py
  - `GLTransitionRenderer`: Centralized transition rendering for GL compositor. Handles both shader-based (Group A) and QPainter-based (Group B) transition rendering.
  - **Phase E Relevance**: Isolates overlay visuals from base-image rendering, enables future shader-backed shadow implementations (Option A from CONTEXT_CACHE_CORRUPTION.md).
  - **Methods**: `render_simple_shader()`, `render_blockspin_shader()`, `render_slide_shader()`, `render_*_fallback()` for QPainter paths.
- rendering/gl_error_handler.py
  - `GLErrorHandler`: Centralized GL error handling with session-level fallback policy (Group A→B→C).
  - `GLCapabilityLevel`: Enum for capability levels (FULL_SHADERS, COMPOSITOR_ONLY, SOFTWARE_ONLY).
  - `GLErrorState`: Dataclass tracking GL error state for fallback decisions.
  - **Features**: Software GL detection, shader failure tracking, capability demotion logging.
  - **Singleton**: `get_gl_error_handler()` returns shared instance.
- rendering/gl_state_manager.py
  - `GLStateManager`: Centralized GL context state management with validated state transitions.
  - `GLContextState`: Enum for GL context states (UNINITIALIZED, INITIALIZING, READY, ERROR, CONTEXT_LOST, DESTROYING, DESTROYED).
  - `GLStateGuard`: Context manager for safe GL operations with automatic error handling.
  - **Features (Dec 2025)**: Thread-safe state access, state change callbacks, transition history for debugging, error recovery tracking, statistics.
  - **Integration**: Used by `GLCompositorWidget` for robust GL lifecycle management.
- rendering/gl_profiler.py
  - `TransitionProfiler`: centralized profiling helper for GL compositor transitions. Tracks frame timing, min/max frame durations, and emits PERF logs. All compositor transitions (Slide, Wipe, Peel, BlockSpin, Warp, Raindrops, BlockFlip, Diffuse, Blinds) now use this single profiler instance instead of per-transition profiling fields.
- rendering/transition_state.py
  - Transition state dataclasses extracted from GLCompositor: `TransitionStateBase`, `CrossfadeState`, `SlideState`, `WipeState`, `BlockFlipState`, `BlockSpinState`, `BlindsState`, `DiffuseState`, `PeelState`, `WarpState`, `RaindropsState`, `CrumbleState`.
  - `TransitionStateManager`: Clean interface for getting/setting transition state with change notifications.
- rendering/transition_factory.py
  - `TransitionFactory`: Factory for creating transition instances based on settings and hardware capabilities. **Integrated into DisplayWidget**, removing 535 lines of duplicate code and 20+ unused imports. Handles all transition type selection, direction randomization, and compositor/CPU fallback logic.
- rendering/widget_setup.py
  - Widget setup helpers extracted from DisplayWidget: `parse_color_to_qcolor`, `resolve_monitor_visibility`, `setup_dimming`, `get_widget_shadow_config`, `compute_expected_overlays`. Reduces nested try/except and prepares for further _setup_widgets decomposition.
- rendering/widget_manager.py
  - `WidgetManager`: Extracted from DisplayWidget. Manages overlay widget lifecycle, positioning, visibility, Z-order, rate-limited raise operations, and effect invalidation.
  - **Phase E Enhancement (2025-12-16)**: Added `invalidate_overlay_effects()`, `_recreate_effect()`, `schedule_effect_invalidation()` for centralized QGraphicsEffect cache-busting
  - **Phase 0.6 (Jan 2026)**: Smart positioning logic for Visualizer (Top vs Bottom alignment).
  - **Phase 0.7 (Jan 2026)**: Robust positioning resolution via `coerce_widget_position` for Media, Reddit, and Clock widgets.
  - **Fade coordination**: `request_overlay_fade_sync()`, `register_spotify_secondary_fade()`, `reset_fade_coordination()`
  - **Jan 10, 2026 Enhancement**: Added compositor ready signal - widgets now wait for `image_displayed` signal before starting fade-in, preventing premature visibility before first frame
  - **Lifecycle Integration (Dec 2025)**: Added `initialize_widget()`, `activate_widget()`, `deactivate_widget()`, `cleanup_widget()` and batch methods for new lifecycle system
  - **Tests**: `tests/test_visualizer_smart_positioning.py`
- rendering/widget_positioner.py
  - `WidgetPositioner`: Centralized widget positioning logic extracted from WidgetManager
  - `PositionAnchor`: Enum for 9 standard widget positions (TOP_LEFT, CENTER, BOTTOM_RIGHT, etc.)
  - `PositionConfig`, `WidgetBounds`: Dataclasses for positioning configuration
  - Position calculation, collision detection, stacking logic, relative positioning
  - **21 unit tests** in `tests/test_widget_positioner.py`
- rendering/widget_factories.py
  - `WidgetFactory`: Abstract base class for widget factories with shadow config extraction.
  - `ClockWidgetFactory`, `WeatherWidgetFactory`, `MediaWidgetFactory`, `RedditWidgetFactory`, `SpotifyVisualizerFactory`, `SpotifyVolumeFactory`: Concrete factories for each widget type.
  - `WidgetFactoryRegistry`: Central registry for widget factories with `create_widget()` method.
  - **Features (Dec 2025)**: Extracts widget creation logic from WidgetManager for better SRP, testability, and extensibility.
- rendering/input_handler.py
  - `InputHandler`: Extracted from DisplayWidget. Handles all user input including mouse/keyboard events, context menu triggers, exit gestures, and **double-click "Next Image" navigation**.
  - **Phase E Enhancement (2025-12-16)**: Provides single choke point for context menu open/close triggers for deterministic effect invalidation ordering.
  - **Signals**: `exit_requested`, `settings_requested`, `next_image_requested` (triggered by 'X' key or double-click), `previous_image_requested`, `cycle_transition_requested`, `context_menu_requested`
  - **Tests**: `tests/test_double_click_navigation.py`, `tests/test_media_keys.py`
- rendering/transition_controller.py
  - `TransitionController`: Extracted from DisplayWidget. Manages transition lifecycle including start, progress, completion, cancellation, and watchdog timeout handling.
  - **Phase 3 (2025-12-16)**: Centralizes transition state management for deterministic overlay visibility changes.
  - **Signals**: `transition_started`, `transition_finished`, `transition_cancelled`
- rendering/image_presenter.py
  - `ImagePresenter`: Extracted from DisplayWidget. Manages image loading, processing, and pixmap lifecycle.
  - **Phase 4 (2025-12-16)**: Centralizes pixmap management to ensure consistent state during transitions.
  - **Signals**: `image_ready`, `image_error`
- rendering/multi_monitor_coordinator.py
  - `MultiMonitorCoordinator`: Singleton coordinator for multi-display screensaver synchronization.
  - **Phase 5 (2025-12-16)**: Replaces scattered class-level variables with proper coordination layer.
  - **Responsibilities**: Ctrl-held state, halo ownership, focus ownership, event filter management, instance registry
  - **Signals**: `ctrl_held_changed`, `halo_owner_changed`
  - **Focus Re-claiming (Dec 2025)**: `claim_focus()` now allows secondary displays to claim focus when current owner is not visible or has unavailable screen (monitor off). Fixes MC build keyboard input on display 2 when display 1's monitor is unavailable.
  - **Thread Safety**: All state access protected by lock for safe cross-thread queries

## Transitions
- transitions/base_transition.py
  - BaseTransition with centralized animation
- transitions/overlay_manager.py
  - Persistent overlay helpers (`get_or_create_overlay`, `prepare_gl_overlay`, diagnostics/raise helpers) registering with shared ResourceManager; logs swap downgrades and readiness telemetry
- transitions/crossfade_transition.py, transitions/gl_compositor_crossfade_transition.py
  - CPU and GL compositor crossfade transitions
- transitions/slide_transition.py, transitions/gl_compositor_slide_transition.py
  - Slide directions stored in settings; cardinals only (LEFT, RIGHT, UP, DOWN)
- transitions/wipe_transition.py, transitions/gl_compositor_wipe_transition.py
  - Wipe directions stored in settings; includes diagonals
- transitions/diffuse_transition.py, transitions/gl_compositor_diffuse_transition.py
  - Diffuse shapes: Rectangle, Membrane. Block size is clamped (min 4px) and shared between CPU and GL paths; the CPU fallback uses a simple block-based dissolve, while the Membrane shape is implemented only in the GLSL compositor path.
- transitions/block_puzzle_flip_transition.py, transitions/gl_compositor_blockflip_transition.py
  - Block puzzle flip with CPU fallback and GL compositor variant
- transitions/gl_compositor_blinds_transition.py
  - GL-only Blinds transition using the compositor; requires hardware acceleration.
- transitions/gl_compositor_peel_transition.py
  - Compositor-backed GL-only Peel transition (strip-based peel of the old image over the new image). Direction stored under `transitions.peel.direction`.
- transitions/gl_compositor_blockspin_transition.py
  - Compositor-backed GL-only 3D Block Spins transition rendering a single full-frame 3D slab (front/back/side faces) with directional axis control (LEFT/RIGHT spin around Y, UP/DOWN spin around X); legacy Block Puzzle grid settings are no longer used.
- transitions/gl_compositor_raindrops_transition.py
  - Compositor-backed GL-only Rain Drops transition using a raindrop-like diffuse region to reveal the new image.
- transitions/gl_compositor_warp_transition.py
  - Compositor-backed GL-only Warp Dissolve transition using a banded horizontal warp of the old image over a stable new image.
- transitions/gl_compositor_crumble_transition.py
  - Compositor-backed GL-only Crumble transition creating a rock-like Voronoi crack pattern across the old image, then pieces fall away with physics-based motion (gravity, rotation, drift) to reveal the new image.
- transitions/gl_compositor_particle_transition.py
  - Compositor-backed GL-only Particle transition where smooth round particles fly in from off-screen and stack to reveal the new image. Supports Directional mode (8 directions + Random Direction + Random Placement), Swirl mode (spiral with Typical/Center Outward/Edges Inward build orders), and Converge mode (all edges converge to center). Features 3D ball shading, motion trails, texture mapping onto particles, optional wobble on arrival, and configurable gloss/light direction.
- rendering/gl_programs/particle_program.py
  - GLSL shader program for Particle transition. Grid-driven analytic approach for predictable performance - each pixel evaluates only a small neighborhood of candidate cells.
  - **Timing**: 65% spawn spread, 30% flight time for smooth animation
  - **Swirl Orders**:
    - Typical: smooth organic swirl ordering (non-blocky)
    - Center Outward: symmetric radial expansion from center (smooth coverage)
    - Edges Inward: edges-to-center ordering with gentle spiral variation
  - **Position-aware blending**: Background only blends after particles arrive at each pixel location
  - **3D Shading**: Fresnel, diffuse, specular highlights with configurable light direction

## Sources
- sources/base_provider.py
  - ImageMetadata, ImageProvider ABC, ImageSourceType enum
- sources/folder_source.py
  - FolderSource: Local folder image provider with recursive scanning
- sources/rss_source.py
  - RSSSource: RSS/Atom feed image provider with caching and rate limiting
  - **Shutdown callback**: `set_shutdown_check(callback)` allows async tasks to abort during downloads
  - **Per-source limits**: `refresh(max_images_per_source=N)` limits downloads per source to prevent blocking
  - **Interruptible delays**: Rate limit delays are split into 0.5s chunks with shutdown checks
  - **Cache pre-loading**: `_load_cached_images()` loads existing cache on init for immediate availability
  - **Priority system**: `_get_source_priority(url)` returns priority (Bing=95, Unsplash=90, Wikimedia=85, NASA=75, Reddit=10)
  - **Cache cleanup**: Removes oldest files when exceeding max size, keeps minimum 20 images

## Widgets
- widgets/base_overlay_widget.py
  - `BaseOverlayWidget`: Abstract base class for all overlay widgets. Provides common functionality for font/color/background/shadow/position management, pixel shift support, thread manager integration, and size calculation for stacking/collision detection.
  - `OverlayPosition`: Enum for standard widget positions (TOP_LEFT, TOP_RIGHT, etc.)
  - `WidgetLifecycleState`: Enum for widget lifecycle states (CREATED, INITIALIZED, ACTIVE, HIDDEN, DESTROYED)
  - `is_valid_lifecycle_transition()`: Validate state transitions
  - **Lifecycle Management (Dec 2025)**: Full lifecycle state machine with `initialize()`, `activate()`, `deactivate()`, `cleanup()` methods. Thread-safe state access via `_lifecycle_lock`. ResourceManager integration for automatic resource cleanup.
  - `calculate_widget_collision()`: Check if two widget rects overlap
  - `calculate_stack_offset()`: Calculate offset for widget stacking
- widgets/clock_widget.py
  - Digital/analogue clock widget extending `BaseOverlayWidget`. Supports three instances (Clock 1/2/3) with per-monitor selection, independent timezones, optional seconds/timezone labels, analogue numerals toggle, subtle vs "Intense Analogue Shadows" mode (doubles drop-shadow opacity/size), digital/analogue display modes, and 9 position options (Top/Middle/Bottom × Left/Center/Right).
  - **Visual Offset Alignment**: `_compute_analog_visual_offset()` calculates precise offset from widget bounds to visual content (XII numeral or clock face edge) so analogue clocks without backgrounds align correctly with other widgets at the same margin. Handles all scenarios: with/without background, with/without numerals, with/without timezone.
  - **Lifecycle (Dec 2025)**: Implements `_initialize_impl()`, `_activate_impl()`, `_deactivate_impl()`, `_cleanup_impl()` hooks for new lifecycle system.
- widgets/weather_widget.py
  - Weather widget extending `BaseOverlayWidget`. Per-monitor selection via settings (ALL or 1/2/3). Features optional forecast line (tomorrow's min/max temp and condition, 8pt smaller than base font), configurable margin from screen edge. Uses Title Case for location and condition display. Supports 9 position options (Top/Middle/Bottom × Left/Center/Right). Animated SVG condition icon container lives beside the text stack with selectable alignment (`NONE`/`LEFT`/`RIGHT`) and a `_ANIMATED_ICON_SCALE_FACTOR` of 1.44 to keep the art ~44 % larger than baseline without clipping.
  - Background fetch runs exclusively via ThreadManager IO (no raw QThread fallback); periodic refresh uses overlay timer helper; retries via single-shot timers on failure.
  - Settings include `show_details_row`, `show_forecast`, a standalone “Animate weather icon” checkbox (independent from the alignment dropdown) that toggles SVG animation at 12 fps with a static-frame fallback when disabled, and an optional “Desaturate Animated Icon” checkbox that threads through defaults/models/factories to apply a `QGraphicsColorizeEffect` so animated art can match monochrome card themes.
- widgets/media_widget.py
  - Spotify/media overlay widget extending `BaseOverlayWidget`. Driven by `core/media/media_controller.py`; per-monitor selection via `widgets.media`, 9 position options (Top/Middle/Bottom × Left/Center/Right), background frame, and monochrome transport controls (Prev/Play/Pause/Next) over track metadata. Uses Title Case for track title and artist display. Artwork uses a square frame for album covers and adapts to non-square thumbnails.
  - Media overlay (Spotify GSMTC card). Handles title/artist text, artwork decode, fade-in coordination, shared shadow, Spotify volume slider anchoring, wake-from-idle logic, and the authoritative transport controls layout. `_compute_controls_layout()` returns the painted rectangles + accessibility hit regions; `handle_controls_click()` applies previous/play/next with click feedback and optimistic controller state so cloned cards (multiple displays) stay in lockstep. InputHandler delegates left-clicks to this helper while right/middle clicks remain direct next/previous shortcuts.
- widgets/reddit_widget.py
  - Reddit overlay widget extending `BaseOverlayWidget`. Shows top posts from a configured subreddit with 4-, 10-, or 20-item layouts (20-item mode for ultra-wide displays), per-monitor selection via `widgets.reddit`, 9 position options (Top/Middle/Bottom × Left/Center/Right), shared overlay fade-in coordination, and click-through to the system browser.
  - **Reddit link handling (2024-12-17)**: Smart A/B/C logic based on primary display coverage:
    - Case A: Primary covered + hard_exit → Exit immediately, bring browser to foreground
    - Case B: Primary covered + Ctrl held → Exit immediately, bring browser to foreground
    - Case C: MC mode (primary NOT covered) → Stay open, bring browser to foreground
    - System-agnostic detection using `QGuiApplication.primaryScreen()` (not screen index assumptions)
  - Supports a second instance (`reddit2_widget`) via `widgets.reddit2.*` settings with independent subreddit/position/display but inheriting all styling from Reddit 1.
- widgets/spotify_visualizer_widget.py
   - Spotify Beat Visualizer widget and background audio worker. Captures loopback audio via a shared `_SpotifyBeatEngine` (single process-wide engine), publishes raw mono frames into a lock-free `TripleBuffer`, performs FFT/band mapping on the COMPUTE pool (not UI thread), and exposes pre-smoothed bar magnitudes plus a derived GPU fade factor to the bar overlay.
   - **Dec 2025**: Added `_clear_gl_overlay()` to properly clear GL bars when Spotify closes (sync_visibility_with_anchor).
   - **Visualizer tuning (v1.243+)**: Uses noise floor subtraction (`noise_floor=2.1`) and dynamic range expansion (`expansion=2.5`) to achieve 0.02-1.0 bar range with reactive drops. V1.2-style smoothing (`smoothing=0.3`, `decay_rate=0.7`) provides aggressive 30% per-frame decay for visible drops while maintaining fast attack. Center-out gradient (`(1-dist)²*0.85+0.15`) ensures bass in center, treble at edges. See `audits/VISUALIZER_DEBUG.md` for tuning history.
   - **Floor controls**: `set_floor_config(dynamic_enabled, manual_floor)` drives dynamic noise floor averaging (ratio 1.05, alpha 0.05) with manual override clamped to 0.12–4.00. Manual selection snaps internal running average to avoid re-enable jumps.
   - The QWidget owns the Spotify-style card, primary overlay fade, and drop shadow; bars are drawn by a dedicated `SpotifyBarsGLOverlay` QOpenGLWidget overlay created and managed by `DisplayWidget`, with a software (CPU) fallback path controlled by `widgets.spotify_visualizer.software_visualizer_enabled` when the renderer backend is set to Software. Bars only animate while the normalized media state is PLAYING; when Spotify is paused or stopped the beat engine decays targets to zero and the overlay's 1-segment idle floor produces a flat single-row baseline. Card fade participates in the primary overlay wave, while the bar field uses a delayed secondary fade computed from the shared `ShadowFadeProfile` progress so the visualiser never pops in or shows stray green pixels.
- widgets/spotify_bars_gl_overlay.py
   - GLSL/VAO Spotify bars overlay with DPI-aware geometry, per-bar peak envelope and 1-segment floor, rendering the main bar stack plus a configurable ghost trail driven by a decaying peak value. Uses the bar border colour for ghost segments with a vertical alpha falloff, respects `ghosting_enabled`, `ghost_alpha`, and `ghost_decay` from `widgets.spotify_visualizer.*` settings, and consumes the GPU fade factor from `SpotifyVisualizerWidget` so opacity ramps in after the card fade using the same `ShadowFadeProfile` timing.
- widgets/spotify_volume_widget.py
  - Spotify-only vertical volume slider paired with the media card; gated on a Spotify GSMTC session.
  - **Coordinated Fade (Dec 2025)**: Now uses `request_overlay_fade_sync()` to participate in primary overlay fade wave, fading in simultaneously with other widgets instead of using delayed secondary fade. Ensures smooth, coordinated appearance.
- widgets/dimming_overlay.py
   - `DimmingOverlay`: Legacy widget-based dimming overlay (kept for fallback/testing). Primary runtime dimming is implemented in the GL compositor (`GLCompositorWidget.set_dimming`).
 - widgets/pixel_shift_manager.py
   - `PixelShiftManager`: Manages periodic 1px shifts of overlay widgets for burn-in prevention. Maximum drift of 4px in any direction with automatic drift-back. Defers during transitions.
   - **Outward Bias (Dec 2025)**: `_calculate_next_offset()` now biases toward outward movement (80% probability) to prevent immediate shift-back behavior. Only ~5% chance to move inward when not at max drift, creating natural drift patterns.
- widgets/context_menu.py
   - `ScreensaverContextMenu`: Dark-themed right-click context menu matching settings dialog styling. Provides Previous/Next image, transition selection submenu, Settings, Background Dimming toggle, Hard Exit Mode toggle, and Exit. Uses monochromatic icons and app-owned dark theme (no Windows accent bleed). Activated by right-click in hard exit mode or Ctrl+right-click in normal mode. Lazy-initialized by DisplayWidget for performance.
- widgets/cursor_halo.py
   - `CursorHaloWidget`: Visual cursor indicator for Ctrl-held interaction mode. Displays a semi-transparent ring with center dot that follows the cursor. Supports fade-in/fade-out animations via AnimationManager.
   - **Jan 10, 2026 Fix**: Fixed double opacity application bug (window opacity AND paint alpha were both being applied, resulting in ~20% effective opacity at 50% fade). Now only uses window opacity for fading.
- widgets/overlay_timers.py
   - Centralised overlay timer helper providing `create_overlay_timer()` and `OverlayTimerHandle` for recurring UI-thread timers (clock/weather/media/Reddit). Prefers `ThreadManager.schedule_recurring` with ResourceManager tracking and falls back to a widget-local `QTimer` when no ThreadManager is available.
- widgets/beat_engine.py
   - `BeatEngine`: Extracted from SpotifyVisualizerWidget. Handles FFT processing, beat detection, and bar smoothing on the COMPUTE pool. Thread-safe state access for UI thread consumption.
   - `BeatEngineConfig`: Configuration dataclass for bar count, smoothing, decay, ghosting.
   - `BeatEngineState`: Current state dataclass with bars, peaks, and playing status.
- widgets/shadow_utils.py
  - Shadow rendering utilities for overlay widgets. Provides consistent drop shadow configuration and rendering.
- widgets/timezone_utils.py
  - Timezone handling and population for clock widgets. Provides timezone list and conversion utilities.

## UI
- ui/settings_dialog.py
  - Main settings dialog with custom title bar, dark theme, and tabbed interface
- ui/styled_popup.py
  - `StyledPopup`: Dark glass themed popup notifications (info, warning, error, success)
  - `StyledColorPicker`: Centralized dark-themed color picker dialog wrapping QColorDialog
- ui/tabs/sources_tab.py - Image source configuration (folders, RSS feeds)
- ui/tabs/display_tab.py - Display mode and hardware acceleration settings. Loads canonical timing defaults (45 s interval) from SettingsManager so tests cover `tests/test_display_tab.py::TestDisplayTab::test_display_tab_default_values`.
- ui/tabs/transitions_tab.py - Transition type, duration, and direction settings
- ui/tabs/widgets_tab.py - Overlay widget configuration (clocks, weather, media, Reddit). Includes stacking prediction labels next to position combos.
- ui/tabs/accessibility_tab.py - Accessibility features (background dimming, pixel shift)
- ui/tabs/presets_tab.py - Presets configuration slider (Purist, Essentials, Media, Full Monty, Custom). Custom preset preserves user settings.
- ui/widget_stack_predictor.py
  - `WidgetType`: Enum of widget types for prediction
  - `WidgetEstimate`: Dataclass for estimated widget dimensions
  - `get_position_status_for_widget()`: Main entry point for settings UI stacking prediction
  - Settings-only module - does NOT affect runtime, purely UI feedback
- ui/system_tray.py
  - System tray icon integration for background operation

## Weather
- weather/open_meteo_provider.py
  - `OpenMeteoProvider`: Weather data provider using Open-Meteo API (free, no API key required)
  - Geocoding, current conditions, and tomorrow's forecast (min/max temp + condition)

## Utilities
- utils/image_cache.py
  - Thread-safe LRU (QImage/QPixmap), memory-bound, eviction
- utils/image_prefetcher.py
  - IO-thread decode to QImage; prefetch N ahead; inflight tracking and optional compute-pool prescale of the first upcoming image to distinct display sizes via `ThreadManager.submit_compute_task`, storing results in `ImageCache` under `"path|scaled:WxH"` keys.
- utils/profiler.py
- utils/lockfree/spsc_queue.py
- utils/monitors.py
- utils/audio_capture.py
  - `AudioCaptureBackend`: Abstract base class for audio capture
  - `PyAudioWPatchBackend`: WASAPI loopback capture (Windows)
  - `SounddeviceBackend`: Cross-platform fallback using sounddevice
  - `create_audio_capture()`: Factory function for best available backend
- utils/lockfree/triple_buffer.py
  - Lock-free triple buffer for audio/visualization data passing between threads

## Rendering Backends
- rendering/backends/__init__.py
  - Backend registry/factory with settings-driven creation and telemetry
- rendering/backends/base.py
  - `RendererBackend`, `RenderSurface`, `TransitionPipeline` interfaces
- rendering/backends/opengl/backend.py
  - OpenGL renderer implementation (primary backend)
- rendering/backends/software/backend.py
  - CPU fallback renderer for troubleshooting scenarios
- rendering/gl_format.py
  - OpenGL format configuration helpers
- rendering/image_processor_async.py
  - Async image processing pipeline with worker thread support

## Themes
- themes/dark.qss
  - Dark theme QSS stylesheet for settings dialog and UI components

## Scripts
- scripts/build.ps1, scripts/build_mc.ps1 - PyInstaller build scripts
- scripts/build_nuitka.ps1, scripts/build_nuitka_mc.ps1 - Nuitka build scripts
- scripts/run_tests.py - Test runner with logging
- scripts/SRPSS_Installer.iss - Inno Setup installer script
- tools/synthetic_widget_benchmark.py - Qt-driven harness for Weather/Reddit/Clock/Media/Transition widgets. Forces `SRPSS_PERF_METRICS=1`, loads cached fixtures, and drives deterministic repaint loops with CLI toggles for widget counts, cadence, transition sizing/speed, and JSONL metric export (`Docs/Benchmark_Parity.md`). Captures `[PERF_WIDGET]` samples plus ThreadManager telemetry (`thread_pool_stats`) and frame-driver cadence stats (`frame_driver_timer`), emitting `[PERF_THREAD]` / `[PERF_TIMER frame_driver.tick]` warnings when pools saturate or ticks drift beyond max(100 ms, 1.5× interval). Media widgets reuse production-style shared feeds, artwork caches, and per-DPR scaled pixmaps. Acts as the synthetic parity harness for CI diffing alongside `tools/run_synthetic_benchmark_suite.py` + `tools/compare_synthetic_suite.py`.

## Root
- versioning.py
  - Application version management and build info

## Docs
- Docs/00_PROJECT_OVERVIEW.md – High-level project overview and architecture summary
- Docs/10_WIDGET_GUIDELINES.md – Canonical overlay widget design (card styling, fade/shadow via ShadowFadeProfile, Z-order/integration with DisplayWidget and overlay_manager, interaction gating)
- Docs/TestSuite.md – Canonical test documentation
- Docs/PERFORMANCE_BASELINE.md – Performance metrics and baselines
- Docs/SAKURA_PETALS_TRANSITION_DESIGN.md – Design document for future sakura petals transition (low priority)
- audits/*.md – Repository-level architecture/optimization audit documents with live checklists
  - audits/SEMANTICS_AUDIT_2025_12_18.md – Live checklist of semantics/naming corrections and code/doc comment updates for sanity/accuracy.

## Active Investigations
- CONTEXT_CACHE_CORRUPTION.md
  - Phase E: context menu / QGraphicsEffect cache corruption affecting overlay shadows/opacity
  - **Status**: MITIGATED - Smart Reddit link handling exits before corruption manifests
  - Root cause: `SetForegroundWindow()` steals focus, triggering activation messages that corrupt Qt's effect cache
  - Solution: Immediate exit when primary display is covered; users never see corruption
  - Details: `audits/PHASE_E_ROOT_CAUSE_ANALYSIS.md`

## Settings (selected)

### Sources
- sources.folders: list of folder paths to scan for images
- sources.rss_feeds: list of RSS/JSON feed URLs
- sources.local_ratio: int (0-100, default 60) - percentage of images from local sources vs RSS
- sources.rss_save_to_disk: bool (default false) - permanently save RSS images
- sources.rss_save_directory: str - directory for permanent RSS image storage
- sources.rss_background_cap: int (default 30) - max RSS images in queue at runtime
- sources.rss_rotating_cache_size: int (default 20) - max RSS images to keep between sessions
- sources.rss_stale_minutes: int (default 30) - TTL for stale RSS images (dynamic based on transition interval)
- sources.rss_refresh_minutes: int (default 10) - background RSS refresh interval

### Display
- display.refresh_sync: bool
- display.hw_accel: bool
- display.mode: fill|fit|shrink
- display.same_image_all_monitors: bool (default false) - same or different images per display

### Transitions
- transitions.type: str (Crossfade, Slide, Wipe, Diffuse, Block Puzzle Flip, Blinds, Peel, 3D Block Spins, Ripple (legacy: Rain Drops), Warp Dissolve, Crumble, Particle)
- transitions.random_always: bool
- transitions.random_choice: str
- transitions.duration_ms: int (global default duration in milliseconds)
- transitions.durations: map of transition type → duration_ms for per-type overrides
- transitions.slide.direction, transitions.slide.last_direction
- transitions.wipe.direction, transitions.wipe.last_direction
- transitions.pool: map of transition type → bool (participation in random rotation)
- transitions.crumble.piece_count: int (4-16, default 8)
- transitions.crumble.crack_complexity: float (0.5-2.0, default 1.0)
- transitions.crumble.mosaic_mode: bool (default false)
- transitions.particle.mode: str (Directional, Swirl, Converge)
- transitions.particle.direction: str (Left to Right, Right to Left, etc., Random Direction, Random Placement)
- transitions.particle.particle_radius: int (8-64, default 24)
- transitions.particle.swirl_turns: float (0.5-5.0, default 2.0)
- transitions.particle.swirl_order: int (0=Typical, 1=Center Outward, 2=Edges Inward)
- transitions.particle.use_3d_shading: bool (default true)
- transitions.particle.texture_mapping: bool (default true)
- transitions.particle.wobble: bool (default false)
- transitions.particle.gloss_size: int (16-128, default 64)
- transitions.particle.light_direction: int (0-4, default 0=Top-Left)

### Timing
- timing.interval: int seconds between image rotations

### Cache
- cache.prefetch_ahead: int (default 5)
- cache.max_items: int (default 24)
- cache.max_memory_mb: int (default 1024)
- cache.max_concurrent: int (default 2)

### Widgets
- widgets.clock.monitor: 'ALL'|1|2|3
- widgets.weather.monitor: 'ALL'|1|2|3
- widgets.media.monitor: 'ALL'|1|2|3
- widgets.reddit.monitor: 'ALL'|1|2|3
- widgets.shadows.*: global widget shadow configuration

### Accessibility
- accessibility.dimming.enabled: bool (default false)
- accessibility.dimming.opacity: int (10-90, default 30)
- accessibility.pixel_shift.enabled: bool (default false)
- accessibility.pixel_shift.rate: int (1-5, default 1)

## Audits
- audits/CODEBASE_AUDIT_2025_12_17.md: Codebase audit checklist and status snapshot
- audits/PHASE_E_ROOT_CAUSE_ANALYSIS.md: Context menu / effect cache corruption mitigation write-up
- audits/VISUALIZER_DEBUG.md: Spotify visualizer debugging notes

## Notes
- DPR-aware scaling in DisplayWidget → ImageProcessor to reduce GL upload cost
- GL overlays are persistent and initialized lazily on first use via `prepare_gl_overlay`; NoPartialUpdate enabled
- Prefetch pipeline: ImageQueue.peek_many → IO decode (QImage) → optional UI warmup (QPixmap) → optional compute pre-scale-to-screen (QImage) → transition
