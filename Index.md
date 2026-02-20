# Index

A living map of modules, purposes, and key classes. Keep this up to date.

## Documentation

| Document | Purpose |
|----------|---------|
| Spec.md | Canonical architecture specification |
| Docs/DESYNC_STRATEGIES.md | Transition/visualizer desynchronization patterns |
| Docs/10_WIDGET_GUIDELINES.md | Widget implementation standards |
| Docs/GL_PIPELINE_ANALYSIS.md | GPU/GL contention analysis |
| Docs/TestSuite.md | Test documentation |
| Docs/SETTINGS_MIGRATION.md | JSON settings migration guide |
| Docs/QTIMER_POLICY.md | QTimer usage policy: when to use QTimer vs ThreadManager, intentional UI-thread timer locations |
| Docs/Defaults_Guide.md | All default settings, storage locations, SettingsManager API, safe change procedures |
| Docs/Visualizer_Debug.md | Authoritative Spotify visualizer architecture + per-mode defaults, debugging, regression harness |
| Docs/Visualizer_Presets_Plan.md | Comprehensive plan for per-visualizer-mode preset system with Advanced toggle |
| Bubble_Vizualiser_Plan.md | Bubble visualizer implementation plan (Phases 1-5 COMPLETE, Phase 6 in progress) |
| Burn_Transition_Plan.md | Burn transition implementation plan (not started) |

## Entry Points

| File | Purpose |
|------|---------|
| main.py | Screensaver entry point (SRPSS.scr/SRPSS.exe) |
| main_mc.py | Manual Controller entry point (SRPSS_MC) |

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| SRPSS_PERF_METRICS | false | Enable performance metrics logging to screensaver_perf.log |
| SRPSS_ENABLE_DEV | false | Enable experimental/broken features (e.g., Imgur widget, Starfield visualizer) |

## Core Managers

All business logic goes through these managers. Never use raw threading or Qt lifecycle methods.

| Manager | File | Key Classes | Purpose |
|---------|------|-------------|---------|
| ThreadManager | core/threading/manager.py | ThreadManager, ThreadPoolType, TaskPriority | IO/COMPUTE pools, UI dispatch |
| ResourceManager | core/resources/manager.py | ResourceManager | Qt object lifecycle tracking |
| SettingsManager | core/settings/settings_manager.py | SettingsManager | JSON settings with migration |
| AnimationManager | core/animation/animator.py | AnimationManager, Animation | All UI animations |
| ProcessSupervisor | core/process/supervisor.py | ProcessSupervisor | Worker process lifecycle |

## Core Modules

| Module | File | Key Classes/Functions | Purpose |
|--------|------|----------------------|---------|
| Threading | core/threading/manager.py | 
un_on_ui_thread(), single_shot() | UI thread dispatch helpers |
| Resources | core/resources/types.py | ResourceType, ResourceHandle | Resource type definitions |
| Events | core/events/event_system.py | EventSystem | Pub/sub event bus |
| Events | core/events/event_types.py | ImageChanged, TransitionStarted | Event type definitions |
| Frame Budget | core/performance/frame_budget.py | FrameBudget, GCController | Frame time allocation |
| Settings | core/settings/defaults.py | get_default_settings() | Canonical defaults |
| Settings | core/settings/models.py | DisplaySettings, TransitionSettings | Type-safe dataclass models |
| Settings | core/settings/json_store.py | JsonSettingsStore | JSON persistence layer (structured roots: widgets, transitions, custom_preset_backup, ui) |
| Storage Paths | core/settings/storage_paths.py | get_app_data_dir(), get_cache_dir(), get_rss_cache_dir(), get_feed_health_file(), run_all_migrations() | Canonical path resolver for all app data (settings, cache, state, logs). Replaces scattered %TEMP% paths. |
| Logging | core/logging/logger.py | get_logger(), is_perf_metrics_enabled() | Centralized logging |
| Media | core/media/media_controller.py | MediaController | GSMTC media state |
| Media | core/media/spotify_volume.py | SpotifyVolumeController | pycaw per-session volume control |
| Media | core/media/system_mute.py | is_available(), get_mute(), set_mute(), toggle_mute() | System-wide mute via IAudioEndpointVolume (pycaw) |
| ~~Eco Mode~~ | ~~core/eco_mode.py~~ | ~~EcoModeManager~~ | **REMOVED** - eco_mode fully stripped |
| Presets | core/settings/presets.py | PresetDefinition, apply_preset() | Widget presets system (moved from core/presets.py) |
| Vis Presets | core/settings/visualizer_presets.py | VisualizerPreset, get_presets(), apply_preset_to_config() | Per-visualizer-mode preset registry (4 presets per mode incl. Custom) |
| Vis Preset Slider | ui/tabs/media/preset_slider.py | VisualizerPresetSlider | Reusable 4-notch slider widget with Advanced toggle for per-mode presets |
| SST I/O | core/settings/sst_io.py | export_to_sst(), import_from_sst(), preview_import_from_sst() | Settings snapshot transport (extracted from settings_manager.py) |
| Lifecycle | core/lifecycle.py | Lifecycle, Cleanable | Runtime-checkable Protocols for start/stop/cleanup interface |
| Rate Limiting | core/reddit_rate_limiter.py | RedditRateLimiter | Reddit API rate limiting (per-process) |
| Reddit Helper Bridge | core/windows/reddit_helper_bridge.py | enqueue_url(), enqueue_settings_request() | ProgramData file queue + helper trigger (URLs, interactive desktop settings launch) |
| Reddit Helper Installer | core/windows/reddit_helper_installer.py | ensure_helper_installed(), trigger_helper_run() | Copies helper payload + launches in active user session (schtasks/token fallback) |
| Reddit Helper Worker | helpers/reddit_helper_worker.py | main(), process_queue() | Interactive desktop worker: opens URLs, handles open_settings action + completion tokens |
| Display Cleanup | rendering/display_cleanup.py | on_destroyed() | Widget destruction/cleanup logic (extracted from display_widget.py) |

