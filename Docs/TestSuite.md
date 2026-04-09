# Test Suite Index

Living reference for testing architecture, policies, and the current regression bar.

**Purpose**: Detailed reference for all tests, what they check, when to use them, and which suites are the minimum guardrails for active bug work.

**Current Collection Snapshot**: `1724 tests` across `115 test files` (`pytest --collect-only tests -q`, Mar 23 2026)
Do not treat this as a forever-static number. Refresh it when the suite shape changes substantially.

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

## Goals

- Fast, reliable test feedback during development.
- Clear separation between unit, integration, regression, and policy-enforcement tests.
- Documented exceptions for flaky/manual-validation cases.
- A clear “minimum regression bar” for currently active bugs so we do not confuse contract coverage with visual sign-off.

## Test Architecture

### Directory Layout

```text
tests/
├── unit/                    # Fast, isolated tests (no Qt dependencies)
│   ├── core/               # Core module unit tests
│   └── test_policy_compliance.py
├── conftest.py             # Shared fixtures (qt_app, settings_manager)
├── pytest.ini              # Pytest configuration
└── test_*.py               # Integration/regression tests (may use Qt)
```

### Test Policy Notes

- **Unit tests**: fast, isolated, no Qt event-loop dependency where possible.
- **Integration/regression tests**: may use Qt, real component interactions, and targeted synthetic scenarios.
- **Policy tests**: static architectural checks in `tests/unit/test_policy_compliance.py`.
- **Visual/runtime bugfixes**: keep a behavior-level regression where possible, but do not confuse source-level or contract-level assertions with real visual validation.
- **Blob Shaper guardrail note**:
  - `tests/test_blob_shaper_plumbing.py` is now also the fence for two easy-to-miss cross-system regressions: live GL array-uniform lookup must use `name[0]` semantics for shaper profile uploads, and the shape editor's right-click contract must still remove authored profile nodes.
  - it also now guards the ring-specific hollow-center contract: ring glow/ghost handling must not reuse the filled signed distance in a way that paints the inner void back in like a filled blob.
  - it also now guards the shaper-specific release feel contract at a non-visual level: after a strong authored pull, the solved contour should return toward base gradually rather than snapping back immediately once energy drops.
- **Visualizer preset tests**:
  - `tests/test_visualizer_presets.py` should stay schema/repair/filter focused.
  - it is also the direct fence for the real authored overwrite flow: Custom -> save over curated filename -> reload preset registry must keep modern keys only across all primary modes.
  - it now explicitly audits forward-only authored schema too: no global ghost mirrors in curated/custom preset payloads, no retired Oscilloscope alias `osc_sensitivity`, and no re-entry of retired compat keys through repair/save flows.
  - it also now guards checked-in artifact parity: the shared `tests_tmp_appdata` visualizer fixture must stay on the modern schema, and `release/main_mc.dist/presets/visualizer_modes` must match the source curated preset tree when that release copy is present in the repo.
  - it now also guards the shared installed preset-root contract for frozen builds: SCR and MC should converge on one ProgramData curated tree, with frozen packaged assets used only as the replacement/bootstrap source rather than as the active runtime tree.
  - `tests/test_visualizer_preset_manifest.py` now also guards the generated-artifact workflow directly: source manifests, release manifests, and the MC release preset tree must be reproducibly regenerated from the authoritative source tree, with stale managed files pruned during mirror.
  - `tests/test_settings_defaults_parity.py` is also part of that fence now: repair-tool mandatory key lists must only reference keys that still exist in canonical defaults, so preset repair/default drift cannot creep in silently.
  - `tests/test_visualizer_presets.py` now also guards the repair-tool mutation workflow: curated-source repairs/reindexes must trigger shipped-artifact regeneration, and reindex must preserve authored suffix text instead of reviving old static names.
  - `tests/test_visualizer_settings_plumbing.py` now also carries the Spectrum lane-contract fence: drifted legacy `Bass / Low / Mid / Hi-Mid / Treble` linear families must be promoted to `Bass / Low-Mid / Vocal / Hi-Mid / Treble` without flattening the user's boundary positions, and the new mirrored/linear lane-strength arrow maps must persist cleanly through model -> creator/applier -> runtime bridge without reviving retired scalar lane keys.
  - it must not freeze non-baseline curated artistic choices such as filenames, pack size, slot labels, or payload tuning outside the explicit `Preset 1` baseline fence.
  - `tests/test_visualizer_preset1_baselines.py` is the intentional rigid synthetic feel fence.
  - if curated preset 1 is intentionally reauthored, refresh the checked-in baseline in the same change.
  - baseline/recovery work is only considered safe when the curated audit, shipped-tree regeneration, runtime creator-bridge fence, and the `Preset 1` synthetic fence are all green together. Do not use one passing suite to assume the others are implicitly safe.

