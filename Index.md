# Index

A living map of modules, purposes, and key classes. Keep this up to date.

## Core Managers
- core/threading/manager.py
  - ThreadManager, ThreadPoolType, TaskPriority
  - UI dispatch helpers: run_on_ui_thread, single_shot
  - IO/Compute pools, lock-free stats and mutation queues
- core/resources/manager.py
  - ResourceManager for Qt object lifecycle tracking (register_qt, cleanup_all)
- core/events/event_system.py
  - EventSystem pub/sub (thread-safe)
- core/settings/settings_manager.py
  - SettingsManager (get/set, dot-notation, section helpers, JSON SST snapshot import/export)
  - Maps application name "Screensaver" to "Screensaver_MC" when running under the MC executable (e.g. `SRPSS MC`, `SRPSS_MC`, `main_mc.py`) so QSettings are isolated between the normal screensaver and MC profiles.
- core/animation/animator.py
  - AnimationManager and easing types
  - Animation class with optional FrameState for decoupled rendering
- core/animation/frame_interpolator.py
  - FrameState: timestamped progress samples for render-time interpolation
  - Decouples animation updates from rendering to eliminate timer jitter

## Engine
- engine/screensaver_engine.py
  - Orchestrator: sources → ImageQueue → display → transitions
  - Caching/prefetch integration via ImageCache + ImagePrefetcher
  - Random transition/type selection with non-repeating logic (persisted)
- engine/display_manager.py
  - Multi-monitor DisplayWidget management, sync scaffolding
- engine/image_queue.py
  - ImageQueue with RLock, shuffle/history, wraparound
  - peek() and peek_many(n) for prefetch look-ahead

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
- rendering/gl_profiler.py
  - `TransitionProfiler`: centralized profiling helper for GL compositor transitions. Tracks frame timing, min/max frame durations, and emits PERF logs. All compositor transitions (Slide, Wipe, Peel, BlockSpin, Warp, Raindrops, BlockFlip, Diffuse, Blinds) now use this single profiler instance instead of per-transition profiling fields.

## Transitions
- transitions/base_transition.py
  - BaseTransition with centralized animation
- transitions/overlay_manager.py
  - Persistent overlay helpers (`get_or_create_overlay`, `prepare_gl_overlay`, diagnostics/raise helpers) registering with shared ResourceManager; logs swap downgrades and readiness telemetry
- transitions/crossfade_transition.py, transitions/gl_crossfade_transition.py, transitions/gl_compositor_crossfade_transition.py
- transitions/slide_transition.py, transitions/gl_slide_transition.py, transitions/gl_compositor_slide_transition.py
- transitions/wipe_transition.py, transitions/gl_wipe_transition.py, transitions/gl_compositor_wipe_transition.py
  - Slide/Wipe directions stored independently in settings; Slide is cardinals only, Wipe includes diagonals
- transitions/diffuse_transition.py, transitions/gl_diffuse_transition.py, transitions/gl_compositor_diffuse_transition.py
  - Diffuse shapes: Rectangle, Membrane. Block size is clamped (min 4px) and shared between CPU and GL paths; the CPU fallback uses a simple block-based dissolve, while the Membrane shape is implemented only in the GLSL compositor path.
- transitions/block_puzzle_flip_transition.py, transitions/gl_block_puzzle_flip_transition.py, transitions/gl_compositor_blockflip_transition.py
- transitions/gl_blinds.py, transitions/gl_compositor_blinds_transition.py
  - GL-only Blinds transition using either a legacy overlay or the compositor; participates in GL prewarm and requires hardware acceleration.
- transitions/gl_compositor_peel_transition.py
  - Compositor-backed GL-only Peel transition (strip-based peel of the old image over the new image). Direction stored under `transitions.peel.direction`.
- transitions/gl_compositor_blockspin_transition.py
  - Compositor-backed GL-only 3D Block Spins transition rendering a single full-frame 3D slab (front/back/side faces) with directional axis control (LEFT/RIGHT spin around Y, UP/DOWN spin around X); legacy Block Puzzle grid settings are no longer used.
