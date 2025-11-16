# Route 3 – OpenGL & Platform Stability Master Checklist

This document is now the single source of truth for all known stability gaps, regressions, audits, remediation tasks, and verification steps across the rendering pipeline, UI, threading, diagnostics, and supporting systems. Every section is actionable and must remain up to date after each change.

## 0. Governance & Audits
- [x] **Audit Sync** – `audits/AUDIT_OpenGL_Stability.md` now mirrors roadmap items (swap downgrades, transition skips, cache issues) and will be updated alongside each checklist change.
- [x] **Spec Tracking** – `Spec.md` now documents random cache clearing, overlay lifecycle, diagnostics telemetry, and banding mitigation per roadmap.
- [x] **Index Refresh** – `Index.md` now covers overlay telemetry/watchdogs, persistence helpers, and the Route3/FlashFlicker docs.
- [x] **Regressions Ledger** – `Docs/FlashFlickerDiagnostic.md` now records 2025-11-14 anomalies (swap downgrade, transition skips, cache persistence, etc.) with roadmap crosslinks.

### 0.1 Baseline Evidence Capture
- [x] Collect per-monitor first-frame and overlay readiness logs (see `logs/screensaver.log` entries for `_GLPuzzleFlipOverlay` stages on screens 0/1).
- [x] Link current flicker triggers from `Docs/FlashFlickerDiagnostic.md` (see "Current Symptoms" + "2025-11-14 Debug Session Anomalies" sections) for quick triage reference.
- [x] Inventory GL resource lifecycle touchpoints in `rendering/display_widget.py` (`_prewarm_gl_contexts`, `_reuse_persistent_gl_overlays`, `_ensure_overlay_stack`, `_force_overlay_ready`) and transition modules.
- [x] Catalog swap-behavior downgrade warnings per display using latest debug output (see `logs/screensaver.log` warnings around lines 2222–2940 for screens 0 & 1).
- [x] Log occurrences of “Transition in progress – skipping this image request” to evaluate rotation pacing (see repeated INFO entries at lines 325–1764 showing skip spam during rotation).

## 1. Rendering & Transition Reliability
### 1.1 Transition Selection & Execution
- [x] Manual transition selection overrides random cache (`transitions.random_choice`); `ui/tabs/transitions_tab.py` now clears cached random entries whenever manual mode persists settings.
- [x] Random rotation respects hardware availability; transitions tab prevents GL-only selection and clears cached random choice when HW accel is disabled.
- [x] `DisplayWidget._create_transition` honors latest settings (type, direction, block counts) from both nested and flat keys (`rendering/display_widget.py` prioritizes nested slide/wipe data before legacy fallbacks).
- [x] Hotkey cycling (C key) updates settings, UI, and random cache coherently (`engine/screensaver_engine.py` clears random cache & disables random_always on cycle).
- [x] `transitions.random_choice` telemetry added to quickly spot mismatches (requested vs. instantiated) via `_log_transition_selection` in `rendering/display_widget.py`.