### Stability Rules

- The suite now forces a workspace-local `APPDATA` in `tests/conftest.py` and resets `core.settings.storage_paths` resolution at session start. Tests should not require a manually exported roaming path override to collect.
- Always use `qt_app.processEvents()` after async GUI work in tests.
- Use timeouts instead of open-ended waits.
- Clean up widgets/timers/transitions explicitly in teardown.
- Document every skip with a reason and a manual validation path when applicable.

---

## Core Infrastructure

### Threading & Concurrency

| Test File | What It Tests | When To Use |
|-----------|---------------|-------------|
| `test_thread_manager.py` | ThreadManager IO/COMPUTE pools, task lifecycle, shutdown | Changing ThreadManager, debugging thread leaks |
| `test_threading.py` | Threading utilities, run_on_ui_thread, locks | Low-level threading changes |
| `test_qt_timer_threading.py` | QTimer behavior in threads | Timer-related threading issues |
| `test_decorators.py` | @rate_limited, @memoize, @timing decorators | Changes to decorator implementations |
| `test_storage_paths.py` | `get_app_data_dir()`, `get_cache_dir()`, canonical path resolution | Storage path changes |

### Process Management

| Test File | What It Tests | When To Use |
|-----------|---------------|-------------|
| `test_process_supervisor.py` | Worker lifecycle, message contracts, health monitoring | Changes to ProcessSupervisor, worker types |
| `test_image_worker.py` | Image worker message processing, shared memory | Image loading pipeline changes |
| `test_fft_worker.py` | FFT worker for visualizer audio processing | Audio/FFT pipeline changes |
| `test_fft_worker_gating.py` | FFT worker gating when Spotify not playing | Visualizer playback gating |
| `test_worker_latency_tuning.py` | Worker latency thresholds and tuning | Performance tuning, latency issues |

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
| `test_rendering_backends.py` | Render backend selection and fallback | Backend changes |

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
| `test_transitions_tab.py` | Transitions tab UI controls, duration persistence | Transition settings UI |

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
Startup-coordination coverage here now asserts against the live overlay startup policy object, so manager-owned Spotify secondary-stage delays cannot silently drift away from the display startup contract.
| `test_widget_manager_refresh.py` | Widget refresh on settings change, position updates | Settings refresh issues |
| `test_overlay_ready_state.py` | Overlay ready/waiting states | Overlay initialization issues |
| `test_overlay_startup_policy.py` | Shared overlay-startup timing policy derivation | Startup fade policy changes |

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
Normal fade-path coverage here now explicitly guards that analog Clock still uses the shared fade helper instead of bypassing startup fade coordination.
| `test_shadow_utils.py` | Shared fade helper visibility/opacity contract | Central fade regressions |
This is now the direct fence for the shared `ShadowFadeProfile.start_fade_in()` contract: widgets must become visible immediately at `opacity=0.0`, rather than waiting for the first animation tick and accidentally collapsing the coordinated fade into a delayed pop under startup load.
It also now guards the shared fade-profile defaults themselves so startup fade tuning does not quietly drift back to an almost-imperceptible feel, and it records the new softer centralized easing profile instead of letting per-widget wrappers invent their own fade shape.
It also guards the honesty of the shared fade API: explicit `duration_ms` overrides must be respected, so true special cases can be intentional instead of silently inheriting the default while pretending otherwise.
| `test_weather_widget.py` | WeatherWidget, Open-Meteo integration | Weather widget, fetch issues |
| `test_media_widget.py` | MediaWidget, GSMTC integration, artwork | Media display changes |
| `test_media_runtime_state.py` | Retained-display snapshot downgrade, missing-session/provider-failover cooldown helpers | Media retained-display contract changes |
| `test_media_display_update.py` | Retained-display policy, alternate-provider snapshot handoff, and media-card re-entry after a real hide | Media lifecycle / retained-metadata behavior changes |
| `test_media_provider_runtime.py` | Shared runtime provider rebinding and persisted auto-fallback path in WidgetManager | Media provider failover / rebinding changes |
| `test_media_widget_runtime_methods.py` | Canonical MediaWidget poll-stage helper behavior and track-identity composition | Media polling cadence / dead-duplicate cleanup |
| `test_media_artwork_layout.py` | Artwork-box layout contract plus decode normalization: square art stays square, wide Spotify video-frame thumbnails cover-crop the square box without stretch/letterbox | Media artwork distortion fixes |
| `test_media_dependent_visibility.py` | Shared anchor-visibility contract for media-dependent widgets (volume/mute satellites) | Media retained-display dependent-widget lifecycle changes |
| `test_reddit_widget.py` | RedditWidget, fetch, display, clicks | Reddit widget issues |
| `test_spotify_visualizer_widget.py` | SpotifyVisualizerWidget, BeatEngine, bar rendering | Visualizer widget changes |
Startup staging coverage here now explicitly guards Spotify secondary-stage deferral, widget self-registration into that stage, first-fresh-frame reveal completion, exact ready-driven reveal after the minimum hidden warmup delay, anchor-visibility release, anchor-sync obedience to the centralized parent secondary-stage deadline, overlay prewarm before reveal, deferred pre-stage wake routing, and the rule that staged hot start must not immediately re-run the normal `engine.wake()` restart path.
Visualizer startup fade timing here is now expected to derive from the shared fade helper contract rather than from local hardcoded durations, and the widget’s old underscored startup flags are now expected to delegate to the shared visualizer startup contract instead of behaving like independent loose state.
It also now guards the retained-media lifecycle boundary on the visualizer side: a paused-but-still-visible anchor should leave the visualizer visible while forcing non-playing reactivity gating, rather than collapsing back into a hide path.
| `test_visualizer_startup_contract.py` | Shared visualizer staged-startup contract derivation | Visualizer startup contract changes |
| `test_display_image_ops.py` | Display image ops visualizer prewarm pipeline | Startup prewarm regressions |
This suite now directly guards that visualizer shader-source preload happens before hidden overlay prewarm, so shader file IO stays out of the first visible startup window.
| `test_reddit_helper_watcher.py` | Queue watcher retry/expiry plus owner-idle exit, explicit session-shutdown requests, duplicate-watcher singleton guard, launch-not-before gating, and shell-not-ready deferral without retry-budget burn | Reddit helper watcher lifecycle / linger regressions |
| `test_spotify_visualizer_integration.py` | Visualizer integration with DisplayWidget | Visualizer integration |
| `test_imgur_cache.py` | Imgur LRU disk cache, GIF conversion | Imgur cache changes |
| `test_imgur_scraper.py` | Imgur web scraping, rate limiting | Imgur scraper changes |
| `test_imgur_widget.py` | Imgur gallery widget lifecycle, grid rendering | Imgur widget changes |

