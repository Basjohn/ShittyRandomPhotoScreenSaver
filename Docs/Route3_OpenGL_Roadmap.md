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
- [ ] PyOpenGL absence triggers software fallback logging; confirm flush path handles both PyOpenGL present/absent scenarios.
- [ ] Watchdog timers per overlay type validated (start/finish, raise timing, stale overlay cleanup).
- [ ] Overlay readiness telemetry aggregated per overlay type to detect repeated forced-ready fallbacks.
- [ ] Overlay Z-order revalidation executed and logged for multi-monitor coverage.

### 1.3 Pixmap Seeding & Banding
- [x] Re-seed `DisplayWidget.current_pixmap` immediately after settings dialog close to prevent display #2 banding. *(Implemented via `DisplayWidget.reset_after_settings()` + `DisplayManager.show_all()`; pending visual confirmation.)*
- [x] Confirm `_has_rendered_first_frame` logic doesn’t block transitions after settings reload. *(Guard reset in `reset_after_settings()` so first frame after settings presents without transition.)*
- [x] Ensure `self._updates_blocked_until_seed` resets across all exit/enter flows for settings dialog. *(Updates disabled in `reset_after_settings()` and re-enabled on next seed in `set_image` / `_on_transition_finished`.)*
- [ ] Validate initial image request on each display seeds pixmap before overlay warmup (no black flashes). *(Implementation in place; dedicated visual/telemetry validation still required.)*

### 1.4 Block Puzzle Flip Scaling
- [ ] New 2–25 grid limits persisted and clamped in settings, engine, and transition instantiation.
- [ ] Watchdog thresholds for large grids (≥20×20) tuned to prevent false positives.
- [ ] Performance metrics gathered for high-density grids (FPS, GPU usage) and documented.
- [ ] Tests cover boundary values (2×2, 25×25) with hardware/software paths.

## 2. Multi-Monitor Consistency
- [ ] Screen-specific refresh rates (165 Hz vs 60 Hz) handled without drift between displays.
- [ ] Warmup overlays run per screen; ensure swap downgrades tracked individually.
- [x] Weather widget enablement respects per-monitor config (screen 1 disabled). Verify no stray network calls when disabled. *(DisplayWidget._setup_widgets now strictly gates WeatherWidget creation per monitor; invalid monitor selectors gate off with a DEBUG note.)*
- [x] Pan & scan state reset per screen; no leaked timers after exit. *(PanAndScan.stop/enable now idempotent; stop logs only when timer/label state changes, and other logs only fire while pan & scan is enabled.)*
- [ ] Exit flow (mouse movement) cleans resources and overlays deterministically on all displays.

## 3. Settings & Persistence
- [ ] Flat settings keys (e.g., `transitions.type`) kept in sync with nested dict for legacy readers.
- [ ] SettingsManager change notifications carry old/new values in logs for audit trails.
- [ ] Random transition cache cleared whenever manual type is chosen or random toggle disabled.
- [ ] Settings dialog writes validated via automated tests (Ruff lint + pytest) for new keys/limits.
- [ ] Ensure boolean normalization (string vs bool) applied consistently (`random_always`, `hw_accel`, etc.).

## 4. Diagnostics & Telemetry
- [ ] Overlay telemetry includes swap behavior, gl readiness, forced software fallback counts.
- [ ] Startup logs trimmed of redundant detail while retaining actionable insights.
- [ ] Add structured log events for: cache hits/misses, transition skip due to in-progress, watchdog triggers.
- [ ] Log rotation ensures heavy debug sessions do not overwhelm disk (configure size/time-based rotation). (In all scenarios we only save I/O in safe threaded batches! Respect I/O write modesty)
- [ ] Document reproduction recipes for major issues (banding, stuck transition, swap downgrade) in `FlashFlickerDiagnostic.md`.

