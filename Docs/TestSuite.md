# Test Suite Index

**Purpose**: Detailed reference for all tests - what they check and when to use them.

**Total Tests**: ~300+ tests across 100 test files

---

## Quick Navigation

- [Core Infrastructure](#core-infrastructure) - Threading, process management, events
- [Rendering & GL](#rendering--gl) - OpenGL, compositor, transitions
- [Widgets & Overlays](#widgets--overlays) - All widget types, positioning, lifecycle
- [Image Pipeline](#image-pipeline) - Queue, cache, prefetch, processing
- [Settings & Configuration](#settings--configuration) - Settings manager, models, dialogs
- [Input & Interaction](#input--interaction) - Keyboard, mouse, media keys
- [Integration & Workflow](#integration--workflow) - End-to-end scenarios
- [Performance & Telemetry](#performance--telemetry) - Timing, dt_max, workloads
- [MC (Manual Controller)](#mc-manual-controller) - MC-specific features
- [Regression Tests](#regression-tests) - Specific bug fixes

---

## Core Infrastructure

### Threading & Concurrency

| Test File | What It Tests | When To Use |
|-----------|---------------|-------------|
| `test_thread_manager.py` | ThreadManager IO/COMPUTE pools, task lifecycle, shutdown | Changing ThreadManager, debugging thread leaks |
| `test_threading.py` | Threading utilities, run_on_ui_thread, locks | Low-level threading changes |
| `test_qt_timer_threading.py` | QTimer behavior in threads | Timer-related threading issues |
| `test_decorators.py` | @rate_limited, @memoize, @timing decorators | Changes to decorator implementations |

### Process Management

| Test File | What It Tests | When To Use |
|-----------|---------------|-------------|
| `test_process_supervisor.py` | Worker lifecycle, message contracts, health monitoring | Changes to ProcessSupervisor, worker types |
| `test_image_worker.py` | Image worker message processing, shared memory | Image loading pipeline changes |
| `test_fft_worker.py` | FFT worker for visualizer audio processing | Audio/FFT pipeline changes |
| `test_fft_worker_gating.py` | FFT worker gating when Spotify not playing | Visualizer playback gating |
| `test_worker_latency_tuning.py` | Worker latency thresholds and tuning | Performance tuning, latency issues |
| `test_eco_mode_worker_control.py` | Worker suspension in eco mode | Eco mode changes, worker control |

### Events & Messaging

| Test File | What It Tests | When To Use |
|-----------|---------------|-------------|
| `test_events.py` | Event system, EventBus, subscriptions | Event system changes |

### Resource Management

| Test File | What It Tests | When To Use |
|-----------|---------------|-------------|
| `test_resource_manager.py` | ResourceManager Qt object tracking, cleanup | Resource cleanup issues, Qt object leaks |
| `test_memory_pooling.py` | QPixmap/QImage pooling for GC pressure | Memory optimization changes |

---

## Rendering & GL

### GL State Management

| Test File | What It Tests | When To Use |
|-----------|---------------|-------------|
| `test_gl_state_manager.py` | GLStateManager state machine, transitions, callbacks | GL initialization changes |
| `test_gl_state_manager_overlay.py` | GL overlay integration patterns | Overlay GL state issues |
| `test_gl_state_and_error_handling.py` | GL error recovery, fallback policies | GL error handling changes |
| `test_gl_fallback_policy.py` | Group A→B→C fallback (shader→QPainter→software) | GL fallback changes |

### GL Compositor

| Test File | What It Tests | When To Use |
|-----------|---------------|-------------|
| `test_gl_compositor_transitions.py` | GL compositor-backed transitions | New GL transitions, compositor changes |
| `test_gl_compositor_transition_lifecycle.py` | Transition start/stop/cleanup in compositor | Transition lifecycle bugs |
| `test_gl_compositor_cleanup.py` | GL compositor resource cleanup | GL resource leaks |
| `test_gl_texture_streaming.py` | Texture upload, PBO pooling, LRU cache | Texture streaming changes |
| `test_gl_overlay_no_black_frames.py` | No black frames during startup/transition | Black frame bugs |

### Transitions

| Test File | What It Tests | When To Use |
|-----------|---------------|-------------|
| `test_transitions.py` | Transition factory, basic transition types | New transition types |
| `test_transitions_integration.py` | Transition integration with DisplayWidget | Transition display issues |
| `test_transition_integration.py` | Crossfade, Slide, Wipe integration | Specific transition bugs |
| `test_transition_state_manager.py` | TransitionStateManager per-transition state | Transition state tracking |
| `test_transition_telemetry.py` | Transition metrics, timing collection | Performance analysis |
| `test_transition_endframe.py` | Final frame correctness (no artifacts) | End-of-transition visuals |
| `test_block_puzzle_flip.py` | Block Puzzle Flip transition specifically | Block flip bugs |
| `test_diffuse_transition.py` | Diffuse transition (Rectangle/Membrane) | Diffuse effect changes |
| `test_particle_transition.py` | Particle transition (8 directions, swirl, converge) | Particle effect changes |
| `test_slide_transition.py` | Slide transition cardinal directions | Slide-specific issues |

### Adaptive Timing

| Test File | What It Tests | When To Use |
|-----------|---------------|-------------|
| `test_adaptive_timer.py` | AdaptiveTimerStrategy, state machine, exit_immediate | Timer behavior changes |
| `test_animation.py` | AnimationManager, easing functions, frame pacing | Animation system changes |

---

## Widgets & Overlays

### Widget Lifecycle

| Test File | What It Tests | When To Use |
|-----------|---------------|-------------|
| `test_widget_lifecycle.py` | WidgetLifecycleState machine (CREATED→INITIALIZED→ACTIVE→HIDDEN→DESTROYED) | Widget lifecycle changes |
| `test_widget_manager.py` | WidgetManager overlay lifecycle, Z-order, raises | Widget management changes |
| `test_widget_manager_refresh.py` | Widget refresh on settings change, position updates | Settings refresh issues |
| `test_overlay_ready_state.py` | Overlay ready/waiting states | Overlay initialization issues |

### Widget Positioning

| Test File | What It Tests | When To Use |
|-----------|---------------|-------------|
| `test_widget_positioner.py` | WidgetPositioner 9-position layout algorithm | Position calculation changes |
| `test_widget_positioning_comprehensive.py` | All widget positioning scenarios | Positioning bugs |
| `test_widget_visual_padding.py` | Visual offset alignment (analog clocks, etc.) | Padding/margin issues |
| `test_visualizer_smart_positioning.py` | Spotify visualizer positioning relative to media widget | Visualizer positioning |

### Widget Factories

| Test File | What It Tests | When To Use |
|-----------|---------------|-------------|
| `test_widget_factories.py` | WidgetFactoryRegistry, all widget factories | New widget types |

### Individual Widgets

| Test File | What It Tests | When To Use |
|-----------|---------------|-------------|
| `test_clock_widget.py` | ClockWidget (digital + analog), multi-clock support | Clock widget changes |
| `test_weather_widget.py` | WeatherWidget, Open-Meteo integration | Weather widget, fetch issues |
| `test_media_widget.py` | MediaWidget, GSMTC integration, artwork | Media display changes |
| `test_reddit_widget.py` | RedditWidget, fetch, display, clicks | Reddit widget issues |
| `test_spotify_visualizer_widget.py` | SpotifyVisualizerWidget, BeatEngine, bar rendering | Visualizer widget changes |
| `test_spotify_visualizer_integration.py` | Visualizer integration with DisplayWidget | Visualizer integration |
| ~~`test_painter_shadow.py`~~ | *(Removed — superseded by `shadow_utils.py`)* | — |

### Widget Behavior

| Test File | What It Tests | When To Use |
|-----------|---------------|-------------|
| `test_widget_raise_order.py` | Z-order raising, overlay stacking | Widget visibility issues |
| `test_widget_overlay_regressions.py` | Regression tests for overlay bugs | Overlay bug fixes |
| `test_widget_performance.py` | Widget rendering performance | Widget perf issues |
| `test_pixel_shift.py` | Burn-in prevention pixel shifting | Pixel shift changes |
| `test_no_legacy_widget_position_strings.py` | Settings don't use WidgetPosition. strings | Settings migration validation |

---

## Image Pipeline

### Queue & Sources

| Test File | What It Tests | When To Use |
|-----------|---------------|-------------|
| `test_image_queue.py` | ImageQueue, local/RSS ratio, fallback | Queue behavior changes |
| `test_rss_behavior.py` | RSSSource, fetch, cache, TTL | RSS feed handling |

### Processing

| Test File | What It Tests | When To Use |
|-----------|---------------|-------------|
| `test_image_processor.py` | ImageProcessor scaling, DPR handling, modes | Image processing changes |
| `test_lanczos_scaling.py` | Lanczos resampling quality | Scaling quality issues |

### Display Integration

| Test File | What It Tests | When To Use |
|-----------|---------------|-------------|
| `test_display_integration.py` | DisplayWidget, multi-monitor, show/hide | Display changes |
| `test_pan_scan_integration.py` | Pan & scan animation integration | Pan/scan feature changes |
| `test_multi_monitor_focus.py` | Focus handling across monitors | Multi-monitor focus issues |
| `test_multidisplay_sync.py` | Multi-display transition synchronization | Sync issues |
| `test_startup_black_flash.py` | No black flash on startup | Startup visual issues |

---

## Settings & Configuration

### Settings Management

| Test File | What It Tests | When To Use |
|-----------|---------------|-------------|
| `test_settings_manager.py` | SettingsManager get/set, migration, defaults | Core settings changes |
| `test_settings_models.py` | Type-safe settings dataclasses (22 tests) | Settings model changes |
| `test_settings.py` | Settings persistence, JSON store | Settings storage changes |
| `test_settings_schema.py` | Settings schema validation | Schema changes |
| `test_settings_sync.py` | Settings synchronization | Sync issues |
| `test_settings_defaults_parity.py` | Defaults match between code and UI | Default value consistency |
| `test_settings_profile_separation.py` | Normal vs MC profile isolation | Profile isolation issues |

### Settings Dialog

| Test File | What It Tests | When To Use |
|-----------|---------------|-------------|
| `test_settings_dialog.py` | SettingsDialog UI, tabs, validation | Dialog UI changes |
| `test_display_tab.py` | Display tab controls, defaults | Display settings UI |
| `test_transitions_tab.py` | Transitions tab, duration controls | Transition settings UI |
| `test_widgets_tab.py` | Widgets tab, enable/disable | Widget settings UI |
| `test_presets.py` | Preset save/load, SST import/export | Preset functionality |
| `test_settings_no_sources_popup.py` | Warning when no sources configured | Source validation |

---

## Input & Interaction

### Keyboard & Mouse

| Test File | What It Tests | When To Use |
|-----------|---------------|-------------|
| `test_ctrl_interaction_mode.py` | Ctrl+click interaction mode, widget editing | Interaction mode changes |
| `test_double_click_navigation.py` | Double-click next image navigation | Double-click behavior |
| `test_media_keys.py` | Global media key handling (play/pause/next/prev) | Media key issues |
| `test_media_key_feedback.py` | Media key visual feedback | Key feedback changes |
| `test_s_hotkey_workflow.py` | S-key settings dialog workflow | Settings hotkey |

### Interaction Modes

| Test File | What It Tests | When To Use |
|-----------|---------------|-------------|
| `test_dimming_and_interaction_fixes.py` | Dimming overlay with interaction modes | Dimming + interaction |

---

## Integration & Workflow

### Full Workflows

| Test File | What It Tests | When To Use |
|-----------|---------------|-------------|
| `test_integration_full_workflow.py` | End-to-end: engine → display → widgets → cleanup | Major architectural changes |
| `test_engine_lifecycle.py` | Engine start/stop/restart states | Engine lifecycle changes |

### Reddit-Specific

| Test File | What It Tests | When To Use |
|-----------|---------------|-------------|
| `test_reddit_exit_logic.py` | Smart Reddit exit (A/B/C cases) | Reddit exit behavior |
| `test_reddit_rate_limiter.py` | Reddit API rate limiting | Rate limit handling |
| `test_reddit_progressive_loading.py` | Progressive post loading | Loading performance |
| `test_reddit_paint_caching.py` | Reddit widget paint caching | Paint performance |
| `test_reddit_helper_installer.py` | Reddit helper installation | Helper installer |

---

## Performance & Telemetry

### Timing & Performance

| Test File | What It Tests | When To Use |
|-----------|---------------|-------------|
| `test_perf_dt_max.py` | dt_max spike detection and analysis | Frame timing issues |
| `test_frame_timing_workload.py` | Frame timing under workload (isolated) | Heavy workload timing |
| `test_performance.py` | General performance metrics | Performance regression |
| `test_slide_jitter.py` | Slide transition jitter measurement | Jitter issues |
| `test_render_strategy_smoke.py` | Render strategy performance smoke test | Render strategy changes |

### Logging

| Test File | What It Tests | When To Use |
|-----------|---------------|-------------|
| `test_logging_routing.py` | Log routing to different files | Logging changes |
| `test_log_throttling.py` | Log deduplication, throttling | Throttling behavior |
| `test_logging_console_encoding.py` | Console log encoding handling | Encoding issues |

---

## MC (Manual Controller)

| Test File | What It Tests | When To Use |
|-----------|---------------|-------------|
| `test_mc_window_flags.py` | MC window flags (Tool vs SplashScreen) | MC window behavior |
| `test_mc_keyboard_input.py` | MC keyboard handling | MC input changes |
| `test_mc_context_menu.py` | MC context menu | MC UI changes |
| `test_mc_eco_mode.py` | MC eco mode | MC eco functionality |

---

## Regression Tests

| Test File | What It Tests | Bug Fixed |
|-----------|---------------|-----------|
| `test_flicker_fix_integration.py` | Flicker during transitions | Flicker on rapid image change |
| `test_phase_e_effect_corruption.py` | Effect cache corruption from context menus | Phase E corruption |
| `test_prewarm_no_deadlock.py` | GL prewarm deadlock prevention | Startup deadlock |
| `test_widget_overlay_regressions.py` | Various overlay widget regressions | Multiple overlay bugs |
| `test_visualizer_preservation.py` | Visualizer state preservation | Visualizer reset bugs |
| `test_visualizer_playback_gating.py` | Visualizer playback state gating | Bars when paused |
| `test_visualizer_modes.py` | Visualizer direction/swirl/converge modes | Mode switching |

---

## Running Tests

### Run All Tests
```powershell
cd f:\Programming\Apps\ShittyRandomPhotoScreenSaver2_5
python tests\pytest.py
```

### Run Specific Test File
```powershell
python tests\pytest.py tests\test_gl_compositor_transitions.py -v
```

### Run Specific Test
```powershell
python tests\pytest.py tests\test_settings_models.py::TestClockWidgetSettings::test_from_settings_accepts_prefixed_position -v
```

### Run With Performance Metrics
```powershell
$env:SRPSS_PERF_METRICS='1'
python tests\pytest.py tests\test_perf_dt_max.py -v
```

### Run Isolated Frame Timing Tests
```powershell
python tests\pytest.py tests\test_frame_timing_workload.py -v
```

---

## Test Infrastructure

### Files

| File | Purpose |
|------|---------|
| `conftest.py` | Pytest fixtures, shared test utilities |
| `pytest.ini` | Pytest configuration |
| `pytest.py` | Custom test runner with logging setup |
| `_gl_test_utils.py` | GL testing utilities |

### Key Fixtures (from conftest.py)

| Fixture | Provides |
|---------|----------|
| `qtbot` | QtBot for GUI testing (from pytest-qt) |
| `qapp` | QApplication instance |

---

## Test Categories Summary

| Category | Count | Files |
|----------|-------|-------|
| Core Infrastructure | 11 | Threading, process, events, resources |
| Rendering & GL | 18 | GL state, compositor, transitions |
| Widgets & Overlays | 24 | All widget types, positioning |
| Image Pipeline | 6 | Queue, processing, display |
| Settings & Config | 11 | Settings, dialogs, presets |
| Input & Interaction | 6 | Keys, mouse, media controls |
| Integration & Workflow | 7 | End-to-end, Reddit, lifecycle |
| Performance & Telemetry | 7 | Timing, logging, perf |
| MC | 4 | Manual Controller specific |
| Regression | 6 | Specific bug fix tests |
| **Total** | **100** | |

---

**Last Updated**: Feb 1, 2026 (post cleanup: removed 4 outdated worker test files)
