In this document neatly arrange, date and detail significant bugs that were fixed in the project.
Include failed solutions and reasoning why the final solution worked. Never remove from this document unless asked, use it as a guide to avoid falling back into bad habbits.
Section by date and type.

######                        ######
#### UNRESOLVED BELOW THIS LINE ####

## PENDING RUNTIME / LIFECYCLE BUG: Reddit Helper Process Lingering After App Close

- **Current symptom:** `SRPSS_RedditHelper` can remain alive long after the main application path has closed.
- **Why this is tricky:** secure-desktop / SYSTEM screensaver runs cannot rely on polite cleanup or normal process-lifetime ownership, so “just exit the helper when the app exits” is not a sufficient model by itself.
- **Architecture note:** this should be solved through explicit helper-lifecycle ownership rules:
  - heartbeat/singleton semantics
  - stale-session or stale-owner detection
  - different rules for installed HKCU Run watcher vs preview/script bootstrap
- **Progress landed (Mar 28 2026):**
  - MC builds now skip helper bootstrap entirely instead of pointlessly carrying the queue watcher model into a direct-open path
  - installed helper launches can now be either persistent or session-scoped depending on the runtime ownership request
  - session-scoped launches now pass `owner-pid` + idle-exit even when the installed helper binary is the command we launch
  - worker exits once the owner is gone and the queue stays idle long enough
  - normal graceful app shutdown now writes an explicit session-owned helper shutdown request so runtime does not have to wait out the whole idle-exit grace window
  - watcher mode now has a per-session singleton guard, so duplicate launches exit instead of stacking multiple lingering helpers
  - stale helper heartbeat pids are now reaped by the user-session runtime before relaunch, so a wedged watcher cannot block recovery forever
- **What is still pending:** real installed SCR validation that the persistent watcher behavior is acceptable and does not create a worse long-lived process problem than the preview/script linger we already fixed.
- **Anti-pattern warning:** do not paper over this with fragile one-shot cleanup hooks that only work when Windows allows a graceful exit path.

## MAJOR VISUAL BUG: Settings Dialog Flicker / Placeholder Regression — Historical Investigation Archived

- **User later confirmed this issue is resolved in live use (Mar 22 2026).**
- The investigation record is retained below because several failed approaches are still useful anti-patterns. The final working state is summarized in the resolved entry dated **2026-03-22**.

- **Problem statement:** On MC builds we only render the fullscreen DisplayWidget on Display 1 while Display 0 remains a normal Windows desktop (winlogon is *not* involved). When we summon Settings (which still launches on Display 0), `engine.stop(exit_app=False)` tears down the MC window on Display 1 *and* leaves Display 0 unprotected for ~3 s while the dialog constructs. Windows fills that gap with a security-style popup that shows a lock icon and rapidly flickers. This is **not** historical behavior; the regression appeared after the March 13 settings work. **Update:** running `main.py` in script mode (non-winlogon screensaver) exhibits the exact same flicker, proving the bug is tied solely to the settings dialog invocation/creation path and is independent of build flags or MC-only windowing.
- **MC-specific observations supplied by user:**
  - Flicker occurs on whichever display is about to host the settings dialog even if that display never had SRPSS content (e.g., MC pinned to Display 1, dialog on Display 0).
  - Switching MC window flags between `Qt.SplashScreen` and `Qt.Tool` does **not** change the outcome; the secure popup still flashes.
  - Adding the `SettingsShieldManager` overlay not only failed to help, it added a second flicker on top of the MC display, so shields are now fully disabled.
  - The issue never repros in screensaver mode (every monitor has a DisplayWidget) which re-confirms this is an MC-only regression tied to mixed content across monitors, not Winlogon.
- **Observed deltas vs ≤ March 12 builds:** identical teardown order except for shields, but settings used to appear almost instantly, suggesting presentation timing/foreground activation hid the blanking earlier. Currently: log timestamps show ~3 s between “Settings requested” and “Settings dialog created,” during which Windows repeatedly presents the placeholder on the target monitor. 
- User note: Settings always opened slowly and there was no shitty ass flickering when it did.
- **Investigation Hypothesis (user):** MC builds need either (a) the dialog to become visible <200 ms so Windows never paints the placeholder, or (b) a masking strategy that works on *non*-MC monitors without introducing new artifacts. Shields are ruled out; we must find a different architectural fix.