### 1.2 GL Overlay Lifecycle
- [x] Triple-buffer requests consistently satisfied with driver-enforced DoubleBuffer; downgrade logs demoted to INFO to reduce noise. Add Display tab note that hardware selects buffer strategy.
- [x] Overlay warmup/prepaint costs (~175–300ms) documented via per-transition GL prepaint profiling (`GL_XFADE_PREPAINT`, `GL_SLIDE_PREPAINT`, `GL_WIPE_PREPAINT`) instead of a global startup prewarm. *(Global `_prewarm_gl_contexts` is no longer invoked from `show_on_screen`; overlays are initialized lazily on first transition, and prepaint timings only WARN on >500ms, INFO for 250–500ms, DEBUG otherwise.)*
- [x] Per-screen refresh rate detection uses live `QScreen.refreshRate()` and applies distinct FPS caps to transitions/pan & scan (current implementation reports 60 Hz for all displays). *(DisplayWidget._detect_refresh_rate now drives `_target_fps`; logs show 165 Hz vs 60 Hz correctly for screens 0/1.)*
- [x] Transition watchdog thresholds updated so routine GL warmups no longer emit timeout warnings. *(Timeout handler now downgrades to DEBUG when overlays report ready; real stalls still log at WARNING.)*
- [x] Widget startup logging (clock/weather) trimmed to essentials; remove verbose field-by-field DEBUG spam. *(ClockWidget/WeatherWidget now avoid per-field DEBUG logs during startup; DisplayWidget logs a single summary INFO line per widget.)*
- [x] GL backend messaging updated to drop “legacy” terminology and triple-buffer preference toggles that no longer apply. *(OpenGL backend now logs “Using OpenGL renderer backend”; triple-buffer preference is treated as best-effort and reported via diagnostics only.)*
- [x] Pan & scan logging only emits when feature is enabled or state changes (avoid disabled-mode noise). *(PanAndScan.stop/enable now idempotent; stop logs only when timer/label state changes, and other logs only fire while pan & scan is enabled.)*
- [x] PyOpenGL absence triggers software fallback logging; confirm flush path handles both PyOpenGL present/absent scenarios. *(When PyOpenGL is missing, `DisplayWidget._perform_initial_gl_flush` logs `[INIT] Skipping low-level GL flush; PyOpenGL not available (using QOpenGLWidget/QSurface flush only)` at INFO, as seen for screens 0/1 in the 2025-11-15 debug run. When PyOpenGL is present, the existing raw GL flush path remains active.)*
- [x] Watchdog timers per overlay type validated (start/finish, raise timing, stale overlay cleanup). *(Each DisplayWidget owns a single-shot watchdog QTimer reused per transition; debug logs show `[WATCHDOG] Started` for Diffuse, GL BlockFlip, and GL Blinds, followed by clean transition finish and `_cancel_transition_watchdog()` with no stray timeouts or leaked timers.)*
- [x] Overlay readiness telemetry aggregated per overlay type to detect repeated forced-ready fallbacks. *(`DisplayWidget.notify_overlay_ready` tracks a per-overlay-per-stage counter in `_overlay_stage_counts` and logs `[DIAG] Overlay readiness ... count=N, details=...`; forced software-ready fallbacks are tagged with `status='forced_ready', gl=False` so repeated occurrences per overlay type are visible in the aggregated counts.)*
- [x] Overlay Z-order revalidation executed and logged for multi-monitor coverage.
- [x] Deterministic exit flow (mouse movement) cleans resources and overlays deterministically on all displays. *(Mouse-move exit triggers `ScreensaverEngine.stop()`, which clears all displays, runs `DisplayManager.cleanup()` (now calling `display.clear()` before close/delete), and then stops the engine; subsequent exit events log `Engine not running` without errors, indicating idempotent teardown across displays.)*
- [x] SettingsManager change notifications carry old/new values in logs for audit trails. *(SettingsManager.set now logs `Setting changed: <key>: <old> -> <new>` at DEBUG; future runs will show both values for keys such as `transitions`, `transitions.type`, and others, improving auditability.)*

### 1.3 Pixmap Seeding & Banding
- [x] Re-seed `DisplayWidget.current_pixmap` immediately after settings dialog close to prevent display #2 banding. *(Implemented via `DisplayWidget.reset_after_settings()` + `DisplayManager.show_all()`; pending visual confirmation.)*
- [x] Confirm `_has_rendered_first_frame` logic doesn’t block transitions after settings reload. *(Guard reset in `reset_after_settings()` so first frame after settings presents without transition.)*
- [x] Ensure `self._updates_blocked_until_seed` resets across all exit/enter flows for settings dialog. *(Updates disabled in `reset_after_settings()` and re-enabled on next seed in `set_image` / `_on_transition_finished`.)*
- [x] Validate initial image request on each display seeds pixmap or a wallpaper snapshot before overlay warmup (no full-screen black frames). *(DisplayWidget.show_on_screen now grabs a per-monitor wallpaper snapshot into `current_pixmap`/`_seed_pixmap`/`previous_pixmap`; `_prewarm_gl_contexts` uses this seeded frame as its dummy pixmap, and `paintEvent` falls back to the previous pixmap when needed, eliminating wallpaper→black startup flashes.)*