### Widget Behavior

| Test File | What It Tests | When To Use |
|-----------|---------------|-------------|
| `test_widget_raise_order.py` | Z-order raising, overlay stacking | Widget visibility issues |
| `test_widget_overlay_regressions.py` | Regression tests for overlay bugs | Overlay bug fixes |
| `test_widget_performance.py` | Widget rendering performance | Widget perf issues |
| `test_pixel_shift.py` | Burn-in prevention pixel shifting | Pixel shift changes |
| `test_no_legacy_widget_position_strings.py` | Settings don't use WidgetPosition. strings | Settings migration validation |
| `test_settings_binding.py` | SliderBinding, CheckBinding, ComboDataBinding declarative bindings | Settings binding utility changes |
| `test_save_debounce.py` | Settings save debounce timer behavior | Save timing changes |

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
| `test_settings_defaults_parity.py` | Canonical defaults, compatibility aliases, and derived snapshot artifacts stay in parity | Default/source-of-truth consistency |
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
| `test_reddit_helper_runtime.py` | User-session helper heartbeat/bootstrap self-heal plus persistent-vs-session-scoped command shaping, secure-desktop queue-entry handoff stamping, and Windows-safe stale-helper PID probing | Reddit helper lifecycle changes |
| `test_reddit_helper_watcher.py` | Queue watcher heartbeat, retry, stale-entry expiry, owner-idle self-exit, explicit session-shutdown requests for session-scoped launches, launch-not-before gating, and shell-not-ready queue deferral | Reddit helper worker changes |
| `test_reddit_helper_task_harness.py` | Scheduled-task authority layer for the real Reddit helper launch contract: COM/XML registration, `schtasks /Query`, `schtasks /Run`, and cleanup of the reusable interactive task definition | Installer/runtime task-authority changes |

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
| `test_widget_setup.py` | Setup helpers, expected-overlay contracts, startup-wave exclusions | Overlay coordination / staged-start contracts |
This suite now also guards that the primary wave starts immediately instead of inserting compositor-only startup dead air, and that Spotify secondary startup remains delayed behind that primary wave instead of collapsing back into it.
It also now guards that the parent display records the centralized Spotify secondary-stage not-before deadline used by runtime startup gating.
| `test_widget_manager.py` | WidgetManager lifecycle, registration, startup ownership | Manager-side startup/fade regressions |
This suite now also guards that WidgetManager mirrors expected overlays back to the parent display and that queued Spotify secondary fades use compositor-ready plus the correct startup-vs-direct delay split, so secondary-stage timing cannot drift onto an orphaned display-local path again.
| `test_visualizer_preservation.py` | Visualizer state preservation | Visualizer reset bugs |
| `test_visualizer_playback_gating.py` | Visualizer playback state gating | Bars when paused |
| `test_visualizer_modes.py` | Visualizer direction/swirl/converge modes | Mode switching |
| `test_visualizer_architecture_split.py` | Focused architecture split guard: required extracted exports, widget delegation, monolith threshold | Architecture split regressions |
| `test_visualizer_overlay_kwargs.py` | `build_gpu_push_extra_kwargs()` ↔ `set_state()` key parity plus shared continuous-energy contract guards (normal persisted paths stay on the canonical smoothed energy source; runtime-only raw-energy seam remains opt-in) | New uniform/kwarg additions |
| `test_visualizer_presets.py` | Curated preset JSON hygiene, SST round-trip, key filtering, canonical mode-payload normalization, and full curated-tree audit via `tools/visualizer_preset_repair.audit_payload()` | Preset file changes |
Line of intent: keep this suite schema/contract-focused. It should guard payload shape, filtering, repair-tool behavior, and direct transient-key preservation, not freeze artistic tuning choices for curated presets.
| `test_widgets_tab.py` | WidgetsTab integration plus cross-mode visualizer save-over-preset payload fences so the real `curated -> Custom -> edit -> save` flow cannot reintroduce retired schema keys | UI save/preset workflow changes |
It now also guards Blob builder bucket structure and gating directly: real bucket order (`Body`, `Appearance`, `Shaper`, `Layout`, `Glow`, then `Advanced`/`Technical`), shaper-mode hiding/disabling of generic deformation controls, and dependent Glow-row hiding when `Reactive Glow` is off.
It also now guards the explicit Spectrum `Move To Custom` path more directly: the first move must flush a valid custom state before any immediate follow-up edit, and sparse Spectrum saves must still persist canonical `spectrum_render_mode` / `spectrum_unique_colors` instead of letting a partial runtime block hit disk.
It also guards curated slot normalization through `tools/visualizer_preset_repair.py --reindex-curated`: gap-filling, canonical filename rewrite, recovery when the earliest remaining preset is no longer slot 1, duplicate-slot detection, and Preset 1 presence per primary mode without freezing the rest of the artistic pack size.
| `test_visualizer_preset_manifest.py` | Shipped curated-preset manifest parity and stale-file sync behavior | Stable onefile extraction / stale curated preset cleanup |
This suite now also guards source-tree reconciliation behavior: new shipped curated files missing from the manifest must still be accepted by source-aware replacement flows, stale manifest-only paths missing from the source tree must be ignored there instead of causing false failures, and replacement now rewrites the target manifest from the reconciled shipped-tree view.
| `test_visualizer_preset1_baselines.py` | Deterministic synthetic preset-1 baseline fence for active shipped modes | Structural migrations, curated preset-1 reauthoring, before/after regression checks |
| `test_spectrum_shaping.py` | Spectrum shape-editor/runtime contract fence: notch families, mirrored vs linear lane identities, lane-strength arrow defaults/promotion, and label-driven Spectrum DSP routing | Spectrum shaper contract or DSP migration changes |
| `test_visualizer_settings_plumbing.py` | Behavior-first settings plumbing (model → creator/applier → frame push → overlay state contract), plus direct adapter coverage for Spectrum / Blob / Bubble / Oscilloscope / Sine mode-owned WidgetsTab bindings and the shared visualizer settings contract/snapshot helpers. Spectrum coverage now includes non-mirrored vocal-lane promotion and mirrored/linear lane-strength arrow persistence. | New visualizer settings, adapter extraction regressions, and sparse-mapping contract drift |
| `test_visualizer_preset_cycling_runtime.py` | Runtime preset cycling API (`WidgetManager`), SpotifyVisualizerWidget middle/XButton shortcuts, InputHandler routing hit-tests, preset wrap-around | Runtime preset shortcut regressions |
| `test_visualizer_alignment.py` | Visualizer positioning relative to other widgets | Positioning changes |
| `test_blob_intensity_reserve.py` | Blob intensity reserve and core floor clamp math | Blob stage tuning |
| `test_micro_wobble_math.py` | Micro wobble amplitude/frequency math | Wobble parameter changes |
| `test_sine_wave_gl_fix.py` | Sine wave GL uniform gating regression | Sine mode uniform issues |
| `test_osc_sine_glow_contract.py` | Focused Osc/Sine glow contract: shader strength/reactivity ownership + mode-specific GPU extra routing | Glow reactivity plumbing |
| `test_bubble_reactivity.py` | Bubble pulse reactivity with simulated audio: rapid beat clusters (burst detection), sustained loud sections, quiet→loud→quiet transitions, single kicks, small→big promotion lifecycle (8 tests) | Bubble sim pulse/reactivity changes |
| `test_input_gain.py` | Input gain (virtual volume): PCM scaling identity check, very-low-gain silence, FFT magnitude linearity, model round-trip (default/to_dict/from_mapping/resolve), audio worker clamping (9 tests) | Input gain pipeline changes |

