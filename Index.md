# Index

A living map of modules, purposes, and key classes. Keep this up to date.

## Documentation

| Document | Purpose |
|----------|---------|
| Spec.md | Canonical architecture specification and single source of truth |
| Docs/00_PROJECT_OVERVIEW.md | High-level introduction, pillars, documentation map |
| Docs/10_WIDGET_GUIDELINES.md | Widget implementation standards + compositor/fade policies |
| Docs/Defaults_Guide.md | Canonical defaults, storage locations, change workflow |
| Docs/QTIMER_POLICY.md | QTimer vs ThreadManager policy and allowed UI-thread timers |
| Docs/TestSuite.md | Test matrix, fixtures, execution order (run `pytest --collect-only tests -q` to see all individual test functions) |
| Docs/Historical_Bugs.md | Chronological archive of dated regressions, failed approaches, fix notes, and reopenings; use this for historical bug context rather than bloating Index/Spec |
| Docs/Guardrails.md | Project policies and guardrails: threading, resource management, settings, visualizer modes, testing, performance, transitions, documentation |
| Docs/Visualizer_Reference.md | Consolidated visualizer documentation: architecture, signal contract, baseline tuning, per-mode reference, settings/UI, testing/validation |
| Docs/Visualizer_Change_Checklist.md | Current cross-system checklist for visualizer setting additions/removals/retunes so UI, runtime, presets, tools, tests, and docs stay aligned |
| Docs/Visualizer_Reset_Matrix.md | Canonical reset/freshness matrix for cold start, mode switches, same-mode apply, preset cycling, and waveform gates |
| Current_Plan.md | Live project plan, rollout status, open validation items, and current implementation backlog |
| Docs/Custom_Style_Implementation.md | Shared SVG/QSS/QRC patterns for custom controls, settings-shell styling, and CSS specificity notes |
| Docs/Visualizer_Setting_Guide.md | Canonical per-mode technical baselines and tuning notes. **Spectrum "Cake" preset is exempt from bar-count changes** per 2026 audit. |
| Docs/Visualizer_Mode_Consolidation_Mental_Model.md | Reusable playbook for consolidating visualizer-mode settings, presets, runtime contracts, and validation without freezing artistic content |
| Spec.md (Visualizer buckets) | Advanced then Technical collapsible buckets per mode (Spectrum/Bubble/Blob/Sine/Osc); state persisted via `_visualizer_adv_state`/`_visualizer_tech_state`. **Helix/Starfield are deprecated** (dev-only remnants kept for backwards compatibility). |

`Index.md` should stay focused on the current map. Use `Current_Plan.md` for active rollout, validation state, and temporary audit work, and `Docs/Historical_Bugs.md` for dated regressions, failed approaches, reopenings, and final fix summaries.

## Tooling

| Tool | Purpose |
|------|---------|
| tools/regen_qrc.py | Regenerates `ui/resources/icons_rc.py` from `icons.qrc`, wraps `pyside6-rcc`, shows success popup |
| tools/visualizer_preset_repair.py | DPI-aware GUI + CLI batch runner. Repairs curated preset JSON/SST files (prunes junk keys, rewrites lean payloads with a single `snapshot.widgets.spotify_visualizer` block, preserves/infers `preset_index`, backfills mandatory per-mode technical + critical visual keys, promotes stale non-mirrored Spectrum `Low/Mid` lane families into the explicit `Low-Mid/Vocal` family without flattening boundary drift, performs one-time legacy Spectrum scalar-to-lane promotion when cleaning genuinely old payloads, and strips retired authored keys like `energy_boost`/`use_raw_energy` plus dead Spectrum scalar lane keys from clean payloads), keeps at most two rotating backups per preset, prunes stale numbered backup spillover on rewrite, persists undo state under `temp/visualizer_preset_backups/undo_state.json`, supports undo, and offers `--repair-all`, `--audit-curated`, and `--reindex-curated` for repo-wide preset hygiene. Tests treat curated packs as fluid authored content and rely on structural guards such as slot uniqueness, schema hygiene, and source/release parity rather than rigid authored-feel baselines. |
| tools/reddit_helper_task_harness.py | Elevated smoke harness for the reusable `SRPSS_RedditHelper` scheduled-task authority layer. Registers the same XML contract the installer uses, proves query/run behavior, and cleans up afterward. |
| tests/run_chunked.py | Chunked test runner — splits full suite into N subprocess chunks (default 4) for memory/timeout isolation |

## Entry Points

| File | Purpose |
|------|---------|
| main.py | Screensaver entry point (SRPSS.scr/SRPSS.exe); script/debug launches accept `--fresh` to clear the runtime log folder before logging starts (preserving `worker_*.log`) |
| main_mc.py | Manual Controller entry point (SRPSS_MC) |

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| SRPSS_ENABLE_DEV | false | Enable experimental/broken features (Imgur widget, Starfield visualizer). See Spec.md § Developer Feature Gate |
| SRPSS_PERF_METRICS | false | Enable performance metrics logging to `screensaver_perf.log` |
| SRPSS_VIZ_DIAGNOSTICS | false | Verbose Spotify visualizer diagnostics (`--viz-diagnostics` CLI alias); gates `[SPOTIFY_VIS][FLOOR]`, `[SPOTIFY_VIS][BARS]`, `[SPOTIFY_VIS][LATENCY]`, and timer instrumentation |
| SRPSS_DISABLE_LOGGING | false | Kill all file/console logging entirely (tools only) |
| SRPSS_LOG_DIR | (auto) | Override log directory. Default: `./logs` (dev) or `%LOCALAPPDATA%\Screensaver\logs` (frozen) |
| SRPSS_FORCE_SOUNDDEVICE | false | Force sounddevice backend instead of PyAudio-WPATCH on Windows (`utils/audio_capture.py`) |
| SRPSS_SPOTIFY_VIS_DEBUG_CONST | 0.0 | Debug: feed constant bar values (float >0) to the visualizer instead of live audio (`tick_pipeline.py`, `audio_worker.py`) |
| SRPSS_HALO_PERF_MIN_MS | 0.25 | Minimum milliseconds for cursor halo perf logging threshold (`widgets/cursor_halo.py`) |

## CLI Flags

