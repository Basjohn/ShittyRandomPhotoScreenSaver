# Route 3 – OpenGL & Platform Stability Master Checklist

This document is now the single source of truth for all known stability gaps, regressions, audits, remediation tasks, and verification steps across the rendering pipeline, UI, threading, diagnostics, and supporting systems. Every section is actionable and must remain up to date after each change.

Checkboxes: `[ ]` = active work; `[x]` = completed or historical items retained for context.

## 0. Governance & Audits (Historical)
- [x] **Audit Sync** – `audits/AUDIT_OpenGL_Stability.md` stays aligned with this roadmap (swap downgrades, transition skips, cache issues).
- [x] **Spec Tracking** – `Docs/Spec.md` documents cache clearing, overlay lifecycle, diagnostics telemetry, and banding mitigation.
- [x] **Index Refresh** – `Docs/Index.md` indexes overlay telemetry/watchdogs, persistence helpers, and the Route 3 / flicker diagnostics docs.
- [x] **Historical regressions** – 2025-11-14 anomalies (swap downgrade, transition skips, cache persistence) are recorded in `audits/AUDIT_OpenGL_Stability.md` and `Docs/FlashFlickerDiagnostic.md`.


## 1. Deep Architectural Audit & Core Stability (Historical)

### 1.1 Architectural audit (completed)
- [x] Full architectural audit across engine, rendering, transitions, widgets, and core modules performed, with central managers (threading, resources, settings, logging, telemetry) confirmed as the single points of truth.
- [x] Long-lived objects (DisplayWidgets, compositor, widgets, ResourceManager registrations, caches) reviewed for leaks and lifecycle issues; remaining risks are tracked as dedicated items elsewhere in this roadmap.

### 1.2 Software transition watchdogs & artifacts (completed)
- [x] Software Diffuse and Block Puzzle Flip watchdog timeouts audited and hardened; `DisplayWidget._on_transition_watchdog_timeout` now safely handles `None` transitions and logs timeouts without crashing.
- [x] Targeted tests/manual scenarios added to ensure no repeated flashing of stalled images and correct cleanup of transition state after watchdog expiry.

## 2. Rendering & Transition Reliability (Historical baseline)
### 2.1 Transition selection & execution
- [x] Random/manual transition selection, C-key cycling, and `DisplayWidget._create_transition` keep settings, random cache, and telemetry in sync.

### 2.2 GL/overlay lifecycle (historical)
- [x] GL overlay-era issues (buffer downgrades, warmup cost, overlay watchdogs, readiness telemetry, exit flow) were audited and fixed before the compositor pipeline. Legacy per-transition GL overlays are now removed; this section is kept only as historical context.

### 2.3 Pixmap seeding, banding & fullscreen behaviour
- [x] Post-settings banding fixed via `DisplayWidget.reset_after_settings()` / `DisplayManager.show_all()`.
- [x] First-frame handling and wallpaper snapshot seeding prevent initial black frames.
- [x] Borderless-fullscreen compatibility mode for QOpenGLWidget eliminates secondary-monitor banding and first-transition black flashes.

## 3. Multi-Monitor & DPI Consistency
- [x] Per-screen refresh rates (e.g. 165 Hz and 60 Hz) honoured with independent AnimationManager instances.
- [x] Per-screen GL compositors and swap-behaviour logging for downgrade detection.
- [x] Widgets respect per-monitor configuration (clocks, weather, media/Spotify) and avoid stray work on disabled screens.
- [x] Pan & scan and exit flow clean up resources deterministically on each display.
- [ ] Add automated regression tests for multi-monitor and mixed-DPI overlays (Ctrl halo, widgets) using mocked QScreens and global cursor positions.

## 4. Settings & Persistence
- [x] Flat settings keys (e.g., `transitions.type`) kept in sync with nested dict for legacy readers. *(TransitionsTab and `_on_cycle_transition` now update both the nested `transitions` dict and flat keys like `transitions.type`/`transitions.random_always`, keeping legacy readers in sync.)*
- [x] SettingsManager change notifications carry old/new values in logs for audit trails. *(SettingsManager.set now logs `Setting changed: <key>: <old> -> <new>` at DEBUG; future runs will show both values for keys such as `transitions`, `transitions.type`, and others, improving auditability.)*
- [x] Random transition cache cleared whenever manual type is chosen or random toggle disabled. *(TransitionsTab clears `transitions.random_choice`/`last_random_choice` when `random_always` is off, and `ScreensaverEngine._on_cycle_transition` removes the same keys whenever the user cycles transitions via the C-key, as seen in recent debug logs.)*
- [ ] Settings dialog writes validated via automated tests (Ruff lint + pytest) for new keys/limits.
- [x] Ensure boolean normalization (string vs bool) applied consistently (`random_always`, `hw_accel`, etc.). *(`display.hw_accel` and `transitions.random_always` are now always interpreted via `SettingsManager.to_bool`/`get_bool` in DisplayWidget, ScreensaverEngine, and TransitionsTab.)*