## RSS Image Source (`sources/rss/`)

| Module | File | Key Classes | Purpose |
|--------|------|-------------|---------|
| Constants | sources/rss/constants.py | DEFAULT_RSS_FEEDS, SOURCE_PRIORITY | Feed URLs, priorities, rate limits, cache settings |
| Cache | sources/rss/cache.py | RSSCache | Disk cache, startup loading, LRU eviction, ResourceManager |
| Parser | sources/rss/parser.py | RSSParser, ParsedEntry | Stateless feed parsing (RSS/Flickr/Reddit), no network I/O |
| Downloader | sources/rss/downloader.py | RSSDownloader | Network I/O, atomic write, domain rate limiting, shutdown-aware |
| Health | sources/rss/health.py | FeedHealthTracker | Persistent feed health, exponential backoff |
| Coordinator | sources/rss/coordinator.py | RSSCoordinator, RSSState | State machine, dynamic budget, orchestration |
| Facade | sources/rss_source.py | RSSSource | Thin backward-compat wrapper around RSSCoordinator |

- **Wallpaper-only ingest**: `sources/rss/downloader.py` now rejects files below 1920×1080 via `QImageReader` metadata probes before anything touches the cache, ensuring undersized Flickr assets never consume disk or queue slots.
- **High-quality fallback budget**: `RSSCoordinator` enforces `MIN_WALLPAPER_REFRESH_TARGET` (11 images). When Flickr/json feeds underfill, it automatically tops up using Bing/NASA (trusted high-res feeds) with elevated per-feed limits, keeping the queue viable without extra network passes.

## Process Workers

| Worker | File | Purpose | Tests |
|--------|------|---------|-------|
| ImageWorker | core/process/workers/image_worker.py | Decode/prescale images in process | 	ests/test_image_worker.py |
| RSSWorker | core/process/workers/rss_worker.py | Fetch/parse RSS feeds | 	ests/test_rss_worker.py |
| ~~FFTWorker~~ | ~~removed~~ | Deprecated: inline FFT replaced process worker | - |
| TransitionWorker | core/process/workers/transition_worker.py | Precompute transition data | 	ests/test_transition_worker.py |
| BaseWorker | core/process/workers/base.py | Base class for all workers | - |

## Engine

| Module | File | Key Classes | Purpose |
|--------|------|-------------|---------|
| ScreensaverEngine | engine/screensaver_engine.py | ScreensaverEngine, EngineState | Core state machine, init, start (1158 lines after refactor) |
| Image Pipeline | engine/image_pipeline.py | load_image_via_worker, load_image_task, load_and_display_image_async, schedule_prefetch | Image loading, prefetch, prescale, cache warmup |
| Engine RSS | engine/engine_rss.py | load_rss_images_async, background_refresh_rss, merge_rss_images_from_refresh, get_rss_background_cap | RSS loading, background refresh, stale eviction |
| Engine Lifecycle | engine/engine_lifecycle.py | stop, cleanup, stop_qtimer_safe | Shutdown sequence, QTimer safety, resource cleanup |
| Engine Handlers | engine/engine_handlers.py | on_cycle_transition, on_settings_requested, on_sources_changed | Hotkey/event handlers |
| DisplayManager | engine/display_manager.py | DisplayManager | Multi-display management |
| ImageQueue | engine/image_queue.py | ImageQueue | Ratio-based image selection |

## Rendering - Core