| Flag | Purpose |
|------|---------|
| `--debug`, `-d` | Enable debug logging (verbose log, console output) |
| `--viz` | Enable Spotify visualizer subsystem logging |
| `--viz-diagnostics`, `--viz-diag` | Enable per-frame visualizer floor/bar/latency diagnostics (also sets `SRPSS_VIZ_DIAGNOSTICS=1`) |
| `--fresh` | Clear runtime log folder before logging starts (preserves `worker_*.log`) |
| `-devblob` | Enable dev-gated Blob visualizer mode. See Spec.md § Visualizer Mode Dev Gates |
| `-devgoo` | Enable dev-gated Goo visualizer mode. See Spec.md § Visualizer Mode Dev Gates |

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
| Dev Gates | core/dev_gates.py | is_blob_enabled(), is_goo_enabled(), force_gate() | CLI-driven dev gates (`-devblob`, `-devgoo`) for visualizer modes under active development. See Spec.md § Visualizer Mode Dev Gates |
| Settings | core/settings/defaults.py | get_default_settings() | Canonical defaults |
| Settings | core/settings/models.py | DisplaySettings, TransitionSettings | Type-safe dataclass models |
| Vis Mode Registry | core/settings/visualizer_mode_registry.py | VisualizerModeDescriptor, iter_visualizer_mode_descriptors(), get_preset_key(), is_mode_active() | Shared visualizer mode identity contract: mode ids, display labels, preset keys, and preset-slider ownership wiring. Dev-gated modes (blob, goo) are filtered out of `iter_visualizer_mode_descriptors()` when their CLI flag is absent; `is_mode_active()` provides the runtime check. |
| Vis Preset Indices | core/settings/visualizer_preset_indices.py | get_missing_preset_fallback_index(), resolve_preset_index_from_mapping(), resolve_all_preset_indices_from_mapping() | Shared preset-index fallback and sparse lookup contract decoupled from curated preset file loading |
| Vis Settings Contract | core/settings/visualizer_settings_contract.py | resolve_visualizer_baselines(), build_visualizer_mode_kwargs(), resolve_visualizer_active_mode_rainbow_state() | Shared baseline/per-mode fallback contract for sparse visualizer settings, used by `SpotifyVisualizerSettings` loaders |
| Vis Settings Snapshot | core/settings/visualizer_settings_snapshot.py | normalize_visualizer_section_mapping(), normalize_visualizer_mode_payload() | Canonical `widgets.spotify_visualizer` normalization for defaults reset, SST import/export, preset payload parsing, and custom visualizer snapshot/export flows |
| Vis Signal Policy | widgets/spotify_visualizer/config_applier.py | _resolve_continuous_energy_bands(), build_gpu_push_extra_kwargs() | Shared visualizer signal handoff. Blob and Bubble now use explicit mode-owned pre-AGC continuous energy because shared post-AGC/dynamic-floor pressure can flatten them; this is runtime routing only, not a persisted schema toggle. All GPU extra kwargs must still stay mode-local. |
| Bubble Gradient Semantics | core/settings/bubble_gradient_semantics.py | resolve_bubble_gradient_direction(), get_bubble_gradient_shader_mode(), get_bubble_gradient_shader_vector() | Canonical Bubble gradient semantics contract: legacy-label migration, persisted semantics versioning, and brightest-point label -> shader mapping |
| Settings | core/settings/json_store.py | JsonSettingsStore | JSON persistence layer (structured roots: widgets, transitions, custom_preset_backup, ui) |
| Storage Paths | core/settings/storage_paths.py | get_app_data_dir(), get_cache_dir(), get_rss_cache_dir(), get_feed_health_file(), run_all_migrations() | Canonical path resolver for all app data (settings, cache, state, logs). Replaces scattered %TEMP% paths. |
| Logging | core/logging/logger.py | get_logger(), is_perf_metrics_enabled(), clear_logs_for_fresh_start() | Centralized logging + pre-start `--fresh` log cleanup |
| Media | core/media/media_controller.py | WindowsGlobalMediaController, create_media_controller(app_filter) | GSMTC media state; app_filter selects provider session (spotify/musicbee) |
| Media | core/media/spotify_volume.py | SpotifyVolumeController(provider=) | pycaw per-session volume control; provider-aware (spotify/musicbee process filter) |
| Media Runtime State | widgets/media/runtime_state.py | MediaWidgetRuntimeState, cache_retained_display_info(), build_retained_display_info(), should_probe_provider_failover() | Shared runtime-only retained-display contract for the media card: cached metadata/artwork, missing-session tracking, paused/non-reactive downgrade, and provider auto-fallback cooldown/state |
| Media Dependent Visibility | widgets/media/dependent_visibility.py | resolve_anchor_visibility(), sync_anchor_dependent_visibility() | Shared anchor-visibility contract for media-dependent satellite widgets such as the volume slider and mute button |
| Media Artwork Layout | widgets/media/artwork_layout.py | compute_artwork_frame_size() | Shared media-artwork sizing helper: keeps square/near-square album art aspect-correct while wide Spotify video-frame thumbnails use a square cover crop instead of stretching or letterboxing |
| Animation | core/animation/types.py | EasingCurve, resolve_easing(name, auto_default) | Shared easing name→enum mapper for all transitions (replaces 12× _resolve_easing duplication) |
| Media | core/media/system_mute.py | is_available(), get_mute(), set_mute(), toggle_mute() | System-wide mute via IAudioEndpointVolume (pycaw) |
| ~~Eco Mode~~ | ~~core/eco_mode.py~~ | ~~EcoModeManager~~ | **REMOVED** - eco_mode fully stripped |
| Presets | core/settings/presets.py | PresetDefinition, apply_preset() | Widget presets system (moved from core/presets.py) |
| Vis Presets | core/settings/visualizer_presets.py | VisualizerPreset, get_presets(), apply_preset_to_config(), get_packaged_visualizer_presets_dir() | Per-visualizer-mode preset registry. Script mode uses the repo `presets/visualizer_modes/<mode>` tree directly; frozen SCR and MC builds now converge on the shared ProgramData curated tree, while packaged/bundled preset assets remain the replacement/bootstrap source. Snapshot overrides are **explicit-only** from `visualizer_mode_overrides` and require marker+mode+preset_index to avoid full-SST export contamination. |
| Preset Repair Tool | tools/visualizer_preset_repair.py | repair_file(), repair_all_presets(), reindex_curated_presets(), audit_all_presets() | Curated preset repair/audit/reindex tool. Missing keys are injected from canonical mode-normalized defaults rather than broad handwritten maps, backups stay under `temp/visualizer_preset_backups` with a two-backup rotation plus persistent undo ledger, and curated-tree mutations now auto-regenerate the shipped preset artifacts. |
| Vis Preset Manifest | core/visualizer_preset_manifest.py | load_curated_visualizer_preset_manifest(), resolve_curated_visualizer_manifest_entries(), scan_curated_visualizer_preset_tree(), sync_curated_preset_tree(), write_curated_visualizer_preset_manifest(), mirror_curated_visualizer_preset_tree(), regenerate_repo_shipped_visualizer_preset_artifacts() | Shipped curated-preset cleanup + regeneration helpers. `presets/visualizer_modes` is the authored source tree; repo-local release trees/manifests are generated from it, frozen stale-file cleanup still uses the manifest contract, and source-aware flows (Replace Visualizers/build prep) reconcile against the actual curated tree before rewriting the target manifest from that mirrored view. |
| Shader Loader | widgets/spotify_visualizer/shaders/__init__.py | preload_fragment_shaders(), load_fragment_shader(), load_all_fragment_shaders() | Fragment shader source loading plus cached startup preload for the visualizer shader set |
| Vis Mode Binding | ui/tabs/media/visualizer_mode_binding.py | initialize_visualizer_mode_combo(), load_visualizer_mode_selection(), load_visualizer_preset_indices(), load_visualizer_rainbow_state() | Shared WidgetsTab adapter for visualizer mode combo initialization plus per-mode preset and rainbow state binding |
| Blob Binding | ui/tabs/media/blob_settings_binding.py | load_blob_mode_settings(), collect_blob_mode_settings() | Blob-owned WidgetsTab load/save adapter so Blob enhancements do not expand the central media-tab coordinator |
| Blob Builder | ui/tabs/media/blob_builder.py | build_blob_ui(), build_blob_growth() | Blob-authored UI builder. Owns the lean Blob control surface with real collapsible buckets in the order `Body -> Appearance -> Shaper -> Layout -> Glow -> Advanced -> Technical`, mode-aware gating for shaper-vs-generic controls, aligned ghost toggle rows, and dependent glow-row hiding when `Reactive Glow` is off. |
| Blob Shape Editor | ui/tabs/media/blob_shape_editor.py | BlobShapeEditor, _PolarEditorCanvas, _EnergyChip | Spatial energy routing editor: two side-by-side polar canvases (base shape + reaction limit) with draggable profile nodes, copy-on-drag energy source palette (bass/mid/vocals/treble/transient), per-energy directional arrow handles used to route inward vs outward live response, top-origin angular authoring (`0.0 = top`) that runtime must mirror exactly, and a ring preview that now mirrors the runtime contract (single authored contour plus derived thickness band) instead of a fake independently-authored inner contour. Runtime routing now treats reaction-canvas energy nodes as authoritative, with base/unqualified nodes retained only as legacy fallback when no react routing exists. The editor reference circle is intentionally smaller now and the outer authoring radius ceiling is larger so stretched reaction silhouettes have materially more editing room inside the same box. Right-click profile-node deletion is part of the editor contract again. |
| Bubble Binding | ui/tabs/media/bubble_settings_binding.py | load_bubble_mode_settings(), collect_bubble_mode_settings() | Bubble-owned WidgetsTab load/save adapter so Bubble direction/color/state work does not expand the central media-tab coordinator; routes gradient labels through the shared semantics helper instead of local direction math |
| Spectrum Binding | ui/tabs/media/spectrum_settings_binding.py | load_spectrum_mode_settings(), collect_spectrum_mode_settings() | Spectrum-owned WidgetsTab load/save adapter, including shape-editor state, mirrored/linear lane-strength arrow persistence, legacy scalar-lane promotion, and spectrum ghost/glow translation |
| Spectrum Builder | ui/tabs/media/spectrum_builder.py | build_spectrum_ui() | Spectrum-authored UI builder. Owns the real collapsible bucket surface (`Appearance -> Shape` and `Render -> Audio -> Ghost`) plus the explicit `SEGMENTS` / `BAR` render-mode buttons that author canonical `spectrum_render_mode`; the Audio bucket now keeps global Spectrum controls while lane power lives in the shaper arrows |
| Oscilloscope Binding | ui/tabs/media/oscilloscope_settings_binding.py | load_oscilloscope_mode_settings(), collect_oscilloscope_mode_settings() | Oscilloscope-owned WidgetsTab load/save adapter, including multi-line color binding and ghost state translation |
| Sine Binding | ui/tabs/media/sine_wave_settings_binding.py | load_sine_wave_mode_settings(), collect_sine_wave_mode_settings() | Sine-owned WidgetsTab load/save adapter, including multi-line travel/offset state and ghost state translation |
| Vis Preset Slider | ui/tabs/media/preset_slider.py | VisualizerPresetSlider | Reusable 4-notch slider widget with Advanced toggle for per-mode presets |
| SST I/O | core/settings/sst_io.py | export_to_sst(), import_from_sst(), preview_import_from_sst() | Settings snapshot transport (extracted from settings_manager.py) |
| Lifecycle | core/lifecycle.py | Lifecycle, Cleanable | Runtime-checkable Protocols for start/stop/cleanup interface |
| Rate Limiting | core/reddit_rate_limiter.py | RedditRateLimiter | Reddit API rate limiting (per-process) |
| Reddit Helper Bridge | core/windows/reddit_helper_bridge.py | enqueue_url(), enqueue_settings_request() | ProgramData-backed queue writer only. Secure-desktop / SYSTEM runs should queue work here and do no browser launching themselves; Winlogon/screensaver-origin entries now stamp a source-aware `not_before_ts` so the user-session watcher does not race Explorer handoff. |
| Reddit Helper Runtime | core/windows/reddit_helper_runtime.py | ensure_helper_runtime(), is_helper_healthy(), resolve_helper_command(), request_session_helper_shutdown() | User-session helper lifecycle contract: heartbeat health, durable interactive scheduled-task launch authority for real SCR handoff, queue-only secure-desktop bridge behavior, session-ticket/watcher health checks, graceful session-owned shutdown requests, and Windows-safe stale-helper PID probing/reaping via `OpenProcess/GetExitCodeProcess` instead of `os.kill(pid, 0)` semantics. |
| Reddit Helper Installer | core/windows/reddit_helper_installer.py | _running_as_system(), _log_helper_event() | Minimal retained helper utilities only; old token/scheduler/runtime-drop behavior is intentionally gone. |
| Reddit Helper Worker | helpers/reddit_helper_worker.py | main(), process_queue(), _run_watcher(), _acquire_watcher_singleton() | Interactive desktop worker: opens URLs, handles open_settings action + completion tokens, writes heartbeat, waits for stable shell readiness after secure-desktop handoff, prefers `os.startfile()` with `QDesktopServices`/`webbrowser` fallbacks, defers shell-not-ready entries without burning retry budget, canonicalizes retry/backoff, expires stale queue entries safely, self-exits for session-scoped launches once the owner is gone and the queue is idle, and enforces a per-session watcher singleton so duplicate helpers do not stack. |
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

