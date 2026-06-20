# Index

Last updated: 2026-06-19

Living map of the current SRPSS codebase.

## Core Documents

| File | Purpose |
|---|---|
| `Spec.md` | Canonical architecture contract |
| `Current_Plan.md` | Active short-term work and validation |
| `Docs/Guardrails.md` | Engineering rules and anti-regression policy |
| `Docs/Contracts.md` | Short contract index that routes quickly to the canonical owner for each major subsystem seam |
| `Docs/Historical_Bugs.md` | Dated bug timeline and postmortems |
| `audits/BubbleAudit/Bubble_End_To_End_Audit.md` | Historical Bubble audit reference for the transition-time perf collapse and loud small-lane recovery work that informed the current tighter runtime-shaped Bubble oracles |
| `audits/BubbleAudit/Bubble_Preset_Runtime_Audit.md` | Document-only audit of Bubble runtime-touching preset settings, with Deep Sea Preset 1 hypotheses and authored experiment order before more Bubble code tuning |
| `audits/BubbleAudit/README.md` | Small entrypoint that points at the Bubble audit reference |
| `audits/GeoAudit/Visualizer_Runtime_Shape_Audit.md` | Active geometry audit with risks, order of work, and start-to-finish checklist for the reopened visualizer CUSTOM/runtime shape family |
| `audits/GeoAudit/README.md` | Small entrypoint that points at the active geometry audit |
| `Docs/Regression_Notes.md` | Smaller resolved regression notes and follow-up hardening items |
| `Docs/Defaults_Guide.md` | Defaults and reset contracts |
| `Docs/Documentation_Maintenance.md` | Lightweight drift-check routine for canonical docs |
| `Docs/TestSuite.md` | Test strategy and execution guidance |
| `Docs/Logging_Guide.md` | CLI-first logging flags, sidecar files, and correlation workflow |
| `Docs/Harness_Index.md` | Compact reference for recurring investigation harnesses and probes |
| `Docs/MEDIAKEYDEBUG.md` | Focus/media-key investigation notes and U-05 harness evidence |
| `Docs/00_PROJECT_OVERVIEW.md` | High-level orientation to the documentation set and main runtime areas |
| `Docs/Custom_Style_Implementation.md` | Styling/reference guardrails for shared settings-dialog and UI chrome work |
| `Docs/10_WIDGET_GUIDELINES.md` | Canonical A-to-Z widget creation guide: ownership, descriptors, settings, runtime integration, `Custom`, logging, and regression-bar expectations |
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
| Canonical defaults | `core/settings/default_settings.py` | Source of default values, including shared widget-global defaults such as card-border width and authored-stacking opt-in |
| Defaults API | `core/settings/defaults.py` | Default loading + preserve-on-reset contract |
| List-capacity policy | `core/settings/widget_capacity_policy.py` | Shared active list-widget capacity policy (`5..25`) and staged-growth helpers |
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
| Bubble parity harness | `tools/bubble_parity_harness.py` | Historical comparison harness for Bubble curated presets against `9d4925e` / `510520e`, used when Deep Sea regressions are too severe for present-day proxy bars to be trusted |
| Widget runtime | `widgets/spotify_visualizer_widget.py` | Runtime visualizer coordinator and resolved activation payload application; authoritative technical replay reads from `_get_mode_technical_config(...)` rather than transient widget cache, latency diagnostics are reset at activation/reset boundaries, cold construction can be seeded with a resolved startup mode, ThreadManager hookup must not replay authoritative technical config before the settings model/cache exist, and active CUSTOM geometry now rejects foreign outer-rect writes once committed rect authority exists |
| Display participation helper | `rendering/spotify_display_participation.py` | Narrow visualizer/display owner selection helper that distinguishes truly absent CUSTOM targets from runtime-known but temporarily non-participating displays, so owner selection can stay cautious during startup and sleep/wake churn |
| Overlay transport | `widgets/spotify_bars_gl_overlay.py` | GL state transport, render-state storage, painted-card rounded-rect stencil mask with border-width inset, resolved-startup-mode-first shader compilation, and deferred warmup of remaining visualizer mode programs |
| Spectrum solid-bar display smoothing | `widgets/spotify_visualizer/spectrum_solid_hysteresis.py` | Display-only solid Spectrum smoothing/easing: continuous display-state motion with small-zone chatter suppression, intentionally kept out of shared audio/floor logic |
| Overlay diagnostics | `widgets/spotify_visualizer/overlay_diagnostics.py` | Passive overlay diagnostics for Glow, Blob, and Sine idle-state logging, extracted so diagnostic payload assembly stays outside render authority code |
| Overlay common uniforms | `widgets/spotify_visualizer/overlay_uniforms.py` | Shared mode-neutral GL uniform upload and rainbow hue/logging prep, extracted so common transport stays outside mode-owned renderer math |
| Overlay render dispatch | `widgets/spotify_visualizer/overlay_render_dispatch.py` | Mode-program resolution and renderer-owned uniform dispatch, extracted so the overlay shell no longer owns lazy mode-program compilation and renderer registry calls inline |
| Overlay frame shell | `widgets/spotify_visualizer/overlay_frame_shell.py` | Shared backbuffer clear, fade gating, and stencil-wrapped render envelope for the overlay paint path |
| Outer card geometry | `widgets/spotify_visualizer/card_geometry.py` | Canonical outer card geometry policy: mode/preset-owned preferred height, blob-width reduction, and media-relative placement, kept intentionally separate from stencil math for future custom layout/resize work |
| Overlay stencil mask | `widgets/spotify_visualizer/overlay_mask.py` | Shared painted-card stencil uniform math for the GL overlay render path, preserving the rounded-rect border-inset clipping contract |
| Overlay state handoff | `widgets/spotify_visualizer/overlay_state.py` | Overlay-local mode reset, activation/generation metadata capture, border-width/floor snapshot handoff, and invisible-frame early return without touching first-frame shader authority |
| Overlay lifecycle bridge | `widgets/spotify_visualizer/media_bridge.py` / `widgets/spotify_visualizer/engine_lifecycle.py` | Runtime overlay clear/destroy policy: mode and preset resets preserve the GL overlay object where possible, while cleanup/teardown still destroys it |
| Config application | `widgets/spotify_visualizer/config_applier.py` | Settings/model to runtime kwargs mapping; engine config replay; shared GPU extras payload construction, including the reusable steady-state Spectrum extras dict |
| Spectrum bar-field contract | `widgets/spotify_visualizer/renderers/spectrum.py` / `widgets/spotify_visualizer/shaders/spectrum.frag` | Shared Spectrum horizontal layout contract: CPU helper and shader agree on the same slightly left-biased bar field so runtime no longer freelances separate left/right spacing math |
| Spline Curve (`devcurve`) runtime | `widgets/spotify_visualizer/tick_pipeline.py` / `widgets/spotify_visualizer/renderers/devcurve.py` | Spline Curve runtime curves, specular slots, idle/play specular alpha activity multiplier, and activation-aware visualizer latency logging |
| Startup contract | `widgets/spotify_visualizer/startup_contract.py` | Staged startup state contract |
| Startup staging | `widgets/spotify_visualizer/startup_staging.py` | Extracted startup staging, lifecycle hooks, hot start, and cleanup |
| Card paint | `widgets/spotify_visualizer/card_paint.py` | Painted-frame-shadow pixmap generation and card style |
| Media bridge | `widgets/spotify_visualizer/media_bridge.py` | Media state tracking, anchor seeding, pause-confirmed playback authority, startup seed-trust classification for provisional non-playing shared-cache seeds, and GL overlay teardown |
| Engine lifecycle | `widgets/spotify_visualizer/engine_lifecycle.py` | Engine reset, audio fallback, wake, generation tracking, and capture/no-capture lifecycle routing |
| Beat engine | `widgets/spotify_visualizer/beat_engine.py` | Shared audio worker/capture lifecycle plus paused idle waveform/bar seeding, short warm-capture grace across real-world play/pause wobble, and Bubble's pressure-aware raw-band continuous feed |
| Bubble simulation | `widgets/spotify_visualizer/bubble_simulation.py` | CPU-side Bubble particle simulation, two-lane Bubble sizing/gating (hero big lane plus small/medium lane), preserved supra-unit loud-path authority at the Bubble-owned dispatch/simulation seam, mild loud-reactive drift lift through the existing drift controls, optional grouped non-swirl drift via authored `bubble_group_drift` with eased shared-carrier turns and cadence-owned swish reversals, display-only big/hero visual smoothing at the rendered-radius seam via the authored `bubble_big_visual_smoothing` control, live size-envelope adaptation for existing bubbles, and per-frame big-lane diagnostics used by the authored Deep Sea regression bars |
| Technical config | `widgets/spotify_visualizer/technical_config.py` | Per-mode technical cache building, runtime override replacement, mode→engine/overlay technical application |
| Activation runtime | `widgets/spotify_visualizer/activation_runtime.py` | Settings-model apply, resolved activation payload application, and full-runtime mode replay without touching first-frame authority gates |
| Runtime config | `widgets/spotify_visualizer/runtime_config.py` | Shared engine/thread/process/audio-block/runtime-bar-state coordination extracted from the widget coordinator; live audio-block changes now flow through the worker's capture-restart seam instead of waiting for a full runtime rebuild, early ThreadManager hookup defers authoritative engine replay until startup activation has seeded mode-owned technical config, and external runtime setters plus bar-buffer resize now resolve/rebind engine dependencies and prefer authoritative replay when that contract is ready |
| Mode transition | `widgets/spotify_visualizer/mode_transition.py` | Visualizer fade/reset sequencing, direct mode-activation ordering, pending-mode activation after fade-out, teardown readiness, and cold-reset runtime-state clearing while preserving first-frame and preset-application guardrails |