## 2. Multi-Monitor Consistency
- [x] Screen-specific refresh rates (165 Hz vs 60 Hz) handled without drift between displays. *(DisplayWidget logs `Detected refresh rate: 165 Hz, target animation FPS: 165` for screen 0 and `60 Hz` / `FPS: 60` for screen 1; subsequent Diffuse and GL BlockFlip transitions instantiate per-screen AnimationManagers at those FPS values with smooth, independent animation.)*
- [x] Warmup overlays run per screen; ensure swap downgrades tracked individually. *(GL prewarm runs all six overlays per screen; for each overlay and screen the logs report `[DIAG] Overlay swap = SwapBehavior.DoubleBuffer (screen=N, name=..., interval=1) — driver enforced double buffer`, confirming per-screen swap downgrade tracking.)*
- [x] Weather widget enablement respects per-monitor config (screen 1 disabled). Verify no stray network calls when disabled. *(DisplayWidget._setup_widgets now strictly gates WeatherWidget creation per monitor; invalid monitor selectors gate off with a DEBUG note.)*
- [x] Pan & scan state reset per screen; no leaked timers after exit. *(PanAndScan.stop/enable now idempotent; stop logs only when timer/label state changes, and other logs only fire while pan & scan is enabled.)*
- [x] Exit flow (mouse movement) cleans resources and overlays deterministically on all displays. *(Mouse-move exit triggers `ScreensaverEngine.stop()`, which clears all displays, runs `DisplayManager.cleanup()` (now calling `display.clear()` before close/delete), and then stops the engine; subsequent exit events log `Engine not running` without errors, indicating idempotent teardown across displays.)*

## 3. Settings & Persistence
- [x] Flat settings keys (e.g., `transitions.type`) kept in sync with nested dict for legacy readers. *(TransitionsTab and `_on_cycle_transition` now update both the nested `transitions` dict and flat keys like `transitions.type`/`transitions.random_always`, keeping legacy readers in sync.)*
- [x] SettingsManager change notifications carry old/new values in logs for audit trails. *(SettingsManager.set now logs `Setting changed: <key>: <old> -> <new>` at DEBUG; future runs will show both values for keys such as `transitions`, `transitions.type`, and others, improving auditability.)*
- [x] Random transition cache cleared whenever manual type is chosen or random toggle disabled. *(TransitionsTab clears `transitions.random_choice`/`last_random_choice` when `random_always` is off, and `ScreensaverEngine._on_cycle_transition` removes the same keys whenever the user cycles transitions via the C-key, as seen in recent debug logs.)*
- [ ] Settings dialog writes validated via automated tests (Ruff lint + pytest) for new keys/limits.
- [x] Ensure boolean normalization (string vs bool) applied consistently (`random_always`, `hw_accel`, etc.). *(`display.hw_accel` and `transitions.random_always` are now always interpreted via `SettingsManager.to_bool`/`get_bool` in DisplayWidget, ScreensaverEngine, and TransitionsTab.)*

### 3.1 Widgets Persistence & Migration (Priority: High)
- [x] Align `ui/tabs/widgets_tab.py` persistence with the `Spec.md` `widgets` schema for `clock`, `clock2`, `clock3`, and `weather`, ensuring monitor, format, timezone, font size, margin, color, and position are written/read via the nested `widgets` dict used by `DisplayWidget._setup_widgets`.
- [x] Implement a one-time migration from legacy flat `widgets.clock.*` keys into the nested `widgets` dict on load, then persist the normalized structure back to settings (keeping legacy keys for backward compatibility if needed).
- [ ] Add a regression test or manual checklist confirming that changes made in the Widgets tab persist across restarts and are reflected correctly in all clocks and the weather widget on each monitor.

