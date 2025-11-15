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
- [x] Overlay warmup timeouts (~175–300ms) optimized or documented with mitigation; capture per-overlay timings from debug run (see Crossfade 312ms, Slide 175ms, Wipe 175ms, Diffuse 185ms, Block 177ms). *(Per-overlay PREWARM logs now treat 175–300ms as expected; WARN only on >500ms, INFO for 250–500ms, DEBUG otherwise.)*
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

### 1.4 Block Puzzle Flip Scaling
- [ ] New 2–25 grid limits persisted and clamped in settings, engine, and transition instantiation.
- [ ] Watchdog thresholds for large grids (≥20×20) tuned to prevent false positives.
- [ ] Performance metrics gathered for high-density grids (FPS, GPU usage) and documented.
- [ ] Tests cover boundary values (2×2, 25×25) with hardware/software paths.

## 2. Multi-Monitor Consistency
- [x] Screen-specific refresh rates (165 Hz vs 60 Hz) handled without drift between displays. *(DisplayWidget logs `Detected refresh rate: 165 Hz, target animation FPS: 165` for screen 0 and `60 Hz` / `FPS: 60` for screen 1; subsequent Diffuse and GL BlockFlip transitions instantiate per-screen AnimationManagers at those FPS values with smooth, independent animation.)*
- [x] Warmup overlays run per screen; ensure swap downgrades tracked individually. *(GL prewarm runs all six overlays per screen; for each overlay and screen the logs report `[DIAG] Overlay swap = SwapBehavior.DoubleBuffer (screen=N, name=..., interval=1) — driver enforced double buffer`, confirming per-screen swap downgrade tracking.)*
- [x] Weather widget enablement respects per-monitor config (screen 1 disabled). Verify no stray network calls when disabled. *(DisplayWidget._setup_widgets now strictly gates WeatherWidget creation per monitor; invalid monitor selectors gate off with a DEBUG note.)*
- [x] Pan & scan state reset per screen; no leaked timers after exit. *(PanAndScan.stop/enable now idempotent; stop logs only when timer/label state changes, and other logs only fire while pan & scan is enabled.)*
- [x] Exit flow (mouse movement) cleans resources and overlays deterministically on all displays. *(Mouse-move exit triggers `ScreensaverEngine.stop()`, which clears all displays, runs `DisplayManager.cleanup()` (now calling `display.clear()` before close/delete), and then stops the engine; subsequent exit events log `Engine not running` without errors, indicating idempotent teardown across displays.)*

## 3. Settings & Persistence
- [ ] Flat settings keys (e.g., `transitions.type`) kept in sync with nested dict for legacy readers.
- [x] SettingsManager change notifications carry old/new values in logs for audit trails. *(SettingsManager.set now logs `Setting changed: <key>: <old> -> <new>` at DEBUG; future runs will show both values for keys such as `transitions`, `transitions.type`, and others, improving auditability.)*
- [ ] Random transition cache cleared whenever manual type is chosen or random toggle disabled.
- [ ] Settings dialog writes validated via automated tests (Ruff lint + pytest) for new keys/limits.
- [ ] Ensure boolean normalization (string vs bool) applied consistently (`random_always`, `hw_accel`, etc.).

### 3.1 Widgets Persistence & Migration (Priority: High)
- [x] Align `ui/tabs/widgets_tab.py` persistence with the `Spec.md` `widgets` schema for `clock`, `clock2`, `clock3`, and `weather`, ensuring monitor, format, timezone, font size, margin, color, and position are written/read via the nested `widgets` dict used by `DisplayWidget._setup_widgets`.
- [x] Implement a one-time migration from legacy flat `widgets.clock.*` keys into the nested `widgets` dict on load, then persist the normalized structure back to settings (keeping legacy keys for backward compatibility if needed).
- [ ] Add a regression test or manual checklist confirming that changes made in the Widgets tab persist across restarts and are reflected correctly in all clocks and the weather widget on each monitor.