## Rendering System

| Module | File | Role |
|---|---|---|
| Display presenter | `rendering/display_widget.py` | Fullscreen presenter per display |
| Transition registry | `rendering/transition_registry.py` | Canonical transition identity, legacy alias canonicalization, UI ordering, cycle/random-pool participation, hardware gating, compositor program routing, and startup shader warmup metadata |
| Widget lifecycle | `rendering/widget_manager.py` | Overlay widget lifecycle/fades/sync, including canonical visualizer refresh payload handoff, startup-equivalent fade-coordinator re-prime on CUSTOM rebuild, full authored-stacking shutdown whenever any widget family is currently in `Custom`, shared authored-position stacking offsets/geometry diagnostics for non-`Custom` overlays only when the global opt-in is enabled, shadow-free visible-footprint measurement plus fixed follow-media media+visualizer lane occupancy for authored stacking, live media refresh reapplication of authored typography/artwork inputs even while CUSTOM resize is active, and the narrow runtime-pause quiesce hook used before display teardown/settings entry |
| Shared stacking planner | `rendering/widget_stacking.py` | Pure non-`Custom` authored stacking planner shared by runtime and settings prediction: left/center/right column grouping, stable top/middle/bottom band ordering, fixed obstacle occupancy for companion blocks, fit reporting, and no CUSTOM layout ownership |
| Widget effect refresh seam | `rendering/widget_effects.py` | Narrow transient-opacity refresh helpers for widgets that currently own a live `QGraphicsOpacityEffect`; intentionally no longer a broad menu/focus/display-change shadow cache-busting path |
| Widget descriptor registry | `rendering/widget_descriptors.py` | Canonical factory-backed widget family metadata plus WidgetsTab section, runtime-capability, service-runtime-contract, and stack-preview/settings-composition registry: stable widget ids, live widget attr names, factory routing, startup-stage intent, inheritance kwargs, config injection such as Gmail shadow plumbing, settings-section order/label/builder/load/save ownership, descriptor-owned load/save orchestration helpers including single-section loader/saver accessors, descriptor-owned lazy-bootstrap/section-id/default-selection policy for WidgetsTab, descriptor-owned lazy/programmatic inter-section dependency metadata, descriptor-owned save-result application for standard persisted keys, descriptor-owned signal-block membership and target collection for standard sections, descriptor-owned default-init metadata for standard widget settings attrs, service-backed/anchor-dependent capability flags, live-refresh handler ownership, descriptor-owned service-widget lifecycle contract participation, canonical widget position-option/layout-edit capability metadata, first-phase CUSTOM resize-mode ownership, descriptor-owned CUSTOM size-lock metadata for WidgetsTab, explicit visualizer follow-media-vs-Custom routing resolution, shared authored-layout restore mutation ownership, canonical application-default position-reset helpers, descriptor-owned preview field reads for WidgetsTab stack/status composition, and environment-aware cached active descriptor/index views so dev-gated families do not drift stale across tests/runtime |
| Defaults section helpers | `ui/tabs/widgets_tab_defaults.py` | Descriptor-owned builder/load/save helpers for shared widget defaults such as shadow toggles, authored-stacking opt-in, and card-border-width persistence |
| Widget setup orchestration | `rendering/widget_setup_all.py` | Shared descriptor-driven creation/reuse/expected-overlay flow for factory-backed widgets plus an explicit Spotify setup plan: media-owned dependents, local visualizer, remote Custom visualizer reconcile with cautious delayed fallback recheck for runtime-known sleeping displays, then final startup with delayed verify/confirm custom-rect stabilization instead of blind next-turn reapply |
| Visualizer creators | `rendering/spotify_widget_creators.py` | Spotify visualizer/volume widget construction, including creator-time WidgetManager attachment and creator-time committed CUSTOM rect priming before startup activation when a saved CUSTOM visualizer rect already exists |
| CUSTOM layout contract | `rendering/custom_layout_contract.py` | Display-local normalized rect persistence helpers, authored-route restore metadata, canonical display-signature resolution plus narrow legacy MC bucket ingestion, snapping, clamp rules, and cross-display target-screen resolution for CUSTOM edit mode |
| CUSTOM layout session manager | `rendering/custom_layout_manager.py` | Global CUSTOM edit-session orchestration across active compositor-backed displays, shell lifecycle, save/cancel/reset commit flow, numbered-monitor transfer authority, runtime layout reapply/reload hooks, explicit post-payload committed-rect reassertion for resizable CUSTOM families, and explicit settings-entry/session teardown ownership |
| CUSTOM edit shell | `widgets/edit_shell_widget.py` | Temporary top-level shell used during CUSTOM edit mode, including drag handling, plain scroll-wheel resize requests, and local reset affordances |
| Runtime flags | `core/runtime_flags.py` | Shared process-wide CLI/runtime feature flags such as `--noupdates`, consumed by startup/runtime code without repeated handwritten `sys.argv` checks |
| Shared service widget runtime | `widgets/service_widget_runtime.py` | Shared lifecycle helpers for service-backed overlay widgets: parent transition-busy probing, deferred single-shot timer reuse, deferred refresh/result staging, spinner suspend/resume, shared fetch-in-progress begin/end guards, shared manual-refresh request flow, shared automatic-startup-update policy including fresh-cache startup skip, visible-fallback preservation for non-authoritative empty/error results, shared deferred-runtime timer/state reset, and timer-stop cleanup used by Gmail/Reddit/Weather slices |
| Media widget | `widgets/media_widget.py` | Now Playing overlay with canonical local smart-poll timer reset and pending playback-state debounce reset ownership, retained-display/runtime-state handling, visible-metadata-only relayout identity so same-track album/artwork/state churn does not refit text, media control feedback, and cross-display Spotify-dependent visibility fan-out through the widget manager |
| Mute button | `widgets/mute_button_widget.py` | Media-adjacent mute toggle anchored to the media card, with canonical local runtime reset ownership for poll state and Spotify secondary-stage reveal state |
| Startup policy | `rendering/overlay_startup_policy.py` | Primary and secondary startup timing |
| Widget positioner | `rendering/widget_positioner.py` | Centralized anchor/margin/stack positioning calculations for overlay widgets |
| Input routing | `rendering/input_handler.py` | Keyboard/mouse/media/control routing; keeps non-link widget controls separate from real URL clicks so refresh/menu interactions do not trigger browser-exit helper paths, emits focused transport/volume hotkey intent such as `Space`/`Home` play-pause, `Left`/`Right` track navigation, `Up`/`Down` slider volume steps, plus `PgUp`/`PgDn`/`End` system-audio requests through the same centralized input contract as the other runtime keyboard actions, and preserves focused-only key ownership rather than global key grabs |
| GL compositor | `rendering/gl_compositor.py` | GL transition/composition surface with transition-resource warmup delegated to the compositor/runtime helpers, compositor-owned skip logic for transitions already warmed through the hidden startup path, shared compositor-side transition desync that is retained only for real multi-display pacing, and actual-start telemetry handoff so transition-duration metrics reflect compositor runtime rather than request-time delay |
| GL lifecycle helpers | `rendering/gl_compositor_pkg/gl_lifecycle.py` | Compositor context initialization plus registry-driven minimal startup transition-program compilation, hidden/quiescent deferred warmup of the remaining transition shader programs and representative transition resources, and the shared first-use transition-program ensure/bind seam |
| Frame push / overlay state | `rendering/display_image_ops.py` | Per-frame overlay state routing, including `border_width_px` handoff to the GL overlay for stencil-mask inset |
| Transition busy state | `rendering/display_widget.py` / `engine/display_manager.py` | Pending/active transition reporting used by overlay widgets to defer refresh/cache churn during image-load and GL transition windows |
| Transition settings UI | `ui/tabs/transitions_tab.py` | Transition settings UI, per-transition specific controls, and registry-driven ordinary transition selector order/load/save behavior |
| Transition factory | `rendering/transition_factory.py` | Runtime transition instantiation, duration/direction resolution, registry-driven canonical name handling, and factory-side random fallback selection |

