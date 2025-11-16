# Route 3 – OpenGL & Platform Stability Master Checklist

This document is now the single source of truth for all known stability gaps, regressions, audits, remediation tasks, and verification steps across the rendering pipeline, UI, threading, diagnostics, and supporting systems. Every section is actionable and must remain up to date after each change.

## 0. Governance & Audits
- [x] **Audit Sync** – `audits/AUDIT_OpenGL_Stability.md` now mirrors roadmap items (swap downgrades, transition skips, cache issues) and will be updated alongside each checklist change.
- [x] **Spec Tracking** – `Spec.md` now documents random cache clearing, overlay lifecycle, diagnostics telemetry, and banding mitigation per roadmap.
- [x] **Index Refresh** – `Index.md` now covers overlay telemetry/watchdogs, persistence helpers, and the Route3/FlashFlicker docs.
- [x] **Regressions Ledger** – `Docs/FlashFlickerDiagnostic.md` now records 2025-11-14 anomalies (swap downgrade, transition skips, cache persistence, etc.) with roadmap crosslinks.

### 0.1 Baseline Evidence Capture (historical)
- [x] 2025-11-14 baseline logs and flicker traces captured; see `Docs/FlashFlickerDiagnostic.md` and archived `screensaver.log` for details.

## 1. Deep Architectural Audit & Core Stability (Priority: High)

### 1.1 Architectural audit
- [ ] Perform a full architectural audit across engine, rendering, transitions, widgets, and core modules to identify conflicts, duplication, and violations of centralization (threading, resources, settings, logging, telemetry).
- [ ] Validate safe lock-free threading usage via the central ThreadManager (task submission, timers, and callbacks), ensuring no ad-hoc threads or unsafe shared-state mutations remain.
- [ ] Review all long-lived objects (DisplayWidgets, compositor, widgets, ResourceManager registrations, caches) for potential memory leaks, reference cycles, or missed cleanup paths.
- [ ] Analyze race conditions and edge cases in lifecycle flows (startup, settings reload, monitor hotplug, exit, error recovery) and document any remaining risks with mitigation tasks.
- [ ] Consolidate and document framework-level patterns (central managers, telemetry helpers, theming, DPI handling) so future features (Spotify widget, analogue clocks, shadows) plug into the same architecture without new fragmentation.

### 1.2 Software transition watchdogs & artifacts
- [ ] Investigate and fix repeated watchdog timeouts and stalled visuals in software Diffuse and Block Puzzle Flip transitions.
- [ ] Ensure `DisplayWidget._on_transition_watchdog_timeout` does not attempt `self._current_transition.cleanup()` after the transition has already set `_current_transition` to `None`.
- [ ] Add targeted tests for CPU Diffuse and Block Puzzle Flip transitions under the software backend, verifying no watchdog timeouts, no repeated flashing of stalled images, and correct cleanup of labels/overlays.

## 2. Rendering & Transition Reliability (Historical baseline)
### 2.1 Transition selection & execution
- [x] Random/manual transition selection, C-key cycling, and `DisplayWidget._create_transition` keep settings, random cache, and telemetry in sync.

### 2.2 GL/overlay lifecycle (historical)
- [x] GL overlay-era issues (buffer downgrades, warmup cost, overlay watchdogs, readiness telemetry, exit flow) were audited and fixed before the compositor pipeline. Legacy per-transition GL overlays are now removed; this section is kept only as historical context.

### 2.3 Pixmap seeding, banding & fullscreen behaviour
- [x] Post-settings banding fixed via `DisplayWidget.reset_after_settings()` / `DisplayManager.show_all()`.
- [x] First-frame handling and wallpaper snapshot seeding prevent initial black frames.
- [x] Borderless-fullscreen compatibility mode for QOpenGLWidget eliminates secondary-monitor banding and first-transition black flashes.