**Approach A – Delay display teardown until dialog is visible** — **FAILED**
- Rationale: Even if teardown is delayed, the dialog often opens on monitor 0 while the compositor/render stack sits on monitor 1 (especially in MC builds where only one display is covered). The moment we finally pause/destroy the compositor, the monitor hosting the dialog will flash Windows’ placeholder, so this approach cannot eliminate flicker without additional masking.

**Approach B – Keep DisplayWidgets composited with a static frame during pause** — **FAILED**
- Rationale: `engine.stop()` always clears and hides every `DisplayWidget` within ~60 ms of the hotkey. Even if we froze the compositor first, the mandatory teardown would still destroy the HWNDs and Windows would drop in its placeholder for the remaining ~3.2 s while `SettingsDialog` builds. Avoiding teardown entirely would violate engine lifecycle contracts (widgets expect cleanup/start) and reintroduce the multi-monitor focus issues that Approach A already failed to solve.

**Approach C – Replace OS placeholder with compositor-controlled blackout** — **FAILED**
- Rationale: Blackout overlays only exist on monitors that currently host DisplayWidgets. MC builds (and script-mode runs) routinely summon Settings on a monitor that **never** had our compositor window, so there is no HWND on that screen to paint the blackout. Windows still shows its placeholder the moment the dialog begins constructing, so this approach cannot solve the regression without an entirely different masking primitive.
- (Historical steps retained for reference)

**Approach D – Cut SettingsDialog construction time to <200 ms without hurting UX** — **FAILED**
- [x] **Target-tab-first creation (no ugly placeholders):**
  [x] **Per-tab styling/shadow application:**
  [x] **Cache heavy-but-static data with freshness checks:**
- **Summary:** Target-tab-first hydration, per-tab styling deferral, and caching are live, but dialog construction still takes ~3 s on MC builds (see latest `screensaver.log`). The flicker persists even when only one monitor hosts SRPSS content, so raw construction speed is insufficient to mask the OS placeholder. Fade-in fallback remains unimplemented and is no longer expected to solve the problem; Approach D is marked failed pending a new direction.

**Approach E – External research before redesign (NEW)**
- [ ] Research and corroborate ROOT CAUSES from **≥5 recent sources** (2024+) focused on Windows multi-monitor Qt apps that mix fullscreen + desktop content. Emphasize findings about secure-desktop placeholders, HWND teardown ordering, and alternative masking primitives. Summarize pros/cons and cite each source before proposing a new architecture.
Mitigation last resort, but unacceptable as early builds of this project did not have this bug.


######
#### RESOLVED BELOW THIS LINE ####
##
##

## 2026-03-28 — Startup Fade / Visualizer Secondary-Stage Ownership Split (Resolved)

**Symptoms**
- Primary overlays could sit behind a compositor-only dead gap and then appear too abruptly instead of following a coordinated fade wave.
- The Spotify visualizer could enter later than before but still in a bad state: jittery first frames, fallback-timer reveal, and occasional startup-side audio restart noise.
- Cold start, mode-cycle recovery, and settings-return recovery could behave differently, which pointed to orchestration drift rather than one isolated renderer bug.

**Root Cause**
- `WidgetManager` / `FadeCoordinator` were the real owners of primary fade state, but Spotify secondary-stage timing still depended on display-local fade/runtime fields.
- That split let coordinator logs look healthy while the live visualizer still followed a different runtime schedule.
- Shared fade behavior also had helper-level leaks: some widgets waited for the first animation tick to become visible, and several callers carried timing literals that were not actually authoritative.

**Fixes**
- Moved Spotify secondary-stage scheduling back under manager-owned control, with display-local fields treated as mirrored readable state rather than a second source of truth.
- Removed the old primary startup dead-gap and fixed the shared fade helper so widgets can become visible immediately at opacity `0.0`.
- Centralized startup contracts into:
  - `rendering/overlay_startup_policy.py` for display-side startup timing
  - `widgets/spotify_visualizer/startup_contract.py` for visualizer staged-startup state
- Delayed visualizer hot-start/reveal behind the centralized Spotify secondary stage, seeded from anchor/media state, and prewarmed shader/overlay work while hidden.
- Blocked the delayed-play startup branch from revealing via fallback before real playback becomes live.
- Restored proper duration-override forwarding so shared fade timing is real policy, not decorative literals.