---

## Running Tests

### Run All Tests (recommended: via pytest runner with logging)
```powershell
cd F:\Programming\Apps\ShittyRandomPhotoScreenSaver
python tests\pytest.py tests/ -q
```
Output goes to `logs/pytest_output.log` (rotating). Check that file if terminal output is blank.

### Run Specific Test File
```powershell
python tests\pytest.py tests\test_visualizer_settings_plumbing.py -v
```

### Run Specific Test
```powershell
python tests\pytest.py tests\test_settings_models.py::TestClockWidgetSettings::test_from_settings_accepts_prefixed_position -v
```

### Run Via python -m pytest (direct, output to terminal)
```powershell
C:\Python311\python.exe -m pytest tests/ -q -c tests/pytest.ini
```

### Run With Performance Metrics
```powershell
$env:SRPSS_PERF_METRICS='1'
python tests\pytest.py tests\test_perf_dt_max.py -v
```

### Scan For Hanging Tests (per-file, 60s timeout each)
```powershell
C:\Python311\python.exe -c "
import subprocess, sys, time, pathlib
cwd = r'F:\Programming\Apps\ShittyRandomPhotoScreenSaver'
ini = 'tests/pytest.ini'
for tf in sorted(pathlib.Path(cwd,'tests').glob('test_*.py')):
    start = time.time()
    try:
        r = subprocess.run([sys.executable,'-m','pytest',str(tf),'-q','-c',ini],
                          capture_output=True,text=True,timeout=60,cwd=cwd)
        el = time.time()-start
        lines = r.stdout.strip().split(chr(10))
        print(f'OK   {el:5.1f}s {tf.name}: {lines[-1]}')
    except subprocess.TimeoutExpired:
        print(f'HANG  60.0s {tf.name}')
"
```