## 3. Multi-Monitor Consistency
- [x] Screen-specific refresh rates (165 Hz vs 60 Hz) handled without drift between displays. *(DisplayWidget logs `Detected refresh rate: 165 Hz, target animation FPS: 165` for screen 0 and `60 Hz` / `FPS: 60` for screen 1; subsequent Diffuse and GL BlockFlip transitions instantiate per-screen AnimationManagers at those FPS values with smooth, independent animation.)*
- [x] Warmup compositor runs per screen; ensure swap downgrades tracked individually. *(GL prewarm now ensures that a single `GLCompositorWidget` exists per screen; for each screen the logs report swap behaviour (e.g. `SwapBehavior.DoubleBuffer`, interval) as part of compositor initialization, confirming per-screen swap downgrade tracking without per-transition GL overlay widgets.)*
- [x] Weather widget enablement respects per-monitor config (screen 1 disabled). Verify no stray network calls when disabled. *(DisplayWidget._setup_widgets now strictly gates WeatherWidget creation per monitor; invalid monitor selectors gate off with a DEBUG note.)*
- [x] Pan & scan state reset per screen; no leaked timers after exit. *(PanAndScan.stop/enable now idempotent; stop logs only when timer/label state changes, and other logs only fire while pan & scan is enabled.)*
- [x] Exit flow (mouse movement) cleans resources and overlays deterministically on all displays. *(Mouse-move exit triggers `ScreensaverEngine.stop()`, which clears all displays, runs `DisplayManager.cleanup()` (now calling `display.clear()` before close/delete), and then stops the engine; subsequent exit events log `Engine not running` without errors, indicating idempotent teardown across displays.)*

## 4. Settings & Persistence
- [x] Flat settings keys (e.g., `transitions.type`) kept in sync with nested dict for legacy readers. *(TransitionsTab and `_on_cycle_transition` now update both the nested `transitions` dict and flat keys like `transitions.type`/`transitions.random_always`, keeping legacy readers in sync.)*
- [x] SettingsManager change notifications carry old/new values in logs for audit trails. *(SettingsManager.set now logs `Setting changed: <key>: <old> -> <new>` at DEBUG; future runs will show both values for keys such as `transitions`, `transitions.type`, and others, improving auditability.)*
- [x] Random transition cache cleared whenever manual type is chosen or random toggle disabled. *(TransitionsTab clears `transitions.random_choice`/`last_random_choice` when `random_always` is off, and `ScreensaverEngine._on_cycle_transition` removes the same keys whenever the user cycles transitions via the C-key, as seen in recent debug logs.)*
- [ ] Settings dialog writes validated via automated tests (Ruff lint + pytest) for new keys/limits.
- [x] Ensure boolean normalization (string vs bool) applied consistently (`random_always`, `hw_accel`, etc.). *(`display.hw_accel` and `transitions.random_always` are now always interpreted via `SettingsManager.to_bool`/`get_bool` in DisplayWidget, ScreensaverEngine, and TransitionsTab.)*

### 4.1 Widgets Persistence & Migration (Priority: High)
- [x] Align `ui/tabs/widgets_tab.py` persistence with the `Spec.md` `widgets` schema for `clock`, `clock2`, `clock3`, and `weather`, ensuring monitor, format, timezone, font size, margin, color, and position are written/read via the nested `widgets` dict used by `DisplayWidget._setup_widgets`.
- [x] Implement a one-time migration from legacy flat `widgets.clock.*` keys into the nested `widgets` dict on load, then persist the normalized structure back to settings (keeping legacy keys for backward compatibility if needed).
- [ ] Add a regression test or manual checklist confirming that changes made in the Widgets tab persist across restarts and are reflected correctly in all clocks and the weather widget on each monitor.

