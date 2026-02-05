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

## Entry Points

| File | Purpose |
|------|---------|
| main.py | Screensaver entry point (SRPSS.scr/SRPSS.exe) |
| main_mc.py | Manual Controller entry point (SRPSS_MC) |

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
| Settings | core/settings/json_store.py | JsonSettingsStore | JSON persistence layer |
| Logging | core/logging/logger.py | get_logger(), is_perf_metrics_enabled() | Centralized logging |
| Media | core/media/media_controller.py | MediaController | GSMTC media state |
| Media | core/media/spotify_volume.py | SpotifyVolumeController | pycaw volume control |
| Eco Mode | core/eco_mode.py | EcoModeManager | MC build resource conservation |
| Rate Limiting | core/reddit_rate_limiter.py | RedditRateLimiter | Reddit API rate limiting |

## Process Workers

| Worker | File | Purpose | Tests |
|--------|------|---------|-------|
| ImageWorker | core/process/workers/image_worker.py | Decode/prescale images in process | 	ests/test_image_worker.py |
| RSSWorker | core/process/workers/rss_worker.py | Fetch/parse RSS feeds | 	ests/test_rss_worker.py |
| FFTWorker | core/process/workers/fft_worker.py | FFT computation for visualizer | 	ests/test_fft_worker.py |
| TransitionWorker | core/process/workers/transition_worker.py | Precompute transition data | 	ests/test_transition_worker.py |
| BaseWorker | core/process/workers/base.py | Base class for all workers | - |

## Engine

| Module | File | Key Classes | Purpose |
|--------|------|-------------|---------|
| ScreensaverEngine | ngine/screensaver_engine.py | ScreensaverEngine | Main orchestrator |
| DisplayManager | ngine/display_manager.py | DisplayManager | Multi-display management |
| ImageQueue | ngine/image_queue.py | ImageQueue | Ratio-based image selection |

## Rendering - Core

| Module | File | Key Classes | Purpose |
|--------|------|-------------|---------|
| DisplayWidget | 
endering/display_widget.py | DisplayWidget | Borderless fullscreen presenter |
| GLCompositor | 
endering/gl_compositor.py | GLCompositorWidget | Single GL surface for transitions |
| TransitionRenderer | 
endering/gl_transition_renderer.py | GLTransitionRenderer | Centralized transition rendering |

## Rendering - Widget Management

| Module | File | Key Classes | Purpose |
|--------|------|-------------|---------|
| WidgetManager | rendering/widget_manager.py | WidgetManager | Widget lifecycle, Z-order, fade coordination via FadeCoordinator |
| FadeCoordinator | rendering/fade_coordinator.py | FadeCoordinator | Centralized lock-free fade synchronization |
| WidgetPositioner | rendering/widget_positioner.py | WidgetPositioner, PositionAnchor | Position calculation |
| WidgetFactories | rendering/widget_factories.py | ClockWidgetFactory, MediaWidgetFactory, etc. | Widget creation |
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

## Transitions

| Transition | CPU File | GL File | Notes |
|------------|----------|---------|-------|
| Crossfade | 	ransitions/crossfade_transition.py | 	ransitions/gl_compositor_crossfade_transition.py | Basic fade |
| Slide | 	ransitions/slide_transition.py | 	ransitions/gl_compositor_slide_transition.py | 4 directions |
| Wipe | 	ransitions/wipe_transition.py | 	ransitions/gl_compositor_wipe_transition.py | 8 directions |
| Diffuse | 	ransitions/diffuse_transition.py | 	ransitions/gl_compositor_diffuse_transition.py | Block/Membrane shapes |
| Block Flip | 	ransitions/block_puzzle_flip_transition.py | 	ransitions/gl_compositor_blockflip_transition.py | Puzzle effect |
| Blinds | - | 	ransitions/gl_compositor_blinds_transition.py | GL only |
| Peel | - | 	ransitions/gl_compositor_peel_transition.py | GL only |
| Block Spin | - | 	ransitions/gl_compositor_blockspin_transition.py | GL only, 3D |
| Raindrops | - | 	ransitions/gl_compositor_raindrops_transition.py | GL only (Ripple) |
| Warp | - | 	ransitions/gl_compositor_warp_transition.py | GL only |
| Crumble | - | 	ransitions/gl_compositor_crumble_transition.py | GL only |
| Particle | - | 	ransitions/gl_compositor_particle_transition.py | GL only |
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
| Cursor Halo | widgets/cursor_halo.py | CursorHaloWidget | Ctrl-held indicator |
| Pixel Shift | widgets/pixel_shift_manager.py | PixelShiftManager | Burn-in prevention |

### Widget Implementations

| Widget | File | Key Class | Settings Prefix |
|--------|------|-----------|-----------------|
| Clock | widgets/clock_widget.py | ClockWidget | widgets.clock, widgets.clock2, widgets.clock3 |
| Weather | widgets/weather_widget.py | WeatherWidget | widgets.weather |
| Media | widgets/media_widget.py | MediaWidget | widgets.media |
| Reddit | widgets/reddit_widget.py | RedditWidget | widgets.reddit, widgets.reddit2 |
| Spotify Visualizer | widgets/spotify_visualizer_widget.py | SpotifyVisualizerWidget | widgets.spotify_visualizer |
| Spotify Bars GL | widgets/spotify_bars_gl_overlay.py | SpotifyBarsGLOverlay | - |
| Spotify Volume | widgets/spotify_volume_widget.py | SpotifyVolumeWidget | widgets.spotify_volume |

### Visualizer Components

| Module | File | Key Classes | Purpose |
|--------|------|-------------|---------|
| Beat Engine | widgets/beat_engine.py | BeatEngine, BeatEngineConfig, BeatEngineState | FFT processing |
| Audio Worker | widgets/spotify_visualizer/audio_worker.py | SpotifyVisualizerAudioWorker | Audio capture coordination |

## Weather System

| Module | File | Key Classes | Purpose |
|--------|------|-------------|---------|
| WeatherWidget | widgets/weather_widget.py | WeatherWidget, WeatherConditionIcon, WeatherDetailIcon, WeatherDetailRow | Weather display with icons, detail metrics, forecast |
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
| display.use_lanczos | bool | false | Use Lanczos resampling |
| display.sharpen_downscale | bool | false | Sharpen when downscaling |
| 	iming.interval | int | 45 | Image rotation interval (seconds) |
| 	ransitions.type | enum | Crossfade | Transition type |
| 	ransitions.duration_ms | int | 1300 | Transition duration |
| input.hard_exit | bool | false | Require ESC/Q to exit |
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

## Test Organization

| Test File | Coverage |
|-----------|----------|
| tests/test_process_supervisor.py | Worker process lifecycle |
| tests/test_image_worker.py | Image decode/prescale |
| tests/test_fft_worker.py | FFT computation |
| tests/test_settings_models.py | Settings dataclasses |
| tests/test_widget_positioner.py | Widget positioning |
| tests/test_gl_state_manager.py | GL state management |
| tests/test_transition_*.py | Transition types |