**Validation**
- Latest user-validated runs covered all three comparison paths:
  - cold start with music already playing
  - full mode cycle back to Spectrum
  - settings open/close and return
- In those runs:
  - primary fade begins at compositor-ready
  - the visualizer reveals through `fresh_frame_ready_delay`, not `fallback_timer`
  - `Audio capture unhealthy, restarting...` no longer appears during startup
  - startup behavior now matches the healthier recovery paths closely enough to close the bug

**Takeaways**
- Keep shared fade ownership centralized. Do not reintroduce display-local scheduling logic that can diverge from manager/coordinator state.
- Prefer narrow mirrored runtime-readable state over duplicate decision-making state.
- If startup needs more polish later, tune it from the shared fade/startup contracts instead of adding visualizer-specific timing hacks.
- Occasional future fade-softness polish is a separate UX tuning topic, not a reason to reopen this resolved startup bug unless the old parity failure returns.


## 2026-02-24 — Spotify Visualizer "Crossover Persistence" (Blob muted after mode switch)

**Symptoms**
- Starting the session in Blob mode behaved normally, but switching into Blob from any other mode (or re-applying Blob via Settings) left radius/glow muted for 5–8 s despite healthy energy readings (`stage_filtered ≈ (1.00,0.03–0.08,0.00)`, radius stuck ~0.27–0.32 while `overall` > 0.6).
- Cold starts (Settings exit) immediately restored reactivity, confirming stale state carried across crossovers rather than shader issues.

**Failed / insufficient attempts**
1. *Overlay-only reset (Jan 2026):* `SpotifyBarsGLOverlay` reset `_blob_stage_progress_*` when `_vis_mode` changed. Helped literal mode flips but not config replays, because the enum often stayed on `blob`.
2. *Widget-only zeroing (Feb 2026 rev 1):* `_reset_visualizer_state()` cleared `_display_bars/_target_bars` and bubble caches but never asked the overlay to reseed, so stale smoothing reappeared on the next GPU push.
3. *Blob smoothing reseed (Feb 2026 rev 2):* Added `_blob_seed_pending` + `_reset_mode_state('blob')` when `_vis_mode` flipped. Still failed whenever settings re-applied Blob without changing the enum.
4. *Overlay reset wiring (Feb 2026 rev 3):* Widget now called `overlay.request_mode_reset()` for `_reset_visualizer_state()` / `_clear_gl_overlay()`. Logs showed `[OVERLAY][RESET]`, yet stage2 remained pinned because the beat engine + widget bars immediately reintroduced stale smoothed data.

**Final fix**
- `_reset_engine_state()` now cancels pending compute tasks, calls `reset_smoothing_state()` / `reset_floor_state()`, replays smoothing config, seeds `_waiting_for_fresh_engine_frame`, and zeros widget bar/energy buffers.
- `_track_engine_generation()` records the post-reset generation so `_on_tick()` blocks GPU pushes (`_waiting_for_fresh_engine_frame`) until `engine.get_latest_generation_with_frame()` reaches the pending generation, guaranteeing Blob never reuses the old smoothing envelope.
- `SpotifyBarsGLOverlay` reseeds `smoothed_energy` on the first non-zero FFT, so stage2 can rise immediately once the engine publishes fresh data.

**Regression coverage & validation**
- Added `tests/test_spotify_visualizer_widget.py::test_blob_crossover_waits_for_fresh_engine_frame`, which stubs the beat engine + overlay bridge, forces a Spectrum→Blob crossover, and asserts GPU pushes remain blocked until the fake engine publishes a new generation with stage2 energy > 0.4.
- Manual log runs (Sine→Blob crossover and Blob cold start, Feb 24) show stage2 surpassing 0.4 within ~1 s after mode switch, with `[SPOTIFY_VIS] Engine delivered fresh frame` immediately clearing the wait gate.

**Takeaways**
- Always reset the shared beat engine, widget bar cache, and overlay state within the same tick when handling cross-mode transitions.
- Gate GPU pushes on fresh FFT generations whenever smoothing state is invalidated.
- Keep regression tests that cover the exact gating contract so future plumbing changes cannot reintroduce stale-state persistence.

## 2026-03-22 — Settings Dialog Flicker / Placeholder Regression (Resolved)

**Symptoms**
- Opening Settings from the screensaver/MC flow could produce a bad Windows placeholder/flicker moment while the dialog came up.
- The regression was especially visible in mixed monitor setups and became tied to the settings invocation path rather than image rendering itself.