### 4.2 Ctrl-Based Temporary Interaction Mode (Priority: Medium)
- [x] Implement a Ctrl-held temporary interaction mode in `DisplayWidget` where mouse movement and left-clicks do **not** exit the screensaver while Ctrl is held; only ESC/Q and hotkeys continue to exit.
- [x] Ensure that, while Ctrl is held, mouse events are delivered to child widgets (clocks, weather, future Spotify/media widget) without toggling `input.hard_exit` in settings, allowing safe, non-persistent interaction.
- [ ] Add targeted tests or a manual checklist verifying Ctrl-held behaviour across displays and widget combinations (no accidental exit, no stuck non-exit state when Ctrl is released).
- [ ] Ensure local and global media keys (play/pause/next/prev/volume) do not cause the screensaver to exit; they should only control media when allowed by the interaction mode and never act as exit keys.

## 5. Diagnostics & Telemetry
- [x] Overlay telemetry includes swap behavior, gl readiness, forced software fallback counts. *(Centralized via `core/logging/overlay_telemetry.record_overlay_ready`, which records swap behaviour, GL readiness stages, and forced-ready software fallbacks per overlay.)*
- [x] Startup logs trimmed of redundant detail while retaining actionable insights. *(Pycache cleanup now logs a single summary line instead of per-directory spam; high-level startup logs (GL format, queue stats, engine initialization) are preserved for diagnostics.)*
- [x] Add structured log events for: cache hits/misses, transition skip due to in-progress, watchdog triggers. *(ImageCache logs `Cache miss:`/`Cache hit:` with paths, DisplayWidget logs `Transition in progress - skipping image request (skip_count=...)`, and watchdogs log `[WATCHDOG] Started` (with transition, overlay, timeout) and completion, providing consistent, grep-friendly markers.)*
- [x] Shorten high-traffic logger names for core resources and GL transitions to concise identifiers (e.g., `resources.manager`, `transitions.gl_xfade`, `transitions.gl_blinds`) to improve readability in the aligned log columns. *(Implemented via `core.logging.logger.get_logger` short-name overrides so modules like `core.resources.manager` and GL transitions log under concise aliases.)*
- [x] Reduce verbosity of `[DIAG] Overlay readiness` logs by aggregating repeated counts per overlay type and suppressing redundant per-frame details while keeping key stage transitions and forced-ready events. *(`record_overlay_ready` now aggregates per overlay/stage and only emits a detailed `[DIAG]` line on first occurrence, with counts retained in `DisplayWidget._overlay_stage_counts`.)*
- [x] Log rotation ensures heavy debug sessions do not overwhelm disk (configure size/time-based rotation). *(Implemented via `RotatingFileHandler` in `core/logging/logger.setup_logging` with 10MB max per file and 5 backups.)*
- [ ] Document reproduction recipes for major issues (banding, stuck transition, swap downgrade) in `FlashFlickerDiagnostic.md`.

## 6. Performance & Resource Management
- [x] AnimationManager timers cleaned post-transition; confirm no `Animation cancelled` flood from expected flow. *(Animations are driven exclusively via `AnimationManager`; transitions call cancel/cleanup on completion or watchdog timeout, and `Animation cancelled` remains a DEBUG-only diagnostic emitted when an animation is intentionally torn down. No warnings or errors are produced from normal transition flow.)*
- [x] ResourceManager lifecycle audited to prevent duplicate initialization per image cycle. *(ScreensaverEngine now owns a single ResourceManager instance shared with DisplayManager, each DisplayWidget, Pan & Scan, transitions, and per-widget AnimationManagers; persistent overlays are created via `overlay_manager.get_or_create_overlay` and registered with this shared manager.)*
- [ ] Image cache sizing (24 items / 1GB) profiled against actual usage; adjust thresholds and logging.
- [ ] Prefetch queue respects in-flight transition skip policy; evaluate whether skip frequency hurts pacing.
- [ ] Software renderer improvements merged and performance profiled for fallback parity.
- [ ] GL compositor Slide smoothness and performance:
  - [ ] Investigate Slide smoothness on mixed-refresh setups (165 Hz + 60 Hz), ensuring that `GLCompositorSlideTransition` feels as smooth as or smoother than the legacy GL Slide on both displays.
  - [ ] Profile per-frame timing for compositor-driven Slide at both refresh rates and verify that AnimationManager step sizes and easing curves (`EasingCurve`) produce visually consistent motion without micro-jitter.
  - [ ] Experiment with small adjustments to easing, durations, and integer pixel snapping in the compositor slide path (without regressing Crossfade) and document chosen defaults in `Spec.md`.