| Module | File | Key Classes | Purpose |
|--------|------|-------------|---------|
| DisplayWidget | rendering/display_widget.py | DisplayWidget | Core fullscreen presenter (1595 lines, delegates to 6 helper modules) |
| Display Setup | rendering/display_setup.py | show_on_screen, setup_widgets, ensure_overlay_stack | Display initialization, widget setup, screen change |
| Display Image Ops | rendering/display_image_ops.py | set_processed_image, on_transition_finished, push_spotify_visualizer_frame | Image display pipeline, transition finish |
| Display GL Init | rendering/display_gl_init.py | init_renderer_backend, ensure_gl_compositor, ensure_render_surface | GL compositor/surface setup, cleanup |
| Display Context Menu | rendering/display_context_menu.py | show_context_menu, on_context_transition_selected | Context menu creation and handlers |
| Display Native Events | rendering/display_native_events.py | handle_nativeEvent, handle_eventFilter | Win32 native events, global event filter, media key passthrough (focus re-claim removed Feb 2026 to keep Settings responsive) |
| Display Input | rendering/display_input.py | handle_mousePressEvent, show_ctrl_cursor_hint, ensure_ctrl_cursor_hint | Cursor halo (shape from `input.halo_shape`), mouse press/move, `_halo_forwarding` guard |
| Display Overlays | rendering/display_overlays.py | start_overlay_fades, perform_activation_refresh | Overlay fades, window diagnostics |
| GLCompositor | rendering/gl_compositor.py | GLCompositorWidget | Core GL surface (1772 lines, thin delegates) |
| GL Transitions | rendering/gl_compositor_pkg/transitions.py | start_crossfade, start_warp, etc. | 12 transition start methods |
| GL Overlays | rendering/gl_compositor_pkg/overlays.py | paint_debug_overlay, paint_spotify_visualizer | Debug/Spotify/dimming overlays |
| GL Lifecycle | rendering/gl_compositor_pkg/gl_lifecycle.py | handle_initializeGL, init_gl_pipeline | GL init, pipeline, shader creation |
| GL Paint | rendering/gl_compositor_pkg/paint.py | handle_paintGL, paintGL_impl | Paint orchestration |
| GL Shader Dispatch | rendering/gl_compositor_pkg/shader_dispatch.py | can_use_*_shader, prepare_*_textures, paint_*_shader, compile_shader, get_viewport_size | Shader capability checks, texture prep, paint dispatch |
| GL Trans Lifecycle | rendering/gl_compositor_pkg/transition_lifecycle.py | cancel_current_transition | Transition cancel, Spotify state |
| GL Compositor Metrics | rendering/gl_compositor_pkg/compositor_metrics.py | begin_animation_metrics, finalize_paint_metrics, etc. | Perf-gated animation/paint/render-timer instrumentation |
| TransitionRenderer | rendering/gl_transition_renderer.py | GLTransitionRenderer | Centralized transition rendering |

## Rendering - Widget Management

| Module | File | Key Classes | Purpose |
|--------|------|-------------|---------|
| WidgetManager | rendering/widget_manager.py | WidgetManager | Widget lifecycle, Z-order, fade coordination via FadeCoordinator |
| FadeCoordinator | rendering/fade_coordinator.py | FadeCoordinator | Centralized lock-free fade synchronization |
| WidgetPositioner | rendering/widget_positioner.py | WidgetPositioner, PositionAnchor | Position calculation |
| WidgetFactories | rendering/widget_factories.py | ClockWidgetFactory, MediaWidgetFactory, etc. | Widget creation |
| SpotifyWidgetCreators | rendering/spotify_widget_creators.py | apply_spotify_vis_model_config() | Reusable vis config apply for init + live refresh |
| WidgetSetup | rendering/widget_setup.py | parse_color_to_qcolor(), compute_expected_overlays() | Setup helpers |

## Rendering - Input & Control

| Module | File | Key Classes | Purpose |
|--------|------|-------------|---------|
| InputHandler | 
endering/input_handler.py | InputHandler | Mouse/keyboard/media keys |
| TransitionController | 
endering/transition_controller.py | TransitionController | Transition lifecycle |
| ImagePresenter | 
endering/image_presenter.py | ImagePresenter | Pixmap management |
| MultiMonitorCoordinator | 
endering/multi_monitor_coordinator.py | MultiMonitorCoordinator | Cross-display coordination |

## Rendering - GL Infrastructure

| Module | File | Key Classes | Purpose |
|--------|------|-------------|---------|
| GL State | 
endering/gl_state_manager.py | GLStateManager, GLStateGuard | GL context state |
| GL Error | 
endering/gl_error_handler.py | GLErrorHandler | Centralized error handling |
| GL Profiler | 
endering/gl_profiler.py | TransitionProfiler | Frame timing metrics |
| Render Strategy | 
endering/render_strategy.py | TimerRenderStrategy | Timer-based rendering |
| Adaptive Timer | 
endering/adaptive_timer.py | AdaptiveTimerStrategy | Adaptive frame pacing |

> **Render timing defaults:** `GLCompositorWidget` now caches the first successfully detected refresh rate per display and reuses it for subsequent restarts/settings-dialog hops. If hardware/Qt fails to report a Hz value, the compositor, display setup, display widget, and adaptive timer all fall back to an uncapped 240 Hz target instead of 60 Hz so high-refresh panels never get stuck at 60 fps.

