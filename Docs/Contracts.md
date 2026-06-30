# Contracts

Last updated: 2026-06-29

Short contract index for SRPSS.

This document is not a second `Spec.md`. Its job is to answer:
- what contract family am I touching?
- where is the canonical owner?
- what nearby files usually participate?

Use this as a fast routing layer, then open the owning files and `Spec.md` for the deeper rules.

## How To Use This

1. Identify the behavior family you are changing or debugging.
2. Start with the canonical owner in the table below.
3. Read the listed related files only after the owner is clear.
4. Treat `Spec.md` as the final architecture contract and `Index.md` as the live module map.

## Core Ownership Contracts

| Contract Family | Canonical Owner | Related Files | Goal |
|---|---|---|---|
| Threading / async task ownership | `core/threading/manager.py` | `engine/*`, widget runtime helpers | One authoritative task submission/cancel/shutdown seam. |
| Qt resource lifecycle | `core/resources/manager.py` | widgets, rendering, displays | One authoritative GUI/resource cleanup seam. |
| Settings read/write/migration | `core/settings/settings_manager.py` | `core/settings/defaults.py`, `core/settings/default_settings.py`, `core/settings/json_store.py` | One persistence API and one schema-normalization path. |
| Shared runtime animation ownership | `core/animation/animator.py` | widget fade helpers, render timing, perf parser | Shared timeline/tick animation without shadow managers; perf output must identify owner and peak active/listener counts. |
| Event publish/subscribe | `core/events/event_system.py` | engine, runtime glue | One cross-module signaling seam. |
| Worker process orchestration | `core/process/supervisor.py` | image pipeline, helper bridges | One worker lifecycle and response-correlation seam. |

## Registry And Metadata Contracts

| Contract Family | Canonical Owner | Related Files | Goal |
|---|---|---|---|
| Widget family identity / settings section metadata | `rendering/widget_descriptors.py` | `rendering/widget_setup_all.py`, `ui/tabs/widgets_tab.py`, `ui/tabs/widgets_tab_defaults.py` | One descriptor truth for factory-backed widgets and standard settings sections. |
| Transition identity / aliases / startup warmup metadata | `rendering/transition_registry.py` | `rendering/transition_factory.py`, `ui/tabs/transitions_tab.py`, compositor helpers | One transition registry instead of duplicated lists. |
| Visualizer mode identity / labels | `core/settings/visualizer_mode_registry.py` | presets, settings UI, widget runtime | Stable internal ids with canonical labels and prefixes. |
| Visualizer preset activation payload | `core/settings/visualizer_presets.py` | `widgets/spotify_visualizer/activation_runtime.py`, settings UI | One resolved mode/preset payload for every activation path. |
| CUSTOM layout normalized storage contract | `rendering/custom_layout_contract.py` | `rendering/custom_layout_manager.py`, `widgets/edit_shell_widget.py` | One display-local persistence and clamp/snap contract. |

## Settings Contracts

| Contract Family | Canonical Owner | Related Files | Goal |
|---|---|---|---|
| Canonical defaults | `core/settings/default_settings.py` | `core/settings/defaults.py` | One source of default truth. |
| Preserve-on-reset / default loading | `core/settings/defaults.py` | settings reset/import flows | One preservation contract for resets/imports. |
| Widgets-map normalization / schema ownership | `core/settings/settings_manager.py` | SST import, `set_widgets_map`, root `widgets` writes | Prevent drift between settings write paths. |
| Silent widgets-map repair writes | `core/settings/settings_manager.py` | `set_widgets_map(..., emit_change=False)`, CUSTOM/runtime repair paths | Only owner-local repair/rebuild paths may suppress `settings_changed`; the write must still sync, normalize, and invalidate dotted caches while the caller refreshes runtime state explicitly. |
| Visualizer settings grouped model | `core/settings/models/_spotify_visualizer.py` | snapshot/serializer/build callers | One ordered grouped field-spec contract for visualizer persistence. |
| Visualizer normalization / legacy migration | `core/settings/visualizer_settings_snapshot.py`, `core/settings/visualizer_settings_contract.py` | preset import/runtime apply | One mapping-normalization seam and one technical migration seam. |
| Shared list-widget capacity policy | `core/settings/widget_capacity_policy.py` | Gmail/Reddit settings + runtime | One active visible-capacity/growth envelope for list widgets. |

## Rendering And Display Contracts