**Failed / insufficient attempts**
1. Shield overlays and masking experiments did not solve the root problem and could add their own flicker.
2. Pure teardown-order tweaks were not enough on their own because the settings path still had visible timing gaps.
3. Early placeholder-tab work and caching helped, but were not originally considered sufficient in isolation.

**Final working state**
- The screensaver/settings handoff now keeps the workflow on the safe path guarded by `tests/test_s_hotkey_workflow.py`: opening Settings hides display windows instead of leaving fullscreen content in a half-torn state over the dialog.
- `SettingsDialog` builds the initial tab immediately and hydrates remaining tabs asynchronously, reducing visible construction pressure during first paint.
- Flicker-regression coverage also lives in `tests/test_flicker_fix_integration.py`, including guards around immediate fullscreen presentation and avoiding `processEvents()`-style races in transition code.

**Validation / guardrail**
- User later confirmed the settings flicker is resolved in live use.
- Keep `tests/test_s_hotkey_workflow.py` and `tests/test_flicker_fix_integration.py` as the minimum regression bar before reworking settings launch flow again.

**Takeaways**
- Do not reintroduce shield-style masking as a first response.
- Keep the settings launch path explicit and test-guarded: hide displays cleanly, paint Settings quickly, and avoid event-loop race hacks.

## 2026-03-22 — MC Keyboard Focus / Ctrl Halo Interaction Regressions (Partially Resolved; Halo Click Path Still Under Watch)

**Symptoms**
- MC hotkeys and media keys could stop working after interaction clicks.
- Ctrl-held suppression could drift across local/global/handler state.
- Cursor Halo behavior regressed around compositor interaction: it could fail to return after slight coordinate drift, and hard-exit interaction clicks could make it vanish immediately.

**Failed / insufficient attempts**
1. Relying on only one Ctrl-held source was too fragile; focus/ownership drift could leave different subsystems disagreeing about whether interaction mode was active.
2. Halo behavior tied too closely to raw move events was vulnerable to compositor coordinate drift and click-driven focus churn.
3. A later "simplify it" experiment that made the top-level Halo window `WA_TransparentForMouseEvents` was a regression: clicks could escape the compositor/widget tree instead of being forwarded through the real display interaction path, which in turn worsened click swallowing and shadow-side fallout. Do not reintroduce that top-level transparent Halo path as a casual cleanup.

**Final fix**
- `display_input._ctrl_interaction_active()` now resolves Ctrl-held state across local widget state, coordinator state, deprecated global state, and handler state.
- `InputHandler.handle_ctrl_press()` explicitly marks handler-held state, so downstream guards agree even after interaction/focus churn.
- MC interaction clicks now perform a best-effort focus reclaim via `display_input._restore_mc_input_focus()`, which keeps keyboard/media support alive after clicking overlays.
- `display_input.show_ctrl_cursor_hint()` clamps small compositor drift back inside the display instead of treating it as a real out-of-bounds exit.
- `display_input.handle_mousePressEvent()` now refreshes halo visibility/activity after interactive clicks in hard-exit mode, so clicking compositor elements no longer makes the halo disappear immediately.
- `CursorHaloWidget._forward_mouse_event()` now routes button events back through the fullscreen display root so the existing interaction router, preset cycling, focus reclaim, and halo keepalive logic all run on forwarded clicks.
- Later Mar 22 follow-up: the blanket click-triggered halo keepalive / focus-reclaim calls in `display_input.handle_mousePressEvent()` were backed back out. They were well-intended, but in live use they worsened Halo visibility and click behavior instead of restoring last-commit behavior. The valuable retained parts are the multi-source Ctrl gate, display-root forwarding, and drift clamp.

**Regression coverage & validation**
- `tests/test_mc_keyboard_input.py` guards the focus reclaim path and hotkey behavior.
- `tests/test_dimming_and_interaction_fixes.py` now guards the multi-source Ctrl gate, halo drift clamp, removal of the bad generic click-keepalive path, and display-root halo forwarding contract.
- User confirmed that keys are now working again in script mode.
- Follow-up note (later Mar 22 user validation): keyboard/focus improvements held, but Cursor Halo click passthrough/hide behavior was still not fully correct. Keep treating Halo click behavior as an active issue even though the underlying keyboard-focus repair remains valuable and should not be reverted casually.