| Worker | File | Purpose | Tests | Notes |
|--------|------|---------|-------|-------|
| ImageWorker | core/process/workers/image_worker.py | Decode/prescale images in process | 	ests/test_image_worker.py | |
| RSSWorker | core/process/workers/rss_worker.py | Fetch/parse RSS feeds | 	ests/test_rss_worker.py | |
| ~~FFTWorker~~ | ~~removed~~ | Deprecated: inline FFT replaced process worker | - | |
| TransitionWorker | core/process/workers/transition_worker.py | Precompute transition data | 	ests/test_transition_worker.py | |
| BaseWorker | core/process/workers/base.py | Worker lifecycle loop + logging setup; Mar 2026: `_teardown_logging()` flushes/closes handlers on shutdown so `worker_*.log` files release immediately (fixes worker_image.log deletion failures). | - | |

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
| Display Image Ops | rendering/display_image_ops.py | set_processed_image, on_transition_finished, push_spotify_visualizer_frame, prewarm_spotify_visualizer_overlay | Image display pipeline, transition finish, and hidden visualizer-overlay prewarm before staged reveal |
| Display GL Init | rendering/display_gl_init.py | init_renderer_backend, ensure_gl_compositor, ensure_render_surface | GL compositor/surface setup, cleanup |
| Display Context Menu | rendering/display_context_menu.py | show_context_menu, on_context_transition_selected | Context menu creation and handlers |
| Display Native Events | rendering/display_native_events.py | handle_nativeEvent, handle_eventFilter | Win32 native events, global event filter, media key passthrough (focus re-claim removed Feb 2026 to keep Settings responsive) |
| Display Input | rendering/display_input.py | handle_mousePressEvent, show_ctrl_cursor_hint, ensure_ctrl_cursor_hint | Cursor halo (shape from `input.halo_shape`), mouse press/move, multi-source Ctrl gate, Halo show path now recreates/shows on move even when no hint exists yet, normal click routing stays on the underlying display/widget tree; `_halo_forwarding` guard remains as a defensive no-jitter fallback. Generic post-click halo keepalive/focus reclaim is no longer forced on every compositor interaction. |
| Display Overlays | rendering/display_overlays.py | start_overlay_fades, perform_activation_refresh | Overlay fades, window diagnostics |
| Overlay Startup Policy | rendering/overlay_startup_policy.py | OverlayStartupFadePolicy, get_overlay_startup_fade_policy() | Canonical startup timing for the primary overlay wave plus Spotify secondary-stage scheduling |
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
| WidgetManager | rendering/widget_manager.py | WidgetManager | Widget lifecycle, Z-order, fade coordination via FadeCoordinator, Spotify secondary-stage registration/wakeup routing, and shared runtime media-provider rebinding/persisted auto-fallback. Owns runtime-safe visualizer preset cycling via `cycle_visualizer_preset(mode, direction)` (settings-backed, non-UI). |
| FadeCoordinator | rendering/fade_coordinator.py | FadeCoordinator | Centralized lock-free fade synchronization |
| WidgetPositioner | rendering/widget_positioner.py | WidgetPositioner, PositionAnchor | Position calculation |
| WidgetFactories | rendering/widget_factories.py | ClockWidgetFactory, MediaWidgetFactory, etc. | Widget creation |
| SpotifyWidgetCreators | rendering/spotify_widget_creators.py | apply_spotify_vis_model_config() | Reusable vis config apply for init + live refresh; forwards curated bar fill/border colours plus opacity into `SpotifyVisualizerWidget.apply_vis_mode_config()` so preset hotswaps can’t inherit stale card colours |
| WidgetSetup | rendering/widget_setup.py | parse_color_to_qcolor(), compute_expected_overlays() | Setup helpers, including the primary expected-overlay contract that intentionally excludes `spotify_visualizer` from the first coordinated fade wave |