| Contract Family | Canonical Owner | Related Files | Goal |
|---|---|---|---|
| Fullscreen display presenter | `rendering/display_widget.py` | `engine/display_manager.py`, GL init helpers | One screen-owned runtime presenter. |
| Display startup / rebuild orchestration | `engine/display_manager.py` | `rendering/display_setup.py`, `rendering/widget_setup_all.py` | Register the full active display set before first show, preserve staggered GL startup through owned scheduling, and suppress stale delayed shows after cleanup. |
| Display setup / startup glue | `rendering/display_setup.py` | `rendering/widget_setup_all.py`, `rendering/display_gl_init.py` | One display bootstrap flow after display ownership is established. |
| Overlay widget lifecycle / fade sync / runtime pause prep | `rendering/widget_manager.py` | `rendering/widget_setup_all.py`, `rendering/widget_stacking.py` | One overlay lifecycle and reveal coordination seam. |
| Authored stacking planner | `rendering/widget_stacking.py` | `rendering/widget_manager.py`, settings preview composition | One non-`Custom` stacking calculation seam. |
| Centralized overlay positioning | `rendering/widget_positioner.py` | overlay widgets | One anchor/margin positioning contract. |
| Centralized input routing | `rendering/input_handler.py` | media, Reddit/Gmail click handlers | One keyboard/mouse/URL routing seam. |
| Renderer backend selection / surface init | `rendering/backends/__init__.py`, `rendering/display_gl_init.py` | `rendering/display_widget.py` | One backend selection + render-surface contract with visible fallback reporting. |

## Performance And Cadence Contracts

| Contract Family | Canonical Owner | Related Files | Goal |
|---|---|---|---|
| Transition paint progress authority | `core/animation/frame_interpolator.py` | `rendering/gl_compositor_pkg/paint.py`, transition controllers | Paint reads use elapsed-time/easing state so visible shader progress is not capped by stale `AnimationManager` callback samples. |
| Transition start / render wake authority | `rendering/gl_compositor.py` | `core/animation/animator.py`, compositor metrics | Render strategy and transition metrics begin at transition start, not from the first animation callback. |
| Transition/display perf health bar | `tools/transition_perf_health_parser.py` | `core/animation/animator.py`, compositor metrics, sidecar logs | Keep paired render/paint starvation, `GL ANIM` vs `GL PAINT`, fallback usage, texture uploads, visualizer latency, and owner/peak-count animation evidence loud. |
| No UI-pressure cadence fixes | `Docs/Guardrails.md` | adaptive timers, display rebuild, settings entry | Do not fix missed paints or low FPS by queueing extra UI work; prove ownership/timing/cache/upload root cause first. |

## CUSTOM Layout Contracts

| Contract Family | Canonical Owner | Related Files | Goal |
|---|---|---|---|
| CUSTOM session orchestration | `rendering/custom_layout_manager.py` | `rendering/custom_layout_contract.py`, `widgets/edit_shell_widget.py`, display rebuild hooks | One edit-session/save/replay/reload seam across active displays. |
| Temporary edit shell behavior | `widgets/edit_shell_widget.py` | custom layout manager | One shell-only drag/resize/reset UI, not live widget truth. |
| Saved custom rect authority reassertion | `widgets/base_overlay_widget.py` | widget subclasses, custom layout manager | Prevent live content sizing from overriding committed custom rects, except for descriptor-approved vertical-only CUSTOM height adjustments that persist back through the shared layout seam while width stays authoritative. |
| Visualizer CUSTOM outer-card authority | `widgets/spotify_visualizer/card_geometry.py`, `widgets/spotify_visualizer_widget.py` | custom layout manager, widget creators | Keep visualizer custom rect authority separate from mode/preset preferred geometry. |
| Clock CUSTOM mode-swap rect ownership | `widgets/clock_widget.py` | custom layout persistence, tests | Digital/analog swaps rebuild and persist the full custom rect, not just inner scaling. |

## Visualizer Contracts

| Contract Family | Canonical Owner | Related Files | Goal |
|---|---|---|---|
| Runtime coordinator | `widgets/spotify_visualizer_widget.py` | activation/config/runtime helpers | One owner for mode activation, render lifecycle, and runtime state handoff. |
| Visualizer tick cadence | `widgets/spotify_visualizer/tick_helpers.py` | `core/animation/animator.py`, transition controllers | Dedicated recurring timer owns visualizer ticks; transition `AnimationManager` instances must not run visualizer `_on_tick()` listeners. |
| Activation / mode switch runtime contract | `widgets/spotify_visualizer/activation_runtime.py` | `mode_transition.py`, preset manager | One resolved-activation path for startup, settings refresh, and hot switches. |
| Technical config caching / replay | `widgets/spotify_visualizer/technical_config.py`, `runtime_config.py` | beat engine, widget runtime | One authoritative runtime technical-config replay seam. |
| Shared beat/audio engine | `widgets/spotify_visualizer/beat_engine.py` | bubble feed, capture lifecycle, idle seed | One capture/floor/reactivity engine shared across modes. |
| Bubble simulation contract | `widgets/spotify_visualizer/bubble_simulation.py` | beat engine, runtime dispatch | One Bubble render-motion owner with isolated loud/soft behavior. |
| Overlay render shell | `widgets/spotify_bars_gl_overlay.py`, `widgets/spotify_visualizer/overlay_frame_shell.py` | overlay mask/state/uniforms | One GL shell for transport, masking, and draw sequencing. |
| Visualizer outer card geometry | `widgets/spotify_visualizer/card_geometry.py` | widget runtime, custom layout | One owner for outer card height/width policy. |
| Display-only Spectrum smoothing | `widgets/spotify_visualizer/spectrum_solid_hysteresis.py` | Spectrum renderer/widget runtime | One visual-only solid-bar smoothing seam. |