## 7. Testing & Tooling
- [ ] Audit entire test suite and test script for accuracy to current architecture and test coverage. Add findings of audit to this section of this document as a live checklist and implement findings.
- [ ] Add GL stress tests to `scripts/run_tests.py` and document usage in `Docs/TestSuite.md`.
- [ ] Create reproducible test scenario for transition cycling + manual overrides (ensures no BlockFlip lock-in).
- [ ] Multi-monitor UI tests (clock/weather positions, enable/disable) automated or scripted manual checklist.
- [ ] Regression suite for random transition caching covering hardware on/off permutations.
- [ ] Add log parsing script to summarize overlay warnings per run for rapid triage.

## 8. Historical Debug Anomalies (2025-11-14)
- [ ] Weather widget network failures: handle geocoding/network errors with backoff and last-known-data fallback (see `Docs/FlashFlickerDiagnostic.md`).

## 9. Roadmap Milestones
- [x] **Milestone A:** GL compositor pipeline in place for Crossfade and Slide on all hw-accelerated displays, with no black-frame or underlay flicker, verified by automated tests and diagnostic logs (including multi-monitor, mixed-refresh scenarios).
- [x] **Milestone B:** Remaining GL transitions (Wipe, Block Puzzle Flip, Blinds, Diffuse) have compositor controllers and tests; legacy per-transition GL overlay widgets have been removed so runtime now uses only compositor-backed or software transitions.
- [ ] **Milestone C:** Post-settings and non-GL banding eliminated on all monitors; reproduction recipes recorded and guarded by tests (including software-backend scenarios).
- [ ] **Milestone D:** Software transitions (Diffuse, Block Puzzle Flip) run to completion without watchdog timeouts or stalls under the software backend, with coverage tests in place.
- [ ] **Milestone E:** Full GL and GLSL diagnostics suite automated (scripts + docs updated).

## 10. References & Supporting Docs
- `Docs/FlashFlickerDiagnostic.md`
- `Docs/TestSuite.md`
- `audits/AUDIT_OpenGL_Stability.md`

- `scripts/run_tests.py`

## 11. Widgets, Input & GL Startup (New tasks 2025-11-15)

### 11.1 Spotify / Media Playback Widget (Priority: Low)
- [ ] Implement a Spotify/media widget using Windows 10/11 media controls (e.g. Global System Media Transport Controls / Windows Media Control API) so that it can show:
  - Current playback state (Playing / Paused)
  - Track title and artist
  - Album artwork, with artwork crossfading in/out when tracks change
- [ ] Provide layout options equivalent to the weather widget (per-monitor selection, corner position, background on/off, margin, opacity) through the widgets settings UI.
- [ ] Add transport controls to the widget UI: clickable Previous (`<`), Play/Pause, and Next (`>`).
- [ ] Gate interactivity behind explicit user intent: transport buttons are only clickable when either `input.hard_exit` is enabled or the Ctrl key is held down in the new temporary interaction mode; in normal mode the widget is display-only to avoid accidental exits.
- [ ] Centralize media-control plumbing in a reusable module (e.g. `core/media/media_controller.py`) so future widgets/features can share the same integration.
- [ ] If Widget cannot retrieve media information or controls widget should fallback to not rendering and log failure silently. 

