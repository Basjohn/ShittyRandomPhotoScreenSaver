# Architectural Stability Audit

This document is a living, actionable checklist for auditing and hardening the architectural stability of **Shitty Random Photo Screensaver**.

Each section lists concrete checks and tasks. Use `[ ]` / `[x]` boxes to track completion.

---

## 1. Settings & Configuration Wiring

- [ ] **Verify all GUI-exposed settings are wired to `SettingsManager`**
  - [ ] Each control in `ui/tabs/*.py` has a corresponding `get`/`set` key in `SettingsManager`.
  - [ ] No orphaned UI controls whose state is never saved.
  - [ ] No stale settings keys that are never read.
- [ ] **Verify persistence correctness**
  - [ ] Settings changed via GUI survive process restarts.
  - [x] Direction settings for transitions (Slide, Wipe, Diffuse) persist and match `DisplayWidget` behaviour.
    - `TransitionsTab` now stores per-transition directions inside the canonical nested `transitions` dict under `transitions['slide']['direction']` / `transitions['wipe']['direction']`. `DisplayWidget._create_transition` reads these nested values exclusively and applies non-repeating random direction logic while keeping the last chosen direction in `transitions['slide']['last_direction']` / `transitions['wipe']['last_direction']` when `random_always` is disabled.
    - Diffuse does not use a direction enum; its user-facing controls are block size and shape. These are persisted inside the canonical `transitions` dict (e.g. `transitions['diffuse']['block_size']` / `transitions['diffuse']['shape']`) and correctly consumed by `DisplayWidget` when creating `DiffuseTransition`.
  - [x] Widget settings (clock, weather, future widgets) persist and are applied on runtime creation.
    - `WidgetsTab` persists all clock and weather configuration into the nested `widgets` dict (including per-monitor selection, timezones, fonts, colors, margins, background frame/opacity, clock bg/border colors and opacities, and weather bg/border colors and opacities, plus icon toggle) and calls `SettingsManager.save()` on each change.
    - `DisplayWidget` reads the same `widgets` structure when it starts, gating each clock and the weather widget by `enabled` and `monitor` selection and then applying font, color, position, and frame settings to the created `ClockWidget`/`WeatherWidget` instances.
- [x] **Normalisation & types**
  - [x] All boolean-like values pass through `SettingsManager.to_bool` / `get_bool` or a local equivalent normalisation once.
    - UI tabs (`display_tab`, `transitions_tab`, `widgets_tab`, `sources_tab`) use `SettingsManager.get_bool` or `SettingsManager.to_bool` to normalise booleans (e.g. `display.hw_accel`, `display.refresh_sync`, `queue.shuffle`, `display.pan_and_scan`, `input.hard_exit`, `transitions.random_always`, widget `enabled` flags, weather `show_icons`).
    - Runtime paths (`DisplayWidget`, `ScreensaverEngine`, `WeatherWidget`) rely on `SettingsManager.to_bool` for settings that may be stored as strings (e.g. `display.hw_accel`, `display.refresh_sync`, `display.same_image_all_monitors`, transition randomisation flags) and only use inline string checks in a few contained cases that behave equivalently to `to_bool`.
  - [x] Nested vs legacy flat keys are either fully migrated or consciously supported in migration-only code paths.
    - Transitions: the canonical nested `transitions` dict is the only source for type/duration/easing/directions in `DisplayWidget`, `TransitionsTab`, and `ScreensaverEngine`. Legacy flat keys such as `transitions.type`, `transitions.duration_ms`, and `transitions.direction` are no longer used by the active pipeline and only remain (if at all) in quarantined or historical configs.
    - Widgets: the canonical nested `widgets` dict is the structure used by `WidgetsTab` and `DisplayWidget`. Any legacy flat `widgets.clock_*` / `widgets.weather_*` keys are treated as migration inputs on first load and are no longer written back; runtime reads and writes use the nested structure only.
    - Display / multi-monitor: `display.same_image_all_monitors` remains the canonical flag and is normalised via `SettingsManager.to_bool`. Legacy `multi_monitor.mode` is retained only for historical configs and is not used by current display selection logic.


## 2. Threading & Concurrency

- [x] Inventory all threads and background workers (QThread, Python `threading`, `ThreadManager`).
  - `ScreensaverEngine` owns a single `ThreadManager` instance that provides IO and COMPUTE pools for image loading, prefetch, and any future compute-heavy work.
  - `ImagePrefetcher` uses the shared `ThreadManager` IO pool plus a `threading.Lock` to gate its in-flight set and writes into `ImageCache`, without touching Qt widgets off the UI thread.
  - `WeatherWidget` prefers the injected `ThreadManager` IO pool for API calls and falls back to a short-lived `QThread`/`WeatherFetcher` pair only when no manager is supplied, cleaning up that thread in `stop()`.
  - No ad-hoc `threading.Thread` workers are used; timers are handled via Qt `QTimer` and `ThreadManager.single_shot`.