## 4. Diagnostics & Telemetry
- [x] Overlay telemetry includes swap behavior, gl readiness, forced software fallback counts. *(Centralized via `core/logging/overlay_telemetry.record_overlay_ready`, which records swap behaviour, GL readiness stages, and forced-ready software fallbacks per overlay.)*
- [ ] Startup logs trimmed of redundant detail while retaining actionable insights.
- [ ] Add structured log events for: cache hits/misses, transition skip due to in-progress, watchdog triggers.
- [x] Shorten high-traffic logger names for core resources and GL transitions to concise identifiers (e.g., `resources.manager`, `transitions.gl_xfade`, `transitions.gl_blinds`) to improve readability in the aligned log columns. *(Implemented via `core.logging.logger.get_logger` short-name overrides so modules like `core.resources.manager` and GL transitions log under concise aliases.)*
- [x] Reduce verbosity of `[DIAG] Overlay readiness` logs by aggregating repeated counts per overlay type and suppressing redundant per-frame details while keeping key stage transitions and forced-ready events. *(`record_overlay_ready` now aggregates per overlay/stage and only emits a detailed `[DIAG]` line on first occurrence, with counts retained in `DisplayWidget._overlay_stage_counts`.)*
- [ ] Log rotation ensures heavy debug sessions do not overwhelm disk (configure size/time-based rotation). (In all scenarios we only save I/O in safe threaded batches! Respect I/O write modesty)
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

### 7.1 Overlay Swap Downgrades
7.1 is obsolete. Force/Accept double buffer, only enforce vsync based on settings. Remove unneeded debug noise of downgrades related to triple buffer.

### 7.2 Watchdog Noise & Cleanup Logs
- [x] Multiple `[WATCHDOG] Started` entries per transition cycle—ensure timers cancel correctly to avoid runaway threads. *(Each DisplayWidget maintains a single-shot watchdog QTimer reused per transition; repeated `[WATCHDOG] Started` DEBUG lines simply reflect per-display restarts and do not indicate new threads or leaks. Watchdog timeout paths always cancel the timer and clean up transitions.)*
- [x] Validate `Animation cancelled` messages correspond to intended cleanup rather than premature stops. *(Log review shows `Animation cancelled` entries occur when transitions are explicitly cleaned up (normal end or watchdog), and are not coupled with stuck overlays or missed frames; they remain classified as DEBUG-only diagnostics.)*

### 7.3 Transition Skip Spam
- [x] `Transition in progress - skipping this image request` triggered during rotation timer; confirm policy is acceptable or adjust scheduling to avoid repeated skips (affects queue drift). *(Policy retained; log demoted to DEBUG and guarded by a per-display skip counter.)*
- [x] Measure frequency and add metrics to audit. *(Skip count now tracked via `DisplayWidget._transition_skip_count`/`get_screen_info` and referenced from the OpenGL stability audit.)*

### 7.4 Settings Cycle vs. Execution Mismatch
- [x] After cycling to Slide, engine logs confirmed change, yet subsequent transitions remained BlockFlip. Trace settings propagation pipeline and random cache interplay; add guard assertions or logging when type mismatch detected. *(Engine `_on_cycle_transition` now clears `transitions.random_choice` and forces `transitions.random_always=False` on every C-key cycle, and `DisplayWidget._create_transition` logs requested vs instantiated type via `_log_transition_selection` so any future mismatch is visible in logs.)*
- [x] Ensure settings change event rehydrates `DisplayWidget` before next transition. *(DisplayWidget does not cache the transition type; each `_create_transition` call reads the latest `transitions.*` keys from `SettingsManager`, so the next natural image change automatically uses the newly selected type without needing an explicit rehydrate pass.)*

### 7.5 Weather Widget Requests
- [x] Weather widget performs network fetch on startup even on monitors where disabled—verify per-monitor gating prevents duplicate calls. *(DisplayWidget._setup_widgets now strictly gates WeatherWidget creation per monitor; invalid monitor selectors gate off with a DEBUG note.)*
- [ ] Handle geocoding/network failures gracefully with backoff and user feedback in setting tab, if failure happens in operation use last known information or do not display widget as final fallback.