### 11.2 Weather Iconography (Priority: Low)
- [ ] Add QPainter-based weather iconography (no external bitmaps) for the primary conditions:
  - Sun: circle + rays (lines radiating out)
  - Cloud: overlapping circles/ellipses
  - Rain: diagonal lines below cloud
  - Snow: asterisks or small circles
  - Thunder: zigzag line below cloud
- [ ] Integrate these icons into `widgets/weather_widget.py`, positioned in the lower-left portion of the widget and styled to match the configured text color (respecting theme and DPI).
- [ ] Add a `show_icon`/style setting for the weather widget (with sensible defaults) and ensure drawing stays performant and flicker-free.

### 11.3 Analogue Clock Mode (Priority: Low)
- [ ] Add an analogue display mode per clock widget (Clock 1/2/3), so each clock can independently choose between digital and analogue representations.
- [ ] Implement an analogue clock paint path that includes:
  - Clock face circle, hour markers, and optional Roman numerals via `drawText()`.
  - Hour/minute/second hands with optional tapered/arrow shapes and a bottom-right drop shadow on the hands.
  - Smooth second-hand animation (driven by AnimationManager) rather than 1Hz ticking, with optional seconds.
  - Timezone label rendered below the analogue clock, matching existing timezone label behaviour.
- [ ] Expose per-clock options in the Widgets tab (digital vs analogue, show numerals, show seconds, hand style) while keeping defaults close to current behaviour.

### 11.4 Widget Drop Shadows (Priority: Low)
- [ ] Introduce a global widget drop-shadow setting (default: enabled) that applies to all overlay widgets (clock(s), weather, future Spotify/media widget, etc.).
- [ ] When shadows are enabled, render a light bottom-right shadow behind text (≈30% opacity) and a stronger shadow behind any enabled backgrounds/frames (≈70% opacity), ensuring shadows do not clip or overlap awkwardly.
- [ ] Centralize shadow configuration (color, offset, opacity) so that widgets share a consistent look and can be tuned in one place; document behaviour and any performance considerations in Spec.md.

### 11.5 Settings GUI Hold-to-Repeat Controls (Priority: Low)
- [ ] Update settings GUI +/- controls (e.g. spin-buttons for numeric values) so that holding the mouse button down continuously increments/decrements the associated setting at a sensible repeat rate, rather than requiring repeated clicks. Ensure buttons are correctly positioned for recieving presses. Most + - type buttons are slightly misaligned on the settings tab for +'s especially.
- [ ] Ensure hold-to-repeat behaviour is consistent across all tabs (Display, Widgets, Transitions, etc.), respects min/max clamps, and does not starve the event loop or introduce visible stutter.

### 11.6 Long-term UI & Widgets ideas (Very low priority)
- [ ] Add small but strong bottom-right drop shadows to most buttons where space allows (including tab buttons), matching project-wide shadow styling.
- [ ] Improve spin button visual design (clean up/down arrows, white icons, appropriate drop shadow for the control container).
- [ ] Ensure the Settings GUI is never created larger than the user's screen (target ~60% of screen space) while remaining resizable.
- [ ] Fix Windows theme accent colours leaking into Settings GUI highlights; force monochrome highlights matching the app theme. *(Requires explicit approval before implementation.)*
- [ ] Revise the About section layout (heading, blurb, four external links) and integrate the `images/Shoogle300W.png` artwork with responsive sizing (scale down only, avoid overlap with text).
- [ ] Add a Reddit widget that lists post titles from a configured subreddit (r/...), with configurable count, text styling, and clickable links opened in the default browser. *(Feasibility depends on acceptable, non-API-key access.)*
- [ ] Add a MusicBee widget mirroring Spotify/media widget behaviour but driven by Music Bee APIs/integration, this is a seperate widget to spotify.
- [ ] Implement a Ctrl+right-click-and-drag custom widget positioning mode with snapping between widgets and per-widget persistent positions.
- [ ] Add a "Reset All Positions" control in the general widgets section to restore default widget positions across displays.