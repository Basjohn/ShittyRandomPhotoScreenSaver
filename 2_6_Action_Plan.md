# 2.6 Action Plan (Full Detail Edition)

> This is the single authoritative plan that merges **every** item from the active Sanity Audit and **all** sections of `Docs/Feature_Investigation_Plan.md` (0–12). Nothing has been shortened—each entry retains its goals, research notes, references, module callouts, checklists, and pitfalls. Work proceeds phase-by-phase; do not skip ahead unless explicitly approved. Status legend: `[ ]` pending, `[~]` in progress, `[x]` complete.

---

## Phase 0 – Core & Infrastructure Hardening

Stabilize logging, threading, resource ownership, settings/schema alignment, and event plumbing so downstream features are built on solid ground.

### 0.1 Logging & Diagnostics
**Goal:** Make logging lifecycle predictable and documented so repeated init/shutdown cycles do not leak handlers or write logs to phantom directories.  
**Current State / Findings:**  
- `setup_logging()` is re-entrant but only partially tears down handlers, causing duplicated file descriptors when toggled.  
- `_FORCED_LOG_DIR` / `_ACTIVE_LOG_DIR` semantics are unclear, leading to discrepancies when logging is disabled.  
- Colored console formatter assumes TTY, spamming escape codes in redirected logs.  
- `.perf.cfg` and `.logging.cfg` files produced by build scripts are undocumented in Spec/Style guides.  
**Modules:** `core/logging/logger.py`, build scripts writing cfg files, `Docs/Spec.md`, `Docs/STYLE_GUIDELINES.md`, `Index.md`.  
**Checklist:**  
- [ ] Tear down existing handlers before reinitializing and clearly document lifecycle.  
- [ ] Clarify forced/active log dir semantics and raise/log when logging is disabled but helpers are invoked.  
- [ ] Auto-disable ANSI coloring when `stdout` is not a terminal.  
- [ ] Describe `.perf.cfg` / `.logging.cfg` generation and expected values in Spec + Style guide.  
- [ ] Ensure build outputs reference the same contract (ties to Phase 6 tooling tasks).  
**Pitfalls:** Avoid double-writing logs or silently discarding them; ensure documentation covers frozen builds vs dev builds.

### 0.2 ThreadManager & ResourceManager
**Goal:** Guarantee every thread-related resource is tracked, cancellable, and observable.  
**Current State / Findings:**  
- `_UiInvoker` and futures/timers are instantiated without ResourceManager registration.  
- Mutation queue silently drops entries without counter metrics.  
- `cleanup_all()` runs even when invoked off the UI thread, risking deadlocks.  
**Modules:** `core/threading/manager.py`, `core/resources/manager.py`, `tests/perf/test_thread_manager_contention.py`.  
**Checklist:**  
- [ ] Register `_UiInvoker`, ThreadManager timers, and task futures with ResourceManager; unregister when complete.  
- [ ] Surface queue drop counts via `inspect_queues()` and expose to tests/logs.  
- [ ] Enforce UI-thread cleanup: marshal `cleanup_all()` to the main thread or warn + abort when called elsewhere.  
- [ ] Provide deterministic single-shot helper that respects QApplication lifecycle (per audit).  
**Pitfalls:** Do not rely on GC finalizers; explicit unregister is required to avoid zombie entries.

### 0.3 Settings Authority
**Goal:** Align defaults, schema, and runtime manager to prevent cache blow-ups and key drift.  
**Current State:**  
- Cache keys use `id(default)`, resulting in misses and unbounded growth.  
- Flattened defaults reintroduce conflicting key paths (e.g., `display.mode`).  
- `set_many` emits change signals for each key, overwhelming UI.  
- SettingsManager never registers with ResourceManager; repeated instantiations leak QSettings handles.  
**Modules:** `core/settings/defaults.py`, `core/settings/schema.py`, `core/settings/settings_manager.py`, docs referencing settings.  
**Checklist:**  
- [ ] Remove `id(default)` cache keying; adopt per-key sentinel strategy with eviction.  
- [ ] Align schema names with defaults and ensure flattening respects canonical path. Document in Spec/Index.  
- [ ] Add batch update context that emits a single aggregated signal.  
- [ ] Register SettingsManager with ResourceManager and clean change handlers on destruction.  
**Pitfalls:** Ensure Presets and Spec tables are updated simultaneously; mismatched docs create regressions.