## Rendering - Input & Control

| Module | File | Key Classes | Purpose |
|--------|------|-------------|---------|
| InputHandler | rendering/input_handler.py | InputHandler | Mouse/keyboard/media keys. `route_widget_click(...)` now hit-tests the Spotify visualizer and forwards middle/XButton preset-cycle clicks to `SpotifyVisualizerWidget.handle_mouse_button()`. |
| TransitionController | rendering/transition_controller.py | TransitionController | Transition lifecycle |
| ImagePresenter | rendering/image_presenter.py | ImagePresenter | Pixmap management |
| MultiMonitorCoordinator | rendering/multi_monitor_coordinator.py | MultiMonitorCoordinator | Cross-display coordination |

## Rendering - GL Infrastructure

| Module | File | Key Classes | Purpose |
|--------|------|-------------|---------|
| GL State | rendering/gl_state_manager.py | GLStateManager, GLStateGuard | GL context state |
| GL Error | rendering/gl_error_handler.py | GLErrorHandler | Centralized error handling |
| GL Profiler | rendering/gl_profiler.py | TransitionProfiler | Frame timing metrics |
| Render Strategy | rendering/render_strategy.py | TimerRenderStrategy | Timer-based rendering |
| Adaptive Timer | rendering/adaptive_timer.py | AdaptiveTimerStrategy | Adaptive frame pacing |

> **Render timing defaults:** `GLCompositorWidget` now caches the first successfully detected refresh rate per display and reuses it for subsequent restarts/settings-dialog hops. If hardware/Qt fails to report a Hz value, the compositor, display setup, display widget, and adaptive timer all fall back to an uncapped 240 Hz target instead of 60 Hz so high-refresh panels never get stuck at 60 fps.

## Rendering - GL Programs

| Module | File | Key Class | Transition |
|--------|------|-----------|------------|
| Program Cache | rendering/gl_programs/program_cache.py | GLProgramCache | All |
| Geometry | rendering/gl_programs/geometry_manager.py | GLGeometryManager | All |
| Texture | rendering/gl_programs/texture_manager.py | GLTextureManager | All |
| Crossfade | rendering/gl_programs/crossfade_program.py | CrossfadeProgram | Crossfade |
| Slide | rendering/gl_programs/slide_program.py | SlideProgram | Slide |
| Wipe | rendering/gl_programs/wipe_program.py | WipeProgram | Wipe |
| Blinds | rendering/gl_programs/blinds_program.py | BlindsProgram | Blinds |
| Diffuse | rendering/gl_programs/diffuse_program.py | DiffuseProgram | Diffuse |
| BlockFlip | rendering/gl_programs/blockflip_program.py | BlockFlipProgram | Block Puzzle Flip |
| BlockSpin | (uses blockflip card-flip shader) | — | 3D Block Spins |
| Ripple | rendering/gl_programs/raindrops_program.py | RainDropsProgram | Ripple |
| Warp | rendering/gl_programs/warp_program.py | WarpProgram | Warp Dissolve |
| Crumble | rendering/gl_programs/crumble_program.py | CrumbleProgram | Crumble |
| Particle | rendering/gl_programs/particle_program.py | ParticleProgram | Particle |
| Burn | rendering/gl_programs/burn_program.py | BurnProgram | Burn |

## Transitions

| Transition | GL File | Notes |
|------------|---------|-------|
| Crossfade | transitions/gl_compositor_crossfade_transition.py | Basic fade |
| Slide | transitions/gl_compositor_slide_transition.py | 4 directions |
| Wipe | transitions/gl_compositor_wipe_transition.py | 8 directions |
| Diffuse | transitions/gl_compositor_diffuse_transition.py | Rectangle/Membrane/Lines/Diamonds/Amorph shapes |
| Block Flip | transitions/gl_compositor_blockflip_transition.py | Puzzle effect |
| Blinds | transitions/gl_compositor_blinds_transition.py | GL only |
| Block Spin | transitions/gl_compositor_blockspin_transition.py | GL only, 3D, 6 directions incl. diagonals |
| Ripple | transitions/gl_compositor_raindrops_transition.py | GL only, configurable ripple count 1-8 |
| Warp Dissolve | transitions/gl_compositor_warp_transition.py | GL only |
| Crumble | transitions/gl_compositor_crumble_transition.py | GL only |
| Particle | transitions/gl_compositor_particle_transition.py | GL only |
| Burn | transitions/gl_compositor_burn_transition.py | GL only, 4 directions, jaggedness/glow/char params |
| Base | transitions/base_transition.py | Abstract base, SlideDirection, WipeDirection, compute_wipe_region |
| Overlay Manager | transitions/overlay_manager.py | GL overlay helpers |

## Widgets

### Base & Infrastructure

| Module | File | Key Classes | Purpose |
|--------|------|-------------|---------|
| Base Overlay | widgets/base_overlay_widget.py | BaseOverlayWidget, OverlayPosition | Abstract base for all widgets |
| Shadow Utils | widgets/shadow_utils.py | ShadowRenderer, ShadowFadeProfile | Drop shadow rendering |
| Overlay Timers | widgets/overlay_timers.py | create_overlay_timer() | ThreadManager timer helper |
| Context Menu | widgets/context_menu.py | ScreensaverContextMenu | Right-click menu |
| Cursor Halo | widgets/cursor_halo.py | CursorHaloWidget | Ctrl-held indicator; 8 shapes (circle/ring/crosshair/diamond/dot/cursor_triangle/cursor_light/cursor_dark); cursor_triangle primary point faces top-left (135°); top-level translucent window that manually forwards events back through the DisplayWidget root. Do not treat the old `WA_TransparentForMouseEvents` branch as current or desirable behavior. |
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
### Visualizer Components