- transitions/gl_compositor_raindrops_transition.py
  - Compositor-backed GL-only Rain Drops transition using a raindrop-like diffuse region to reveal the new image.
- transitions/gl_compositor_warp_transition.py
  - Compositor-backed GL-only Warp Dissolve transition using a banded horizontal warp of the old image over a stable new image.
- transitions/gl_compositor_clawmarks_transition.py
  - Legacy compositor-backed GL-only Claw Marks / Shooting Stars transition. This effect has been removed from the active transition pool and its GLSL "claws" shader path is hard-disabled; the module is kept only as a reference and any legacy requests are mapped to a safe Crossfade-style fallback instead of a dedicated Claw transition.
- transitions/gl_compositor_shuffle_transition.py
  - Legacy compositor-backed GL-only Shuffle transition. This effect has been retired for v1.2 and is no longer part of the active transition set; any legacy references are mapped to a Crossfade fallback. The module is kept only as a reference and may be removed entirely in a future cleanup.

## Sources
- sources/base_provider.py
  - ImageMetadata
- sources/folder_source.py
- sources/rss_source.py

## Widgets
- widgets/clock_widget.py
  - Digital clock widget supporting three instances (Clock 1/2/3) with per-monitor selection, independent timezones, optional seconds and timezone labels
- widgets/weather_widget.py
  - Weather widget with per-monitor selection via settings (ALL or 1/2/3); planned QPainter-based iconography
 - widgets/media_widget.py
   - Spotify/media overlay widget driven by `core/media/media_controller.py`; per-monitor selection via `widgets.media`, corner positioning, background frame, and monochrome transport controls (Prev/Play/Pause/Next) over track metadata. Artwork uses a square frame for album covers and adapts to non-square thumbnails (e.g. Spotify video stills) by widening/tallening the card frame while still using a cover-style crop (no letterboxing/pillarboxing) so video-shaped assets respect their aspect ratio without changing existing album-art styling.
 - widgets/spotify_visualizer_widget.py
   - Spotify Beat Visualizer widget and background audio worker. Captures loopback audio via a shared `_SpotifyBeatEngine` (single process-wide engine), publishes raw mono frames into a lock-free `TripleBuffer`, performs FFT/band mapping and time-based smoothing on the COMPUTE pool (not UI thread), and exposes pre-smoothed bar magnitudes plus a derived GPU fade factor to the bar overlay. The QWidget owns the Spotify-style card, primary overlay fade, and drop shadow; bars are drawn by a dedicated `SpotifyBarsGLOverlay` QOpenGLWidget overlay created and managed by `DisplayWidget`, with a software (CPU) fallback path controlled by `widgets.spotify_visualizer.software_visualizer_enabled` when the renderer backend is set to Software. Bars only animate while the normalized media state is PLAYING; when Spotify is paused or stopped the beat engine decays targets to zero and the overlay’s 1-segment idle floor produces a flat single-row baseline. Card fade participates in the primary overlay wave, while the bar field uses a delayed secondary fade computed from the shared `ShadowFadeProfile` progress so the visualiser never pops in or shows stray green pixels.
 - widgets/spotify_bars_gl_overlay.py
   - GLSL/VAO Spotify bars overlay with DPI-aware geometry, per-bar peak envelope and 1-segment floor, rendering the main bar stack plus a configurable ghost trail driven by a decaying peak value. Uses the bar border colour for ghost segments with a vertical alpha falloff, respects `ghosting_enabled`, `ghost_alpha`, and `ghost_decay` from `widgets.spotify_visualizer.*` settings, and consumes the GPU fade factor from `SpotifyVisualizerWidget` so opacity ramps in after the card fade using the same `ShadowFadeProfile` timing.
 - widgets/spotify_volume_widget.py
   - Spotify-only vertical volume slider paired with the media card; gated on a Spotify GSMTC session and participating in the secondary Spotify fade wave via a GPU fade factor derived from the visualiser card’s `ShadowFadeProfile` progress so it fades in slightly after the card while respecting the same hard-exit / Ctrl interaction gating as the media widget.
  - widgets/reddit_widget.py
   - Reddit overlay widget showing top posts from a configured subreddit with 4- and 10-item layouts, per-monitor selection via `widgets.reddit`, shared overlay fade-in coordination, and click-through to the system browser.
 - widgets/overlay_timers.py
   - Centralised overlay timer helper providing `create_overlay_timer()` and `OverlayTimerHandle` for recurring UI-thread timers (clock/weather/media/Reddit). Prefers `ThreadManager.schedule_recurring` with ResourceManager tracking and falls back to a widget-local `QTimer` when no ThreadManager is available.