### 0.4 Event System
**Goal:** Prevent subscription leaks and clamp history/recursion depth reliably.  
**Findings:** Subscriptions never auto-unsubscribe, `_publish_depth` grows per-thread, and history cannot be disabled (privacy risk).  
**Modules:** `core/events/event_system.py`.  
**Checklist:**  
- [ ] Provide RAII/context-managed subscription objects that auto unsubscribe.  
- [ ] Purge `_publish_depth` entries even when exceptions occur; use `try/finally`.  
- [ ] Add option to disable history or redact payloads; document in Spec.  
**Pitfalls:** Ensure thread safety when modifying subscription map while publishing.

### 0.5 Engine / Rendering Foundations
**Goals:** Clean teardown and GL resource tracking.  
**Findings:**  
- ScreensaverEngine double-emits `stopped`, keeps ProcessSupervisor alive during settings dialog, and doesn’t store subscription IDs.  
- DisplayManager creates ad-hoc ResourceManagers, leaving hotplug signals connected post-cleanup.  
- GL compositor and DisplayWidget instantiate GL managers/textures without ResourceManager tracking.  
**Modules:** `engine/screensaver_engine.py`, `engine/display_manager.py`, `rendering/gl_compositor.py`, `rendering/display_widget.py`.  
**Checklist:**  
- [ ] Capture subscription IDs, unsubscribe on cleanup, ensure timers/workers shut down once.  
- [ ] Inject ResourceManager/ThreadManager dependencies; disconnect Qt signals and document lifetimes.  
- [ ] Register GL resources (program caches, textures, geometry) with ResourceManager and free deterministically.  
**Pitfalls:** Avoid raw `QTimer` usage inside engine; align with ThreadManager policy.

---

## Phase 1 – UI Shell, Dialog Consistency, and QuickNotes Governance

Enforce a single popup chrome (StyledPopup), remove raw timers, sync QSS + Style Guide, and document deferred widgets.

### 1.1 StyledPopup Adoption
**Goal:** Every dialog (settings, toasts, popups, tooling) uses the frameless StyledPopup that mimics “Export Complete”.  
**Current State:** Custom classes (`NoSourcesPopup`, `ResetDefaultsDialog`) duplicate drop shadows/title bars, diverging from spec.  
**Modules:** `ui/settings_dialog.py`, `ui/tabs/*`, `widgets/*`, `main.py`, tooling dialogs.  
**Checklist:**  
- [ ] Replace bespoke dialogs and any `QMessageBox` remnants with `StyledPopup.show_*` helpers.  
- [ ] Centralize button definitions (labels, values, defaults) so confirmations share copy and layout.  
- [ ] Update doc references banning `QMessageBox` and ad-hoc dialog frames.  
**Pitfalls:** Ensure popups triggered from background threads marshal via ThreadManager to UI thread.

### 1.2 Timer Policy
**Goal:** No raw `QTimer.singleShot` in UI code; timers should either be registered with ResourceManager or scheduled via ThreadManager.  
**Checklist:**  
- [ ] Replace toast/auto-dismiss timers with ThreadManager helpers; register any remaining QTimers.  
- [ ] Document pattern in Style Guide and enforce via tests.  
**Pitfalls:** Many modules create timers before QApplication exists—add guards or no-ops with warnings to avoid crashes.