- [x] Ensure a central `ThreadManager` (or equivalent) owns lifetime and shutdown of worker threads.
  - Core initialization in `ScreensaverEngine._initialize_core_systems()` creates the main `ThreadManager` and passes it into `DisplayManager` / `DisplayWidget` and utilities like `ImagePrefetcher`.
  - Engine `cleanup()` calls `thread_manager.shutdown()` before `ResourceManager.cleanup_all()`, ensuring pools are drained/cancelled and futures are deregistered before Qt object teardown.
  - Transitions and overlay helpers that need delayed UI work (e.g. `overlay_manager.schedule_raise_when_ready`) rely on `ThreadManager.single_shot` / `run_on_ui_thread` rather than their own executors.
- [x] Replace ad-hoc raw `QThread` usage with centralised patterns where possible.
  - WeatherWidget now prefers the central `ThreadManager` IO pool for background fetches when created via `DisplayWidget`/`DisplayManager`; direct `QThread` usage remains only as a fallback when no `ThreadManager` is available (e.g., in isolated tests or tools).
- [x] Verify safe cross-thread signal/slot usage (no direct UI calls from worker threads).
  - `ThreadManager.run_on_ui_thread` dispatches callbacks onto the Qt UI thread via a dedicated `_UiInvoker` QObject; weather fetch callbacks and overlay polling both use this path to interact with widgets.
  - The `WeatherWidget` fallback `QThread` path uses Qt signals (`data_fetched` / `error_occurred`) to hand results back to the widget on the UI thread; the worker object itself never updates UI directly.
  - `ImagePrefetcher` callbacks only touch `ImageCache` and internal state under a lock and never manipulate QWidgets from worker threads.


## 3. Resource & Lifecycle Management

- [x] Map ownership of long-lived Qt widgets and overlays (`DisplayWidget`, compositor, overlays, widgets).
  - Ownership chain: `ScreensaverEngine``DisplayManager`  per-screen `DisplayWidget` instances. Each `DisplayWidget` owns its clock/weather widgets, renderer backend (`_renderer_backend`/`_render_surface`/`_gl_compositor`), and transition overlays, with overlays parented to the display and registered via the shared `ResourceManager`.
- [x] Confirm all dynamically created widgets/overlays are cleaned up on display close / app exit.
  - `DisplayManager.cleanup()` iterates all displays, calling `display.clear()` then `close()`/`deleteLater()`. `DisplayWidget.clear()` stops pan & scan, stops any active transition, hides all overlays, clears pixmap references, and triggers repaint; `_on_destroyed()` additionally destroys the render surface, hides/detaches the compositor, stops pan & scan, stops/cleans the active transition, hides overlays, and cancels the transition watchdog. Engine `cleanup()` then invokes `ResourceManager.cleanup_all()` to delete all registered Qt objects.
- [x] Audit image cache / pixmap lifetime to avoid leaks and double frees.
  - `ImageCache` implements a bounded LRU over `QImage`/`QPixmap` with size accounting and eviction, used by the engine for the duration of its lifetime. Per-display pixmaps live only on `DisplayWidget` (`current_pixmap`, `previous_pixmap`, `_seed_pixmap`) and are dropped in `clear()`, so cached images and widget-held pixmaps do not leak across runs or double-free.


## 4. Rendering & Transitions Pipeline

- [ ] Confirm `GLCompositorWidget` is the only GL rendering path in use (no legacy per-transition GL overlays).
- [ ] Ensure software fallback transitions (Diffuse, Block Puzzle Flip) are stable and non-blocking.
- [ ] Validate transition selection logic for random vs manual selection and hardware-accel availability.


## 5. Widgets (Clock, Weather, Future Widgets)

- [x] Clock widgets: verify creation, positioning, theming, and persistence.
  - `DisplayWidget._apply_widget_settings()` creates `ClockWidget` instances for `clock`, `clock2`, and `clock3`, gating each by `widgets.clock{N}.enabled` and `monitor` selection so they appear only on the intended screens.
  - Clock position and layout come from `widgets.clock.position` and a `ClockPosition` map, with sensible defaults per clock, and margins / font sizes applied per settings.
  - `WidgetsTab` persists clock styling into `widgets.clock` (including font family/size, text color, background frame toggle, background color/opacity, and border color/opacity); `DisplayWidget` reads these and applies them, with Clock 2/3 inheriting the main clock style for visual consistency.
- [x] Weather widget: verify cached-start behaviour, retry policy, and settings wiring (location, opacity, icons).
  - `WeatherWidget` loads a cached snapshot from `last_weather.json` and, when still valid, starts by displaying cached data immediately before scheduling background refreshes via `ThreadManager` or a fallback `QThread`.
  - On errors, the widget logs failures, uses a retry timer for backoff, and only fades in once valid data has been shown at least once to avoid flashing error states.
  - `WidgetsTab` persists weather configuration under `widgets.weather` (location, monitor, position, font, show/hide background, background color/opacity, border color/opacity, and icon toggle), and `DisplayWidget` consumes the same structure to configure the runtime `WeatherWidget`.
