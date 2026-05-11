# Current Plan

Last updated: 2026-05-11

This file tracks active work only. Completed implementation details belong in `Docs/Historical_Bugs.md` or the relevant reference docs, not here.

## Guardrails
- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, and `Docs/Historical_Bugs.md`.
- Keep harnesses/probes intact unless explicitly asked to retire them.
- Treat `presets/visualizer_modes/` as authored content. Tests may validate schema/index/repair behavior, but must not force exact preset names, slots, or creative numeric values.
- Do not close visual/runtime bugs from tests alone when symptoms are user-visible.
- Avoid broad focus, window-flag, compositor, widget-shadow, visualizer, or Qt effect rewrites unless the current task directly requires them.

## Active Tasks

### 1. Module Size Refactors (2026-05-11) — IN PROGRESS

#### 1a. Split `core/settings/models.py` → `core/settings/models/` package ✅ DONE
- `_enums.py` — DisplayMode, TransitionType, WidgetPosition
- `_core.py` — Display, Transition, Input, Cache, Source, Shadow, Clock settings
- `_visualizer_helpers.py` — per-mode constants and coercion helpers
- `_spotify_visualizer.py` — SpotifyVisualizerSettings (1624 lines, standalone)
- `_widget_settings.py` — Weather, Reddit, Media, Accessibility settings
- `_app.py` — AppSettings container
- `__init__.py` — re-exports all public names (backward compat verified, 171 tests pass)

#### 1b. Extract from `spotify_visualizer_widget.py` (2958 → 2159) ✅ DONE
Five extraction passes completed — each a pure structural move with thin forwarder left behind:

| Pass | Cluster | Target file | Lines: before→after |
|---|---|---|---|
| 1 | Startup staging + lifecycle hooks | `spotify_visualizer/startup_staging.py` | 2958→2681 (−277) |
| 2 | Painted-frame-shadow + card paint | `spotify_visualizer/card_paint.py` | 2681→2564 (−117) |
| 3 | Media state, anchor, overlay teardown | `spotify_visualizer/media_bridge.py` | 2564→2350 (−214) |
| 4 | Engine reset, fallback, wake, gen tracking | `spotify_visualizer/engine_lifecycle.py` | 2350→2242 (−108) |
| 5 | `_replay_engine_config` → `config_applier.py` | — | 2242→2159 (−83) |

Total reduction: **2958 → 2159 (−799 lines, −27%)**. All 155 tests pass. Index.md updated.

### 2. Completed Audit Items (2026-05-11)
- ✅ D-01: Removed stale archive comment in `widget_manager.py`
- ✅ D-05: Removed always-true `is_devcurve_enabled()` gate
- ✅ D-06: Removed dead `force_gate(devcurve=...)` parameter
- ✅ V-08/A-08: Moved `_exchange_code` off UI thread via ThreadManager
- ✅ V-01: Registered gmail_widget.py QTimers with ResourceManager
- ✅ A-03: Registered feedback.py shared QTimer with ResourceManager
- ✅ D-02: Deleted `core/presets.py` shim (zero callers)
- ✅ V-02, A-04, A-05, A-06: Reddit/weather/spotify_volume/widget_manager timers verified already registered

### 3. Gmail Thread Grouping
Status: Not active. Design contract needed before implementation.

## Watchlist
- Mute button fade-in reliability under startup event pressure.
- Transition random mode actual distribution vs expected uniform over long runtime.
- Settings destructive-flow checks: reset/import when touching settings architecture.
- Settings cache stale-read behavior after section/root writes.

## Deferred / Not Active
- Gmail IMAP Archive remains hidden unless a source-backed finding or small diagnostic harness proves a reliable accepted command.
- Shared “open Gmail/Reddit links on monitor index 0” work remains optional stretch work and is not active.
- Visualizer technical-ownership migration, activation-payload unification, preset/runtime bleed cleanup, and painted-card clipping work are complete and should stay documented in `Spec.md`, `Index.md`, and `Docs/Historical_Bugs.md`, not carried here as active tasks.
- `card_height.py` centralization is not active work. Revisit only if a focused sizing bug justifies it.
- Reassessing residual opacity-effect invalidation is not active work. Revisit only if a concrete shadow/effect corruption issue resurfaces.

## Documentation Rule
- Architecture: `Spec.md`
- Module map: `Index.md`
- Policy: `Docs/Guardrails.md`
- Dated regressions: `Docs/Historical_Bugs.md`
- Drift-check routine: `Docs/Documentation_Maintenance.md`
- Harness reference: `Docs/Harness_Index.md`