### 1.3 Theming & Documentation
**Goal:** Align `themes/dark.qss` and Style Guide with StyledPopup + shared palette.  
**Checklist:**  
- [ ] Clean up duplicate selectors, add StyledPopup-specific rules, convert hard-coded RGBA values into shared tokens.  
- [ ] Expand Style Guide section 5 with concrete selectors, layout margins, icon glyph references, and behavior rules.  
- [ ] Cross-reference in Feature Plan so future requests cite this canonical implementation.  
**Pitfalls:** Keep theme changes scoped; avoid regressing other widgets by touching unrelated selectors.

### 1.4 Tests & QuickNotes
- [ ] Extend `tests/test_settings_dialog.py` (and other UI suites) to ensure StyledPopup usage, asynchronous operations, and ResourceManager cleanup.  
- [ ] Document QuickNotes widget deferral (Feature Plan §0): status 🚫, revisit trigger “storage/hover backlog reduced”. Keep note visible so future phases know it remains intentionally deferred.

---

## Phase 2 – Sources Tab Responsiveness, RSS Priority & Dedupe, “5 Images” Guard

Implement the in-depth plan from Feature Investigation §8 while resolving audit issues in sources modules.

### 2.1 Responsive Sources Tab
**Goal:** Folder scans, cache clears, RSS refreshes must not block the settings dialog.  
**Checklist:**  
- [ ] Move heavy operations to ThreadManager IO pool; surface progress via EventSystem (with optional progress modal).  
- [ ] Keep buttons enabled/disabled appropriately and allow cancellation when possible.  
**Pitfalls:** Ensure ThreadManager single-shot is not invoked before QApplication instantiation.

### 2.2 Priority & Multi-select UX
**Details (from Feature Plan §8):**  
- Priority equals list order; label rows with “Priority #”.  
- Add ExtendedSelection (Shift/Ctrl/mouse drag) for batch removal.  
- Keep numbering current after reorder/add/remove.  
**Modules:** `ui/tabs/sources_tab.py`, `engine/screensaver_engine.py`, `core/settings/settings_manager.py`, `Spec.md`.  
**Checklist:**  
- [ ] Display priority numbers in the UI (delegate or suffix).  
- [ ] Persist ordering in settings; ensure “Just Make It Work” writes feeds sorted by desired priority.  
- [ ] Update tooltips/docs to explain priority semantics.  

### 2.3 Cache & Dedupe Unification
**Goal:** Consolidate the multiple dedupe layers (engine queue, `_rss_pipeline.record_images`, worker cache, disk cache).  
**Checklist:**  
- [ ] Map all dedupe checkpoints and pick a single owner (likely pipeline manager).  
- [ ] Broadcast generation tokens on cache clears so workers stop referencing stale `_cached_urls`.  
- [ ] Instrument dedupe decisions (per feed) for diagnostics.  
**Pitfalls:** Do not expand manifest size; consider probabilistic filters only if measured collision risk is low. All resets must run through ThreadManager (no UI blocking).  

### 2.4 “5 Images” Startup Guard
**Details:** Screensaver must not launch in RSS-only mode until at least five images are downloaded; once guard is satisfied, downloads continue asynchronously. Hybrid mode may fall back to local sources.  
**Modules:** `engine/screensaver_engine.py`, `_rss_pipeline`, UI actions (“Clear Cache”, “Remove All”, “Just Make It Work”).  
**Checklist:**  
- [ ] Add guard counter with pause/resume hooks in `_rss_pipeline` (`pause_after(count)` semantics).  
- [ ] When guard active, UI-triggered operations should only fetch five synchronous images before returning control.  
- [ ] Emit guard start/stop events and add telemetry for startup latency.  
- [ ] Tests: extend `tests/test_screensaver_engine_rss_seed.py` to assert guard behavior and hybrid bypass.  
**Pitfalls:** Ensure guard cooperates with cache clears mid-download; resets should keep the 5-image limit. Avoid raw timers; rely on ThreadManager scheduling.  