## Gmail Integration

| Module | File | Role |
|---|---|---|
| OAuth manager | `core/gmail/gmail_oauth.py` | OAuth 2.0 PKCE flow, token storage (DPAPI) |
| REST API client | `core/gmail/gmail_client.py` | Gmail REST API — metadata, labels, read/unread/archive/spam/trash actions |
| IMAP client | `core/gmail/gmail_imap.py` | IMAP + App Password — headers, unread count, selected-mailbox order, UID actions, and rejection of degraded partial fetch snapshots |
| Deep-link helpers | `core/gmail/gmail_deeplinks.py` | Gmail inbox/thread/search URL builders; `X-GM-THRID` decimal-to-hex conversion |
| Browser window routing | `core/windows/browser_window_routing.py` | Shared Windows browser-window keyword building, display-0 preference ranking, and best-effort foreground policy reused by helper and MC direct-open flows |
| Unified backend | `core/gmail/gmail_backend.py` | Routes to OAuth/REST or IMAP based on config |
| Widget components | `widgets/gmail_components.py` | Nine-position `GmailPosition` enum, date formatting modes, formatting/text cleanup utilities, punctuation-aware shortening, email cache |
| Settings UI | `ui/tabs/widgets_tab_gmail.py` | Backend selector, credentials, non-blocking IMAP Save & Test, widget settings, sender/subject cleanup controls, grouping toggle, deferred auth refresh, and Gmail-specific signal-block/visibility guardrails |
| Settings cache | `ui/settings_dialog_cache.py` | Settings dialog cached defaults/font data; cache generation includes canonical defaults modules so Gmail defaults do not go stale |
| Overlay widget | `widgets/gmail_widget.py` | Screensaver overlay for Gmail list rendering, backend-safe actions, row/menu hit targets, shared transition-aware refresh/result deferral, empty-fetch preservation of valid displayed mail, fixed-window fetch/cache with configured-vs-visible capacity split (`limit` remains configured capacity), header-safe fallback layout, async cache writes, DPR-aware stable-content paint cache, grouping toggle support, perf instrumentation, and CUSTOM vertical content-fit participation that may persist committed height changes while keeping width fixed |
| Reddit post provider seam | `core/reddit_post_provider.py` | Provider-backed post retrieval contract for the branded Reddit widget; current default is Reddit RSS retrieval with selectable PullPush and public-JSON alternatives so future external/authenticated backends can swap in without changing Reddit card rendering/runtime ownership |
| Overlay widget | `widgets/reddit_widget.py` | Screensaver overlay for subreddit cards, provider-backed staged post display, progressive staged growth from cache, fixed-window fetch/cache with configured-vs-visible capacity split (`limit` remains configured capacity), transition-aware refresh/result deferral, refresh spiral interaction, visible-fallback preservation for non-authoritative empty/error fetches, cache-regenerated paint reuse, hit-target routing, performance instrumentation, Reddit-local startup policy that never expires cached posts while still attempting refresh only when updates are enabled, the blocked gate is clear, and the persisted recent-startup-attempt cooldown is clear, plus CUSTOM vertical content-fit participation that may persist committed height changes while keeping width fixed |
| Blockflip controller | `transitions/gl_compositor_blockflip_transition.py` | Block Puzzle Flip controller that now limits itself to timing plus effective shader-grid hints; the compositor shader owns the reveal path instead of CPU-side per-block `QRegion` accumulation |
| Asset guard tests | `tests/test_gmail_assets.py` | Verifies required Gmail image assets exist and normal/MC Nuitka scripts include only the notification OGG plus Qt multimedia requirements |

