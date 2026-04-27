# Index

Last updated: 2026-04-23

Living map of the current SRPSS codebase.

## Core Documents

| File | Purpose |
|---|---|
| `Spec.md` | Canonical architecture contract |
| `Current_Plan.md` | Active short-term work and validation |
| `Docs/Guardrails.md` | Engineering rules and anti-regression policy |
| `Docs/Historical_Bugs.md` | Dated bug timeline and postmortems |
| `Docs/Defaults_Guide.md` | Defaults and reset contracts |
| `Docs/TestSuite.md` | Test strategy and execution guidance |
| `Docs/Visualizer_Reference.md` | Visualizer architecture and contracts |
| `Docs/Visualizer_Change_Checklist.md` | Required sweep for visualizer changes |

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
| ProcessSupervisor | `core/process/supervisor.py` |

## Settings and Persistence

| Module | File | Role |
|---|---|---|
| Canonical defaults | `core/settings/default_settings.py` | Source of default values |
| Defaults API | `core/settings/defaults.py` | Default loading + preserve-on-reset contract |
| Settings store | `core/settings/json_store.py` | Atomic JSON persistence |
| Settings manager | `core/settings/settings_manager.py` | Dotted API over structured roots |
| Snapshot normalization | `core/settings/visualizer_settings_snapshot.py` | Canonical visualizer mapping normalization |
| Baseline/fallback contract | `core/settings/visualizer_settings_contract.py` | Shared fallback resolution for visualizer settings |
| Preset index contract | `core/settings/visualizer_preset_indices.py` | Shared preset index fallback/lookup |

## Visualizer System

| Module | File | Role |
|---|---|---|
| Mode registry | `core/settings/visualizer_mode_registry.py` | Mode ids, labels, key prefixes, slider ownership |
| Preset manager | `core/settings/visualizer_presets.py` | Curated/custom loading + apply |
| Preset repair tool | `tools/visualizer_preset_repair.py` | Audit/repair/reindex curated preset payloads |
| Widget runtime | `widgets/spotify_visualizer_widget.py` | Runtime visualizer coordinator |
| Overlay transport | `widgets/spotify_bars_gl_overlay.py` | GL state transport and render-state storage |
| Config application | `widgets/spotify_visualizer/config_applier.py` | Settings/model to runtime kwargs mapping |
| Startup contract | `widgets/spotify_visualizer/startup_contract.py` | Staged startup state contract |

## Rendering System

| Module | File | Role |
|---|---|---|
| Display presenter | `rendering/display_widget.py` | Fullscreen presenter per display |
| Widget lifecycle | `rendering/widget_manager.py` | Overlay widget lifecycle/fades/sync |
| Startup policy | `rendering/overlay_startup_policy.py` | Primary and secondary startup timing |
| Input routing | `rendering/input_handler.py` | Keyboard/mouse/media/control routing |
| GL compositor | `rendering/gl_compositor.py` | GL transition/composition surface |

## Gmail Integration

| Module | File | Role |
|---|---|---|
| OAuth manager | `core/gmail/gmail_oauth.py` | OAuth 2.0 PKCE flow, token storage (DPAPI) |
| REST API client | `core/gmail/gmail_client.py` | Gmail REST API — metadata, labels, actions |
| IMAP client | `core/gmail/gmail_imap.py` | IMAP + App Password — headers, unread count |
| Unified backend | `core/gmail/gmail_backend.py` | Routes to OAuth/REST or IMAP based on config |
| Settings UI | `ui/tabs/widgets_tab_gmail.py` | Backend selector, credentials, widget settings |
| Overlay widget | `widgets/gmail_widget.py` | Screensaver overlay — email list, actions |

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
| `--devgmail` | Enable Gmail widget gate |