### 2.5 Reddit Rate Limits & Research
**From Feature Plan:** Document current Reddit activity windows and rate limits (backoff > 60s?). Ensure UI priority interplay doesn’t stall entire queue when Reddit feeds are throttled. Add research notes to Spec.  

---

## Phase 3 – Widgets, Shadows, Fade Coordination, Weather & Reddit Options, Pixel Shift

Implement Feature Plan sections 3–7 alongside audit findings.

### 3.1 Drop Shadow System Review (Feature Plan §3)
**Goal:** Migrate to central `ShadowFadeProfile`, reduce QGraphicsEffect overhead, and document canonical shadow profiles.  
**Checklist:**  
- [ ] Enumerate all `QGraphicsDropShadowEffect` usages (including `shadow_utils_old`).  
- [ ] Define card vs badge profiles (radius 8px/4px, offsets, alpha).  
- [ ] Prototype GL overlay shadow strips (Spotify card) to avoid effect corruption.  
- [ ] Update Docs/10_WIDGET_GUIDELINES.md + Style Guide with diagrams, offset values, and references to Qt performance research [^1][^2].  
**Pitfalls:** Keep fade-sync logic intact; ensure new profiles integrate with `ShadowFadeProfile`.  

### 3.2 WidgetManager Reliability
- [ ] Register/unregister widgets, timers, and fade callbacks with ResourceManager; disconnect compositor signals on teardown.  
- [ ] Document expected overlay/fade handshake so widgets know when to register.  

### 3.3 Spotify Volume Widget Fade Coordination (Feature Plan §4)
**Checklist:**  
- [ ] Add guarded log verifying `request_overlay_fade_sync("spotify_volume")` is invoked before fade start.  
- [ ] Ensure `add_expected_overlay()` happens before anchor widget triggers the fade.  
- [ ] Add regression test (`tests/test_widget_fade_sync.py`) simulating volume/visualizer handshake.  

### 3.4 Spotify Visualizer Enhancements (Feature Plan §5)
**Goal:** Ship new GLSL visualizer modes (morphing waveform ribbon, DNA helix, radial bloom, spectrogram ribbon, phasor particle swarm) without altering the existing Spectrum mode implementation or performance envelope.  
**Requirement:** Spectrum bar mode remains untouched; all new work layers on top of the current FFT pipeline and widget plumbing.  

**Shared Constraints & Defaults:**  
- Maintain the current card footprint (width/height, padding, chrome) unless the user toggles the new “Vertical orientation,” in which case geometry rotates and DisplayWidget repositions the overlay.  
- Reuse existing settings infrastructure @widgets/spotify_visualizer_widget.py#1-948, overlay chrome @widgets/spotify_bars_gl_overlay.py#1-151, and FFT plumbing @widgets/spotify_visualizer/beat_engine.py#1-314.  
- Introduce `spotify_visualizer.mode` (default `spectrum`). Presets: `Cinematic` → helix, `Artistic` → waveform. Each mode gains scoped defaults (e.g., `helix.twist=1.0`, `waveform.ribbon_thickness=0.35`, `phasor.particle_count=128`).  
- Add per-mode settings for thickness, twist, history depth, particle count, etc., surfaced in Widgets tab along with a vertical orientation toggle and any auxiliary controls (opacity multipliers, ribbon offset).  

**Performance Considerations vs Spectrum:**  
- Morphing Waveform Ribbon: ~parity (reuse existing VBO, single strip; CPU overhead negligible).  
- DNA Helix: ~1.2× shader cost due to dual curve calculations but still within present shader complexity.  
- Radial Bloom: Equal when clamped to semicircle; full radial (vertical orientation) is ~1.1× fragment load.  
- Spectrogram Ribbon: Heavier (history buffer). Limit stored frames to ≤32 and auto-degrade to 16 under GPU pressure.  
- Phasor Particle Swarm: Comparable if particle count = bar count × 4; default 128 particles to match current fill rate.  