| Module | File | Key Classes/Functions | Purpose |
|--------|------|-------------|---------|
| Beat Engine | widgets/beat_engine.py | BeatEngine, BeatEngineConfig, BeatEngineState | FFT processing |
| Audio Worker | widgets/spotify_visualizer/audio_worker.py | SpotifyVisualizerAudioWorker, VisualizerMode(SPECTRUM/OSCILLOSCOPE/STARFIELD/BLOB/HELIX/SINE_WAVE/BUBBLE), _AudioFrame | Audio capture coordination (delegates FFT to bar_computation). Helix/Starfield enums remain for backwards compatibility but are **deprecated** and not surfaced in production. |
| Shared| Beat Engine | widgets/spotify_visualizer/beat_engine.py | _SpotifyBeatEngine, get_shared_spotify_beat_engine | Shared engine with COMPUTE-pool smoothing, waveform + energy band extraction; `_compute_gate_token` invalidates stale FFT tasks; `generation_id` + `latest_generation_with_frame`/`latest_generation_with_waveform` let widgets await fresh bars and fresh waveform publication before resuming. Bar-count changes now rebuild through the same canonical startup/runtime path instead of warming separate hidden engines by count. |
| Bar Computation | widgets/spotify_visualizer/bar_computation.py | fft_to_bars, compute_bars_from_samples, maybe_log_floor_state, get_zero_bars, _apply_adaptive_normalization, _apply_reactive_smoothing | DSP/FFT bar computation pipeline; Spectrum now combines `spectrum_shape_nodes` with label-driven mirrored/linear lane-strength maps so authored lane arrows directly shape per-lane energy routing rather than feeding old scalar lane hacks. **Dual-window envelope normalizer** (short-term ~300ms limiter + long-term ~3s sustain) replaces single running peak — preserves dynamics during sustained loud passages. **Dynamic band splits** driven by draggable notch positions. `_drop_speed` scales decay constants in reactive smoothing. `_agc_strength` (0.0–1.0) scales envelope tracking rates and normalization strength: 0.0 bypasses normalization entirely, 0.5 default, 1.0 max compression. **Global transient_clamp** (0–3, default 1.5): applied immediately after transient bus update to cap all three transient channels before kick lane, bubble dispatch, or AGC reads them. |
| Technical Controls | ui/tabs/media/technical_controls.py | build_per_mode_technical_group, register_per_mode_technical_controls, load_per_mode_technical_controls, collect_per_mode_technical_controls, get_per_mode_controls, _BASE_CONTROL_DEFS, _BUCKET_DEFS, _TRANSIENT_MIX_META | Shared per-mode Technical settings group. A single metadata registry now drives widget construction, coercion, save/load, mode gating, and bucket placement for bar count, adaptive/manual sensitivity, dynamic floor/range, per-mode audio block size, **input_gain** (5%–200%), **agc_strength** (0%–100%), **kick_lane_gain** (0%–200%), **transient_pulse_gain** (0%–300%), **transient_clamp** (0%–300%), and the per-mode transient mix sliders (§2.3). AGC/transient visibility buckets persist per mode, AGC tooltips now carry mode-specific recommendation ranges, the AGC slider now uses a centralized recommended-position groove marker, and this layer is the canonical boundary between shared pre-FFT controls and mode-authored renderer controls such as Sine `Line Response` and Oscilloscope `Line Amplitude`. Direct-storage transient keys stay unprefixed (`spectrum_lane_transient_mix`, `bubble_transient_mix_vocal`, etc.), and retired compat controls are no longer part of the live settings UI/schema. |
| Builder Scaffold | ui/tabs/media/builder_scaffold.py | build_mode_scaffold, add_builder_swatch_row, bind_setting_signal, bind_color_button, ModeScaffold | Shared visualizer-mode UI scaffold for Spectrum/Oscilloscope/Sine/Blob/Bubble. Owns the repeated preset slider wiring, normal/advanced/technical container plumbing, advanced-toggle persistence, standard swatch-row spacing, and common control-binding/save helpers so mode builders stop hand-rolling both layout chrome and signal plumbing independently. This is the current architectural boundary; deeper metadata should be reserved for genuinely repeated feature families, not every mode-specific control. |
| Spectrum Shape Editor | ui/tabs/media/spectrum_shape_editor.py | SpectrumShapeEditor, interpolate_nodes, interpolate_nodes_mirrored | Interactive node-based curve editor for bar-height profile plus lane-native vertical energy arrows; draggable frequency-zone notch labels (boundary anchors locked, interior notches draggable); `notch_positions_changed` and `lane_strengths_changed` persistence signals; slightly taller mirrored/linear editor layout. |
| Energy Bands | widgets/spotify_visualizer/energy_bands.py | EnergyBands, extract_energy_bands | Bass/mid/high/overall frequency band extraction from FFT bars |
| Transient Bus | widgets/spotify_visualizer/transient_bus.py | TransientBus, TransientEnergyBands, OnsetEvent | Fast-path transient energy extractor (Approach A dual-path). Spectral flux onset detection with per-band adaptive thresholds, onset ring buffer, kick/snare/vocal classification. Single-writer (COMPUTE pool), single-reader (UI tick). |
| Card Height | widgets/spotify_visualizer/card_height.py | preferred_height, DEFAULT_GROWTH | Reusable card height expansion for all modes (spectrum/osc/starfield/blob/helix/sine/bubble); Helix/Starfield values are legacy only and flagged **deprecated**. |
| Bubble Simulation | widgets/spotify_visualizer/bubble_simulation.py | BubbleSimulation, BubbleState | CPU-side particle simulation for bubble mode; tick()/snapshot() on COMPUTE thread pool, coalesced results posted to UI thread; snapshot() returns (pos_data, extra_data, trail_data); trail records 3 previous positions per bubble (TRAIL_STEPS=3); drift system now includes **Swish (Horizontal/Vertical)** for axis-locked wobble plus **Swirl (Clockwise/Counter-Clockwise)** for tangential orbits around the card centre. **Hybrid pulse system**: delta-based transient detection (via `_bass_running_avg`/`_midhi_running_avg`) + sustained-floor absolute energy curve. `max(delta, sustained)` prevents both AGC constant-inflation AND sustained-chorus deflation. |
| Config Applier | widgets/spotify_visualizer/config_applier.py | apply_vis_mode_kwargs, build_gpu_push_extra_kwargs, _color_or_none | Per-mode keyword↔attribute mapping; caches the last applied settings snapshot for `_reset_visualizer_state()` and passes rainbow/ghost/bubble uniforms. Spectrum now pushes mirrored/linear lane-strength maps through this layer instead of the retired authored scalar lane controls. Energy source selection reads the widget runtime flag `._use_raw_energy` only as a runtime/debug seam; persisted settings now stay on the canonical smoothed post-AGC path. Shared glow uniforms are built from mode-specific osc/sine settings at GPU push time. |
| Preset Workflow | core/settings/visualizer_presets.py | VisualizerPreset dataclass, `_build_presets_for_mode`, `_filter_settings_for_mode` | Drop-in preset loader. Curated folders use mode-specific JSON under `presets/visualizer_modes/*`; snapshot-style overrides are opt-in and explicit (dedicated folder + markers). Filters keys via global allowlist + mode prefixes, auto-expands preset counts, keeps Custom trailing. Main shipped visualizer modes currently maintain a six-slot curated pack, and duplicate slot ids are test-guarded. |
| Blob Math | widgets/spotify_visualizer/blob_math.py | compute_stage_offset(), compute_blob_radius_preview() | Shared staged sizing helper used by diagnostics/tests/overlay + shader mirroring Stage Gain/Core Scale logic |
| Blob Pockets | widgets/spotify_visualizer/blob_pockets.py | BlobPocket, BlobPocketState, advance_blob_pocket_state, build_blob_pocket_uniform_payload | Runtime-only non-shaped Blob concurrent deformation allocator; lets fresh kick/snare/high hits claim or rotate through local reaction pockets without leaking that ownership into Blob Shaper or persisted preset/settings payloads |
| Mode Transition | widgets/spotify_visualizer/mode_transition.py | cycle_mode, mode_transition_fade_factor, persist_vis_mode, reset_visualizer_state, start_widget_fade_in/out, reset_teardown_bookkeeping, on_mode_cycle_requested, prepare_engine_for_mode_reset, check_mode_teardown_ready, invalidate_shadow_cache_if_needed, get_gpu_fade_factor | Mode-cycling crossfade, fade in/out, teardown bookkeeping, shared-engine reset + generation tracking, overlay clear on crossfade reset, shadow cache invalidation, GPU fade factor (~500 LOC) |
| Startup Contract | widgets/spotify_visualizer/startup_contract.py | VisualizerStartupState | Canonical staged-startup state for the Spotify visualizer so reveal/hot-start timing is not spread across ad-hoc widget booleans |
| Tick Pipeline | widgets/spotify_visualizer/tick_pipeline.py | on_tick, process_heartbeat, dispatch_bubble_simulation, consume_engine_bars, push_gpu_frame, record_tick_perf, log_audio_latency_metrics | Main tick entry point, heartbeat detection, bubble dispatch, engine bar consumption, GPU push (~420 LOC) |
| Tick Helpers | widgets/spotify_visualizer/tick_helpers.py | log_perf_snapshot, rebuild_geometry_cache, apply_visual_smoothing, get_transition_context, resolve_max_fps, update_timer_interval, pause_timer_during_transition, log_tick_spike | Tick utilities, perf metrics, geometry cache (extracted from widget) |
| Shader Loader | widgets/spotify_visualizer/shaders/__init__.py | SHARED_VERTEX_SHADER, load_fragment_shader, load_all_fragment_shaders | GLSL shader source loading for multi-shader architecture |