## 4. Diagnostics & Telemetry
- [x] Overlay telemetry includes swap behavior, gl readiness, forced software fallback counts. *(Centralized via `core/logging/overlay_telemetry.record_overlay_ready`, which records swap behaviour, GL readiness stages, and forced-ready software fallbacks per overlay.)*
- [x] Startup logs trimmed of redundant detail while retaining actionable insights. *(Pycache cleanup now logs a single summary line instead of per-directory spam; high-level startup logs (GL format, queue stats, engine initialization) are preserved for diagnostics.)*
- [x] Add structured log events for: cache hits/misses, transition skip due to in-progress, watchdog triggers. *(ImageCache logs `Cache miss:`/`Cache hit:` with paths, DisplayWidget logs `Transition in progress - skipping image request (skip_count=...)`, and watchdogs log `[WATCHDOG] Started` (with transition, overlay, timeout) and completion, providing consistent, grep-friendly markers.)*
- [x] Shorten high-traffic logger names for core resources and GL transitions to concise identifiers (e.g., `resources.manager`, `transitions.gl_xfade`, `transitions.gl_blinds`) to improve readability in the aligned log columns. *(Implemented via `core.logging.logger.get_logger` short-name overrides so modules like `core.resources.manager` and GL transitions log under concise aliases.)*
- [x] Reduce verbosity of `[DIAG] Overlay readiness` logs by aggregating repeated counts per overlay type and suppressing redundant per-frame details while keeping key stage transitions and forced-ready events. *(`record_overlay_ready` now aggregates per overlay/stage and only emits a detailed `[DIAG]` line on first occurrence, with counts retained in `DisplayWidget._overlay_stage_counts`.)*
- [x] Log rotation ensures heavy debug sessions do not overwhelm disk (configure size/time-based rotation). *(Implemented via `RotatingFileHandler` in `core/logging/logger.setup_logging` with 10MB max per file and 5 backups.)*
- [ ] Document reproduction recipes for major issues (banding, stuck transition, swap downgrade) in `FlashFlickerDiagnostic.md`.

## 5. Performance & Resource Management
- [ ] Pycache purge on startup inspected; evaluate necessity vs. cold-start penalty.
- [x] AnimationManager timers cleaned post-transition; confirm no `Animation cancelled` flood from expected flow. *(Animations are driven exclusively via `AnimationManager`; transitions call cancel/cleanup on completion or watchdog timeout, and `Animation cancelled` remains a DEBUG-only diagnostic emitted when an animation is intentionally torn down. No warnings or errors are produced from normal transition flow.)*
- [x] ResourceManager lifecycle audited to prevent duplicate initialization per image cycle. *(ScreensaverEngine now owns a single ResourceManager instance shared with DisplayManager, each DisplayWidget, Pan & Scan, transitions, and per-widget AnimationManagers; persistent overlays are created via `overlay_manager.get_or_create_overlay` and registered with this shared manager.)*
- [ ] Image cache sizing (24 items / 1GB) profiled against actual usage; adjust thresholds and logging.
- [ ] Prefetch queue respects in-flight transition skip policy; evaluate whether skip frequency hurts pacing.
- [ ] Software renderer improvements merged and performance profiled for fallback parity.

## 6. Testing & Tooling
- [ ] Audit entire test suite and test script for accuracy to current architecture and test coverage. Add findings of audit to this section of this document as a live checklist and implement findings.
- [ ] Add GL stress tests to `scripts/run_tests.py` and document usage in `Docs/TestSuite.md`.
- [ ] Create reproducible test scenario for transition cycling + manual overrides (ensures no BlockFlip lock-in).
- [ ] Multi-monitor UI tests (clock/weather positions, enable/disable) automated or scripted manual checklist.
- [ ] Regression suite for random transition caching covering hardware on/off permutations.
- [ ] Add log parsing script to summarize overlay warnings per run for rapid triage.

## 7. Recent Debug Session Anomalies (2025-11-14)
These items require follow-up with code changes or validation and must remain listed until resolved.


### 7.5 Weather Widget Requests
- [ ] Handle geocoding/network failures gracefully with backoff and user feedback in setting tab, if failure happens in operation use last known information or do not display widget as final fallback.





## 8. Roadmap Milestones
- [ ] **Milestone A:** Single GL compositor pipeline in place for all GL transitions, with no black-frame or underlay flicker on any monitor, verified by automated tests and diagnostic logs.
- [ ] **Milestone B:** Post-settings banding eliminated on all monitors; reproducible test case recorded and guarded by tests.
- [ ] **Milestone C:** Software transitions (Diffuse, Block Puzzle Flip) run to completion without watchdog timeouts or stalls under the software backend, with coverage tests in place.
- [ ] **Milestone D:** Full GL and GLSL diagnostics suite automated (scripts + docs updated).

## 9. References & Supporting Docs
- `Docs/FlashFlickerDiagnostic.md`
- `Docs/TestSuite.md`
- `audits/AUDIT_OpenGL_Stability.md`

- `scripts/run_tests.py`