| Mode | Description | External Inspiration |
| --- | --- | --- |
| Morphing Waveform Ribbon | Mirror waveform that morphs in place (no scrolling) while preserving card bounds. | TimArt/3DAudioVisualizers[^3] |
| DNA Helix | Dual helices twisting with amplitude and optional slow Z scroll (“growth”). | ShaderToy `dtl3Dr`[^4] |
| Radial Bloom | Clamp GLava’s radial shader into a semicircle (horizontal) or full circle (vertical orientation). | GLava radial module[^5] |
| Spectrogram Ribbon | Stack recent FFT frames as translucent ribbon layers above/below bars. | Stanford CCRMA OpenGL viz[^6] |
| Phasor Particle Swarm | Replace solid bars with particle emitters along the same x positions; swirling phasor trails capture beats. | PAV “Phasor”[^7] |

**Implementation Steps:**  
1. Add `spotify_visualizer.mode` enum + per-mode settings (thickness, twist, particle count, history depth) + vertical orientation toggle in Widgets tab UI; ensure config persists in `core/settings/defaults.py`, `core/settings/models.py`, and presets.  
2. Implement GLSL programs for each mode under `widgets/spotify_visualizer/*`, sharing buffers with Spectrum wherever possible; capability detection should fall back to Spectrum whenever GL requirements fail (session-scoped demotion only).  
3. Update DisplayWidget / overlay layout so card rotation + padding adjustments respect orientation toggle without breaching ShadowFadeProfile constraints.  
4. Update presets (`Cinematic` helix defaults, `Artistic` waveform) and document tables in Spec.md & Index.md.  

**Testing & Telemetry:**  
- Headless GL smoke tests to initialize each mode (mock GL context) and assert no errors.  
- Config persistence tests covering mode switches + preset application (ensure `config.json` writing is stable).  
- GL uniform budget snapshot tests comparing each mode vs Spectrum to ensure no unexpected uniform uploads/VBO allocations.  
- Guard any new performance logging behind `SRPSS_PERF_METRICS`; reuse `screensaver_perf.log` pipeline.  

**Modules / References:** `widgets/spotify_visualizer_widget.py`, `widgets/spotify_bars_gl_overlay.py`, `widgets/spotify_visualizer/*`, `ui/tabs/widgets_tab.py`, `core/settings/defaults.py`, `core/settings/models.py`, `Spec.md`, `Docs/Feature_Investigation_Plan.md`, `tests/visualizer/*`.  

**Pitfalls:** Maintain existing ghosting/adaptive sensitivity logic across modes (shared helpers); never mutate Spectrum shader/perf caps; capability detection must demote once per session (no per-call silent fallbacks); ensure vertical orientation keeps card bounds consistent with Widget Guidelines.  

### 3.5 Weather Widget – Animated SVG Icons (Feature Plan §6)
**Goal:** Replace text-only widget with animated SVG icons using `QSvgRenderer`.  
**Checklist:**  
- [ ] Promote to QWidget + QHBoxLayout (text column + icon container) so layout alignment is reliable.  
- [ ] Load icons via `QSvgRenderer`, set `framesPerSecond`, and connect `repaintNeeded` to `update()` (no extra timers).  
- [ ] Add settings for `widgets.weather.icon_scale` and animation toggle (defaults documented).  
- [ ] Maintain small LRU cache (≤6 renderers) and pause animations during transitions.  
- [ ] Map provider condition codes to `images/weather/manifest.json`.  
- [ ] Tests: throttle repaint signal counts, ensure caching works, update `tools/download_weather_icons.py` if needed.  
**Pitfalls:** Do not spawn extra threads; rely on renderer’s animation driver. Document fallback to static icons when animation disabled.  