**Takeaways**
- Interaction reliability depends on focus reclaim and state agreement together; fixing only one side is not enough.
- Halo lifetime should be treated as its own interaction contract, not just a side effect of mouse-move traffic.
- Halo passthrough must preserve the real display interaction pipeline; bypassing the display root silently breaks preset cycling / keepalive behavior even when focus handling looks correct.
- Top-level transparent Halo windows are not equivalent to real compositor passthrough in this project; preserving forwarded ownership is safer than assuming Qt click-through will land on the right target.
- When a bug family only partly resolves, keep the resolved sub-contracts documented separately so later work does not accidentally unwind them while chasing the remaining visual issue.

## 2026-03-22 — Blob Ghost/Pulse Investigation (Resolved Subsystems Archived)

**Symptoms**
- Blob spent a long period oscillating between several failure classes:
  - ghost shape mismatch
  - ghost flicker
  - live core briefly hitting the "correct" shape and then snapping back
  - settings that appeared to do nothing, especially when trying to disable kick assist or cap reactive lift
- The user repeatedly reported that Blob could look musically expressive for a moment and then throw jarring oversized pulses unrelated to the actual track.

**Failed / retired approaches**
1. *Delayed-history / state-blend ghost replay:* created obvious "second blob" behavior and visible flicker.
2. *Ghost-only peak time / stage snapshotting:* preserved the wrong motion model and still produced wrong-shape behavior.
3. *Trying to solve the remaining pulse problem as ghost math:* misleading. Once parity returned, the real issue was in the live-core reaction path.

**Root causes that were actually fixed**
- **Divergent live vs ghost source paths:** Blob ghost memory and live uniforms were not always starting from the same processed support signal. That made the ghost look like a different interpretation of the audio.
- **Wrong event-energy ownership:** discrete kick/snare help could leak back into the same `bass/overall` channels driving whole-body scale, creating giant pulses instead of smooth staged growth.
- **Zero-valued controls silently ignored:** parts of Blob’s live-band path still used `... or default` reads, so valid `0` values for settings like `blob_kick_lane_gain`, `blob_pulse_cap`, and transient mixes were replaced by defaults. This made "off" or "minimum" settings feel fake.

**Final working state / guardrails**
- Ghost and live Blob now share the same processed live-band source before ghost hold/decay, restoring silhouette parity.
- Scheduler help is now intentionally asymmetric:
  - continuous `bass/overall` remain the main whole-body support
  - kick assist primarily feeds staged growth inputs
  - snare assist primarily feeds live `mid/high` wobble/stretch behavior
- `blob_pulse_cap` and `blob_pulse_release_ms` were added so reactive lift can be capped and released more gracefully without slowing attack.
- `blob_kick_lane_gain` now genuinely applies to Blob as a real user control; `0%` disables scheduler kick assist for Blob while leaving continuous support and snare-driven deformation available.
- Most importantly: Blob control reads in the live-band path must preserve valid zeroes. Do not reintroduce `... or default` when reading zero-allowed Blob controls.

**Regression coverage & validation**
- `tests/test_ghost_isolation.py` now guards Blob scheduler boost routing, kick-lane disable behavior, and the retired ghost-path contracts.
- `tests/test_visualizer_reactivity_quality.py` covers bounded Blob boost behavior on calm passages.
- User later confirmed that ghost/main-blob shape parity became correct again after this work, even though some preset/live-feel tuning remained an artistic validation task.

**Takeaways**
- Blob problems that "look like ghosting" may actually be live-core ownership bugs.
- Do not spend discrete scheduler events in the same channels that drive whole-body scalar pulse unless that is an intentional design choice.
- When a slider supports `0`, never read it through truthy fallback logic.
- Record retired experimental branches explicitly; otherwise Blob work tends to bounce back to the same two failed ideas.

## 2026-02-26 / 2026-03-05 — Pixel Shift Visualizer Bleed-Through (Resolved)

**Symptoms**
- Visualizer bar content briefly flashed inside the weather widget every pixel shift tick.
- Earlier investigation (Feb 26) found no code delta in the pixel shift subsystem itself; the bug was architectural.

**Failed / insufficient attempts**
1. *Feb 26 audit:* Diffed `base_overlay_widget.py`, `pixel_shift_manager.py`, `display_setup.py` — found no functional changes. Concluded issue was outside the subsystem.
2. *Mar 5 — skip `parent.update()` for small moves (≤3px):* Reduced generic overlay flicker during pixel shift, but did NOT fix the visualizer-specific bleed. The GL overlay content still appeared over the weather widget.