## Rendering - GL Programs

| Module | File | Key Class | Transition |
|--------|------|-----------|------------|
| Program Cache | 
endering/gl_programs/program_cache.py | GLProgramCache | All |
| Geometry | 
endering/gl_programs/geometry_manager.py | GLGeometryManager | All |
| Texture | 
endering/gl_programs/texture_manager.py | GLTextureManager | All |
| Crossfade | 
endering/gl_programs/crossfade_program.py | CrossfadeProgram | Crossfade |
| Slide | 
endering/gl_programs/slide_program.py | SlideProgram | Slide |
| Wipe | 
endering/gl_programs/wipe_program.py | WipeProgram | Wipe |
| Blinds | 
endering/gl_programs/blinds_program.py | BlindsProgram | Blinds |
| Diffuse | 
endering/gl_programs/diffuse_program.py | DiffuseProgram | Diffuse |
| BlockFlip | 
endering/gl_programs/blockflip_program.py | BlockFlipProgram | Block Puzzle Flip |
| BlockSpin | 
endering/gl_programs/blockspin_program.py | BlockSpinProgram | 3D Block Spins |
| Peel | 
endering/gl_programs/peel_program.py | PeelProgram | Peel |
| Warp | 
endering/gl_programs/warp_program.py | WarpProgram | Warp Dissolve |
| Raindrops | 
endering/gl_programs/raindrops_program.py | RaindropsProgram | Ripple |
| Crumble | 
endering/gl_programs/crumble_program.py | CrumbleProgram | Crumble |
| Particle | 
endering/gl_programs/particle_program.py | ParticleProgram | Particle |
| Burn | rendering/gl_programs/burn_program.py | BurnProgram | Burn |

## Transitions

| Transition | CPU File | GL File | Notes |
|------------|----------|---------|-------|
| Crossfade | 	ransitions/crossfade_transition.py | 	ransitions/gl_compositor_crossfade_transition.py | Basic fade |
| Slide | 	ransitions/slide_transition.py | 	ransitions/gl_compositor_slide_transition.py | 4 directions |
| Wipe | 	ransitions/wipe_transition.py | 	ransitions/gl_compositor_wipe_transition.py | 8 directions |
| Diffuse | 	ransitions/diffuse_transition.py | 	ransitions/gl_compositor_diffuse_transition.py | Rectangle/Membrane/Lines/Diamonds/Amorph shapes |
| Block Flip | 	ransitions/block_puzzle_flip_transition.py | 	ransitions/gl_compositor_blockflip_transition.py | Puzzle effect |
| Blinds | - | 	ransitions/gl_compositor_blinds_transition.py | GL only |
| Peel | - | 	ransitions/gl_compositor_peel_transition.py | GL only |
| Block Spin | - | 	ransitions/gl_compositor_blockspin_transition.py | GL only, 3D, 6 directions incl. diagonals |
| Raindrops | - | transitions/gl_compositor_raindrops_transition.py | GL only (Ripple), configurable ripple count 1-8, per-transition random seed for position variety |
| Warp | - | 	ransitions/gl_compositor_warp_transition.py | GL only |
| Crumble | - | 	ransitions/gl_compositor_crumble_transition.py | GL only |
| Particle | - | 	ransistions/gl_compositor_particle_transition.py | GL only |
| Burn | - | transitions/gl_compositor_burn_transition.py | GL only, 5 directions, jaggedness/glow/smoke/ash params |
| Base | 	ransitions/base_transition.py | - | Abstract base |
| Overlay Manager | 	ransitions/overlay_manager.py | - | GL overlay helpers |

## Widgets

### Base & Infrastructure

| Module | File | Key Classes | Purpose |
|--------|------|-------------|---------|
| Base Overlay | widgets/base_overlay_widget.py | BaseOverlayWidget, OverlayPosition | Abstract base for all widgets |
| Shadow Utils | widgets/shadow_utils.py | ShadowRenderer, ShadowFadeProfile | Drop shadow rendering |
| Overlay Timers | widgets/overlay_timers.py | create_overlay_timer() | ThreadManager timer helper |
| Context Menu | widgets/context_menu.py | ScreensaverContextMenu | Right-click menu |
| Cursor Halo | widgets/cursor_halo.py | CursorHaloWidget | Ctrl-held indicator; 5 shapes (circle/ring/crosshair/diamond/dot); `_halo_forwarding` guard prevents jitter feedback loop |
| Pixel Shift | widgets/pixel_shift_manager.py | PixelShiftManager | Burn-in prevention |

### Widget Implementations

