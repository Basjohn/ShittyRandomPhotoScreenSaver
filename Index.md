# Index

Last updated: 2026-05-14

Living map of the current SRPSS codebase.

## Core Documents

| File | Purpose |
|---|---|
| `Spec.md` | Canonical architecture contract |
| `Current_Plan.md` | Active short-term work and validation |
| `Docs/Guardrails.md` | Engineering rules and anti-regression policy |
| `Docs/Historical_Bugs.md` | Dated bug timeline and postmortems |
| `Docs/Regression_Notes.md` | Smaller resolved regression notes and follow-up hardening items |
| `Docs/Defaults_Guide.md` | Defaults and reset contracts |
| `Docs/Documentation_Maintenance.md` | Lightweight drift-check routine for canonical docs |
| `Docs/TestSuite.md` | Test strategy and execution guidance |
| `Docs/Harness_Index.md` | Compact reference for recurring investigation harnesses and probes |
| `Docs/MEDIAKEYDEBUG.md` | Focus/media-key investigation notes and U-05 harness evidence |
| `Docs/00_PROJECT_OVERVIEW.md` | High-level orientation to the documentation set and main runtime areas |
| `Docs/Custom_Style_Implementation.md` | Styling/reference guardrails for shared settings-dialog and UI chrome work |
| `Docs/10_WIDGET_GUIDELINES.md` | Canonical widget implementation guidance and integration checklist |
| `Docs/Visualizer_Reference.md` | Visualizer architecture and contracts |
| `Docs/Visualizer_Change_Checklist.md` | Required sweep for visualizer changes |
| `Docs/Transition_Change_Checklist.md` | Required sweep for adding or changing transitions |

## Entry Points

| File | Purpose |
|---|---|
| `main.py` | Screensaver runtime (`/s`, `/c`, `/p`, script mode) |
| `main_mc.py` | Media Center runtime |

## Manager Layer

| Manager | File |
|---|---|
| ThreadManager | `core/threading/manager.py` |
| ResourceManager | `core/resources/manager.py` |
| SettingsManager | `core/settings/settings_manager.py` |
| AnimationManager | `core/animation/animator.py` |
| EventSystem | `core/events/event_system.py` |
| ProcessSupervisor | `core/process/supervisor.py` |

## Settings and Persistence

| Module | File | Role |
|---|---|---|
| Canonical defaults | `core/settings/default_settings.py` | Source of default values |
| Defaults API | `core/settings/defaults.py` | Default loading + preserve-on-reset contract |
| Settings store | `core/settings/json_store.py` | Atomic JSON persistence |
| Settings manager | `core/settings/settings_manager.py` | Dotted API over structured roots, legacy-key alias migration, and persisted visualizer schema version gating |
| Visualizer settings model | `core/settings/models/_spotify_visualizer.py` | Canonical grouped field-spec/default/build/serialize contract for visualizer settings; keeps `from_settings()`, `from_mapping()`, and `to_dict()` aligned through ordered section merges rather than entry-point-specific handwritten payloads |
| Snapshot normalization | `core/settings/visualizer_settings_snapshot.py` | Canonical visualizer mapping normalization |
| Technical normalization / legacy migration contract | `core/settings/visualizer_settings_contract.py` | Migrates legacy shared technical inputs into canonical per-mode visualizer settings |
| Preset index contract | `core/settings/visualizer_preset_indices.py` | Shared preset index fallback/lookup |
| Shadow tuning loader | `core/settings/shadow_tuning.py` | Loads `shadowtuning.json`; provides `CARD_SHADOW_TUNING` + `VOLUME_SLIDER_SHADOW_TUNING` |
| Storage paths | `core/settings/storage_paths.py` | Canonical `%APPDATA%` path resolver for all persistent files |

## Performance and Observability

| Module | File | Role |
|---|---|---|
| Frame budget / GC controller | `core/performance/frame_budget.py` | Frame pacing and GC budget helpers for render/runtime hot paths |
| Widget perf profiler | `core/performance/widget_profiler.py` | Widget paint/timer metrics sampling and perf log emission |