### 3.6 Reddit Widget Options & Header Parity (Feature Plan §7 + §7.1)
**Checklist:**  
- [ ] Rename “Exit when Reddit links opened” to “Open When Reddit Links Are Clicked”; add “Copy Clicked Reddit Links To Clipboard” checkbox.  
- [ ] Enforce mutual exclusivity except on MC builds (where both can be enabled); reuse `self._mc_build` gating.  
- [ ] Update click handler (`rendering/display_widget.py`) to set clipboard text before executing action.  
- [ ] Migrate settings key (`widgets.reddit.exit_on_click` → `widgets.reddit.open_on_click`) with `SettingsManager.validate_and_repair()` shim. Update presets + Spec tables.  
- [ ] Add header frame toggle/styling parity with Spotify widget; update Widget Guidelines to require header frame options for all widgets with headings/logo.  
- [ ] Tests: `tests/ui/test_widgets_tab.py` for mutual exclusivity + persistence.  
**Pitfalls:** Ensure tooltip text adheres to Style Guide (no inline QSS). Document MC vs normal builds difference.  

### 3.7 Pixel Shift Boundary Enforcement (Feature Plan §7.2)
**Checklist:**  
- [ ] Audit `DisplayWidget._apply_pixel_shift()` to clamp overlay rects within `screen_geometry.adjusted(margins)`.  
- [ ] Provide per-widget bounding boxes via WidgetManager (notify overlays when geometry shifts).  
- [ ] Add regression test simulating max pixel shift deltas on multi-monitor setups to ensure widgets remain fully visible.  
- [ ] Update Widget Guidelines (positioning section) with pixel-shift constraints.  

---

## Phase 4 – Transitions & Display Enhancements (Feature Plan §2)

Deliver all transition/UI enhancements plus DisplayWidget hygiene items.

### 4.1 Image Cache Slider (Feature Plan §2.1)
- [ ] Raise `cache.max_items` default to 30 (min 30, max 100). Add slider + spinbox near RSS cache controls, persist via SettingsManager, and trigger cache/prefetcher reinit without restart.  
- [ ] Update presets (Performance, Balanced) to 60/90 respectively and document in Spec/Index.  
- [ ] Ensure ThreadManager handles heavy reinit work to avoid UI freezes.  

### 4.2 Transition Controls
**Blinds Feather Control (§2.2):**  
- [ ] Slider (0–10) shown when Blinds selected; thread value through TransitionFactory to GL shader uniform.  
- [ ] Clamp for software renderer fallback; update presets and docs.  

**Particle Direction Disable (§2.3):**  
- [ ] `_update_particle_mode_visibility()` should disable direction combo when mode == Converge, preserving stored value for other modes.  
- [ ] Document in Spec preset table.  

**3D Block Spins Enhancements (§2.4):**  
- [ ] Extend direction enum for diagonal travel, add sheen toggle, axis blending, and random mode caching so repeated transitions honor user choice.  
- [ ] Update shader to support new directions and add capability gate for GL < 3.3.  
- [ ] Presets: Cinematic uses “Diagonal TL→BR” with high sheen.  

**Peel Transition Options (§2.5):**  
- [ ] Add slice-width slider, diagonal directions, motion-blur toggle; gate via `_refresh_hw_dependent_options()` so non-GL builds hide controls.  
- [ ] Update shader uniforms and documentation.  

**Block Puzzle Flip Direction Matrix (§2.6):**  
- [ ] Extend shared direction enum with `BlockPuzzleDirection` (Up/Down/Left/Right/Diagonal TL→BR/Diagonal TR→BL/Center Burst/Random).  
- [ ] Show direction combo only for Block Puzzle Flip; persist random choice per rotation, update TransitionFactory + GL shader uniforms, add CPU fallback for software renderer.  
- [ ] Tests: extend `tests/test_transition_state_manager.py` and related suites to cover new enumeration.  