## 5. Performance & Resource Management
- [ ] Pycache purge on startup inspected; evaluate necessity vs. cold-start penalty.
- [ ] AnimationManager timers cleaned post-transition; confirm no `Animation cancelled` flood from expected flow.
- [ ] ResourceManager lifecycle audited to prevent duplicate initialization per image cycle.
- [ ] Image cache sizing (24 items / 1GB) profiled against actual usage; adjust thresholds and logging.
- [ ] Prefetch queue respects in-flight transition skip policy; evaluate whether skip frequency hurts pacing.
- [ ] Software renderer improvements merged and performance profiled for fallback parity.

## 6. Testing & Tooling
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
- [ ] Multiple `[WATCHDOG] Started` entries per transition cycle—ensure timers cancel correctly to avoid runaway threads.
- [ ] Validate `Animation cancelled` messages correspond to intended cleanup rather than premature stops.

### 7.3 Transition Skip Spam
- [x] `Transition in progress - skipping this image request` triggered during rotation timer; confirm policy is acceptable or adjust scheduling to avoid repeated skips (affects queue drift). *(Policy retained; log demoted to DEBUG and guarded by a per-display skip counter.)*
- [x] Measure frequency and add metrics to audit. *(Skip count now tracked via `DisplayWidget._transition_skip_count`/`get_screen_info` and referenced from the OpenGL stability audit.)*

### 7.4 Settings Cycle vs. Execution Mismatch
- [ ] After cycling to Slide, engine logs confirmed change, yet subsequent transitions remained BlockFlip. Trace settings propagation pipeline and random cache interplay; add guard assertions or logging when type mismatch detected.
- [ ] Ensure settings change event rehydrates `DisplayWidget` before next transition.

### 7.5 Weather Widget Requests
- [x] Weather widget performs network fetch on startup even on monitors where disabled—verify per-monitor gating prevents duplicate calls. *(DisplayWidget._setup_widgets now strictly gates WeatherWidget creation per monitor; invalid monitor selectors gate off with a DEBUG note.)*
- [ ] Handle geocoding/network failures gracefully with backoff and user feedback.

### 7.6 Resource Reinitialization Flood
- [ ] Numerous “ResourceManager initialized” logs during run; determine if redundant instantiations indicate lifecycle leak.
- [ ] Ensure ResourceManager reuse for overlays between frames instead of recreating per transition.

### 7.7 Transition Grid Logging
- [ ] GL BlockFlip repeatedly logs grid 8×4 despite settings set to 10×10/other values—confirm final values passed respect UI configuration and that grid matches aspect ratio logic.

### 7.8 Exit Sequence Cleanup
- [ ] Pan & Scan stop logged multiple times on exit; ensure idempotent cleanup without redundant operations.
- [ ] Verify display manager cleanup completes before ResourceManager tear-down to avoid race conditions.

## 8. Roadmap Milestones
- [ ] **Milestone A:** Transition reliability restored (all types functional) with documented verification.
- [ ] **Milestone B:** Post-settings banding eliminated on all monitors; reproducible test case recorded.
- [ ] **Milestone C:** Overlay swap strategy finalized; documentation and UI messaging updated.
- [ ] **Milestone D:** Full GL diagnostics suite automated (scripts + docs updated).
- [ ] **Milestone E:** Dual-monitor burn-in test passed (0 flicker, no stuck transitions) over 30-minute run.

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
- [ ] Profile OpenGL startup on reference hardware (per-overlay prewarm + first real frame) and document costs in the OpenGL stability audit. Use existing PREWARM logs to capture per-overlay timings and total startup per screen (currently ~1.0s per screen for 5 overlays).
- [ ] Document that the current eager prewarm still allows an initial black-frame flicker before any transition (especially noticeable with GL Blinds) and treat this as a defect rather than a trade-off.
- [ ] Design and implement a lighter-but-effective prewarm strategy that specifically eliminates the black-frame flicker while reducing total startup cost. Avoid exposing a user-facing "prewarm mode" toggle unless strictly necessary; capture the chosen approach in Spec.md and the OpenGL stability audit.

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

---

## Update Log
- **2025-11-14:** Rebuilt roadmap into comprehensive live checklist; incorporated latest debug anomalies and outstanding remediation tasks.