| Widget | File | Key Class | Settings Prefix |
|--------|------|-----------|-----------------|
| Clock | widgets/clock_widget.py | ClockWidget | widgets.clock, widgets.clock2, widgets.clock3 |
| Weather | widgets/weather_widget.py | WeatherWidget | widgets.weather |
| Media | widgets/media_widget.py | MediaWidget | widgets.media (double-click artwork refresh: resets diff gating) |
| Reddit | widgets/reddit_widget.py | RedditWidget | widgets.reddit, widgets.reddit2 |
| RedditComponents | widgets/reddit_components.py | RedditPosition, RedditPost, smart_title_case, try_bring_reddit_window_to_front | Extracted helpers for reddit widget |
| Imgur | widgets/imgur/ | ImgurWidget, ImgurScraper, ImgurImageCache | widgets.imgur |

**Imgur Widget Details:**
- **widget.py**: ImgurWidget - Grid-based image display with configurable layout modes (vertical/square/hybrid), circular buffer rotation, smooth fade transitions, high-DPI support, **synchronous cache loading** (matches Reddit pattern for immediate fade-in with content)
- **scraper.py**: ImgurScraper - BeautifulSoup HTML parsing, conservative rate limiting (24 req/10min), exponential backoff, 429 handling, gallery page parsing (NOTE: not viable due to Imgur React SPA)
- **image_cache.py**: ImgurImageCache - LRU disk cache (100MB max), GIF-to-first-frame conversion, high-DPI pixmap loading, **metadata persistence after every put**, **auto-rebuild from files if metadata missing**
- **Features**: Concurrent downloads (4 at a time), cell pixmap caching, click-to-browser, header with logo colorization, fade coordination
- **Limitation**: Only 160x160 thumbnails available - Imgur deprecated size suffixes and gallery parsing requires JS rendering
| Spotify Visualizer | widgets/spotify_visualizer_widget.py | SpotifyVisualizerWidget | widgets.spotify_visualizer |
| Spotify Bars GL | widgets/spotify_bars_gl_overlay.py | SpotifyBarsGLOverlay | - |
| Spotify Volume | widgets/spotify_volume_widget.py | SpotifyVolumeWidget | widgets.spotify_volume |
| Mute Button | widgets/mute_button_widget.py | MuteButtonWidget | widgets.media.mute_button_enabled |

### Visualizer Components

| Module | File | Key Classes/Functions | Purpose |
|--------|------|-------------|---------|
| Beat Engine | widgets/beat_engine.py | BeatEngine, BeatEngineConfig, BeatEngineState | FFT processing |
| Audio Worker | widgets/spotify_visualizer/audio_worker.py | SpotifyVisualizerAudioWorker, VisualizerMode(SPECTRUM/OSCILLOSCOPE/STARFIELD/BLOB/HELIX/SINE_WAVE/BUBBLE), _AudioFrame | Audio capture coordination (delegates FFT to bar_computation) |
| Shared Beat Engine | widgets/spotify_visualizer/beat_engine.py | _SpotifyBeatEngine, get_shared_spotify_beat_engine | Shared engine with COMPUTE-pool smoothing, waveform + energy band extraction |
| Bar Computation | widgets/spotify_visualizer/bar_computation.py | fft_to_bars, compute_bars_from_samples, maybe_log_floor_state, get_zero_bars | DSP/FFT bar computation pipeline (inline, extracted from audio_worker) |
| Energy Bands | widgets/spotify_visualizer/energy_bands.py | EnergyBands, extract_energy_bands | Bass/mid/high/overall frequency band extraction from FFT bars |
| Card Height | widgets/spotify_visualizer/card_height.py | preferred_height, DEFAULT_GROWTH | Reusable card height expansion for all modes (spectrum/osc/starfield/blob/helix/sine/bubble); all defaults raised +1.0x |
| Bubble Simulation | widgets/spotify_visualizer/bubble_simulation.py | BubbleSimulation, BubbleState | CPU-side particle simulation for bubble mode; tick()/snapshot() on COMPUTE thread pool, coalesced results posted to UI thread |
| Config Applier | widgets/spotify_visualizer/config_applier.py | apply_vis_mode_kwargs, build_gpu_push_extra_kwargs, _color_or_none | Per-mode keyword↔attribute mapping; passes rainbow, ghosting, heartbeat, bubble settings (extracted from widget, ~430 LOC) |
| Mode Transition | widgets/spotify_visualizer/mode_transition.py | cycle_mode, mode_transition_fade_factor, persist_vis_mode | Mode-cycling crossfade logic (extracted from widget, ~120 LOC) |
| Tick Helpers | widgets/spotify_visualizer/tick_helpers.py | log_perf_snapshot, rebuild_geometry_cache, apply_visual_smoothing, get_transition_context, resolve_max_fps, update_timer_interval, pause_timer_during_transition, log_tick_spike | Tick utilities, perf metrics, geometry cache (extracted from widget) |
| Shader Loader | widgets/spotify_visualizer/shaders/__init__.py | SHARED_VERTEX_SHADER, load_fragment_shader, load_all_fragment_shaders | GLSL shader source loading for multi-shader architecture |

### Visualizer Shaders