### 4.3 Display/Rendering Hygiene
- [ ] Align documentation of `_render_strategy_manager` fallback with actual behavior; ensure software renderer downgrade path is deterministic.  
- [ ] Document (or plan) DisplayWidget refactor to separate input, overlay, and eco mode responsibilities as per audit.  

---

## Phase 5 – Input, Media Integration, RSS Extensions, QuickNotes Re-entry

Execute Feature Plan §1, §12, and remaining media/widget items after earlier phases are stable.

### 5.1 Global Media Key Passthrough (Feature Plan §1)
**Goal:** Media keys always invoke OS actions (play/pause/next/volume) across all builds; no suppression.  
**Current State:**  
- `InputHandler.handle_key_press()` returns `False` when `_is_media_key`, but `DisplayWidget.keyPressEvent()` still accepts the event, blocking OS passthrough.  
- Tests currently confirm suppression (behavior to invert).  
**Settings Defaults / Presets:**  
- Introduce `input.media_keys.passthrough_enabled = True` in defaults and ensure MC preset matches. Document in Spec keybinding table.  
**Modules:** `rendering/display_widget.py`, `rendering/input_handler.py`, `core/engine/input_hooks.py`, `core/settings/defaults.py`, `tests/test_media_keys.py`, `Spec.md`.  
**Checklist:**  
- [ ] Update `DisplayWidget.keyPressEvent()` to `event.ignore()` when `_is_media_key` returns `False` so OS receives event.  
- [ ] Review `nativeEventFilter` (Index: `core/engine/input_hooks.py`) to ensure WM_APPCOMMAND isn’t consumed prematurely.  
- [ ] Add optional helper `platform/win32/media_passthrough.py` to replay WM_APPCOMMAND when fullscreen focus still blocks keys; gate fallback commands via setting.  
- [ ] Add default/preset entry + Spec table updates; ensure Standard, Minimal, MC builds align.  
- [ ] Extend `tests/test_media_keys.py` to assert passthrough and absence of unintended exits.  
**Pitfalls:** Avoid double-triggering actions; respect “exit on any key” logic and ensure MC vs Saver builds both behave correctly.

### 5.2 Spotify Volume Telemetry
- [ ] Ensure perf harness obeys `SRPSS_PERF_METRICS`; logging toggles should not spam production logs.  
- [ ] Add metrics summary to perf docs/harness as per audit.  

### 5.3 Reddit Priority Beyond RSS
- [ ] After Phase 2’s UI priority work, confirm Reddit widget + presets/docs reflect new ordering, especially for “Just Make It Work” and future priority-based features.  

### 5.4 AlphaCoders / RSS HTML Feeds (Feature Plan §12)
**Goal:** Determine feasibility of pulling curated AlphaCoders galleries into RSS/JSON pipeline.  
**Unknowns:** Endpoint availability, rate limits/ToS, API keys, CDN link resolution, attribution rules.  
**Checklist:**  
- [ ] Research AlphaCoders developer docs/forums for RSS/JSON endpoints; if none, prototype HTML parser (requests + selectolax) extracting `{title, image_url, source_url}`.  
- [ ] Decide whether to extend `RSSSource` (virtual feeds) or create `AlphaCodersSource`.  
- [ ] Evaluate caching impact (4K images) and ThreadManager budget for multi-MB downloads.  
- [ ] Document findings in Spec (Sources section) and update Feature Plan status.  
**Pitfalls:** Must respect licensing/attribution. Significant size may require adjusted cache policies.  

### 5.5 QuickNotes Re-entry
- [ ] Once Settings UI backlog shrinks and storage constraints are handled, revisit QuickNotes widget (Feature Plan §0). Document new scope, dependencies, and gating criteria.  

---

## Phase 6 – Documentation, Testing, and Tooling

Keep docs/tests/tools synchronized with implementation.

