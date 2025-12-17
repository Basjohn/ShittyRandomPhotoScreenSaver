# Index

A living map of modules, purposes, and key classes. Keep this up to date.

## Refactor Status
- audits/REFACTOR_DISPLAY_WIDGET.md
  - **COMPLETE**: display_widget.py reduced from 4780 → 2783 lines (42% reduction)
  - Extracted: WidgetManager, InputHandler, TransitionController, ImagePresenter, MultiMonitorCoordinator
  - Target: ~1000 lines (further reduction deferred - current flow stable)
- audits/REFACTOR_GL_COMPOSITOR.md
  - **COMPLETE**: gl_compositor.py reduced from 4416 → 2179 lines (50.6% reduction)
  - Extracted: GLProgramCache, GLGeometryManager, GLTextureManager, GLTransitionRenderer, GLErrorHandler
  - Per-compositor instances for GLGeometryManager and GLTextureManager (OpenGL VAOs/textures are context-specific)

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
- core/settings/settings_manager.py
  - SettingsManager (get/set, dot-notation, section helpers, JSON SST snapshot import/export)
  - Maps application name "Screensaver" to "Screensaver_MC" when running under the MC executable (e.g. `SRPSS MC`, `SRPSS_MC`, `main_mc.py`) so QSettings are isolated between the normal screensaver and MC profiles.
  - `validate_and_repair()`: Validates settings types and repairs corrupted values (lists, ranges, enums)
  - `backup_settings(path)`: Creates timestamped JSON backup of all settings
  - `_get_default_image_folders()`: Dynamic default folders (user's Pictures) instead of hardcoded paths
- core/settings/defaults.py
  - Default settings values for all configuration options
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
  - `program_cache.py`: `GLProgramCache` singleton for centralized lazy-loading of shader programs. Replaces 10+ module-level globals with single cache class.
  - `geometry_manager.py`: `GLGeometryManager` - **per-compositor instance** for VAO/VBO management. Handles quad and box mesh creation/cleanup. Changed from singleton because OpenGL VAOs are context-specific.
  - `texture_manager.py`: `GLTextureManager` - **per-compositor instance** for texture upload, caching (LRU), and PBO pooling. Changed from singleton because OpenGL textures are context-specific.
  - `base_program.py`: `BaseGLProgram` ABC with shared vertex shader and compilation helpers.
  - `peel_program.py`: `PeelProgram` for the Peel transition GLSL.
  - `blockflip_program.py`: `BlockFlipProgram` for the BlockFlip transition GLSL.
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
  - **Fade coordination**: `request_overlay_fade_sync()`, `register_spotify_secondary_fade()`, `reset_fade_coordination()`
- rendering/input_handler.py
  - `InputHandler`: Extracted from DisplayWidget. Handles all user input including mouse/keyboard events, context menu triggers, and exit gestures.
  - **Phase E Enhancement (2025-12-16)**: Provides single choke point for context menu open/close triggers for deterministic effect invalidation ordering.
  - **Signals**: `exit_requested`, `settings_requested`, `next_image_requested`, `previous_image_requested`, `cycle_transition_requested`, `context_menu_requested`
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
  - `calculate_widget_collision()`: Check if two widget rects overlap
  - `calculate_stack_offset()`: Calculate offset for widget stacking
- widgets/clock_widget.py
  - Digital clock widget extending `BaseOverlayWidget`. Supports three instances (Clock 1/2/3) with per-monitor selection, independent timezones, optional seconds and timezone labels, analog/digital modes.
- widgets/weather_widget.py
  - Weather widget extending `BaseOverlayWidget`. Per-monitor selection via settings (ALL or 1/2/3). Features optional forecast line (tomorrow's min/max temp and condition, 8pt smaller than base font). Planned QPainter-based iconography.
- widgets/media_widget.py
  - Spotify/media overlay widget extending `BaseOverlayWidget`. Driven by `core/media/media_controller.py`; per-monitor selection via `widgets.media`, corner positioning, background frame, and monochrome transport controls (Prev/Play/Pause/Next) over track metadata. Artwork uses a square frame for album covers and adapts to non-square thumbnails.
- widgets/reddit_widget.py
  - Reddit overlay widget extending `BaseOverlayWidget`. Shows top posts from a configured subreddit with 4- and 10-item layouts, per-monitor selection via `widgets.reddit`, shared overlay fade-in coordination, and click-through to the system browser.
  - **Reddit link handling (2024-12-17)**: Smart A/B/C logic based on primary display coverage:
    - Case A: Primary covered + hard_exit → Exit immediately, bring browser to foreground
    - Case B: Primary covered + Ctrl held → Exit immediately, bring browser to foreground
    - Case C: MC mode (primary NOT covered) → Stay open, bring browser to foreground
  - System-agnostic detection using `QGuiApplication.primaryScreen()` (not screen index assumptions)
  - Supports a second instance (`reddit2_widget`) via `widgets.reddit2.*` settings with independent subreddit/position/display but inheriting all styling from Reddit 1.
- widgets/spotify_visualizer_widget.py
   - Spotify Beat Visualizer widget and background audio worker. Captures loopback audio via a shared `_SpotifyBeatEngine` (single process-wide engine), publishes raw mono frames into a lock-free `TripleBuffer`, performs FFT/band mapping on the COMPUTE pool (not UI thread), and exposes pre-smoothed bar magnitudes plus a derived GPU fade factor to the bar overlay.
   - **Visualizer tuning (v1.243)**: Uses noise floor subtraction (`noise_floor=2.1`) and dynamic range expansion (`expansion=2.5`) to achieve 0.02-1.0 bar range with reactive drops. V1.2-style smoothing (`smoothing=0.3`, `decay_rate=0.7`) provides aggressive 30% per-frame decay for visible drops while maintaining fast attack. Center-out gradient (`(1-dist)²*0.85+0.15`) ensures bass in center, treble at edges. See `audits/VISUALIZER_DEBUG.md` for tuning history.
   - The QWidget owns the Spotify-style card, primary overlay fade, and drop shadow; bars are drawn by a dedicated `SpotifyBarsGLOverlay` QOpenGLWidget overlay created and managed by `DisplayWidget`, with a software (CPU) fallback path controlled by `widgets.spotify_visualizer.software_visualizer_enabled` when the renderer backend is set to Software. Bars only animate while the normalized media state is PLAYING; when Spotify is paused or stopped the beat engine decays targets to zero and the overlay's 1-segment idle floor produces a flat single-row baseline. Card fade participates in the primary overlay wave, while the bar field uses a delayed secondary fade computed from the shared `ShadowFadeProfile` progress so the visualiser never pops in or shows stray green pixels.
 - widgets/spotify_bars_gl_overlay.py
   - GLSL/VAO Spotify bars overlay with DPI-aware geometry, per-bar peak envelope and 1-segment floor, rendering the main bar stack plus a configurable ghost trail driven by a decaying peak value. Uses the bar border colour for ghost segments with a vertical alpha falloff, respects `ghosting_enabled`, `ghost_alpha`, and `ghost_decay` from `widgets.spotify_visualizer.*` settings, and consumes the GPU fade factor from `SpotifyVisualizerWidget` so opacity ramps in after the card fade using the same `ShadowFadeProfile` timing.
- widgets/spotify_volume_widget.py
  - Spotify-only vertical volume slider paired with the media card; gated on a Spotify GSMTC session and participating in the secondary Spotify fade wave via a GPU fade factor derived from the visualiser card’s `ShadowFadeProfile` progress so it fades in slightly after the card while respecting the same hard-exit / Ctrl interaction gating as the media widget.
- widgets/dimming_overlay.py
   - `DimmingOverlay`: Semi-transparent black overlay for background dimming. Sits above transitions but below all widgets to reduce brightness and improve widget readability.
 - widgets/pixel_shift_manager.py
   - `PixelShiftManager`: Manages periodic 1px shifts of overlay widgets for burn-in prevention. Maximum drift of 4px in any direction with automatic drift-back. Defers during transitions.
 - widgets/context_menu.py
   - `ScreensaverContextMenu`: Dark-themed right-click context menu matching settings dialog styling. Provides Previous/Next image, transition selection submenu, Settings, Background Dimming toggle, Hard Exit Mode toggle, and Exit. Uses monochromatic icons and app-owned dark theme (no Windows accent bleed). Activated by right-click in hard exit mode or Ctrl+right-click in normal mode. Lazy-initialized by DisplayWidget for performance.
 - widgets/cursor_halo.py
   - `CursorHaloWidget`: Visual cursor indicator for Ctrl-held interaction mode. Displays a semi-transparent ring with center dot that follows the cursor. Supports fade-in/fade-out animations via AnimationManager.
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
- ui/tabs/display_tab.py - Display mode and hardware acceleration settings
- ui/tabs/transitions_tab.py - Transition type, duration, and direction settings
- ui/tabs/widgets_tab.py - Overlay widget configuration (clocks, weather, media, Reddit). Includes stacking prediction labels next to position combos.
- ui/tabs/accessibility_tab.py - Accessibility features (background dimming, pixel shift)
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
- sources.rss_background_cap: int (default 30) - max RSS images in queue
- sources.rss_stale_minutes: int (default 30) - TTL for stale RSS images
- sources.rss_rotating_cache_size: int (default 10) - minimum cached RSS images to keep

### Display
- display.refresh_sync: bool
- display.hw_accel: bool
- display.mode: fill|fit|shrink
- display.same_image_all_monitors: bool (default true) - same or different images per display

### Transitions
- transitions.type: str (Crossfade, Slide, Wipe, Diffuse, Block Puzzle Flip, Blinds, Peel, 3D Block Spins, Rain Drops, Warp Dissolve, Crumble)
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
- audits/COMPREHENSIVE_AUDIT_2025_12_14.md: **ACTIVE** Full codebase audit triggered by RSS reload bug - 67 items across testing, architecture, reliability, performance, UX, documentation
- audits/v1_2 ROADMAP.md: Living roadmap for v1.2 features and performance goals
- audits/GLSL_Performance_Optimizations.md: GLSL shader optimization analysis and implementation notes
- audits/Performance_Audit_2025-12-05.md: Comprehensive performance audit identifying frame timing issues
- audits/FLICKER_INVESTIGATION.md: Widget and transition flicker root cause analysis and fixes
- audits/UI_THREAD_AUDIT.md: UI thread blocking operations inventory and optimization plan
- audits/ARCHITECTURE_AUDIT.md: Exhaustive architecture audit with prioritized action plan
- audits/ARCHITECTURE_AUDIT_2025_12.md: December 2025 deep audit with live checklists (threading, centralization, resources, performance, deadlocks, cache) - 24 items completed
- audits/DIMMING_WIDGET_BUGS_2025_12.md: Dimming overlay and widget startup bugs investigation and fixes

## Notes
- DPR-aware scaling in DisplayWidget → ImageProcessor to reduce GL upload cost
- GL overlays are persistent and initialized lazily on first use via `prepare_gl_overlay`; NoPartialUpdate enabled
- Prefetch pipeline: ImageQueue.peek_many → IO decode (QImage) → optional UI warmup (QPixmap) → optional compute pre-scale-to-screen (QImage) → transition