## Known Issues & Skipped Tests

| Test File | Issue | Resolution |
|-----------|-------|------------|
| `test_gl_compositor_transitions.py` | All 14 tests skipped — GL frame-grab tests hang due to `QTest.qWait` + Qt event loop interaction requiring a live GPU context | Marked `@pytest.mark.skip`. Covered by runtime integration testing |
| `test_display_integration.py` | Previously hung when run as a batch — fixture teardown didn't stop running transitions | Fixed: `display_widget` fixture now calls `widget.clear()` + `processEvents()` before close |
| `test_transition_endframe.py` | 9 tests skipped — requires GL context for end-frame pixel assertions | Runtime integration only |
| `test_transitions_integration.py` | 3 tests skipped — requires GL context | Runtime integration only |

### Collection Health

- `pytest --collect-only tests -q` now completes cleanly without manual environment overrides.
- Avoid hard-coding stale “known failures” here. When a regression is active, record it in [Current_Plan.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Current_Plan.md) or the relevant bug/debug doc instead of letting this section decay.
- Active startup-reactivity coverage currently splits between:
  - `tests/test_widget_manager.py` for manager-owned source-of-truth checks around expected overlays, compositor-ready, and Spotify secondary-stage scheduling
  - `tests/test_spotify_visualizer_widget.py` for widget-side staged startup and reveal gating
  - `tests/test_widget_setup.py` for the primary-wave exclusion contract plus the stronger “fade immediately, delay only the visualizer” startup cadence
  - `tests/test_clock_widget.py` for the analog Clock shared-fade contract so a primary overlay cannot silently bypass the coordinated fade wave
  - `tests/test_shadow_utils.py` for the shared fade helper itself, so “delay then instant plaster” regressions fail at the centralized seam instead of only surfacing in live runtime
  - `tests/test_display_image_ops.py` for centralized shader preload plus visualizer overlay prewarm ordering
  - manual/log validation for true cold-start parity versus settings re-entry and mode-cycle refresh