### 4.1 Widgets Persistence & Migration (Priority: High)
- [x] Align `ui/tabs/widgets_tab.py` persistence with the `Spec.md` `widgets` schema for `clock`, `clock2`, `clock3`, and `weather`, ensuring monitor, format, timezone, font size, margin, color, and position are written/read via the nested `widgets` dict used by `DisplayWidget._setup_widgets`.
- [x] Implement a one-time migration from legacy flat `widgets.clock.*` keys into the nested `widgets` dict on load, then persist the normalized structure back to settings (keeping legacy keys for backward compatibility if needed).
- [x] Add a regression test or manual checklist confirming that changes made in the Widgets tab persist across restarts and are reflected correctly in all clocks and the weather widget on each monitor. *(Covered by `tests/test_widgets_persistence_integration.py`.)*

### 4.2 Ctrl-Based Temporary Interaction Mode (Priority: Medium)
- [x] Implement a Ctrl-held temporary interaction mode in `DisplayWidget` where mouse movement and left-clicks do **not** exit the screensaver while Ctrl is held; only ESC/Q and hotkeys continue to exit.
- [x] Ensure that, while Ctrl is held, mouse events are delivered to child widgets (clocks, weather, future Spotify/media widget) without toggling `input.hard_exit` in settings, allowing safe, non-persistent interaction.
- [x] Add targeted tests or a manual checklist verifying Ctrl-held behaviour across displays and widget combinations (no accidental exit, no stuck non-exit state when Ctrl is released). *(Covered by `tests/test_ctrl_interaction_mode.py`.)*
- [x] Ensure local and global media keys (play/pause/next/prev/volume) do not cause the screensaver to exit; they should only control media when allowed by the interaction mode and never act as exit keys. *(Guarded by `test_media_keys_do_not_exit_screensaver` in `tests/test_ctrl_interaction_mode.py`.)*

## 5. Diagnostics & Telemetry
- [x] Overlay telemetry for swap behaviour, GL readiness, and software fallbacks (`core/logging/overlay_telemetry.py`).
- [x] Startup logs trimmed to actionable summaries (GL format, queue stats, engine initialization) without pycache spam.
- [x] Structured log events for cache hits/misses, transition skips, and watchdog triggers.
- [x] Short logger names for core resources and GL transitions (for readability in aligned log columns).
- [x] Aggregated `[DIAG] Overlay readiness` logging to avoid per-frame spam while tracking per-overlay counts.
- [x] Log rotation via `RotatingFileHandler` (10MB x 5 files) to keep debug sessions bounded.
- [x] Reproduction recipes for banding, stuck transitions, and swap downgrades recorded in `Docs/FlashFlickerDiagnostic.md`.