## 10. Widgets, Input & GL Startup (New tasks 2025-11-15)

### 10.5 Spotify / Media Playback Widget (Priority: Low)
- [ ] Implement a Spotify/media widget using Windows 10/11 media controls (e.g. Global System Media Transport Controls / Windows Media Control API) so that it can show:
  - Current playback state (Playing / Paused)
  - Track title and artist
  - Album artwork, with artwork crossfading in/out when tracks change
- [ ] Provide layout options equivalent to the weather widget (per-monitor selection, corner position, background on/off, margin, opacity) through the widgets settings UI.
- [ ] Add transport controls to the widget UI: clickable Previous (`<`), Play/Pause, and Next (`>`).
- [ ] Gate interactivity behind Hardened Exit mode: transport buttons are only clickable when `input.hard_exit` is enabled; in normal mode the widget is display-only to avoid accidental exits.
- [ ] Centralize media-control plumbing in a reusable module (e.g. `core/media/media_controller.py`) so future widgets/features can share the same integration.
- [ ] If Widget cannot retrieve media information or controls widget should fallback to not rendering and log failure silently. 

### 10.6 Weather Iconography (Priority: Low)
- [ ] Add QPainter-based weather iconography (no external bitmaps) for the primary conditions:
  - Sun: circle + rays (lines radiating out)
  - Cloud: overlapping circles/ellipses
  - Rain: diagonal lines below cloud
  - Snow: asterisks or small circles
  - Thunder: zigzag line below cloud
- [ ] Integrate these icons into `widgets/weather_widget.py`, positioned in the lower-left portion of the widget and styled to match the configured text color (respecting theme and DPI).
- [ ] Add a `show_icon`/style setting for the weather widget (with sensible defaults) and ensure drawing stays performant and flicker-free.

### 10.7 Analogue Clock Mode (Priority: Low)
- [ ] Add an analogue display mode per clock widget (Clock 1/2/3), so each clock can independently choose between digital and analogue representations.
- [ ] Implement an analogue clock paint path that includes:
  - Clock face circle, hour markers, and optional Roman numerals via `drawText()`.
  - Hour/minute/second hands with optional tapered/arrow shapes and a bottom-right drop shadow on the hands.
  - Smooth second-hand animation (driven by AnimationManager) rather than 1Hz ticking, with optional seconds.
  - Timezone label rendered below the analogue clock, matching existing timezone label behaviour.
- [ ] Expose per-clock options in the Widgets tab (digital vs analogue, show numerals, show seconds, hand style) while keeping defaults close to current behaviour.

### 10.8 Widget Drop Shadows (Priority: Low)
- [ ] Introduce a global widget drop-shadow setting (default: enabled) that applies to all overlay widgets (clock(s), weather, future Spotify/media widget, etc.).
- [ ] When shadows are enabled, render a light bottom-right shadow behind text (≈30% opacity) and a stronger shadow behind any enabled backgrounds/frames (≈70% opacity), ensuring shadows do not clip or overlap awkwardly.
- [ ] Centralize shadow configuration (color, offset, opacity) so that widgets share a consistent look and can be tuned in one place; document behaviour and any performance considerations in Spec.md.

### 10.9 Settings GUI Hold-to-Repeat Controls (Priority: Low)
- [ ] Update settings GUI +/- controls (e.g. spin-buttons for numeric values) so that holding the mouse button down continuously increments/decrements the associated setting at a sensible repeat rate, rather than requiring repeated clicks. Ensure buttons are correctly positioned for recieving presses. Most + - type buttons are slightly misaligned on the settings tab for +'s especially.
- [ ] Ensure hold-to-repeat behaviour is consistent across all tabs (Display, Widgets, Transitions, etc.), respects min/max clamps, and does not starve the event loop or introduce visible stutter.

### 10.10 Widgets Tab Persistence & Migration (Priority: High)
- [x] Align Widgets tab persistence with the `Spec.md` `widgets` schema for `clock`, `clock2`, `clock3`, and `weather`, ensuring that monitor, format, timezone, font size, margin, color, and position are written/read via the nested `widgets` dict used by `DisplayWidget._setup_widgets`.
- [x] Implement a one-time migration from legacy flat `widgets.clock.*` keys into the nested `widgets` dict on load, then persist the normalized structure back to settings (keeping legacy keys for backward compatibility if needed).
- [ ] Add a regression test or manual checklist confirming that changes made in the Widgets tab persist across restarts and are reflected correctly in all clocks and the weather widget on each monitor.