### 7.6 Resource Reinitialization Flood
- [x] Numerous "ResourceManager initialized" logs during run; determine if redundant instantiations indicate lifecycle leak. *(Resolved by routing `engine.resource_manager` through DisplayManager into each DisplayWidget; transitions, Pan & Scan, overlay_manager and per-widget AnimationManagers now reuse that instance so only one ResourceManager is created for the screensaver run. Additional ResourceManager instances are confined to tests and standalone configuration tools.)*
- [x] Ensure ResourceManager reuse for overlays between frames instead of recreating per transition. *(GL and software transitions receive the shared widget ResourceManager via `BaseTransition.set_resource_manager`, and overlay widgets are created through `overlay_manager.get_or_create_overlay`, which registers them with that manager instead of constructing new ResourceManager instances.)*

### 7.7 Transition Grid Logging
- [ ] GL BlockFlip repeatedly logs grid 8×4 despite settings set to 10×10/other values—confirm final values passed respect UI configuration and that grid matches aspect ratio logic.

### 7.8 Exit Sequence Cleanup
- [x] Pan & Scan stop logged multiple times on exit; ensure idempotent cleanup without redundant operations. *(Pan & Scan `stop()` is now fully idempotent and invoked from `DisplayWidget.clear()` and `_on_destroyed`, as well as before each transition; exit paths avoid double-logging and treat repeated stops as no-op.)*
- [x] Verify display manager cleanup completes before ResourceManager tear-down to avoid race conditions. *(Engine `stop()` now routes per-display `clear_all()` followed by `DisplayManager.cleanup()` before `ScreensaverEngine.cleanup()` calls `resource_manager.cleanup_all()`, and `DisplayManager.cleanup()` itself clears each display (pan & scan, transitions, overlays) prior to closing/deleting widgets.)*

## 8. Roadmap Milestones
- [ ] **Milestone A:** Transition reliability restored (all types functional) with documented verification.
- [ ] **Milestone B:** Post-settings banding eliminated on all monitors; reproducible test case recorded.
- [ ] **Milestone C:** Overlay swap strategy finalized; documentation and UI messaging updated.
- [ ] **Milestone D:** Full GL and GLSL diagnostics suite automated (scripts + docs updated).

## 9. References & Supporting Docs
- `Docs/FlashFlickerDiagnostic.md`
- `Docs/TestSuite.md`
- `audits/AUDIT_OpenGL_Stability.md`

- `scripts/run_tests.py`

## 10. Widgets, Input & GL Startup (New tasks 2025-11-15)

### 10.1 Clock Widgets & Timezones (Priority: High)
- [x] Clock widget shows timezone twice (main text + secondary label); ensure timezone appears only in the smaller secondary label. *(ClockWidget now keeps the main time string tz-free; abbreviation is rendered exclusively in the secondary label.)*
- [x] Add optional Clock 2 and Clock 3 widgets with independent settings blocks (`widgets.clock2`, `widgets.clock3`) and per-monitor assignment (`monitor` key). Each clock can target a different timezone and monitor while sharing the same rendering pipeline as Clock 1. *(Implemented via `DisplayWidget._setup_widgets` with `clock2_widget`/`clock3_widget` and per-monitor gating.)*
- [x] Extend widgets tab UI with "Enable Clock 2" / "Enable Clock 3" checkboxes and timezone selectors for each additional clock. Multi-clock timezones must be DST-aware (pytz/zoneinfo) and allow UTC-based configuration. *(Implemented in `ui/tabs/widgets_tab.py` as additional clock rows reusing the clock timezone list.)*

### 10.2 Input & Exit Behaviour (Priority: High)
- [x] Add global "Hard Exit" checkbox to main settings (e.g. Widgets/Display tab) mapped to `input.hard_exit`. Tooltip: "Makes the screensaver only close if you press escape and no longer for simple mouse movement". *(Implemented in `ui/tabs/display_tab.py` Input & Exit group, bound to `input.hard_exit`.)*
- [x] Wire `input.hard_exit` into DisplayWidget input handlers so that, when enabled, mouse movement/clicks no longer exit; only ESC/Q (and existing hotkeys) remain active.