## Shared Shadow Path

| Module | File | Role |
|---|---|---|
| Painted frame shadows | `widgets/base_overlay_widget.py` | Settings-controlled cached painter-drawn card, text, and header shadow path for framed runtime overlay widgets, plus the shared reassertion seam that keeps saved CUSTOM rects authoritative when live content sizing tries to resize a custom-positioned overlay, the runtime min/max-size lock that lets committed CUSTOM shrink replay survive authored defaults, the narrow runtime content-height helper for descriptor-approved vertical-only CUSTOM adjustments, and the shared deferred parent-restack trigger for authored stacking after content-height changes outside CUSTOM |
| Shadow tuning | `core/settings/shadow_tuning.py` | Canonical `shadowtuning.json` defaults for card, text, header, control, icon, and Spotify volume-slider painted shadows |
| Volume slider | `widgets/spotify_volume_widget.py` | Spotify volume overlay with local canonical flush-timer reset ownership, provider retargeting, deferred Core Audio writes, low-frequency mixer-session resync hooks, painted-frame/track shadow rendering, and intentionally media-owned CUSTOM move/resize participation through an authored slider scale contract |
| Edit grid overlay | `widgets/edit_grid_overlay_widget.py` | Temporary per-display low-opacity grid overlay shown only during active CUSTOM edit sessions, above the compositor and below the temporary shells |
| Visualizer parity | `widgets/spotify_visualizer_widget.py` | Uses the shared painted-shadow contract for the visualizer card without changing GL/audio/bar rendering, supports Custom-only independent display routing while keeping exact Follow Media parity outside Custom, and now treats the committed CUSTOM rect as the visualizer's active outer-geometry authority |
| Analog clock geometry | `widgets/clock_widget.py` | Shared analogue face/card/numeral layout metrics, authored optical Roman-numeral placement map, framed outer-ring breathing-room contract, below-face timezone spacing contract, and CUSTOM runtime full-rect swap ownership between digital and analogue |