### 11. Deep Architectural Audit (Priority: High)
- [ ] Perform a full architectural audit across engine, rendering, transitions, widgets, and core modules to identify conflicts, duplication, and violations of centralization (threading, resources, settings, logging, telemetry).
- [ ] Validate safe lock-free threading usage via the central ThreadManager (task submission, timers, and callbacks), ensuring no ad-hoc threads or unsafe shared-state mutations remain.
- [ ] Review all long-lived objects (DisplayWidgets, overlays, widgets, ResourceManager registrations, caches) for potential memory leaks, reference cycles, or missed cleanup paths.
- [ ] Analyze race conditions and edge cases in lifecycle flows (startup, settings reload, monitor hotplug, exit, error recovery) and document any remaining risks with mitigation tasks.
- [ ] Consolidate and document framework-level patterns (central managers, telemetry helpers, theming, DPI handling) so future features (Spotify widget, analogue clocks, shadows) plug into the same architecture without new fragmentation.

### 11.1 Single GL Compositor Pipeline (Priority: High)
- [x] Design and implement `rendering/gl_compositor.py` providing a single per-display GL compositor widget (`GLCompositorWidget`, one QOpenGLWidget per DisplayWidget) responsible for drawing the base image and GL transitions, instead of per-transition GL overlays.
- [x] Add an integration path in `DisplayWidget` to host the GL compositor as a child covering the full client area in borderless fullscreen mode. Crossfade now routes through this compositor when hardware acceleration and the OpenGL backend are active; legacy per-transition GL overlays remain as a fallback when the compositor is unavailable.
- [x] Port GL Crossfade to the compositor model as a pure controller (`GLCompositorCrossfadeTransition`) that drives the compositor's rendering, while keeping CPU Crossfade and the legacy GL crossfade overlay for non-compositor paths.
- [ ] Port remaining GL transitions (Slide, Wipe, Block Puzzle Flip, Blinds) to the compositor model as pure controllers (timing/params only), then remove old per-transition GL overlay widgets once parity is verified.
- [ ] Extend GL tests and underlay-coverage tests to exercise the compositor pipeline directly (multi-frame crossfades, multi-monitor sizes, and additional GL transition controllers), asserting no underlay leaks or mostly-black frames during transitions on reference hardware.
- [ ] Treat current per-transition GL overlays as temporary until the compositor reaches feature parity; once complete, simplify `transitions/` to a single compositing path to reduce DWM/stacking complexity.

### 11.2 Software Transition Watchdogs & Artifacts (Priority: Medium)
- [ ] Investigate and fix repeated watchdog timeouts and stalled visuals in software Diffuse and Block Puzzle Flip transitions (as seen in 2025-11-16 debug logs with `DiffuseTransition` and `BlockPuzzleFlipTransition` timing out at 6.0s despite 6.375s durations).
- [ ] Ensure `DisplayWidget._on_transition_watchdog_timeout` does not attempt `self._current_transition.cleanup()` after the transition has already set `_current_transition` to `None`; guard cleanup calls and ordering to avoid `AttributeError: 'NoneType' object has no attribute 'cleanup'` and ensure consistent visual state.
- [ ] Add targeted tests for CPU Diffuse and Block Puzzle Flip transitions that run them to completion under the software backend, verifying no watchdog timeouts, no repeated flashing of stalled images, and correct cleanup of labels/overlays.

---

## Update Log
- **2025-11-14:** Rebuilt roadmap into comprehensive live checklist; incorporated latest debug anomalies and outstanding remediation tasks.
- **2025-11-15:** Implemented multi-clock widgets and Hard Exit input mode, extended Diffuse transition (block sizes + shapes), integrated GL Blinds into persistent overlay prewarm, and updated startup path with wallpaper snapshot seeding, seeded prewarm pixmaps, and previous-pixmap fallback to remove initial black-frame flicker (pending extended soak testing). Added explicit tasks for widgets persistence/migration, black-frame elimination for GL prewarm/first-frame handling, and logging readability (shorter logger names, trimmed overlay diagnostics).