### Test Fixture Best Practices
When writing tests that create `DisplayWidget` or start transitions:
1. **Always call `widget.clear()`** in fixture teardown before `close()`
2. **Always call `qt_app.processEvents()`** after close/deleteLater
3. **Never leave transitions running** between tests — they create timers/animations that hang the event loop
4. **Avoid `QTest.qWait()` in parametrized tests** — it processes events and can leave state between iterations

---

## Test Infrastructure

### Files

| File | Purpose |
|------|---------|
| `conftest.py` | Pytest fixtures, shared test utilities. Supports `--chunk`/`--total-chunks` CLI for chunked execution |
| `pytest.ini` | Pytest configuration |
| `pytest.py` | Custom test runner with logging setup. Supports `-k`, `-v`, and module paths for targeted runs |
| `run_chunked.py` | Chunked test runner — splits full suite into N subprocess chunks (default 4) for memory/timeout isolation |
| `_gl_test_utils.py` | GL testing utilities |

### Key Fixtures (from conftest.py)

| Fixture | Provides |
|---------|----------|
| `qtbot` | QtBot for GUI testing (from pytest-qt) |
| `qapp` | QApplication instance |

---

## Test Categories Summary

| Category | Approx. Files | Notes |
|----------|-------|-------|
| Core Infrastructure | 12 | Threading, process, events, resources, storage paths |
| Rendering & GL | 20 | GL state, compositor, transitions, rendering backends |
| Widgets & Overlays | 27 | All widget types, positioning, Imgur |
| Image Pipeline | 6 | Queue, processing, display |
| Settings & Config | 13 | Settings, dialogs, presets, bindings |
| Input & Interaction | 6 | Keys, mouse, media controls |
| Integration & Workflow | 7 | End-to-end, Reddit, lifecycle |
| Performance & Telemetry | 7 | Timing, logging, perf |
| MC | 3 | Manual Controller specific |
| Regression | 18 | Bug fixes, architecture split, visualizer plumbing |
| **Total** | **115 files** | Current collected `test_*.py` count as of Mar 23 2026 |