**Root Cause**
Double-shifting of `SpotifyVisualizerWidget` (card) and `SpotifyBarsGLOverlay` (GL surface).

Both were registered with `PixelShiftManager` (PSM), but they are **dependent widgets** that already inherit pixel shift through the media widget chain:
1. PSM shifts `MediaWidget` via `apply_pixel_shift()` → `_update_position()` → `media_layout` → `_position_spotify_visualizer()` → vis card repositioned relative to shifted media 
2. PSM **also** direct-moved the vis card by `offset` on top → **double-shift** 
3. Every tick, `set_state(rect=vis.geometry())` set the GL overlay to the card's double-shifted position
4. PSM **also** direct-moved the GL overlay → **triple offset** possible 
5. The GL overlay drifted past the card boundary and overlapped the weather widget

**Fix**
- `display_setup.py`: Removed `spotify_visualizer_widget` from the PSM registration loop. The card is positioned relative to the media widget (same pattern as the volume widget, which was already excluded).
- `display_image_ops.py`: Removed `pixel_shift_manager.register_widget(overlay)` for the GL overlay. The overlay tracks the card's geometry via `set_state(rect=vis.geometry())` every tick.
- `widget_manager.py`: Removed stale `update_original_position()` call for the vis widget.
- `base_overlay_widget.py`: Added secondary defence — skip `parent.update(old_geo.united(new_geo))` when move delta ≤3px per axis and no size change (reduces unnecessary repaints).

**Status**
- **Resolved** — User confirmed pixel shift no longer causes visualizer bleed into weather widget.

**Takeaways**
- Widgets positioned relative to a pixel-shifted parent must NOT be independently registered with PSM — they inherit the shift through the positioning chain.
- `QOpenGLWidget` overlays that track their source widget's geometry every tick are especially vulnerable to double-shift because the per-tick `setGeometry()` resets any PSM offset, creating visible jitter.
- The volume widget was already excluded from PSM for the same reason (comment in `display_setup.py`). The vis card and GL overlay should have followed the same pattern from the start.

## 2026-03-05 — Settings Spinbox/LineEdit Fill Regression (Resolved)

**Symptoms**
- Every `QSpinBox` and `QLineEdit` inside the settings dialog rendered with the container gray instead of the intended `#282828` fill.
- `SPINBOX_STYLE` QSS was attached to `WidgetsTab`, yet the widgets never showed the correct background.

**Root Cause**
CSS specificity conflict. Every tab's `QScrollArea` had this inline rule (also centralized in `SCROLL_AREA_STYLE`):
```css
QScrollArea QWidget { background: transparent; }
```
This descendant selector has **specificity 002** (two type selectors), which beats the `SPINBOX_STYLE` rules like `QSpinBox { background-color: #282828; }` at **specificity 001**. Because `QSpinBox` IS-A `QWidget`, the transparent background was always winning. The same rule also existed in `dark.qss` line 380 for `#subsettingsDialog`.

**Failed attempts (all reverted)**
1. Global stylesheet append in `settings_theme.load_theme` — no effect (specificity still lost).
2. Palette forcing in `apply_shadows_to_inputs` — bypassed by QSS.
3. Stack stylesheet sync + STYLE_PROBE hooks — confirmed styles existed but didn't help.
4. Dialog-level palette override — palette changed but QSS still won.

**Fix**
- Removed `QScrollArea QWidget { background: transparent; }` from `SCROLL_AREA_STYLE` in `shared_styles.py`.
- Replaced all inline scroll area stylesheets in `widgets_tab.py`, `transitions_tab.py`, `sources_tab.py`, `display_tab.py` with centralized `SCROLL_AREA_STYLE` import.
- `accessibility_tab.py` already used the import — no change needed.
- Fixed `dark.qss` `#subsettingsDialog QScrollArea QWidget` → `#subsettingsDialog QScrollArea > QWidget > QWidget`.
- The remaining rules (`QScrollArea { ... }` and `QScrollArea > QWidget > QWidget { ... }`) use direct-child combinators, so they only target the viewport and content widget — not all descendants.