- [x] Confirm widgets can be individually enabled/disabled per display where applicable.
  - Clock and weather widgets are each gated by an `enabled` flag and a per-widget `monitor` selector (`ALL` or an integer index), so each overlay can be targeted to specific displays or all monitors without requiring duplicate global settings.


## 6. Error Handling, Logging & Diagnostics

- [ ] All critical paths (image loading, transitions, network fetches) log errors with enough context.
- [ ] No noisy debug logging in hot paths in production configuration.
- [ ] Watchdog or timeout paths for long transitions are well-bounded and logged.


## 7. Tests & Tooling

- [ ] Curate a minimal but strong test suite for transitions, image loading, and widget startup.
- [ ] Ensure test runners and logs are discoverable from `Docs/TestSuite.md`.


## 8. Documentation & Specs

- [ ] Keep `Spec.md` as single source of current architecture (no historical notes).
- [ ] Keep `Index.md` aligned with module reality (new modules added, dead ones pruned).


## 9. Performance, Memory & Bloat

- [ ] **Hot-path performance without fidelity loss**
  - [ ] Review rendering and transition hot paths (`DisplayWidget`, `gl_compositor`, software transitions) for avoidable allocations, redundant work, and unnecessary logging.
  - [ ] Confirm that any micro-optimisations do not reduce visual quality (no banding, tearing, or timing drift across monitors).
  - [x] Compositor transitions Crossfade/Slide/Wipe/Blinds verified in debug runs to complete within a few milliseconds of their configured `duration_ms` on both 165 Hz and 60 Hz displays, with no visible artefacts.
  - [x] CPU `BlockPuzzleFlipTransition` and `GLCompositorBlockFlipTransition` now override `get_expected_duration_ms()` to report their total two-phase timeline (`duration_ms + flip_duration_ms`), so telemetry "TIMING DRIFT" warnings are eliminated while preserving the existing visual timing; tests for both transitions pass.
- [ ] **Memory usage & leaks**
  - [x] Verified via code review and debug runs that long-lived objects (DisplayWidget, GLCompositorWidget, overlays, AnimationManagers, ThreadManager, ImageCache) are either engine-owned and cleaned up on shutdown (e.g. `ScreensaverEngine.cleanup()` calling `thread_manager.shutdown()` and clearing displays) or persistent-per-display but reused without unbounded growth (e.g. overlay widgets and GL compositor per display).
  - [x] Confirmed that `ImageCache` and weather cache are bounded with clear eviction semantics: runtime logs show cache size stabilising at 24/24 items and ~0.9–1.0 GB with regular evictions, and no evidence of unbounded memory growth over long runs.
- [ ] **Duplication & conflicting behaviour**
  - [ ] Identify duplicated logic across transitions and widgets (e.g. multiple bool normalisation helpers, legacy display_widget variants, old GL overlay paths) and consolidate on a single implementation where safe.
  - [x] Bool normalisation has been centralised on `SettingsManager.to_bool` / `get_bool` and remaining ad-hoc helpers removed from production code; legacy helpers only remain in quarantined/temporary modules.
  - [x] Identified `temp/display_widget_prev.py` as a legacy DisplayWidget implementation retained only as a reference; the active pipeline uses `rendering.display_widget.DisplayWidget` and the GL compositor path. The temp file is effectively quarantined and not referenced by the engine.
  - [x] Confirmed that software transitions and their GL-compositor counterparts intentionally share behaviour (e.g. BlockPuzzleFlip SW vs GLCompositorBlockFlip) but are wired through different rendering paths; these are documented as parallel implementations rather than accidental duplication.
  - [ ] Remove or explicitly quarantine any remaining dead code paths (legacy per-transition GL overlays / temp files) that are no longer exercised by the current pipeline once GL compositor coverage is complete.
- [ ] **Bloat & configuration hygiene**
  - [ ] Audit settings keys for obsolete flags and modes that are not used by the current engine (e.g. legacy `multi_monitor.mode`, old transition keys) and either migrate or deprecate them explicitly.
  - [x] Confirmed that nested settings keys are the primary source of truth (e.g. `transitions.slide.direction`, `widgets.clock.*`), with legacy flat keys still read for backwards compatibility. The engine now prefers nested keys and only falls back to old keys when necessary.
  - [ ] Catalogue remaining legacy settings keys (e.g. older transition flags, `multi_monitor.mode`) and mark them as deprecated in `Spec.md` once usage has been removed from production code.
  - [ ] Confirm that logging in production builds is concise and avoids excessively verbose diagnostics in steady state (current `--debug` runs are intentionally noisy for audit).


---

> This document should be updated as architecture evolves. When implementing changes prompted by this audit, reference the relevant checklist items and mark them as completed.