| Shader | File | Uniforms | Purpose |
|--------|------|----------|---------|
| Spectrum | widgets/spotify_visualizer/shaders/spectrum.frag | u_bars[64], u_peaks[64], u_fill_color, u_border_color, u_ghost_alpha, u_slanted, u_border_radius | Segmented bar analyzer; 3 profiles (Legacy/Curved/Slanted); slanted: diagonal inner edges + linchpin both-side slant; curved: border radius 0-12px |
| Oscilloscope | widgets/spotify_visualizer/shaders/oscilloscope.frag | u_waveform[256], u_prev_waveform[256], u_osc_ghost_alpha, u_line_color, u_glow_*, u_reactive_glow, u_line_count, u_line{2,3}_{color,glow_color}, u_bass/mid/high_energy, u_osc_vertical_shift, u_rainbow_enabled, u_rainbow_hue_offset | Pure audio waveform with Catmull-Rom spline, per-band energy, equalized multi-line glow (3 lines: bass/mid/high), ghost trail (previous waveform overlay), rainbow hue cycling, vertical shift slider (-50 to 200) |
| Sine Wave | widgets/spotify_visualizer/shaders/sine_wave.frag | u_line_color, u_glow_*, u_reactive_glow, u_sensitivity, u_osc_speed, u_osc_sine_travel, u_sine_travel_line2, u_sine_travel_line3, u_card_adaptation, u_playing, u_line_count, u_line{2,3}_{color,glow_color}, u_bass/mid/high_energy, u_wave_effect, u_micro_wobble, u_osc_vertical_shift, u_heartbeat, u_heartbeat_intensity, u_rainbow_enabled, u_rainbow_hue_offset | Sine wave visualizer: audio-reactive amplitude, card adaptation, multi-line (up to 3) with per-line colors/travel, playback-gated oscillation, wave effect, micro wobble (smooth snake-like bass-driven), heartbeat (transient triangular bumps), rainbow hue cycling, vertical shift, line positioning (LOB=X phase, VShift=Y, Line2@70%, Line3@100%) |
| Starfield | widgets/spotify_visualizer/shaders/starfield.frag | u_star_density, u_travel_speed, u_star_reactivity, u_travel_time, u_nebula_tint{1,2} | Point-star starfield with nebula background, CPU-accumulated monotonic travel (dev-gated) |
| Blob | widgets/spotify_visualizer/shaders/blob.frag | u_blob_color, u_blob_pulse, u_blob_outline_color, u_blob_smoothed_energy, u_blob_reactive_deformation (0-3.0), u_blob_constant_wobble, u_blob_reactive_wobble | 2D SDF organic metaball with separated constant wobble (time-driven, zero when cw=0) and reactive wobble (energy-driven), vocal wobble, dip contraction, CPU-smoothed glow, quadratic reactive deformation (range 0-3.0) |
| Helix | widgets/spotify_visualizer/shaders/helix.frag | u_helix_turns, u_helix_double, u_helix_speed, u_helix_glow_*, u_helix_glow_color | Parametric double-helix with depth shading and user-controllable glow color |
| Bubble | widgets/spotify_visualizer/shaders/bubble.frag | u_bubble_count, u_bubbles_pos[110], u_bubbles_extra[110], u_specular_dir, u_outline_color, u_specular_color, u_gradient_light, u_gradient_dark, u_pop_color | SDF-based bubble visualizer: thin outlines, crescent specular highlights, warm gradient background, pop flash, rainbow hue cycling; CPU simulation on COMPUTE pool |

> **Default tweak (v2.75):** Spectrum mode now ships with Single Piece Mode enabled in `core/settings/defaults.py`, matching the preferred “pillar” presentation without manual toggles.

## Weather System

| Module | File | Key Classes | Purpose |
|--------|------|-------------|---------|
| WeatherWidget | widgets/weather_widget.py | WeatherWidget | Weather display with icons, detail metrics, forecast (1320 LOC) |
| WeatherComponents | widgets/weather_components.py | WeatherConditionIcon, WeatherDetailIcon, WeatherDetailRow, WeatherPosition, WeatherFetcher | Extracted helper classes for weather widget |
| OpenMeteoProvider | weather/open_meteo_provider.py | OpenMeteoProvider | Open-Meteo API integration, geocoding, caching |

**Features:**
- Day/night icon variants (auto-selected based on `is_day` from API)
- Monochrome icon mode (grayscale conversion on load, zero paint overhead)
- Font size hierarchy (location 100%, condition 80%, detail 50%)
- Detail metrics row (rain chance, humidity, wind speed)
- Icon alignment (LEFT/RIGHT/NONE)
- 30-minute refresh with early 30s refresh after startup
- Dual cache (provider + widget) with 30-minute TTL

## Image Processing

| Module | File | Key Classes | Purpose |
|--------|------|-------------|---------|
| Image Processor | 
endering/image_processor.py | ImageProcessor | Synchronous wrapper |
| Async Processor | 
endering/image_processor_async.py | AsyncImageProcessor | ThreadManager-based |
| Display Modes | 
endering/display_modes.py | DisplayMode | FILL/FIT/SHRINK enums |