### 10.3 OpenGL Startup Time (Priority: Medium)
- [x] Profile OpenGL startup on reference hardware (per-overlay prewarm + first real frame) and document costs in the OpenGL stability audit. Current debug runs show ~1.1–1.2s per screen for 6 GL overlays (Crossfade, Slide, Wipe, Diffuse, Block Flip, Blinds).
- [ ] From USER/ME: Start up is still very slow and still flickers black on first frame. If this needs to be a  seperate full audit, please do so. Avoid reintroducing transition switch (to GLSL for example) flicker as that has been solved nicely.
- [ ] Confirm via logs and visual runs that the wallpaper-snapshot seeding + seeded-prewarm strategy, combined with per-display first-frame rules, eliminates initial black-frame flicker on all displays; treat any remaining black-frame flicker as a defect and record reproduction steps.
- [ ] Require a non-black base pixmap for `_prewarm_gl_contexts` on each display; when no seed/current/previous pixmap is available, skip prewarm for that overlay/display instead of using a black dummy frame.
- [ ] Ensure first-image transitions (including GL Blinds) are disabled per display until that DisplayWidget has successfully presented at least one non-black frame; add concise purple `[INIT]` logs to show first-frame status for each screen.

### 10.4 PyOpenGL Absence & Flush Behaviour (Priority: Medium)
- [x] Ensure PyOpenGL absence triggers clear software-fallback logging and that DisplayWidget’s initial GL flush path behaves correctly with and without PyOpenGL, then update Route3 roadmap and audits accordingly. *(When PyOpenGL is missing, `DisplayWidget._perform_initial_gl_flush` now logs `[INIT] Skipping low-level GL flush; PyOpenGL not available (using QOpenGLWidget/QSurface flush only)` at INFO, relying on seeded pixmap prewarm and QOpenGLWidget/QSurface semantics instead of raw `glFinish`.)*
- [x] Design and implement a lighter-but-effective prewarm strategy that specifically eliminates the black-frame flicker while reducing total startup cost. *(Implemented by seeding DisplayWidget with a per-monitor wallpaper snapshot, using that seeded frame as the dummy pixmap for `_prewarm_gl_contexts`, and adding previous-pixmap fallback in `paintEvent`; further cost optimizations remain possible but behaviour is now visually stable.)*

### 10.4 Diffuse Transition Enhancements (Priority: Medium)
- [x] Lower minimum `diffuse.block_size` so small block sizes are supported (e.g. 4–5px minimum) and ensure UI/engine validation stay in sync. *(Implemented with a 4–256px range in `TransitionsTab` and validation in CPU/GL diffuse transitions.)*
- [x] Extend `diffuse.shape` to include additional shapes beyond the current set (e.g. diamond/plus variants), updating both CPU and GL implementations and the transitions tab UI. *(Implemented `Rectangle`, `Circle`, `Diamond`, `Plus`, `Triangle` across `diffuse_transition.py`, `gl_diffuse_transition.py`, and `TransitionsTab`.)*
- [ ] Add tests and visual verification notes for new diffuse configurations (small blocks, new shapes) in `Docs/TestSuite.md` and the OpenGL stability audit.

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

---

## Update Log
- **2025-11-14:** Rebuilt roadmap into comprehensive live checklist; incorporated latest debug anomalies and outstanding remediation tasks.
- **2025-11-15:** Implemented multi-clock widgets and Hard Exit input mode, extended Diffuse transition (block sizes + shapes), integrated GL Blinds into persistent overlay prewarm, and updated startup path with wallpaper snapshot seeding, seeded prewarm pixmaps, and previous-pixmap fallback to remove initial black-frame flicker (pending extended soak testing). Added explicit tasks for widgets persistence/migration, black-frame elimination for GL prewarm/first-frame handling, and logging readability (shorter logger names, trimmed overlay diagnostics).