---

## Current Regression Bar (Mar 22 2026)

- `tests/test_dimming_and_interaction_fixes.py`
  Minimum bar for Ctrl-held gating, Halo drift clamp, hard-exit click keepalive, and Halo forwarding contract. Important: this is source/runtime contract coverage, not visual proof that Halo click passthrough is fully solved.
- `tests/test_mc_keyboard_input.py`
  Guards the MC focus reclaim / hotkey path that restored working keys after click interactions.
- `tests/test_spotify_visualizer_widget.py`
  Guards shared-engine fresh-frame/reset gating during mode switches.
  It is also now the direct regression fence for staged visualizer startup: secondary-stage deferral, first-fresh-frame reveal, ready-driven post-warmup reveal scheduling, and anchor-visibility release.
  Still important because the Oscilloscope half-dead-line bug is not yet considered closed.
- `tests/test_media_runtime_state.py`, `tests/test_media_display_update.py`, and `tests/test_media_provider_runtime.py`
  These are now the direct regression fence for retained media display: cached metadata/artwork must survive temporary session loss, provider auto-fallback must stay on the shared settings-backed runtime path, and a previously hidden media card must re-enter through the shared fade path when metadata returns.
- `tests/test_media_widget_runtime_methods.py`
  This is the direct fence for the post-audit MediaWidget helper cleanup: poll-stage changes must rebuild the active timer immediately, and track identity must keep artwork-sensitive diff gating instead of drifting back to an older duplicate-helper variant.
- `tests/test_media_artwork_layout.py`
  This is the direct fence for the Spotify video-frame artwork fix: artwork must fit inside the configured box without square-frame distortion, and decode should normalize pixmap scaling metadata before painting gets involved.
- `tests/test_ghost_isolation.py`
  Guards Blob ghost routing/isolation and retired ghost-path branches. This protects the code contract, but Blob ghost visuals still require user validation.
- `tests/test_visualizer_presets.py`
  Guards curated preset schema, repair-tool behavior, and payload hygiene only. Do not use it to freeze aesthetic tuning decisions.
  It is also the regression fence for curated reindex behavior (`--reindex-curated`) so slot repair stays metadata-only and deterministic, while tolerating authored artistic pack changes outside the rigid Preset 1 baseline fence.
  It also now guards the real authored overwrite path end-to-end: `WidgetsTab.build_visualizer_preset_payload()` -> filename metadata application -> JSON write -> `reload_presets()` must not leak retired compat keys back into curated mode payloads.
  It also now guards checked-in schema mirrors: the shared APPDATA fixture and the MC release preset tree cannot silently drift back to retired compat keys or stale curated payloads.
- `tests/test_blob_shaper_plumbing.py`
  This is the direct non-visual contract fence for Blob Shaper authoring/runtime parity: model keys, preset/save payload seams, duplicate-angle wrap handling, top-origin angular routing (`0.0 = top`), reaction-canvas-authoritative runtime routing with legacy base fallback, dedicated shaper-drive band blending, broadened/smoothed routing fields, moderate-energy shaper-drive visibility, base-resting drive behavior, and the rule that shaper idle/paused state must not keep wobbling the authored silhouette away from the GUI.
  It also now guards the latest solved-contour contract directly: overlapping local signed contributors must not numerically average the shaper back toward base just because different authored nodes are active together. Arrow direction is interpreted relative to the authored local reaction direction (so inward-authored dips can be driven inward correctly), opposite-direction travel is clamped to a tighter safe inward target instead of mirroring large outward deltas through the center, larger authored gaps require more local energy to fully reach/hold, positive drive can overshoot slightly beyond the authored reaction contour on kicks, and shaper-active playback resolves to one CPU-solved runtime profile that the shader renders directly. The suite now includes deterministic continuity checks on the solved contour itself, a tougher inward-directed angular continuity scenario, a direct shader-contract check for `u_blob_runtime_profile`, and a time-series motion fence with a meaningful minimum delta so "Blob still moves smoothly under shaper playback" is reproducible without relying only on screenshots.