## Key Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| display.hw_accel | bool | true | Enable hardware acceleration |
| display.mode | enum | fill | Image display mode |
| display.use_lanczos | bool | false | Use Lanczos resampling (now stored in defaults) |
| display.sharpen_downscale | bool | false | Sharpen when downscaling |
| 	timing.interval | int | 45 | Image rotation interval (seconds) |
| 	transitions.type | enum | Random | Transition type selected when Random pool disabled |
| 	transitions.duration_ms | int | 4000 | Baseline transition duration (per-type overrides exist) |
| input.hard_exit | bool | true | Require ESC/Q to exit (matches user profile) |
| input.halo_shape | str | circle | Cursor halo shape: circle, ring, crosshair, diamond, dot |
| cache.prefetch_ahead | int | 5 | Images to prefetch |
| cache.max_items | int | 24 | Max cache entries |

## Environment Variables

| Variable | Values | Purpose |
|----------|--------|---------|
| SRPSS_PERF_METRICS | 1/true/on/yes | Enable performance logging |
| SRPSS_DISABLE_LOGGING | 1/true/on/yes | Disable all logging |
| SRPSS_LOG_DIR | path | Override log directory |
| SRPSS_PROFILE_CPU | 1/true/on/yes | Enable CPU profiling |

## Log Files

| File | Contents | Enabled By |
|------|----------|------------|
| screensaver.log | Main application log (INFO+) | Always |
| screensaver_verbose.log | Debug/INFO details | --verbose or --debug |
| screensaver_perf.log | Performance metrics | SRPSS_PERF_METRICS=1 |
| screensaver_spotify_vis.log | Visualizer debug | SRPSS_PERF_METRICS=1 |
| screensaver_spotify_vol.log | Volume debug | SRPSS_PERF_METRICS=1 |

## Common Patterns

### Thread Safety

`python
# CORRECT - Use ThreadManager
from core.threading.manager import ThreadManager
threads = ThreadManager()
threads.submit_io_task(self.load_image)
threads.invoke_in_ui_thread(lambda: self.label.setPixmap(img))

# CORRECT - Use locks for state
with self._state_lock:
    self._ready = True
`

### Resource Management

`python
# CORRECT - Register Qt objects
from core.resources.manager import ResourceManager
resources = ResourceManager()
resources.register_qt(widget, "My widget")
`

### Settings Access

`python
# CORRECT - Use SettingsManager
from core.settings.settings_manager import SettingsManager
settings = SettingsManager()
value = settings.get("display.mode", "fill")
`

## UI - Settings Dialog Tabs