## Visualizer System

| Module | File | Role |
|---|---|---|
| Mode registry | `core/settings/visualizer_mode_registry.py` | Mode ids, labels, canonical default-mode fallback, and key-prefix ownership |
| Preset manager | `core/settings/visualizer_presets.py` | Curated/custom loading, canonical activation payload resolution, and preset apply |
| Preset repair tool | `tools/visualizer_preset_repair.py` | Audit/repair/reindex curated preset payloads |
| Widget runtime | `widgets/spotify_visualizer_widget.py` | Runtime visualizer coordinator and resolved activation payload application; authoritative technical replay reads from `_get_mode_technical_config(...)` rather than transient widget cache, latency diagnostics are reset at activation/reset boundaries, cold construction can be seeded with a resolved startup mode, and ThreadManager hookup must not replay authoritative technical config before the settings model/cache exist |
| Overlay transport | `widgets/spotify_bars_gl_overlay.py` | GL state transport, render-state storage, painted-card rounded-rect stencil mask with border-width inset, resolved-startup-mode-first shader compilation, and deferred warmup of remaining visualizer mode programs |
| Overlay diagnostics | `widgets/spotify_visualizer/overlay_diagnostics.py` | Passive overlay diagnostics for Glow, Blob, and Sine idle-state logging, extracted so diagnostic payload assembly stays outside render authority code |
| Overlay common uniforms | `widgets/spotify_visualizer/overlay_uniforms.py` | Shared mode-neutral GL uniform upload and rainbow hue/logging prep, extracted so common transport stays outside mode-owned renderer math |
| Overlay render dispatch | `widgets/spotify_visualizer/overlay_render_dispatch.py` | Mode-program resolution and renderer-owned uniform dispatch, extracted so the overlay shell no longer owns lazy mode-program compilation and renderer registry calls inline |
| Overlay frame shell | `widgets/spotify_visualizer/overlay_frame_shell.py` | Shared backbuffer clear, fade gating, and stencil-wrapped render envelope for the overlay paint path |
| Overlay stencil mask | `widgets/spotify_visualizer/overlay_mask.py` | Shared painted-card stencil uniform math for the GL overlay render path, preserving the rounded-rect border-inset clipping contract |
| Overlay state handoff | `widgets/spotify_visualizer/overlay_state.py` | Overlay-local mode reset, activation/generation metadata capture, border-width/floor snapshot handoff, and invisible-frame early return without touching first-frame shader authority |
| Overlay lifecycle bridge | `widgets/spotify_visualizer/media_bridge.py` / `widgets/spotify_visualizer/engine_lifecycle.py` | Runtime overlay clear/destroy policy: mode and preset resets preserve the GL overlay object where possible, while cleanup/teardown still destroys it |
| Config application | `widgets/spotify_visualizer/config_applier.py` | Settings/model to runtime kwargs mapping; engine config replay; shared GPU extras payload construction, including the reusable steady-state Spectrum extras dict |
| Spline Curve (`devcurve`) runtime | `widgets/spotify_visualizer/tick_pipeline.py` / `widgets/spotify_visualizer/renderers/devcurve.py` | Spline Curve runtime curves, specular slots, idle/play specular alpha activity multiplier, and activation-aware visualizer latency logging |
| Startup contract | `widgets/spotify_visualizer/startup_contract.py` | Staged startup state contract |
| Startup staging | `widgets/spotify_visualizer/startup_staging.py` | Extracted startup staging, lifecycle hooks, hot start, and cleanup |
| Card paint | `widgets/spotify_visualizer/card_paint.py` | Painted-frame-shadow pixmap generation and card style |
| Media bridge | `widgets/spotify_visualizer/media_bridge.py` | Media state tracking, anchor seeding, GL overlay teardown |
| Engine lifecycle | `widgets/spotify_visualizer/engine_lifecycle.py` | Engine reset, audio fallback, wake, generation tracking |
| Technical config | `widgets/spotify_visualizer/technical_config.py` | Per-mode technical cache building, runtime override replacement, mode→engine/overlay technical application |
| Activation runtime | `widgets/spotify_visualizer/activation_runtime.py` | Settings-model apply, resolved activation payload application, and full-runtime mode replay without touching first-frame authority gates |
| Runtime config | `widgets/spotify_visualizer/runtime_config.py` | Shared engine/thread/process/audio-block/runtime-bar-state coordination extracted from the widget coordinator; live audio-block changes now flow through the worker's capture-restart seam instead of waiting for a full runtime rebuild, early ThreadManager hookup defers authoritative engine replay until startup activation has seeded mode-owned technical config, and external runtime setters plus bar-buffer resize now resolve/rebind engine dependencies and prefer authoritative replay when that contract is ready |
| Mode transition | `widgets/spotify_visualizer/mode_transition.py` | Visualizer fade/reset sequencing, direct mode-activation ordering, pending-mode activation after fade-out, teardown readiness, and cold-reset runtime-state clearing while preserving first-frame and preset-application guardrails |

