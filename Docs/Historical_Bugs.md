In this document neatly arrange, date and detail significant bugs that were fixed in the project.
Include failed solutions and reasoning why the final solution worked. Never remove from this document unless asked, use it as a guide to avoid falling back into bad habbits.
Section by date and type.

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