**Cleanup**
- Removed all STYLE_PROBE diagnostic code from `settings_dialog.py` (`_log_stylesheet`, `_install_stylesheet_hooks`, `_log_tab_styles`, `_sync_stack_stylesheet`, `_log_palette_snapshot`, `_style_probe_enabled`).
- Removed `_SpinboxProbeFilter`, `_style_probe_enabled()`, `_format_color_hex()`, `_log_input_styles()`, `_install_spinbox_probes()` from `widgets_tab.py`.
- Removed unused `os`, `QPalette` imports from `settings_dialog.py`.

**Status**
- ✅ **Resolved** — Visually confirmed `#282828` fill on all spinboxes, entry boxes, and line edits.

## 2026-03-06 — Widget C++ Object Already Deleted on Provider Switch (Resolved)

**Symptoms**
- `RuntimeError: Internal C++ object (SpotifyVisualizerWidget) already deleted` when switching Spotify provider in settings GUI and returning to the application.
- Same error for `MuteButtonWidget` and `SpotifyVolumeWidget`.
- Error occurred in `widget_manager.py` `_register_spotify_secondary_fade` closures fired by `QTimer.singleShot`.

**Root Cause**
When the user switches media providers in settings, the engine destroys the old Spotify widgets (visualizer, mute button, volume). However, `QTimer.singleShot` lambdas in `_register_spotify_secondary_fade` still held Python references to the destroyed widgets. When the timers fired, accessing any Qt method (`objectName()`, `isVisible()`, etc.) on the stale Python wrapper raised `RuntimeError` because the underlying C++ object was already deleted by Qt.

**Fix**
- Added a validity guard at the top of both `_starter()` and `_run_sync()` closures in `widget_manager.py`:
```python
try:
    widget.objectName()
except RuntimeError:
    return
```
- This pattern is consistent with existing exception handling in the file (no `shiboken6` import needed).

**Status**
- ✅ **Resolved** — No RuntimeError on provider switch in settings.

**Takeaways**
- Any `QTimer.singleShot` lambda that captures a widget reference must guard against the widget being destroyed before the timer fires.
- Use `try/except RuntimeError` around a lightweight Qt accessor (`objectName()`) as the validity check.
- This is distinct from the `Shiboken.isValid()` pattern used for background-thread callbacks — deferred main-thread timers need the same protection.

## 2026-03-14 — Visualizer Preset Tooling Regression (Resolved)

**Symptoms**
- Running `visualizer_preset_repair.py` on new Spectrum presets (e.g., `preset_2_cake.json`) shrank the JSON but silently reset `spectrum_shape_nodes` and all shaping sliders back to defaults. The GUI then loaded "Preset 2" with the default curve, ignoring the user-authored shape entirely.
- Switching from any curated preset back to Custom instantly overwrote the Custom slot (even without hitting Save). Toggling presets was enough to nuke hand-tuned slider values because the parser reapplied the curated dict into the Custom slot while the UI reloaded.

**Root Causes**
1. `_collect_visualizer_sections` appended `snapshot.custom_preset_backup` *after* the `snapshot.widgets.spotify_visualizer` block. Because the parser merges sections in order, the backup dict (which still held default values) overwrote the curated entries the moment the preset was reapplied.
2. The repair tool only inferred `preset_index`, leaving `name` blank whenever the snapshot lacked metadata. The UI therefore showed the placeholder "Preset 2" even for curated files like `preset_2_cake`. Combined with #1, it looked as if presets were not sticking.

**Fixes**
- Parser now feeds `custom_preset_backup` first and then the main `widgets.spotify_visualizer` block, so curated settings remain authoritative and the Custom slot stops being overwritten when presets reload. @core/settings/visualizer_presets.py#223-247
- `tools/visualizer_preset_repair.py` now derives friendly names from the filename when missing metadata (e.g., `preset_2_cake.json` → "Preset 2 (Cake)"). We also re-ran the tool to confirm Spectrum retains custom shape nodes and that backups are emitted (`.bak1`).

**Status**
- ✅ Resolved — Spectrum `preset_2_cake.json` retains custom shaping data and displays the friendly name. Switching between presets and Custom no longer wipes the Custom slot. Cross-mode audit pending to ensure every curated file behaves the same way.

**Takeaways**
- Always merge snapshot backup sections *before* the primary widget payload so curated presets remain authoritative.
- Repair-tool outputs must include human-friendly names; otherwise it’s impossible to tell curated presets apart in the UI.