> **Manual floor contract (Mar 2026):** Global and per-mode `manual_floor` keys clamp to `0.12–1.0` everywhere (UI sliders, `SpotifyVisualizerSettings`, audio worker, shared beat engine). Canonical defaults live in `core/settings/default_settings.py` via `core/settings/defaults.py`, while `core/settings/defaults_snapshot.py` / `defaults_snapshot.json` are derived artifacts from that same source through `core/settings/defaults_snapshot_builder.py`. All of those paths seed 0.12 so curated presets, defaults, and migrations can’t resurrect the retired 2.1 baseline. SettingsManager migrations and the audio worker both reseed the dynamic accumulator whenever a clamped value is applied.

### Visualizer Per-Mode Renderers (`widgets/spotify_visualizer/renderers/`)

Extracted from the monolithic `_render_with_shader` method in `spotify_bars_gl_overlay.py` (Mar 2026). Each renderer encapsulates uniform uploads for one mode via `get_uniform_names()` + `upload_uniforms(gl, u, state)`.

| Renderer | File | Purpose |
|----------|------|---------|
| GL Helpers | renderers/gl_helpers.py | `set1f()`, `set1i()`, `set_color4()` — shared GL uniform upload helpers (extracted from 7× duplication). Live array uniforms still depend on `spotify_bars_gl_overlay.py` querying the driver with `name[0]` lookup tokens. |
| Registry | renderers/__init__.py | `RENDERERS` dict, `upload_mode_uniforms()`, `get_all_uniform_names()` dispatch |
| Spectrum | renderers/spectrum.py | Bar data, peaks, ghost alpha, fill/border colours, height scale |
| Oscilloscope | renderers/oscilloscope.py | Waveform, ghost waveform, shared line/glow, smoothed energy bands |
| Sine Wave | renderers/sine_wave.py | Shared line/glow, heartbeat, density, displacement, crawl, travel |
| Starfield *(deprecated)* | renderers/starfield.py | Star density, travel, nebula tints, energy bands |
| Blob | renderers/blob.py | Ghost alpha, blob colours, body response/release, glow, smoothed/peak energy, per-band peak (bass/mid/high/overall) for SDF ghost shape, single outward stretch control, runtime concurrent pocket upload for non-shaped rapid-hit deformation, and Blob Shaper profile/routing upload with editor-aligned top-origin angular sampling, reaction-canvas-authoritative energy routing, authored-direction-aware arrow semantics (toward/away from the local authored reaction delta rather than only center-relative inward/outward), broadened cosine-smoothed shaper routing fields, stronger stage-preferred shaper-drive bands, creator-path wiring for authored runtime controls, gain-boosted shaper drive for moderate live energy, tighter safe opposite-direction targets for inward routing, gap-aware energy shaping so larger authored travel needs more energy, slight kick-driven overshoot past the reaction contour, and a CPU-solved runtime contour upload (`u_blob_runtime_profile`) so filled/ring/glow rendering stays on one shared contour instead of detached shell-motion offsets | 
| Helix *(deprecated)* | renderers/helix.py | Turns, speed, glow, fill/border, energy bands |
| Bubble | renderers/bubble.py | Bubble arrays (pos/extra/trail), trail strength/opacity, specular/gradient dirs, colours |

### Visualizer Shaders