### 6.1 Documentation Sync
- [ ] Update `Docs/Spec.md`, `Index.md`, `Docs/Feature_Investigation_Plan.md`, and `audits/SanityAudit.md` whenever new settings/modules ship.  
- [ ] Refresh `Docs/10_WIDGET_GUIDELINES.md` and `Docs/STYLE_GUIDELINES.md` with: shadow profiles, header frame policy, tooltip conventions, pixel shift constraints, StyledPopup selectors, timer policy, Spotify/Weather widget instructions.  
- [ ] Maintain Feature Investigation doc as living record—sections should note when work moves into action plan or completes.  

### 6.2 TestSuite & New Suites
- [ ] `Docs/TestSuite.md` must catalog new suites: thread contention, fade coordination, weather SVG timing, visualizer mode snapshots, RSS guard tests, etc., plus PowerShell invocation snippets per policy.  
- [ ] Implement referenced test files (`tests/perf/test_thread_manager_contention.py`, `tests/ui/test_fade_coordination.py`, `tests/widgets/test_weather_icons.py`, `tests/visualizer/test_modes.py`, etc.).  

### 6.3 Tooling & Scripts
- [ ] **`scripts/build_nuitka.ps1`:** add venv awareness, `--skip-install` flag, helper payload checksum validation, doc references for `.perf.cfg`/`.logging.cfg`, safer SCR rename (warn before deleting signed binary).  
- [ ] **`tools/run_tests.py`:** limit `__pycache__` purges (scope by path or make opt-in), detect missing `tests/pytest.py`, lock log rotation for concurrent runs.  
- [ ] **`tools/perf_integration_harness.py`:** respect ResourceManager/ThreadManager policies, avoid global env mutations, share timer helpers with main app.  
- [ ] **Metrics parsers/log parser:** unify parsing/stat helpers between Spotify VIS & slide metrics scripts; allow config-driven keyword categories for overlay log parser; tie scripts to perf/log env docs.  
- [ ] **Visualizer/overlay harnesses:** expose public APIs (no poking private attributes), register widgets with ResourceManager, consolidate FFT/intensity helper code.  

---

## Phase 7 – Monitoring, Future Widgets, Continuous Auditing

Long-range coordination once core work is complete.

- [ ] **Future Widget Program:** Maintain `Docs/Future_Widget_Plans.md` for Imgur, Flickr, ArtStation, Tumblr, etc., ensuring prerequisites (shadow centralization, WidgetManager cleanup, perf harnesses) are satisfied before implementation.  
- [ ] **RSS HTML Scrape Feasibility:** Continue AlphaCoders/offline feed research, update plan with blockers or schedule once Phase 2 stabilizes.  
- [ ] **Audit Trail:** After finishing each phase, append findings/resolutions to `audits/SanityAudit.md` and track new risks.  

---

## References
[^1]: Qt Forum – “why program is so laggy after using QGraphicsDropShadowEffect.”  
[^2]: *Performance and Solutions for QWidget::setGraphicsEffect()* – warns against per-widget effects.  
[^3]: TimArt, *3D Audio Visualizers* (GitHub) – waveform inspiration.  
[^4]: ShaderToy `dtl3Dr` – DNA helix visualization.  
[^5]: GLava radial shader – basis for radial bloom mode.  
[^6]: Stanford CCRMA, *Sound Visualization with OpenGL* – spectrogram ribbon reference.  
[^7]: Processing Audio Visualization (PAV) “Phasor” – particle swarm inspiration.  
[^8]: Qt 6.8 `QSvgRenderer` docs – animated SVG guidance.  

---

### Usage Notes
1. Always pull work from the **lowest-numbered** phase with unfinished items.  
2. Update checklist status inline with notes when scope changes; never remove context.  
3. Mirror completions in Spec/Index/TestSuite + audits immediately.  
4. Treat this document as the single source of truth—new discoveries should be added to the appropriate phase or a new phase, not scattered elsewhere.