## Service-Backed Widget Contracts

| Contract Family | Canonical Owner | Related Files | Goal |
|---|---|---|---|
| Shared service-widget lifecycle mechanics | `widgets/service_widget_runtime.py` | Gmail, Reddit, Weather | One place for transition-aware refresh deferral, visible fallback preservation, and timer ownership. |
| Gmail backend routing | `core/gmail/gmail_backend.py` | OAuth, IMAP, REST, widget | One backend-selection seam for Gmail data/actions. |
| Reddit post-source provider seam | `core/reddit_post_provider.py` | `widgets/reddit_widget.py`, widget factory, future external/authenticated feed backends | One explicit post-retrieval contract for the branded Reddit widget, with family-shared provider selection, PullPush/public-JSON/RSS provider support, and no movement of card/runtime ownership out of the widget. |
| Gmail overlay rendering / runtime behavior | `widgets/gmail_widget.py` | `widgets/gmail_components.py`, settings tab | One Gmail card/runtime contract, including width-fixed CUSTOM vertical content-fit participation for descriptor-approved height persistence. |
| Reddit overlay rendering / runtime behavior | `widgets/reddit_widget.py` | service-widget runtime, helper bridge | One Reddit card/runtime contract, including Reddit-local cache reuse/startup refresh policy plus width-fixed CUSTOM vertical content-fit participation for descriptor-approved height persistence. |
| Weather overlay rendering / runtime behavior | `widgets/weather_widget.py` | weather cache/runtime helpers | One Weather card/runtime contract. |

## Media And Dependent Widget Contracts

| Contract Family | Canonical Owner | Related Files | Goal |
|---|---|---|---|
| Media widget runtime / provider behavior | `widgets/media_widget.py` | controllers, painting, widget manager | One media card owner for text/layout/provider state. |
| Mute button dependent behavior | `widgets/mute_button_widget.py` | media widget, widget manager | One dependent mute-button anchor/reveal contract. |
| Spotify volume dependent behavior | `widgets/spotify_volume_widget.py` | media widget, custom layout manager | One dependent volume-slider anchor/resize contract. |
| Spotify widget creation ordering | `rendering/spotify_widget_creators.py` | widget setup all, widget manager | One creator seam for media-owned dependents and visualizer setup. |

## Logging And Diagnostics Contracts

| Contract Family | Canonical Owner | Related Files | Goal |
|---|---|---|---|
| Logging setup / sidecar routing | `core/logging/logger.py` | `Docs/Logging_Guide.md` | One CLI-first logging family contract. |
| Operator logging workflow | `Docs/Logging_Guide.md` | logger setup, runtime flags | One map for where diagnostics should go. |
| Fallback warning policy | `core/logging/logger.py`, `Docs/Guardrails.md` | runtime call sites | Fallbacks stay loud at `WARNING+` and carry family tags when possible. |

## Security / External Routing Contracts

| Contract Family | Canonical Owner | Related Files | Goal |
|---|---|---|---|
| Secure URL launch bridge | `core/windows/secure_url_launcher.py` | helper/task routes | One secure-desktop URL-launch seam. |
| Browser foreground preference | `core/windows/browser_window_routing.py` | Gmail/Reddit/helper callers | One narrow browser targeting/ranking seam. |
| DPAPI credential storage | `core/windows/dpapi.py` | Gmail auth/token storage | One credential encryption/decryption seam. |

## Build / Runtime Variant Contracts

| Contract Family | Canonical Owner | Related Files | Goal |
|---|---|---|---|
| SCR bootstrap | `main.py` | logger, engine startup, packaged runtime | One normal screensaver entry path. |
| MC bootstrap | `main_mc.py` | MC settings/runtime policy | One media-center entry path. |
| Canonical settings/storage paths | `core/settings/storage_paths.py` | settings manager, caches, runtime data | One filesystem location contract. |

## Deep-Dive References

- `Spec.md`: full architecture/behavior contract.
- `Index.md`: live module map.
- `Docs/Guardrails.md`: anti-regression rules.
- `Docs/Historical_Bugs.md`: dated failure shapes and lessons.
- `Docs/Logging_Guide.md`: logging-family workflow.
- `Docs/10_WIDGET_GUIDELINES.md`: widget creation and settings integration.