| Shader | File | Uniforms | Purpose |
|--------|------|----------|---------|
| Spectrum | widgets/spotify_visualizer/shaders/spectrum.frag | u_bars[64], u_peaks[64], u_fill_color, u_border_color, u_ghost_alpha, u_slanted, u_border_radius | Segmented bar analyzer; 3 profiles (Legacy/Curved/Slanted); slanted: diagonal inner edges + linchpin both-side slant; curved: border radius 0-12px |
| Oscilloscope | widgets/spotify_visualizer/shaders/oscilloscope.frag | u_waveform[256], u_prev_waveform[256], u_osc_ghost_alpha, u_line_color, u_glow_*, u_reactive_glow, u_line_count, u_line{2,3}_{color,glow_color}, u_bass/mid/high_energy, u_osc_vertical_shift, u_rainbow_enabled, u_rainbow_hue_offset | Pure audio waveform with Catmull-Rom spline, per-band energy, equalized multi-line glow (3 lines: bass/mid/high), ghost trail (previous waveform overlay), rainbow hue cycling, vertical shift slider (-50 to 200). Feb 2026 parity: uses the same premultiplied glow budget/composite helper as sine_wave so overlapping glows stay sub-1.0 and shader compile failures cannot dump to Spectrum fallback. |
| Sine Wave | widgets/spotify_visualizer/shaders/sine_wave.frag | u_line_color, u_glow_*, u_reactive_glow, u_sensitivity, u_osc_speed, u_osc_sine_travel, u_sine_travel_line2, u_sine_travel_line3, u_card_adaptation, u_playing, u_line_count, u_line{2,3}_{color,glow_color}, u_bass/mid/high_energy, u_wave_effect, u_micro_wobble, u_osc_vertical_shift, u_heartbeat, u_heartbeat_intensity, u_sine_density, u_sine_displacement, u_rainbow_enabled, u_rainbow_hue_offset, u_width_reaction | Sine wave visualizer: audio-reactive amplitude, card adaptation, multi-line (up to 3) with tight phase offsets. **Density**: two-piece linear mapping (0.25–3.0 → 0.65–8.5 cycles) + thickness taper at high densities. **Heartbeat**: CPU spike-ratio detection (600ms decay) + shader +120% amplitude with cubic ease-out swell. **Displacement**: smooth bass-reactive offset with slowly rotating angle (replaces old chaotic randomDirection jitter), per-line variation (1.0x/0.85x/1.15x phase, 1.0x/1.1x/1.25x Y). Wave effect, micro wobble, crawl, rainbow hue cycling (line colours exempt), vertical shift, width reaction. Glow uses per-line premultiplied budget. |
| Starfield | widgets/spotify_visualizer/shaders/starfield.frag | u_star_density, u_travel_speed, u_star_reactivity, u_travel_time, u_nebula_tint{1,2} | Point-star starfield with nebula background, CPU-accumulated monotonic travel (dev-gated) |
| Blob | widgets/spotify_visualizer/shaders/blob.frag | u_blob_color, u_blob_pulse, u_blob_outline_color, u_blob_smoothed_energy, u_blob_peak_energy, u_blob_peak_bass/mid/high/overall, u_ghost_alpha, u_blob_glow_reactivity, u_blob_glow_max_size, u_blob_reactive_deformation (0-3.0), u_blob_constant_wobble, u_blob_reactive_wobble, u_blob_stretch_tendency, u_blob_stretch_inner, u_blob_stretch_outer, u_blob_runtime_profile, u_blob_pockets, u_blob_pocket_mix | 2D SDF organic metaball with CPU-smoothed glow, a runtime-only non-shaped concurrent deformation-pocket layer for rapid local hits, and a CPU-solved Blob Shaper contour path. Authored Blob controls now collapse to a leaner canonical surface: `blob_pulse` is the master body-response gate, `blob_pulse_release_ms` is the authored release control, and the single authored `blob_stretch` control derives the shader's internal stretch uniforms (`tendency = outer`, `inner = 0`). In the current Blob Shaper contract, scalar body-pulse radius terms and staged body-size growth both respect `u_blob_pulse`, while directional shaper deformation is resolved upstream into one spring-smoothed runtime contour profile that the shader renders directly for filled and ring modes. Non-shaped rapid-hit pocket ownership is runtime-only in the current contract and must not bleed into persisted settings or Blob Shaper routing. Ring shading now keeps a separate outer-glow/ghost distance so the hollow center does not get repainted like generic exterior space. This keeps the dark band, edge, outline, and glow attached to the same contour again instead of relying on separate shell-motion offsets. Positive shaper travel may still overshoot slightly past the authored reaction contour on stronger kicks, but current visual validation for inward safety, organic motion feel, and ring seam behavior remains open in [Current_Plan.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Current_Plan.md). **Ghosting (current code path, not yet user-validated)**: retained-peak energy envelope path is still active, but live blob deformation uniforms and ghost peak memory now both derive from the same processed Blob live-band source (transient + scheduler aware) instead of diverging immediately. The delayed-history/state-blend branch and ghost-only peak snapshot branch remain retired. Blob ghost behavior is still an active validation item. **Glow**: reactivity (0-200%) and max size (10-300%) sliders under Advanced bucket. Taste The Rainbow shifts fill/glow/outline colours, edge highlight exempt. |
| Helix | widgets/spotify_visualizer/shaders/helix.frag | u_helix_turns, u_helix_double, u_helix_speed, u_helix_glow_*, u_helix_glow_color | Parametric double-helix with depth shading and user-controllable glow color |
| Bubble | widgets/spotify_visualizer/shaders/bubble.frag | u_bubble_count, u_bubbles_pos[110], u_bubbles_extra[110], u_bubbles_trail[330], u_trail_strength, u_tail_opacity, u_specular_dir, u_outline_color, u_specular_color, u_gradient_light, u_gradient_dark, u_pop_color | SDF-based bubble visualizer: thin outlines, crescent specular highlights, warm gradient background, pop flash, rainbow hue cycling. **Water ripple wake**: concentric expanding rings at trail sample positions (3 per bubble at different ages), sin(dist*freq) ring pattern with Gaussian decay, centre fade to avoid bright dot on bubble, soft outer edges. Trail Strength + Tail Opacity sliders. CPU simulation on COMPUTE pool. |

> **Default tweak (v2.75):** Spectrum mode now ships with Single Piece Mode enabled in `core/settings/defaults.py`, matching the preferred “pillar” presentation without manual toggles.

## Weather System

| Module | File | Key Classes | Purpose |
|--------|------|-------------|---------|
| WeatherWidget | widgets/weather_widget.py | WeatherWidget | Weather display with icons, detail metrics, forecast (1320 LOC) |
| WeatherComponents | widgets/weather_components.py | WeatherConditionIcon, WeatherDetailIcon, WeatherDetailRow, WeatherPosition, WeatherFetcher | Extracted helper classes for weather widget |
| OpenMeteoProvider | weather/open_meteo_provider.py | OpenMeteoProvider | Open-Meteo API integration, geocoding, caching |


## Image Processing

| Module | File | Key Classes | Purpose |
|--------|------|-------------|---------|
| Image Processor | rendering/image_processor.py | ImageProcessor | Synchronous wrapper |
| Async Processor | rendering/image_processor_async.py | AsyncImageProcessor | ThreadManager-based |
| Display Modes | rendering/display_modes.py | DisplayMode | FILL/FIT/SHRINK enums |

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
| input.hard_exit | bool | false (`Screensaver`), true (`Screensaver_MC`) | Profile-aware exit mode; MC resets and startup overrides force hard-exit on |
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

### Label Alignment Helpers

- `ui/tabs/shared_styles.py::add_section_label()` — standard combo/spin/text row labels. Applies `SECTION_HEADING_STYLE` (Jost bold 14px) with a fixed 34 px height and `margin-top: -12px` so all control baselines match.
- `ui/tabs/shared_styles.py::add_swatch_label()` — dedicated helper for color swatch rows. Uses `SWATCH_LABEL_STYLE` (shorter 28 px height, positive top margin) so ColorSwatchButton rows stay visually centered even though the controls sit taller due to drop shadows.
- All settings tabs must run swatch rows through `add_swatch_label()` (or its wrappers such as `_swatch_row`) instead of local label math. Existing adopters: Media visualizer builders, Widgets tab (Media/Weather/Clock/Reddit), and Transitions → Burn.

## UI - Settings Dialog Tabs