- Active targeted suites for the current blob/preset/settings work:
  - `python -m pytest tests/test_visualizer_presets.py tests/test_visualizer_preset_manifest.py tests/test_settings_dialog.py tests/test_settings_defaults_parity.py -q`
  - `python -m pytest tests/test_blob_shaper_plumbing.py -q`
  - `python -m pytest tests/test_visualizer_reactivity_quality.py -k "blob" -q`
  - `python -m pytest tests/test_widgets_tab.py tests/test_visualizer_settings_plumbing.py -k "blob" -q`
  - `python -m pytest tests/test_blob_shaper_plumbing.py tests/test_visualizer_reactivity_quality.py -k "blob" -q`
  - `python -m pytest tests/test_blob_shaper_plumbing.py tests/test_blob_intensity_reserve.py -q`
  - `python -m pytest tests/test_visualizer_presets.py tests/test_visualizer_settings_plumbing.py tests/test_widgets_tab.py -k "blob_shaper or blob_pulse or blob_shape" -q`
  - `python -m pytest tests/test_blob_shaper_plumbing.py tests/test_visualizer_reactivity_quality.py -k "blob_stage_inputs or blob_kick_assist or blob_vocal_phrase or blob_pulse_release" -q`
  - `python -m pytest tests/test_visualizer_settings_plumbing.py tests/test_widgets_tab.py tests/test_visualizer_presets.py -k "blob" -q`
  - `python -m pytest tests/test_visualizer_preset_manifest.py tests/test_settings_dialog.py tests/test_settings_defaults_parity.py -q`
  - `python -m pytest tests/test_reddit_helper_watcher.py tests/test_reddit_helper_runtime.py tests/test_settings_defaults_parity.py -q`
  - `python -m pytest tests/test_reddit_helper_watcher.py tests/test_reddit_helper_runtime.py -q`
- `tests/test_visualizer_reactivity_quality.py`
  Guards Blob/Spectrum behavior-level reactivity contracts. It now includes a representative Blob Preset 1-style moderate-kick stage regression so future fixes do not drift back toward the over-damped “live bands move but stage stays asleep” failure.
  It also guards the Blob stage ladder directly: stage 1 must keep headroom, stage 2/3 must be reachable on stronger phrases, and stage-1 decay must not leave the silhouette parked in one size.
- `tests/test_visualizer_settings_plumbing.py`
  This suite should prefer real model/applier/creator/frame-push behavior checks over source-text assertions. A few static contract checks remain where GL/shader runtime surfaces are impractical.
It is also now the direct regression fence for extracted WidgetsTab adapters (`spectrum_settings_binding.py`, `blob_settings_binding.py`, `bubble_settings_binding.py`, `oscilloscope_settings_binding.py`, `sine_wave_settings_binding.py`) and for `core/settings/visualizer_settings_contract.py` plus `core/settings/visualizer_settings_snapshot.py`, so coordinator-shrinking refactors and sparse-mapping/SST contract work stay behavior-safe.
It is also now a direct guard for the Spectrum Energy Arrows contract: the lane-native maps emitted by `spectrum_settings_binding.py` must survive save/load and creator/applier translation without leaking `spectrum_bass_emphasis`, `spectrum_mid_suppression`, or `spectrum_vocal_position` back into authored runtime state.
  Bubble gradient semantics coverage also lives here now: legacy-label migration, `center_out_reverse`, and canonical shader-vector/mode mapping are tested without relying on visual inspection alone.
- `tests/test_visualizer_preset1_baselines.py`
  This is the intentional rigid fence for curated preset feel. If preset 1 is deliberately reauthored, refresh the checked-in baseline in the same change.
- `tests/test_s_hotkey_workflow.py` and `tests/test_flicker_fix_integration.py`
  Minimum regression bar for the now-resolved settings flicker / settings-launch workflow.

---

**Last Updated**: Mar 28, 2026 (startup suites now also guard against primary-wave dead-air and keep the visualizer delay isolated to the Spotify secondary stage)