## Rendering System

| Module | File | Role |
|---|---|---|
| Display presenter | `rendering/display_widget.py` | Fullscreen presenter per display |
| Widget lifecycle | `rendering/widget_manager.py` | Overlay widget lifecycle/fades/sync, including canonical visualizer refresh payload handoff |
| Widget descriptor registry | `rendering/widget_descriptors.py` | Canonical factory-backed widget family metadata plus WidgetsTab section and runtime-capability registry: stable widget ids, parent attributes, factory routing, startup-stage intent, inheritance kwargs, config injection such as Gmail shadow plumbing, settings-section order/label/builder ownership, service-backed/anchor-dependent capability flags, and live-refresh handler ownership |
| Widget setup orchestration | `rendering/widget_setup_all.py` | Shared descriptor-driven creation/reuse/expected-overlay flow for factory-backed widgets plus the remaining Spotify-dependent setup path |
| Shared service widget runtime | `widgets/service_widget_runtime.py` | Shared lifecycle helpers for service-backed overlay widgets: parent transition-busy probing, deferred single-shot timer reuse, deferred refresh/result staging, spinner suspend/resume, and timer-stop cleanup used by Gmail/Reddit/Weather slices |
| Startup policy | `rendering/overlay_startup_policy.py` | Primary and secondary startup timing |
| Widget positioner | `rendering/widget_positioner.py` | Centralized anchor/margin/stack positioning calculations for overlay widgets |
| Input routing | `rendering/input_handler.py` | Keyboard/mouse/media/control routing; keeps non-link widget controls separate from real URL clicks so refresh/menu interactions do not trigger browser-exit helper paths |
| GL compositor | `rendering/gl_compositor.py` | GL transition/composition surface with transition-resource warmup delegated to the compositor/runtime helpers |
| GL lifecycle helpers | `rendering/gl_compositor_pkg/gl_lifecycle.py` | Compositor context initialization, minimal startup transition-program compilation, and deferred warmup of the remaining transition shader programs |
| Frame push / overlay state | `rendering/display_image_ops.py` | Per-frame overlay state routing, including `border_width_px` handoff to the GL overlay for stencil-mask inset |
| Transition busy state | `rendering/display_widget.py` / `engine/display_manager.py` | Pending/active transition reporting used by overlay widgets to defer refresh/cache churn during image-load and GL transition windows |

## Gmail Integration