| Module | File | Key Classes/Functions | Purpose |
|--------|------|-----------------------|---------|
| SettingsDialog | ui/settings_dialog.py | SettingsDialog | Main settings dialog container (1595 LOC, refactored from ~1957). Transitions tab (Feb 2026) now runs **every checkbox/slider row through `_aligned_row()`** so the shared gutter is honored and the `QLayout::addChildLayout` spam is gone; follow this helper whenever adding controls to transitions or media tabs. The outer shell uses the current paint-based rounded-edge treatment so acrylic/title-bar behavior remains stable. |
| SettingsAboutTab | ui/settings_about_tab.py | build_about_tab(), update_about_header_images() | About tab UI, header image scaling, and shipped visualizer replacement action (`Replace Visualizers`) with script-safe no-op behavior |
| Preset Artifact Tool | tools/regenerate_visualizer_shipped_presets.py | main() | Repo helper that regenerates both shipped visualizer preset trees/manifests from the authoritative source preset tree before parity-sensitive tests or packaging |
| WidgetsTab | ui/tabs/widgets_tab.py | WidgetsTab, _RainbowGlowLabel, NoWheelSlider | Widget config orchestrator; `_RainbowGlowLabel` uses QPainter for per-letter rainbow glow (Qt has no text-shadow CSS support). Settings-tab rainbow UI still caches per-mode checkbox/slider state for instant swaps, while live runtime mode changes now resync rainbow from persisted mode+preset config in the visualizer widget itself. |
| WidgetsTab Clock | ui/tabs/widgets_tab_clock.py | build_clock_ui(), load_clock_settings(), save_clock_settings(), _update_clock_mode_visibility() | Clock 1/2/3 UI, load, save; analog/digital mode visibility gating |
| WidgetsTab Weather | ui/tabs/widgets_tab_weather.py | build_weather_ui(), load_weather_settings(), save_weather_settings(), _update_weather_icon_visibility(), _update_weather_bg_visibility() | Weather UI, load, save; icon + background visibility gating; uses GeocodeCompleter for live city autocomplete |
| Geocode Completer | ui/widgets/geocode_completer.py | GeocodeCompleter | Live city autocomplete via Open-Meteo geocoding API with 400ms debounce; falls back to static city list offline |
| WidgetsTab Media | ui/tabs/widgets_tab_media.py | build_media_ui(), load_media_settings(), save_media_settings() | Spotify + Beat Visualizer UI coordinator; per-viz builders extracted to ui/tabs/media/. Handles osc/sine glow persistence (`*_glow_intensity`, `*_glow_reactivity`) with legacy fallback from `*_glow_size`. |
| Media Builders | ui/tabs/media/*.py | build_spectrum_ui(), build_oscilloscope_ui(), build_starfield_ui(), build_blob_ui(), build_helix_ui(), build_sine_wave_ui(), build_bubble_ui() | Per-visualizer UI builders (extracted from widgets_tab_media.py, ~1400 LOC). Mirrored spectrum editor now preserves center→edge node semantics in UI mapping; osc/sine builders expose glow reactivity sliders. |
| Color Utils | ui/color_utils.py | qcolor_to_list(), list_to_qcolor() | Centralized QColor ↔ list conversion (replaces inline helpers in widgets_tab_media + widget_setup) |
| WidgetsTab Reddit | ui/tabs/widgets_tab_reddit.py | build_reddit_ui(), load_reddit_settings(), save_reddit_settings(), _update_reddit_enabled_visibility() | Reddit 1/2 UI, load, save; all controls gated by enabled checkbox |
| WidgetsTab Imgur | ui/tabs/widgets_tab_imgur.py | build_imgur_ui(), load_imgur_settings(), save_imgur_settings() | Imgur UI, load, save (dev-gated) |
| Settings Binding | ui/tabs/settings_binding.py | SliderBinding, CheckBinding, ComboDataBinding, ComboIndexBinding, ColorBinding, RawBinding, apply_bindings_load, collect_bindings_save | Declarative widget↔config key binding utility for reducing save/load boilerplate |
| Shared Styles | ui/tabs/shared_styles.py | NoWheelSlider, RecommendedMarkSlider, SPINBOX_STYLE, COMBOBOX_STYLE, SLIDER_STYLE, CIRCLE_CHECKBOX_STYLE, TOOLTIP_STYLE, SCROLL_AREA_STYLE, SUBSECTION_DIVIDER_STYLE, SUBSECTION_DIVIDER_TITLE_STYLE, style_group_box() | Centralised QSS constants, shared widgets (`NoWheelSlider`, `RecommendedMarkSlider`), and `style_group_box()` helper for seam-free QGroupBox borders across all tabs. `RecommendedMarkSlider` provides subtle groove markers for shared guidance surfaces such as the visualizer `AGC Strength` recommendation. |
| SourcesTab | ui/tabs/sources_tab.py | SourcesTab | Image source config |
| TransitionsTab | ui/tabs/transitions_tab.py | TransitionsTab | Transition config; Burn Settings group (direction 4-way, jaggedness, glow intensity, char width, glow colour picker, smoke/ash toggles + density sliders) shown conditionally when Burn is selected |
| DisplayTab | ui/tabs/display_tab.py | DisplayTab | Display settings |
| AccessibilityTab | ui/tabs/accessibility_tab.py | AccessibilityTab | Accessibility options |
| PresetsTab | ui/tabs/presets_tab.py | PresetsTab | Setting presets |

## Utilities Boundary

| Package | Purpose | Key Modules |
|---------|---------|-------------|
| `utils/` | Runtime utilities (image, audio, monitors, lock-free) | `image_cache.py`, `image_loader.py`, `image_prefetcher.py`, `audio_capture.py`, `monitors.py`, `text_utils.py`, `profiler.py`, `lockfree/spsc_queue.py`, `lockfree/triple_buffer.py` |
| `core/utils/` | Framework utilities (decorators) | `decorators.py` (retry, throttle, etc.) |

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
| tests/test_overlay_startup_policy.py | Startup fade policy derivation and delay floors |
| tests/test_display_image_ops.py | Display image ops visualizer prewarm pipeline and shader-preload ordering |
| tests/test_visualizer_startup_contract.py | Visualizer staged-startup contract derivation |
| tests/test_visualizer_preset_manifest.py | Shipped curated-preset manifest parity, stale-file sync policy, and source->release regeneration contract |
| tests/test_sine_wave_gl_fix.py | Sine wave GL overlay fix regression (mode validation, cycle, shader, card height) |
| tests/test_micro_wobble_math.py | Micro wobble shader math: energy weighting, spatial freq, displacement bounds, smoothness (20 tests) |
| tests/test_visualizer_settings_plumbing.py | Visualizer settings plumbing: behavior-first model/creator/applier/frame-push coverage plus a small static shader/contract layer |
| tests/test_visualizer_architecture_split.py | Focused architecture split guard: required extracted exports, widget delegation, monolith threshold |
| tests/test_osc_sine_glow_contract.py | Focused Osc/Sine glow contract checks |
| tests/conftest.py | Shared fixtures + `--chunk`/`--total-chunks` CLI options for chunked test execution |
| tests/unit/test_policy_compliance.py | Threading/import policy enforcement |
| tests/test_transient_bus.py | Transient bus: kick detection, onset classification, adaptive threshold, ring buffer, reset, decay, config sensitivity, AGC envelope fields, beat engine integration (17 tests) |
| tests/test_transient_preset_preservation.py | Transient bus preset preservation: default settings, model resolvers, repair injection/preservation, mandatory suffixes (10 tests) |
| tests/test_transient_per_mode_integration.py | Per-mode transient integration: Spectrum kick lane + lane mix, Bubble pulse + bass/vocal mix, Blob deform uniforms + bass/vocal mix, Sine/Osc width mix, Heartbeat boost, GPU push pipeline, Settings model round-trip (37 tests) |