## Utilities
- utils/image_cache.py
  - Thread-safe LRU (QImage/QPixmap), memory-bound, eviction
- utils/image_prefetcher.py
  - IO-thread decode to QImage; prefetch N ahead; inflight tracking and optional compute-pool prescale of the first upcoming image to distinct display sizes via `ThreadManager.submit_compute_task`, storing results in `ImageCache` under `"path|scaled:WxH"` keys.
- utils/profiler.py
- utils/lockfree/spsc_queue.py
- utils/monitors.py

## Docs
- Docs/TestSuite.md – canonical tests
- Docs/AUDIT_*.md – technical audits
- Docs/FlashFlickerDiagnostic.md – flicker/banding symptom tracker and mitigation history
 - Docs/10_WIDGET_GUIDELINES.md – canonical overlay widget design (card styling, fade/shadow via ShadowFadeProfile, Z-order/integration with DisplayWidget and overlay_manager, interaction gating)
 - audits/*.md – repository-level Cleaning/Architecture/Optimization audit documents with live checklists

## Settings (selected)
- display.refresh_sync: bool
- display.hw_accel: bool
- display.mode: fill|fit|shrink
 - transitions.type (includes all CPU and GL/compositor-backed transition types such as Crossfade, Slide, Wipe, Diffuse, Block Puzzle Flip, Blinds, Peel, 3D Block Spins, Rain Drops, Warp Dissolve; legacy `Shuffle` values are mapped to `Crossfade` for back-compat)
- transitions.random_always: bool
- transitions.random_choice: str
- transitions.duration_ms: int (global default duration in milliseconds for transitions)
 - transitions.durations: map of transition type name → duration_ms used for per-transition duration independence (e.g. Crossfade/Slide/Wipe/Diffuse/Block Puzzle Flip/Blinds/Peel/3D Block Spins/Rain Drops/Warp Dissolve)
- transitions.slide.direction, transitions.slide.last_direction (legacy flat keys maintained for back-compat; nested `transitions['slide']['direction']` is the canonical form)
- transitions.wipe.direction, transitions.wipe.last_direction (legacy flat keys maintained for back-compat; nested `transitions['wipe']['direction']` is the canonical form)
- transitions.pool: map of transition type name → bool controlling whether a type participates in random rotation and C-key cycling (explicit selection remains allowed regardless of this flag; GL-only types still respect `display.hw_accel`).
- timing.interval: int seconds
- display.same_image_all_monitors: bool
- cache.prefetch_ahead: int (default 5)
- cache.max_items: int (default 24)
- cache.max_memory_mb: int (default 1024)
- cache.max_concurrent: int (default 2)
- widgets.clock.monitor: 'ALL'|1|2|3
- widgets.weather.monitor: 'ALL'|1|2|3
 - widgets.media.monitor: 'ALL'|1|2|3
 - widgets.reddit.monitor: 'ALL'|1|2|3
 - widgets.shadows.*: global widget shadow configuration shared by all overlay widgets

## Audits
- audits/v1_2 ROADMAP.md: Living roadmap for v1.2 features and performance goals
- audits/GLSL_Performance_Optimizations.md: GLSL shader optimization analysis and implementation notes
- audits/Performance_Audit_2025-12-05.md: Comprehensive performance audit identifying frame timing issues

## Notes
- DPR-aware scaling in DisplayWidget → ImageProcessor to reduce GL upload cost
- GL overlays are persistent and initialized lazily on first use via `prepare_gl_overlay`; NoPartialUpdate enabled
- Prefetch pipeline: ImageQueue.peek_many → IO decode (QImage) → optional UI warmup (QPixmap) → optional compute pre-scale-to-screen (QImage) → transition