## Source Ingestion

| Module | File | Role |
|---|---|---|
| RSS coordinator | `sources/rss/coordinator.py` | Feed orchestration plus startup/download budget logic keyed to the real runtime RSS pool target instead of an unrelated fixed cache ceiling; high-quality Bing/NASA fallback only tops up real deficits |
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
| `SRPSS_DISABLE_LOGGING` / `SRPSS_DISABLE_LOGS` | Disable runtime logging |
| `SRPSS_FORCE_LOG_DIR` | Override log directory |
| `SRPSS_FORCE_SOUNDDEVICE` | Force sounddevice audio backend |

## Runtime CLI Flags

| Flag | Purpose |
|---|---|
| `--debug`, `-d` | Debug logging |
| `--verbose`, `-v` | Full verbose DEBUG/INFO stream in `screensaver_verbose.log` |
| `--perf` | Performance telemetry sidecar logs |
| `--viz` | Visualizer logging plus visualizer diagnostics sidecars |
| `--geo` | Geometry/z-order/CUSTOM-layout sidecar logs |
| `--set` | Settings mutation/import/schema sidecar logs |
| `--life` | Widget/worker/engine lifecycle sidecar logs |
| `--cache` | Image-cache/prefetch/cache-authority sidecar logs |
| `--viz-diagnostics`, `--viz-diag` | Legacy compatibility alias for extra visualizer diagnostics |
| `--fresh` | Clear all resolved runtime log files at startup |
| `-devblob` | Enable blob mode gate |
| `--devcurve` | Compatibility no-op alias |