## 6. Performance & Resource Management
- [x] AnimationManager timers cleaned post-transition; confirm no `Animation cancelled` flood from expected flow. *(Animations are driven exclusively via `AnimationManager`; transitions call cancel/cleanup on completion or watchdog timeout, and `Animation cancelled` remains a DEBUG-only diagnostic emitted when an animation is intentionally torn down. No warnings or errors are produced from normal transition flow.)*
- [x] ResourceManager lifecycle audited to prevent duplicate initialization per image cycle. *(ScreensaverEngine now owns a single ResourceManager instance shared with DisplayManager, each DisplayWidget, Pan & Scan, transitions, and per-widget AnimationManagers; persistent overlays are created via `overlay_manager.get_or_create_overlay` and registered with this shared manager.)*
- [x] Image cache sizing (24 items / 1GB) profiled against actual usage; adjust thresholds and logging. *(ImageCache now tracks hits/misses/evictions and `ScreensaverEngine.stop()` logs a concise `[PERF] ImageCache` summary per run.)*
- [x] Prefetch queue respects in-flight transition skip policy; evaluate whether skip frequency hurts pacing. *(Operationalized via the **Route3 Perf Scenario: Prefetch Queue vs Transition Skips** in `Docs/TestSuite.md`, which uses the `[PERF] Engine summary` queue stats and per-display `transition_skip_count` metrics to validate that skips remain bounded and do not harm pacing in real runs.)*
- [ ] Software renderer improvements merged and performance profiled for fallback parity.
- [ ] GL compositor Slide smoothness and performance:
  - [ ] Investigate Slide smoothness on mixed-refresh setups (165 Hz + 60 Hz), ensuring that `GLCompositorSlideTransition` feels as smooth as or smoother than the legacy GL Slide on both displays. *(`GLCompositorWidget` now emits `[PERF] [GL COMPOSITOR] Slide metrics` per transition (duration, frames, avg_fps, dt_min/dt_max, size), with separate logs per display; recent logs show durations closely tracking configured `duration_ms` and frame counts consistent with each screen's detected refresh rate.)*
  - [ ] Profile per-frame timing for compositor-driven Slide at both refresh rates and verify that AnimationManager step sizes and easing curves (`EasingCurve`) produce visually consistent motion without micro-jitter.
  - [ ] Experiment with small adjustments to easing, durations, and integer pixel snapping in the compositor slide path (without regressing Crossfade) and document chosen defaults in `Spec.md`.

## 7. Testing & Tooling
- [ ] Audit entire test suite and test script for accuracy to current architecture and test coverage. Add findings of audit to this section of this document as a live checklist and implement findings.
- [x] Create reproducible test scenario for transition cycling + manual overrides (ensures no BlockFlip lock-in). *(Covered by the **Route3 Scenario: Transition Cycling + Manual Overrides (BlockFlip lock-in)** section in `Docs/TestSuite.md`.)*
- [x] Multi-monitor UI tests (clock/weather positions, enable/disable) automated or scripted manual checklist. *(Covered by the **Route3 Scenario: Multi-Monitor Widgets & UI (Clocks & Weather)** section in `Docs/TestSuite.md`.)*
- [ ] Regression suite for random transition caching covering hardware on/off permutations.
- [x] Add log parsing script to summarize overlay warnings per run for rapid triage. *(Implemented as `scripts/overlay_log_parser.py`, which summarizes watchdog, overlay readiness, swap downgrade, and fallback overlay entries from a given log file.)*
 - [x] Add a Slide metrics log parser to summarize GLCompositor Slide performance per log run. *(Implemented as `scripts/slide_metrics_parser.py`, which groups `[PERF] [GL COMPOSITOR] Slide metrics` entries by resolution and reports duration/fps/jitter statistics.)*

## 8. Historical Debug Anomalies (2025-11-14)
- [ ] Weather widget network failures: handle geocoding/network errors with backoff and last-known-data fallback.

## 9. Roadmap Milestones
- [x] **Milestone A:** GL compositor pipeline in place for Crossfade and Slide on all hw-accelerated displays, with no black-frame or underlay flicker, verified by automated tests and diagnostic logs (including multi-monitor, mixed-refresh scenarios).
- [x] **Milestone B:** Remaining GL transitions (Wipe, Block Puzzle Flip, Blinds, Diffuse) have compositor controllers and tests; legacy per-transition GL overlay widgets have been removed so runtime now uses only compositor-backed or software transitions.
- [x] **Milestone C:** Post-settings and non-GL banding eliminated on all monitors; reproduction recipes recorded and guarded by tests (including software-backend scenarios).
- [x] **Milestone D:** Software transitions (Diffuse, Block Puzzle Flip) run to completion without watchdog timeouts or stalls under the software backend, with coverage tests in place. *(Guarded by `test_diffuse_transition_software_backend_no_watchdog` and `test_block_flip_transition_software_backend_no_watchdog` in `tests/test_transition_integration.py`, which force the software backend and assert clean completion with the transition watchdog armed.)*
- [x] **Milestone E:** Full GL and GLSL diagnostics suite automated (scripts + docs updated).

## 10. References & Supporting Docs
- `Docs/TestSuite.md`
- `audits/AUDIT_OpenGL_Stability.md`

- `scripts/run_tests.py`

## 11. Widgets, Input & GL Startup (New tasks 2025-11-15)

### 11.1 Spotify / Media Playback Widget (Priority: Low)
- [x] Implement a Spotify widget using Windows 10/11 media controls (Global System Media Transport Controls / Windows Media Control API) so that it can show:
  - Current playback state (Playing / Paused)
  - Track title and artist
  - Album name
  - Album artwork as a static icon when available, with the text layout shrinking horizontally when artwork is absent.
- [x] Hide the widget entirely when no Spotify GSMTC session is active or when media APIs/controllers are unavailable, treating this as "no media" rather than showing other players.
- [ ] Use the official Spotify logo (or a transparency supporting equivalent) in the widget header alongside a clear "SPOTIFY" label, aligned with the app theme for good UX. The logo should be scaled to fit the header height, overall shape and customization of widget resembles our general widget designs/rules. *(Current implementation supports an optional logo from `/images`, but the final asset and UX polish remain TODO.)*
- [x] Provide layout options equivalent to the weather widget (per-monitor selection, corner position, background on/off, margin, opacity) through the widgets settings UI.
- [x] Add transport controls to the widget UI: Previous (`<`), Play/Pause, and Next (`>`), wired via the centralized media controller.
- [x] Gate interactivity behind explicit user intent: transport behaviour is only invoked when either `input.hard_exit` is enabled or the Ctrl key is held down in the temporary interaction mode; in normal mode the widget remains effectively display-only and clicks still exit the screensaver.
- [x] Centralize media-control plumbing in a reusable module (`core/media/media_controller.py`) so future widgets/features can share the same integration, including a NoOp fallback and Spotify session selection.
- [x] If the widget cannot retrieve media information or controls it should fall back to not rendering and log failure softly, rather than raising. *(Implemented by hiding the widget when `get_current_track()` returns `None`, with controller failures logged at debug/info.)*
- [x] Ensure the media widget is kept above GL and software transition overlays via `transitions.overlay_manager.raise_overlay()` so that Spotify text/artwork and transport controls remain visible in both software and compositor-backed modes.



### 11.2 Weather Iconography (Priority: Low)
- [ ] Replace the current simple ASCII condition tags (e.g. `[CLOUD]`, `[RAIN]`, `[SUN]`) with a more refined iconography approach (either improved ASCII that is an ASCII  based drawing that resembles the icon in question or a free-to-use icon set) that remains readable and theme-aware.
- [ ] Integrate the chosen iconography into `widgets/weather_widget.py`, positioned cleanly relative to the text and styled to match the configured text color (respecting theme and DPI).
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
- [ ] Ensure the Settings GUI is never created larger than the user's screen (target ~60% of screen space) while remaining resizable. Minimum height is currently much too large, if that adjustment will fix that great, if not minimum height needs be 850px
- [ ] Fix Windows theme accent colours leaking into Settings GUI highlights; force monochrome highlights matching the app theme. *(Requires explicit approval before implementation.)*
- [x] Revise the About section layout (heading replaced with image "F:\\Programming\\Apps\\ShittyRandomPhotoScreenSaver\\images\\Logo.png", blurb - "C:\\Users\\Basjohn\\Documents\\AboutBlurb.txt", four external links with styled buttons shown in blurb, keep Hotkey text below links, matching alignments) and integrate the `images/Shoogle300W.png` artwork top aligned with the logo.png with responsive sizing for both (scale down only, avoid overlap with text). An exact example can be seen here "F:\\Programming\\Apps\\ShittyRandomPhotoScreenSaver\\images\\ABOUTExample.png"
The example shows the main content area of the tab which is the only area you need to adjust for this.
- [MD Proposal] Add a Reddit widget that lists post titles from a configured subreddit (r/...), with configurable count, text styling, and clickable links opened in the default browser. The widget heading should use the official Reddit logo (or a transparent equivalent) alongside `r/<subreddit>` and default to showing roughly 10 items sorted by “hot”. *(Feasibility depends on acceptable, non-API-key access.)*
- [?] Add a MusicBee widget mirroring Spotify/media widget behaviour but driven by Music Bee APIs/integration, this is a seperate widget to spotify.
- [Skip] Implement a Ctrl+right-click-and-drag custom widget positioning mode with snapping between widgets and per-widget persistent positions.
- [Skip] Add a "Reset All Positions" control in the general widgets section to restore default widget positions across displays.

## 12. Future GL-Only Transitions (Concept Stage)

- [ ] **Peel (GL-only)** – Strips of the current image curl and peel away in a chosen direction to reveal the next image underneath. Implemented as a compositor-backed fullscreen shader using per-strip math; division (1–20 strips) and direction reuse existing Slide/Wipe direction settings.
- [ ] **Rain Drops (GL-only)** – 3D-ish raindrops land on the image, with ripples and refractive distortion that gradually blend the old image into the new one. Implemented as a screen-space distortion + crossfade effect with a capped number of active droplets.
- [ ] **Warp Dissolve (GL-only)** – Many small image tiles explode outward over a black underlay, briefly rotating before falling back into place as tiles of the next image. Implemented via instanced tile geometry driven by the compositor, reusing Block Puzzle division logic.
- [ ] **3D Block Spins (GL-only)** – Evolution of Block Puzzle where tiles behave as thin 3D slabs with visible thickness and glossy edges as they rotate from old image to new image. Implemented as instanced 3D-ish boxes with per-instance transforms.
- [ ] **Claw Marks (GL-only)** – Sharp claw/scratch paths tear open the current image, widening over time until the entire frame is replaced by the next image. Implemented as a procedural mask-based reveal in a fullscreen shader.

All five concepts are documented in more detail (feasibility, performance notes, and blockers) in `Docs/GL_Transitions_Proposal.md`. They are **GL-only** and must be hidden or mapped to safe CPU fallbacks when `display.hw_accel` is disabled.