| Module | File | Key Classes/Functions | Purpose |
|--------|------|-----------------------|---------|
| SettingsDialog | ui/settings_dialog.py | SettingsDialog | Main settings dialog container (1595 LOC, refactored from ~1957) |
| SettingsAboutTab | ui/settings_about_tab.py | build_about_tab(), update_about_header_images() | About tab UI, header image scaling |
| WidgetsTab | ui/tabs/widgets_tab.py | WidgetsTab, NoWheelSlider | Widget config orchestrator (965 LOC, refactored from ~3200) |
| WidgetsTab Clock | ui/tabs/widgets_tab_clock.py | build_clock_ui(), load_clock_settings(), save_clock_settings(), _update_clock_mode_visibility() | Clock 1/2/3 UI, load, save; analog/digital mode visibility gating |
| WidgetsTab Weather | ui/tabs/widgets_tab_weather.py | build_weather_ui(), load_weather_settings(), save_weather_settings(), _update_weather_icon_visibility(), _update_weather_bg_visibility() | Weather UI, load, save; icon + background visibility gating |
| WidgetsTab Media | ui/tabs/widgets_tab_media.py | build_media_ui(), load_media_settings(), save_media_settings() | Spotify + Beat Visualizer UI coordinator; per-viz builders extracted to ui/tabs/media/ |
| Media Builders | ui/tabs/media/*.py | build_spectrum_ui(), build_oscilloscope_ui(), build_starfield_ui(), build_blob_ui(), build_helix_ui(), build_sine_wave_ui(), build_bubble_ui() | Per-visualizer UI builders (extracted from widgets_tab_media.py, ~1400 LOC) |
| Color Utils | ui/color_utils.py | qcolor_to_list(), list_to_qcolor() | Centralized QColor ↔ list conversion (replaces inline helpers in widgets_tab_media + widget_setup) |
| WidgetsTab Reddit | ui/tabs/widgets_tab_reddit.py | build_reddit_ui(), load_reddit_settings(), save_reddit_settings(), _update_reddit_enabled_visibility() | Reddit 1/2 UI, load, save; all controls gated by enabled checkbox |
| WidgetsTab Imgur | ui/tabs/widgets_tab_imgur.py | build_imgur_ui(), load_imgur_settings(), save_imgur_settings() | Imgur UI, load, save (dev-gated) |
| Settings Binding | ui/tabs/settings_binding.py | SliderBinding, CheckBinding, ComboDataBinding, ComboIndexBinding, ColorBinding, RawBinding, apply_bindings_load, collect_bindings_save | Declarative widget↔config key binding utility for reducing save/load boilerplate |
| Shared Styles | ui/tabs/shared_styles.py | NoWheelSlider, SPINBOX_STYLE, TOOLTIP_STYLE, SCROLL_AREA_STYLE | Centralised QSS constants and shared widgets (NoWheelSlider) for all settings tabs |
| SourcesTab | ui/tabs/sources_tab.py | SourcesTab | Image source config |
| TransitionsTab | ui/tabs/transitions_tab.py | TransitionsTab | Transition config |
| DisplayTab | ui/tabs/display_tab.py | DisplayTab | Display settings |
| AccessibilityTab | ui/tabs/accessibility_tab.py | AccessibilityTab | Accessibility options |
| PresetsTab | ui/tabs/presets_tab.py | PresetsTab | Setting presets |

## Utilities Boundary

| Package | Purpose | Key Modules |
|---------|---------|-------------|
| `utils/` | Runtime utilities (image, audio, monitors, lock-free) | `image_cache.py`, `image_loader.py`, `image_prefetcher.py`, `audio_capture.py`, `monitors.py`, `text_utils.py`, `profiler.py`, `lockfree/spsc_queue.py`, `lockfree/triple_buffer.py` |
| `core/utils/` | Framework utilities (decorators) | `decorators.py` (retry, throttle, etc.) |

## Audits

| Document | Purpose |
|----------|---------|
| audits/ARCHITECTURE_AUDIT_2026_02.md | Master architecture audit (210 files, 55K LOC) |
| audits/AUDIT_MONOLITH_REFACTORS.md | Refactoring plans for 8 files over 1500 lines |
| audits/AUDIT_THREADING.md | time.sleep, raw QTimer, untracked deleteLater sites |
| audits/AUDIT_DEAD_CODE.md | Dead/retired modules to clean up |
| audits/AUDIT_THREADING_RACE_CONDITIONS_2026_02.md | Widget Shiboken guard audit, ThreadPoolExecutor fix |
| audits/AUDIT_SETTINGS_GUI.md | Settings GUI audit: visibility gating, defaults, healing, hardcoded violations |
| audits/AUDIT_SETTINGS_SYSTEM.md | Settings system audit: models.py sync, migration, healing, hardcoded paths |
| audits/AUDIT_RESOURCE_VRAM.md | ResourceManager/VRAM/memory audit: GL handles, QTimer lifecycle, leak risks |
| audits/AUDIT_CODE_HYGIENE.md | Code hygiene: monoliths, unused imports, dead code, QTimer policy, bare exceptions, naming, save pattern bugs |

## Test Organization

| Test File | Coverage |
|-----------|----------|
| tests/test_process_supervisor.py | Worker process lifecycle |
| tests/test_image_worker.py | Image decode/prescale |
| ~~tests/test_fft_worker.py~~ | Removed (FFT worker deprecated) |
| tests/test_settings_binding.py | Settings binding utility (26 tests) |
| ~~tests/test_painter_shadow.py~~ | Removed (orphaned, superseded by shadow_utils) |
| tests/test_settings_models.py | Settings dataclasses |
| tests/test_widget_positioner.py | Widget positioning |
| tests/test_gl_state_manager.py | GL state management |
| tests/test_transition_*.py | Transition types |
| tests/test_widgets_tab.py | WidgetsTab creation, defaults, save/load roundtrip |
| tests/test_adaptive_timer.py | AdaptiveTimer strategies, thread lifecycle (27 tests) |
| tests/test_display_integration.py | DisplayWidget transitions, engine, settings, widgets (57 tests) |
| tests/test_weather_widget.py | Weather fetch, display, caching (26 tests) |
| tests/test_slide_jitter.py | Slide transition frame timing (7 tests) |
| tests/test_widget_manager.py | WidgetManager lifecycle, fade, factory |
| tests/test_sine_wave_gl_fix.py | Sine wave GL overlay fix regression (mode validation, cycle, shader, card height) |
| tests/test_micro_wobble_math.py | Micro wobble shader math: energy weighting, spatial freq, displacement bounds, smoothness (20 tests) |
| tests/test_action_plan_3_0.py | Action Plan 3.0: heartbeat settings/math, artwork double-click fix, halo forwarding guard, halo shapes, sine line positioning, rainbow/ghosting roundtrip, shader source validation (37 tests) |
| tests/test_visualizer_settings_plumbing.py | Visualizer settings plumbing: bubble kwargs, card height, rainbow greyscale, model/creator/applier/overlay/shader/UI plumbing, bubble simulation thread safety (30 tests) |
| tests/unit/test_policy_compliance.py | Threading/import policy enforcement |