| Module | File | Role |
|---|---|---|
| OAuth manager | `core/gmail/gmail_oauth.py` | OAuth 2.0 PKCE flow, token storage (DPAPI) |
| REST API client | `core/gmail/gmail_client.py` | Gmail REST API — metadata, labels, read/unread/archive/spam/trash actions |
| IMAP client | `core/gmail/gmail_imap.py` | IMAP + App Password — headers, unread count, selected-mailbox order, UID actions, and rejection of degraded partial fetch snapshots |
| Deep-link helpers | `core/gmail/gmail_deeplinks.py` | Gmail inbox/thread/search URL builders; `X-GM-THRID` decimal-to-hex conversion |
| Unified backend | `core/gmail/gmail_backend.py` | Routes to OAuth/REST or IMAP based on config |
| Widget components | `widgets/gmail_components.py` | Nine-position `GmailPosition` enum, date formatting modes, formatting/text cleanup utilities, punctuation-aware shortening, email cache |
| Settings UI | `ui/tabs/widgets_tab_gmail.py` | Backend selector, credentials, non-blocking IMAP Save & Test, widget settings, sender/subject cleanup controls, grouping toggle, deferred auth refresh, and Gmail-specific signal-block/visibility guardrails |
| Settings cache | `ui/settings_dialog_cache.py` | Settings dialog cached defaults/font data; cache generation includes canonical defaults modules so Gmail defaults do not go stale |
| Overlay widget | `widgets/gmail_widget.py` | Screensaver overlay for Gmail list rendering, backend-safe actions, row/menu hit targets, shared transition-aware refresh/result deferral, empty-fetch preservation of valid displayed mail, header-safe fallback layout, async cache writes, DPR-aware stable-content paint cache, grouping toggle support, and perf instrumentation |
| Asset guard tests | `tests/test_gmail_assets.py` | Verifies required Gmail image assets exist and normal/MC Nuitka scripts include only the notification OGG plus Qt multimedia requirements |

## Shared Shadow Path

| Module | File | Role |
|---|---|---|
| Painted frame shadows | `widgets/base_overlay_widget.py` | Settings-controlled cached painter-drawn card, text, and header shadow path for framed runtime overlay widgets |
| Shadow tuning | `core/settings/shadow_tuning.py` | Canonical `shadowtuning.json` defaults for card, text, header, control, icon, and Spotify volume-slider painted shadows |
| Visualizer parity | `widgets/spotify_visualizer_widget.py` | Uses the shared painted-shadow contract for the visualizer card without changing GL/audio/bar rendering |

## Source Ingestion

| Module | File | Role |
|---|---|---|
| RSS coordinator | `sources/rss/coordinator.py` | Feed orchestration and budget logic |
| RSS downloader | `sources/rss/downloader.py` | Network and image download pipeline |
| RSS cache | `sources/rss/cache.py` | Local cache and eviction |
| RSS facade | `sources/rss_source.py` | Backward-compatible source wrapper |

## Useful Tools

| Tool | Purpose |
|---|---|
| `tools/flicker_test.py` | Settings dialog flicker/ghost harness |
| `tools/winprobe_observer.py` | External transient HWND observer |
| `tools/reddit_helper_task_harness.py` | Scheduled-task helper smoke test |
| `tools/regen_qrc.py` | Regenerate Qt icon resource module |
| `tools/hardware_ingress_validator.py` | Hardware-ingress validation layer for U-05 — correlates real physical key events with SRPSS log responses |

## Runtime Environment Variables

| Variable | Purpose |
|---|---|
| `SRPSS_ENABLE_DEV` | Enable dev-only features (non-mode-gate features) |
| `SRPSS_VIZ_DIAGNOSTICS` | Enable verbose visualizer diagnostics |
| `SRPSS_PERF_METRICS` | Enable perf metrics logging |
| `SRPSS_DISABLE_LOGGING` / `SRPSS_DISABLE_LOGS` | Disable runtime logging |
| `SRPSS_FORCE_LOG_DIR` | Override log directory |
| `SRPSS_FORCE_SOUNDDEVICE` | Force sounddevice audio backend |

## Runtime CLI Flags

| Flag | Purpose |
|---|---|
| `--debug`, `-d` | Debug logging |
| `--viz` | Visualizer logging |
| `--viz-diagnostics`, `--viz-diag` | Enable diagnostics and set env toggle |
| `--fresh` | Clear runtime logs at startup |
| `-devblob` | Enable blob mode gate |
| `--devcurve` | Compatibility no-op alias |
| Tick helpers | `widgets/spotify_visualizer/tick_helpers.py` | Transition context, FPS retuning, steady-timer ownership, AnimationManager tick-listener lifecycle, geometry cache, visual smoothing, and perf snapshot logging |
