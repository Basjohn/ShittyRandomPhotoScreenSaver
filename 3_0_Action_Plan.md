# 3.0 Action Plan

## Core Architecture & Safety Policies

**EVERY code change MUST adhere to these guardrails.**

### 1. Threading & Resource Management
- **ThreadManager for ALL business logic threading:** Use `core/threading/manager.py` (`submit_io_task()`, `submit_compute_task()`, `invoke_in_ui_thread()`). NEVER use raw `threading.Thread()`, `ThreadPoolExecutor()`, or `QThread` for business logic.
- **Locking:** Use `threading.Lock()` for basic flags/state, `threading.RLock()` for class data. Protect GL overlay state with locks.
- **UI Thread:** Qt widget updates MUST be invoked via `invoke_in_ui_thread()`.
- **Resource Management:** Register Qt objects via `core/resources/manager.py` (`self._resources.register_qt(...)`).
- **No raw QTimers:** Favour lock-free atomic threading or SPSC Queues and coalescing whenever viable.

### 2. Modularity & Monolith Avoidance
- Centralised modules should be created over inline code when possible and when they do not already exist.
- When a module approaches 1700+ lines, immediately add tasks to refactor/modularise (unless extremely risky).
- Avoid file bloat and FAVOUR MODULARITY WHERE POSSIBLE.

### 3. State & Logging
- **Logging:** Output 2 or more logs of every script run. Verbose logs keep normal logs clean. Logs rotate to keep size down.
- Avoid debug spam and infinite repeats in debug.
- **Deduplication:** Use the DeduplicatingRotatingFileHandler. `[PERF]`, `[SPOTIFY_VIS]`, and `[SPOTIFY_VOL]` tagged logs go to their respective files.

### 4. Settings Defaults
- Every new setting MUST be added to all 8 layers: model dataclass, `from_settings()`, `from_mapping()`, `to_dict()`, creator kwargs, widget init, extra dict, and GL overlay state (see `Docs/Defaults_Guide.md`).

### 5. Transition & Visualizer Policies
- **Transitions:** All visual transitions must end on a final frame matching the fully-rendered new wallpaper at progress 1.0 (no remnants).
- **Overlays:** Follow `Docs/10_WIDGET_GUIDELINES.md` for styling, shadow/fade, and overlay stack integration.

### 6. Minimal Painting & Tick Work
- Minimal painting, minimal tick work, minimal work on UI thread.
- Minimal work that starts at the exact same time as a transition does; desync slightly where possible.
- Use `update()` instead of `repaint()`. Gate high-frequency operations behind `SRPSS_PERF_METRICS`.

---

## Task 1: "Taste The Rainbow" Mode (Global Visualizer Setting)

**Goal:** Implement a global toggle that slowly shifts the hue/color of the active visualizer through the spectrum, looping continuously, and retaining its state across mode switches.

### User Requirements (verbatim)
> "Effect exists above Visualizer Mode Selection in GUI (Sliders/Options Conditional to being checked) and applies to all visualizers when on, taking their current colour as the starting colour, when switching modes via double click with this on we keep the colour we were on with the previous mode. All of this is exclusive to this Taste The Rainbow mode and does not interfere with anything when disabled. It slowly (but sliders adjust this and other useful aspects) goes from the current colour all the way through the colour spectrum and back to its starting/base colour. The shift applies to glows, lines etc. They are all shifted at the same time and not colorized to be identical units. This effect continuously loops when on. When off we just use our normal colours again."
>
> "Perhaps this would benefit from centralization? Or would that be wasteful?"

### Complexity Analysis
- **Approach:** A single `u_rainbow_hue_offset` uniform (0.0–1.0) passed to ALL shaders is the cleanest path. Each shader applies an HSV hue rotation to its output color in a shared GLSL function. This avoids modifying every color uniform on the CPU side.
- **Reasoning:** Each visualizer has multiple color uniforms (fill, border, glow, edge, line, etc.). Rotating them all on the CPU would require touching 15+ color values per tick. A post-process hue shift in the shader is a single `vec3 rgb2hsv → shift → hsv2rgb` per fragment, which is trivially cheap.
- **State persistence across mode switches:** The hue offset is accumulated time-based (`accumulated_time * speed`). Since `_accumulated_time` already persists across mode switches in `SpotifyBarsGLOverlay`, the rainbow state naturally survives double-click mode cycling.
- **Centralization verdict:** A dedicated module is wasteful for a single float uniform. The state lives in `SpotifyBarsGLOverlay._rainbow_hue_offset` (computed from `_accumulated_time * rainbow_speed`), and the settings live in the existing visualizer model. No new manager needed.

### Research & Planning
- [x] Determine rendering approach: single `u_rainbow_hue_offset` uniform + shared GLSL `hueShift()` function in each shader.
- [x] Assess state persistence: `_accumulated_time` already persists across mode switches — no extra state needed.
- [x] Centralization: Not needed. Single uniform passed through existing `set_state()` → `paintGL()` pipeline.

### Implementation Checklist — COMPLETE
- [x] **Shared GLSL function:** HSV hue shift added to all 7 `.frag` files. Applied as final step before `fragColor` when `u_rainbow_hue_offset > 0.0`.
- [x] **Greyscale saturation fix:** All 7 shaders force `s = 1.0` when `s < 0.05 && v > 0.05` so rainbow works on white/grey colours.
- [x] **GL overlay:** `u_rainbow_hue_offset` uniform queried for all programs. Computed from `_accumulated_time * _rainbow_speed` when enabled.
- [x] **set_state():** `rainbow_enabled`, `rainbow_speed` parameters added.
- [x] **Settings model (all 8 layers):** Complete.
- [x] **UI:** Checkbox + speed slider added above Visualizer Mode combobox.
- [x] **UI save/load:** Wired.
- [x] **Testing:** Verified on oscilloscope, sine_wave, blob, helix, starfield, bubble. Spectrum under investigation (may need app restart to reload shader from disk).

---

## Task 2: Minor Issues & Tweaks

### 2.1 Multi-Monitor Resolution/Compositor Glitch
**Goal:** Fix the compositor/display layout getting stuck between displays (e.g., 4k and 1440p) when monitors sleep and wake up.

> *User:* "If MC Build is on my Display 1 (4k) and my display 0 is (1440p) and I turn off both displays, come back and turn them both on, then regardless of order the compositor (etc) gets stuck between both displays, half on display 0 and half on display 1."

#### Complexity Analysis
- **Root cause hypothesis:** When displays sleep/wake, Windows may reassign screen indices or change the primary display temporarily. Qt emits `screenChanged` signals but the `DisplayWidget` geometry and `GLCompositorWidget` viewport may not re-anchor to the correct screen bounds.
- **Key files:** `rendering/display_setup.py` (`handle_screen_change`), `rendering/display_widget.py` (`_handle_screen_change`), `rendering/multi_monitor_coordinator.py`, `rendering/display_native_events.py`.
- **Reasoning:** The `handle_screen_change` in `display_setup.py` is connected via `windowHandle().screenChanged`, but this may not fire reliably on Windows when both monitors sleep/wake simultaneously. We may need to also listen for `QGuiApplication.screenAdded`/`screenRemoved` or handle `WM_DISPLAYCHANGE` in `display_native_events.py`.

#### Investigation Checklist
- [x] **Research:** `screenChanged` is unreliable on Windows when multiple monitors sleep/wake simultaneously.
- [x] **Trace:** Added `WM_DISPLAYCHANGE` (0x007E) handler in `display_native_events.py` with logging.
- [x] **Analyse:** `handle_screen_change` in `display_setup.py` properly re-evaluates geometry and compositor viewport.
- [x] **Fix:** Added `WM_DISPLAYCHANGE` handler that iterates all `DisplayWidget` instances, calls `_handle_screen_change()` to re-anchor geometry, `_invalidate_overlay_effects()` to refresh overlays, and `refresh_playback_state()` on media widgets.
- [ ] **Test:** Verify on multi-monitor setup with different resolutions.

### 2.2 Media Widget Fade Out on Wake
**Goal:** Ensure the media widget stays visible (doesn't fade out incorrectly) when waking the screensaver with Spotify active.

> *User:* "Similarly, when I do this for the screensaver build (wake up and screensaver is there already) I notice the media widget is always faded out despite leaving spotify on. I'd advise checking what was done for 1 as well, that problem very likely exists in both builds..."

#### Complexity Analysis
- **Root cause hypothesis:** When displays sleep, the overlay fade system may interpret the lack of paint events or the deactivation as a reason to fade out the media widget. On wake, the Spotify playback state poll may not re-trigger, so the widget stays faded.
- **Key files:** `rendering/fade_coordinator.py`, `rendering/widget_manager.py`, `widgets/media_widget.py`, `rendering/display_overlays.py`.
- **Reasoning:** The `FadeCoordinator` drives overlay visibility. If the media widget's fade target was set to 0.0 during sleep (e.g., because a `WM_ACTIVATE` deactivation triggered a fade-out), it won't automatically fade back in unless something re-requests visibility. The fix likely involves hooking into the same wake/display-change event from 2.1 to force a `request_overlay_fade_sync` or equivalent.

#### Investigation Checklist
- [x] **Research:** Media widget enters idle state during sleep, `_refresh_async()` not triggered on wake.
- [x] **Analyse:** `FadeCoordinator`/`WidgetManager` had no suspend/resume awareness.
- [x] **Fix:** Added `MediaWidget.refresh_playback_state()` public method that resets idle state, resets poll stage to fastest, and triggers async refresh. Called from the `WM_DISPLAYCHANGE` handler (same hook as 2.1). Also calls `_invalidate_overlay_effects()` to force overlay visibility re-evaluation.
- [ ] **Test:** Verify media widget stays visible after sleep/wake with Spotify playing.

### 2.3 Settings GUI Enter Key Behavior ✅ READY TO IMPLEMENT
**Goal:** Pressing Enter in the Settings GUI should safely close it and return to the screensaver, not minimize it.

> *User:* "Pushing Enter key in settings gui minimizes it instead of safely closing it and going back to the screensaver like when X is clicked."

#### Complexity Analysis
- **Root cause:** `SettingsDialog` extends `QDialog`. Qt's default `QDialog` behavior maps Enter/Return to `accept()`, which by default calls `done(QDialog.Accepted)`. However, the dialog has no `accept()` override, and the `closeEvent` has source-checking logic. The minimize behavior suggests Enter is hitting a default button that calls `showMinimized()` — likely the title bar minimize button has `autoDefault` or `default` set.
- **Fix:** Override `keyPressEvent` in `SettingsDialog` to intercept `Key_Return`/`Key_Enter` and call `self.close()` instead. This triggers the same `closeEvent` path as clicking X.
- **Complexity:** Single-line fix. No thread safety concerns. No settings changes.

#### Implementation
- [x] **Confirmed:** No `keyPressEvent` override exists in `SettingsDialog` (checked `ui/settings_dialog.py`).
- [x] **Add `keyPressEvent`** to `SettingsDialog` that intercepts Enter/Return and calls `self.close()`. Implemented in `ui/settings_dialog.py` line ~1312.

### 2.3.1 Control Halo Visual Customization
**Goal:** Add a combobox in the "Input and Exit" area of settings GUI to select the control halo shape.

> *User:* "Let's add in Control Halo visual customization options. A Combobox where we have our current one Circle (Default), Diamond (This is like Circle except the outer ring is a diamond shape), Standard (Renders what looks like a normal windows cursor triangle without the tail) and Precision (Which is circle without the outer ring). Placed in Input and Exit area of settings gui."

#### Complexity Analysis
- **Current code:** `widgets/cursor_halo.py` — `CursorHaloWidget.paintEvent()` draws a hardcoded circle ring + center dot. The halo is a top-level frameless window that follows the cursor when Ctrl is held.
- **Approach:** Add a `halo_shape` setting (enum: `circle`, `diamond`, `standard`, `precision`). In `paintEvent()`, branch on the shape to draw:
  - **Circle (default):** Current ring + dot (no change).
  - **Diamond:** Same center dot, but outer ring replaced with a rotated 45° square (diamond). Same stroke width and shadow.
  - **Standard:** Draw a filled triangle pointing upper-left (like a Windows cursor arrow without the tail). Shadow offset matches.
  - **Precision:** Current center dot only, no outer ring. Smallest footprint.
- **Reasoning:** All shapes are simple QPainter primitives (drawEllipse, drawPolygon, drawLine). No GL involvement. The setting propagates via `SettingsManager` → `DisplayWidget` → `CursorHaloWidget.set_shape()`.
- **Key files:** `widgets/cursor_halo.py`, `rendering/display_widget.py` (creates halo), `ui/tabs/input_exit_tab.py` (or equivalent settings area), `core/settings/models.py`.

#### Implementation Checklist
- [ ] **Settings model:** Add `halo_shape: str = "circle"` to the appropriate model dataclass. Register in all 8 layers.
- [ ] **CursorHaloWidget:** Add `set_shape(shape: str)` method. Refactor `paintEvent()` to branch on `self._shape`.
  - `circle`: existing code
  - `diamond`: QPainterPath with 4 points rotated 45°, same stroke/shadow
  - `standard`: QPainterPath triangle (upper-left pointing arrow head), filled white with shadow
  - `precision`: center dot only, skip outer ring
- [ ] **DisplayWidget:** Pass `halo_shape` setting to `CursorHaloWidget` on creation and on settings change.
- [ ] **UI:** Add combobox to Input and Exit tab with options: Circle, Diamond, Standard, Precision.
- [ ] **Testing:** Verify all 4 shapes render correctly, shadow follows shape, fade in/out works.

### 2.4 Blob Core Size Intensity ✅ READY TO IMPLEMENT
**Goal:** Make the minimum size of the Blob visualizer ~15% larger during intense bass.

> *User:* "We should make the core size of the Blob (The minimum size) get ahigher/intense."
bout 15% larger than now when bass is is 
#### Complexity Analysis
- **Current code:** In `blob.frag` line 35-37:
  ```glsl
  float r = 0.44 * clamp(u_blob_size, 0.1, 2.5);
  r += u_bass_energy * 0.077 * u_blob_pulse;
  ```
  The base radius is `0.44 * size`. The bass pulse adds `bass * 0.077 * pulse` which at max bass (1.0) and default pulse (1.0) adds 0.077 — about 17.5% of the 0.44 base. But this is the *pulse* (breathing), not the *minimum core size*.
- **The ask:** The *minimum* size (the size at rest/silence) should be ~15% larger when bass is intense. This means the base `r` itself should grow with sustained bass, not just the pulse.
- **Fix:** Add a bass-driven base size boost: `r += u_bass_energy * u_bass_energy * 0.066;` (quadratic so it only kicks in at higher bass levels, ~15% of 0.44 = 0.066).
- **Complexity:** Single shader line change. No settings changes needed.

#### Implementation
- [x] **Modify `blob.frag`:** Added `r += u_bass_energy * u_bass_energy * 0.066;` after base radius calculation (line 37). Quadratic ramp ensures the boost only kicks in at higher bass levels (~15% of 0.44 base).

---

## Task 3: Oscilloscope Ghosting Option

**Goal:** Add a ghosting/trail effect to the Oscilloscope visualizer with an intensity slider, similar to how spectrum bars have ghost peaks.

> *User:* "Add a Ghosting option to oscilloscope with an intensity slider."

### Complexity Analysis
- **Current code:** The oscilloscope renders waveform lines in `oscilloscope.frag`. There is no trail/ghosting — each frame draws the current waveform only. The spectrum mode already has ghosting via `u_ghost_alpha` and a CPU-side peak envelope (`_peaks` buffer).
- **Approach:** Oscilloscope ghosting is fundamentally different from spectrum ghosting. Spectrum ghosting tracks per-bar peak values that decay. Oscilloscope ghosting needs to retain the *previous frame's waveform shape* and render it at reduced alpha behind the current frame.
- **Implementation options:**
  1. **CPU double-buffer:** Store the previous tick's waveform in a second uniform array (`u_prev_waveform[256]`). The shader draws the previous waveform at `ghost_alpha` before drawing the current one. Simple, no FBO needed.
  2. **Multi-frame trail (stretch):** Store N previous frames for a longer trail. More expensive (N×256 floats). Probably overkill — a single previous frame gives a nice subtle trail.
- **Reasoning:** Option 1 is cleanest. The CPU already has the waveform each tick. Storing the previous frame is trivial (swap buffers). The shader already supports multi-line rendering, so drawing a ghost line is just another `eval_line()` call at reduced alpha.
- **Key files:** `oscilloscope.frag`, `spotify_bars_gl_overlay.py` (waveform buffer management, uniform push), `core/settings/models.py`, UI.

### Implementation Checklist — COMPLETE
- [x] **Settings model (all 8 layers):** `osc_ghosting_enabled`, `osc_ghost_intensity` added.
- [x] **GL overlay:** Ring buffer of 6 frames for `_prev_waveform` (not just 1 frame behind). Provides ~100ms delay at 60fps for visible ghost separation.
- [x] **Shader:** `u_prev_waveform[256]` and `u_osc_ghost_alpha` added to `oscilloscope.frag`. Ghost line rendered behind current waveform.
- [x] **UI:** Checkbox + intensity slider added.
- [x] **Bug fix:** Single-frame prev_waveform was nearly identical to current (due to smoothing). Ring buffer delay of 6 frames creates visible ghost trail.

---

## Task 4: Sine Wave Visualizer — Micro Wobble Rework

**Goal:** Completely rework the Sine Wave Micro Wobble to produce a smooth, snake-like (but bass-reactive) movement across the lines, replacing the current high-frequency jagged bumps.

> *User:* "Sine Wave Visualizer Micro Wobble should be completely reworked to give a smooth almost snake like (but bass reactive) movement across the lines."

### Complexity Analysis
- **Current code:** `sine_wave.frag` — Micro Wobble uses 5 high-frequency `sin()` terms (spatial freq 89–283) to create jagged bumps/dents. The result is added to `wave_val` before amplitude scaling. Driven by `u_micro_wobble` (0.0–1.0) and vocal/mid energy.
- **Problem:** The high spatial frequencies produce choppy, spiky distortions rather than smooth undulation. The user wants a snake-like organic flow.
- **New approach:** Replace the 5 high-frequency terms with 2–3 low-frequency sinusoids (spatial freq ~3–12) with slow time modulation. Use bass energy (not mid) as the primary driver so the snake "pulses" with kicks. Add a slight phase offset per line in multi-line mode so each line snakes independently.
- **Reasoning:** Low spatial frequencies create broad, smooth curves. Slow time speeds prevent jitter. Bass reactivity gives the "pulse" feel. The `u_micro_wobble` slider still controls amplitude (0 = off, 1 = max snake).
- **Key files:** `widgets/spotify_visualizer/shaders/sine_wave.frag` (all 3 micro wobble blocks: mw1, mw2, mw3).

### Implementation Checklist — COMPLETE (v2 rework)
- [x] **v2 rework:** Replaced v1 low-freq approach (too subtle) with multi-layer snake ripples. 4 sin terms per line with spatial freq 16–27 and fast time modulation (3.2–3.8x). Multiplier raised from 0.18 to 0.55 for clearly visible snake distortions.
- [x] **Energy drive:** `clamp(mw_bass * 2.5, 0.0, 1.5)` — allows overdrive for strong beats.
- [x] **Per-line variety:** Each line has unique phase offsets and slightly different frequency mixes.
- [ ] **Testing:** Verify snake-like motion at various slider values. *(Requires live app run)*

---

## Task 5: Sine Wave Visualizer — Heartbeat Slider

**Goal:** Add a "Heartbeat" slider to the Sine Wave visualizer. When above 0, audio jumps (transients) cause triangular bumps to form along the line, largest in the travel direction, smallest opposite. Bumps deform the line briefly and leave a subtle ghost trail when travel is NONE.

> *User:* "Heartbeat slider should be added. (Also Sine Wave) When this is above 0 audio jumps cause triangular bumps to form, these are largest in the direction the sine wave is travelling toward, smallest where it comes from, but they are in sync. The bumps deform the line briefly and if travelling for a line is set to NONE leave a subtle ghosting of the original shape/line before returning."

### Complexity Analysis
- **Transient detection:** Need to detect sudden energy spikes (audio "jumps"). This is a CPU-side computation: compare current frame's energy to a short-term average. When `current_energy - avg_energy > threshold`, a "heartbeat" event fires.
- **Triangular bump rendering:** In the shader, when a heartbeat is active, add a triangular displacement to `wave_val`. The triangle's peak is offset in the travel direction (positive phase shift for left-travel, negative for right). The triangle decays over ~200–400ms.
- **Directional asymmetry:** The bump is an asymmetric triangle — steep rise in travel direction, gentle fall opposite. When travel is NONE, the bump is symmetric.
- **Ghost trail:** When travel is NONE and a heartbeat fires, render a faint copy of the pre-bump line shape that fades out over ~300ms. This requires storing the previous frame's wave values (or simply rendering a second line at reduced alpha with the un-bumped wave_val).
- **Key uniforms needed:** `u_heartbeat` (0.0–1.0 slider), `u_heartbeat_intensity` (CPU-computed current bump strength, decaying), `u_heartbeat_phase` (CPU-computed phase offset for directional asymmetry).
- **Key files:** `sine_wave.frag`, `spotify_bars_gl_overlay.py` (uniform passing), `spotify_visualizer_widget.py` (transient detection in `_on_tick`), `core/settings/models.py` (new setting).

### Implementation Checklist — COMPLETE (v2 rework)
- [x] **Settings model (all 8 layers):** `sine_heartbeat: float = 0.0` added.
- [x] **Transient detection (CPU):** Rolling bass average in `_on_tick()`. Threshold triggers `_heartbeat_intensity = 1.0`, decays at `dt * 4.0`.
- [x] **Shader uniforms:** `u_heartbeat`, `u_heartbeat_intensity` added. Travel direction reused from per-line `u_sine_travel*`.
- [x] **v2 shader bump:** 5 alternating up/down sharp triangular spikes (was 3 barely-visible bumps). Squared falloff for pointier peaks. Multiplier raised from 0.3 to 0.8.
- [x] **GL overlay:** Heartbeat uniforms pushed in sine_wave render block.
- [x] **UI:** Slider added to Sine Wave section.
- [ ] **Testing:** Verify bumps appear on bass transients. *(Requires live app run)*

### NEW: Sine Wave Width Reaction Slider — COMPLETE
- [x] **Settings model (all 8 layers):** `sine_width_reaction: float = 0.0` added.
- [x] **Shader:** `u_width_reaction` uniform. Bass-driven line width boost (2px base → up to ~8px). `eval_line()` accepts `bass_width_boost` param.
- [x] **UI:** Slider added to Sine Wave section (0–100%).
- [ ] **Testing:** Verify width stretching on bass. *(Requires live app run)*

---

## Task 6: Bug Reports

### 6.1 Double-Click Artwork Refresh Not Working
**Goal:** Investigate whether double-clicking artwork in the Media widget correctly refreshes the artwork.

> *User:* "Double-clicking Artwork in Media does not seem to refresh it, unsure about this being a bug."

#### Complexity Analysis
- **Current code:** `media_widget.py` `handle_double_click()` (line ~872) busts the GSMTC cache, clears the scaled artwork cache, resets `_refresh_in_flight`, and calls `_refresh_async()`. This should force a full re-query.
- **Possible issues:**
  1. The GSMTC re-query returns the same cached artwork from Windows (OS-level cache, not ours).
  2. The `_refresh_async()` callback may not trigger a repaint if the track info hasn't changed (dedup logic).
  3. The double-click may not be reaching `handle_double_click()` due to hit-testing or event routing issues (e.g., the click lands on a control button overlay instead of the artwork area).
- **Investigation approach:** Add logging to `handle_double_click()` to confirm it fires. Check if `_on_track_info_received()` actually receives new artwork bytes. Check if the artwork comparison logic short-circuits when bytes are identical.
- **Key files:** `widgets/media_widget.py`, `rendering/display_widget.py` (event routing), `core/media/gsmtc_bridge.py` (GSMTC cache).

#### Investigation Checklist
- [x] **Verify routing:** `handle_double_click()` already logs and fires correctly.
- [x] **Root cause found:** `handle_double_click()` busted the GSMTC cache but did NOT reset `_last_track_identity` or `_skipped_identity_updates`. The diff gating in `display_update.py` (lines 98-111) skipped the update because the track identity hadn't changed, so artwork was never re-decoded.
- [x] **Fix applied:** Added `self._last_track_identity = None` and `self._skipped_identity_updates = 0` to `handle_double_click()` so the diff gate passes on the next refresh.
- [ ] **Testing:** Verify double-click refreshes artwork. *(Requires live app run)*

### 6.2 Volume Slider Control Halo Teleporting/Erratic Movement
**Goal:** Fix the control halo teleporting and moving erratically when trying to adjust the volume slider with a single mouse click.

> *User:* "Trying to adjust the volume slider with a single mouse click has the control halo teleporting and moving erratically."

#### Complexity Analysis
- **Current code:** The `CursorHaloWidget` is a top-level frameless window that follows the cursor. It receives mouse events and forwards them to the parent `DisplayWidget` via `_forward_mouse_event()`. The `DisplayWidget` then routes clicks to `SpotifyVolumeWidget.handle_press()`.
- **Root cause hypothesis:** When the user clicks on the volume slider area, the halo's `mousePressEvent` fires, which forwards the event to `DisplayWidget`. But the `DisplayWidget` also receives the original click (since the halo has `WindowDoesNotAcceptFocus`). This may cause a double-dispatch: the halo moves to the click position, then the forwarded event causes another position update, creating a teleport/jitter loop.
- **Alternative hypothesis:** The `show_at()` / `move_to()` methods map local→global coordinates using `_parent_widget.mapToGlobal()`. If the parent widget reference becomes stale or points to the wrong display, the global coordinates will be wrong, causing teleportation.
- **Key files:** `widgets/cursor_halo.py` (`_forward_mouse_event`, `show_at`, `move_to`), `rendering/display_widget.py` (mouse event handling, halo positioning).

#### Investigation Checklist
- [x] **Root cause found:** Feedback loop — halo receives mouse move → forwards to DisplayWidget → DisplayWidget repositions halo via `show_ctrl_cursor_hint()` → halo moves → new mouse move fires → repeat. The forwarded event's position is mapped through `halo.mapToGlobal → parent.mapFromGlobal` which can have rounding/timing mismatches causing jitter.
- [x] **Fix applied:** Added `_halo_forwarding` guard flag. `CursorHaloWidget._forward_mouse_event()` sets `parent._halo_forwarding = True` before `sendEvent()` and resets it in a `finally` block. `handle_mouseMoveEvent()` in `display_input.py` checks this flag and skips halo repositioning when True. Volume drag routing still processes the event normally.
- [x] **Files changed:** `widgets/cursor_halo.py` (guard flag set/reset), `rendering/display_input.py` (guard check), `rendering/display_widget.py` (flag initialization).
- [ ] **Testing:** Verify halo follows cursor smoothly without jitter during volume slider interaction. *(Requires live app run)*

---

## Task 7: Control Halo Visual Customization

**Goal:** Add visual customization options for the control halo, allowing users to select different shapes via a combobox in settings.

> *User:* "Let's add in Control Halo visual customization options. Multiple shapes selectable via settings."

### Implementation Checklist
- [x] **Settings:** `input.halo_shape` stored in SettingsManager (not a dataclass model — simple key/value). Options: circle (default), ring, crosshair, diamond, dot.
- [x] **UI:** Combobox added to Display tab → Input & Exit group. Load/save wired through `_load_settings()` / `_save_settings()`.
- [x] **CursorHaloWidget:** `set_shape()` method + `paintEvent()` dispatches to `_paint_circle`, `_paint_ring`, `_paint_crosshair`, `_paint_diamond`, `_paint_dot`. Each shape has shadow + main pass.
- [x] **Wiring:** `ensure_ctrl_cursor_hint()` in `display_input.py` reads `input.halo_shape` from SettingsManager and calls `set_shape()` on creation.
- [ ] **Testing:** Verify all shapes render correctly. *(Requires live app run)*

---

## Task 8: Sine Wave Line Positioning Fix

**Goal:** Fix multi-line positioning so that when Line Offset = 0 and Vertical Shift = 0, all 3 lines overlap perfectly. Remove any internal/hardcoded offset. Line Offset controls X-axis separation, Vertical Shift controls Y-axis separation. Line 2 is affected slightly less than Line 3.

> *User:* "The Sine Wave positioning may be slightly off. The internal offset should not be there. The offset should be from the options Line Offset and Vertical Shift. Line Offset X axis, Vertical Shift Y Axis. Line 2 is affected by offset/shift slightly less than line 3 is. If Line Offset is 0 and Vertical shift is 0 but there are 3 lines they all overlap perfectly."

### Complexity Analysis
- **Current code:** `sine_wave.frag` — Lines 2/3 have hardcoded phase offsets in the sine function (`+ 2.094` for line 2, `+ 4.189` for line 3 — these are 2π/3 and 4π/3). Additionally, when `v_shift_pct == 0`, there's a `lob * 0.12` Y-offset applied. Both of these create separation even when the user sets both sliders to 0.
- **Fix:** Remove the hardcoded sine phase offsets (2.094 / 4.189). Instead, derive X-axis phase offset from `u_sine_line_offset_bias` (Line Offset slider). Y-axis offset from `u_sine_vertical_shift` (Vertical Shift slider). Line 2 gets `factor * 0.7`, Line 3 gets `factor * 1.0` so Line 3 is affected more.
- **Key files:** `sine_wave.frag` (line 2/3 sine calls and ny2/ny3 positioning).

### Implementation Checklist
- [x] **Remove hardcoded phase offsets:** Changed `sin(nx * sine_freq + 2.094 + phase2)` → `sin(nx * sine_freq + lob_phase2 + phase2)` where `lob_phase2 = lob * 2.094 * 0.7`. Line 3: `lob_phase3 = lob * 4.189` (100%).
- [x] **Remove hardcoded Y offsets:** Removed `lob * 0.12` fallback. Now `ny2 = ny + v_spacing * 0.7` and `ny3 = ny - v_spacing`. At VShift=0, v_spacing=0, so all lines overlap perfectly.
- [ ] **Testing:** Verify 3 lines overlap perfectly at 0/0. Verify separation increases with sliders. Verify Line 3 separates more than Line 2. *(Requires live app run)*

---

---

## Task 9: Spectrum Rainbow ("Taste The Rainbow") Not Working

**Goal:** Spectrum bars must respond to the Taste The Rainbow hue-rotation exactly like all other visualizer modes do.

> *User:* "Spectrum still is not affected by Taste The Rainbow at all. This needs to be a deep investigative task following the full flow chain as the problem has persisted through several fixes."

### Complexity Analysis
- **Shader side:** `spectrum.frag` has `u_rainbow_hue_offset` declared and the hue-shift block is present (lines ~474–495). The shader code is correct.
- **Uniform push side:** `_render_with_shader()` in `spotify_bars_gl_overlay.py` pushes `u_rainbow_hue_offset` in the **common uniforms** block (lines ~1114–1128) before the mode-specific blocks. The push reads `self._rainbow_enabled` and `self._accumulated_time`. This looks correct at first glance.
- **Tick gate:** `spotify_visualizer_widget.py` line ~1565 sets `animated_mode = (self._vis_mode_str != 'spectrum') or getattr(self, '_rainbow_enabled', False)`. So when rainbow is on, spectrum should still push every tick. This also looks correct.
- **Root cause hypotheses (in priority order):**
  1. **`_accumulated_time` is not advancing for spectrum.** Spectrum is not in the `animated_mode` list unless rainbow is on. If `_rainbow_enabled` is `False` on the widget at the time the tick check runs (i.e. the flag was set on the overlay but not on the widget), `should_push` will be False and `_accumulated_time` will never advance → `hue_offset` stays 0.
  2. **`_rainbow_enabled` is set on `SpotifyVisualizerWidget` but not propagated to `SpotifyBarsGLOverlay`.** The `set_state()` call path must pass `rainbow_enabled` through `extra` dict → overlay `set_state()`. If the key is missing from the extra dict for spectrum mode, the overlay's `_rainbow_enabled` stays False.
  3. **`_rainbow_diag_logged` one-shot guard** fires on the first frame (when rainbow may be off) and never logs again, masking the real state.
  4. **`_accumulated_time` is only advanced in `set_state()` for animated modes.** If spectrum's `set_state()` path skips the time accumulation when `playing=False`, the hue offset stays frozen.

### Investigation Checklist
- [ ] **Trace the `extra` dict:** In `spotify_visualizer/config_applier.py` `_build_extra_dict()`, confirm `rainbow_enabled` and `rainbow_speed` are unconditionally added (not gated on mode). Current code at line ~348 looks correct — verify it actually runs for spectrum.
- [ ] **Trace `set_state()` on overlay:** Confirm `SpotifyBarsGLOverlay.set_state()` receives and stores `rainbow_enabled=True` when the toggle is on. Add a one-shot log.
- [ ] **Trace `_accumulated_time` advancement:** Confirm `_accumulated_time` is incremented in `set_state()` regardless of mode. If it's only incremented inside an `if mode != 'spectrum'` guard, that's the bug.
- [ ] **Check `should_push` gate:** In `spotify_visualizer_widget.py` `_on_tick()`, log `animated_mode` and `should_push` when rainbow is enabled and mode is spectrum. If `should_push` is False, the overlay never gets a new frame.
- [ ] **Fix:** Ensure `_accumulated_time` advances for all modes when rainbow is enabled. Ensure `rainbow_enabled` reaches the overlay's `set_state()` for spectrum. Remove the `_rainbow_diag_logged` one-shot guard or make it re-fire when state changes.
- [ ] **Key files:** `widgets/spotify_bars_gl_overlay.py` (`set_state`, `_render_with_shader`), `widgets/spotify_visualizer/config_applier.py` (`_build_extra_dict`), `widgets/spotify_visualizer_widget.py` (`_on_tick`, `should_push` logic).

---

## Task 10: Taste The Rainbow — Gate on Music Playing / Visualizer Animating

**Goal:** Rainbow hue rotation should only advance while music is playing OR the visualizer is actively animating. When paused/idle, the hue freezes at its current value.

> *User:* "Taste the rainbow should only colour change while music is playing OR the visualizer is animating, whatever is more performant/reliable to gate behind. Otherwise it sticks with the colour it is on."

### Complexity Analysis
- **Current behaviour:** `hue_offset = (self._accumulated_time * self._rainbow_speed * 0.1) % 1.0` — `_accumulated_time` advances every frame regardless of `_playing`.
- **Preferred gate:** `self._playing` (already stored on the overlay as `self._playing: bool`). This is the most reliable signal — it's set from the `playing` kwarg in `set_state()` which comes from the Spotify playback state.
- **Alternative gate:** Check if any animated visualizer mode is running (non-spectrum, or spectrum with active bars). Less reliable since bars can be non-zero even when paused (decay).
- **Implementation:** In `_render_with_shader()`, only advance the hue accumulator when `self._playing` is True. Store a `_rainbow_hue_accum: float` field separate from `_accumulated_time` so it doesn't affect other time-based animations. Freeze it when not playing.

### Implementation Checklist
- [ ] **Add `_rainbow_hue_accum: float = 0.0`** to `SpotifyBarsGLOverlay.__init__()`.
- [ ] **Advance `_rainbow_hue_accum`** only when `self._playing` is True, using the same `dt` that `_accumulated_time` uses (derived from `set_state()` timestamp delta).
- [ ] **Use `_rainbow_hue_accum`** instead of `_accumulated_time` for the `u_rainbow_hue_offset` push.
- [ ] **Key files:** `widgets/spotify_bars_gl_overlay.py` (`__init__`, `set_state`, `_render_with_shader`).

---

## Task 11: Bubble Visualizer — Multiple Bugs

**Goal:** Fix 5 distinct bugs in the Bubble visualizer mode to reach the reference visual quality shown in the goal image.

> *User:* "Bubble is currently very problematic." (See sub-issues below.)

### 11.1 UP/DOWN Direction — No Visible Bubbles

**Symptom:** When UP or DOWN direction is selected, only slight white bumps appear at the top/bottom occasionally. Bubbles do not flow.

**Root cause hypothesis:**
- `_spawn_position("up", ...)` returns `y = -margin` (just off the bottom edge in UV space). But in the shader, UV Y=0 is top and Y=1 is bottom. The simulation uses `b.y -= move_y` (line ~188 in `bubble_simulation.py`), meaning positive `vy` moves UP in UV space (decreasing Y). For direction "up", `sv = (0.0, 1.0)` so `move_y = 1.0 * base_vel * dt > 0`, meaning `b.y` decreases — bubbles move toward Y=0 (top). Spawn at `y = -margin` (above the card in UV) means they start off-screen and immediately exit. **The spawn edge is wrong for UP direction** — bubbles should spawn at `y = 1.0 + margin` (bottom) and travel toward `y = 0` (top).
- Similarly for DOWN: spawn at `y = 1.0 + margin` but `sv = (0.0, -1.0)` → `move_y = -base_vel * dt` → `b.y -= (-base_vel * dt)` = `b.y += base_vel * dt` → Y increases → moves toward bottom. Spawn should be at `y = -margin`.
- **Fix:** Swap spawn Y for UP and DOWN in `_spawn_position()`. UP should spawn at `y = 1.0 + margin`, DOWN at `y = -margin`.

**Implementation Checklist:**
- [x] Fix `_spawn_position()` in `bubble_simulation.py`: UP → `y = 1.0 + margin`, DOWN → `y = -margin`.
- [x] Verify LEFT/RIGHT are correct (LEFT: spawn at `x = 1.0 + margin`, RIGHT: spawn at `x = -margin`).
- [ ] Add a log line on first spawn to confirm spawn coordinates. *(Deferred — runtime verification needed)*

### 11.2 Clustering — Uniform Grouping, Large Gaps, Overlapping Bubbles

**Symptom:** Bubbles cluster uniformly at spawn, leaving large gaps. Bubbles overlap each other.

**Root cause:**
- Cluster spawning (20% chance, 2–3 bubbles within ±0.03 UV) fires at the same time for all small bubbles during the initial fill, creating a visible uniform grid of clusters.
- No overlap prevention: `_spawn_bubble_at()` does not check if the new bubble's radius overlaps any existing bubble.

**Fix:**
- **Stagger initial spawn:** Add a `spawn_delay` or `age` offset to newly spawned bubbles so they don't all appear at frame 0. Alternatively, pre-age them randomly on first fill.
- **Overlap prevention:** In `_spawn_bubble_at()`, check distance from all existing bubbles. If `dist < r1 + r2 + min_gap`, reject and retry (up to N attempts). Use `min_gap = 0.005` (half a small bubble radius).
- **Reduce cluster tightness:** Increase cluster spread from ±0.03 to ±0.06–0.08 UV.
- **Randomise initial positions:** On first fill (when `len(self._bubbles) == 0`), scatter and fade in bubbles across the full card area rather than spawning from the edge.

**Implementation Checklist:**
- [x] Add overlap check in `_spawn_bubble_at()` with retry loop (max 8 attempts).
- [x] Increase cluster spread to ±0.07 UV.
- [x] On first fill (age == 0, `_time < 0.5`), use random positions across card instead of edge spawn.
- [x] Pre-age bubbles randomly on first fill: `b.age = random.uniform(0, b.max_age * 0.3)`.
- [x] Fade-in ramp for initial-fill bubbles (alpha 0→1 over 1.5s).

### 11.3 Big Bubble Pulsing Not Working + Slider Wiring Audit

**Symptom:** Big bubble pulsing does not respond. At maximum slider value there is no noticeable pulse.

**Root cause (confirmed):**
- Wiring was correct end-to-end. The actual bug was that the pulse multipliers in `snapshot()` were far too weak: `1.0 + bass * pulse * 0.3` gives only 15–30% size increase at typical energy levels — imperceptible.
- Additionally, the pulse used raw instantaneous energy (no smoothing), causing jitter rather than a smooth thump.

**Fix:**
- Added `pulse_energy: float` field to `BubbleState` — smoothed per-bubble energy with fast attack (8×/s) and slow decay (2×/s).
- Raised multipliers: big bubbles `0.3 → 0.8`, small bubbles `0.2 → 0.6`. At `pulse_energy=0.5` (moderate bass) + max slider: 40% size increase. At loud bass: up to 64%.
- `tick()` drives `pulse_energy` per bubble; `snapshot()` uses it instead of raw energy.

**Implementation Checklist:**
- [x] Audit every `bubble_*` setting key end-to-end through all 8 layers. **All wiring verified correct.**
- [x] Confirm `big_bass_pulse` and `small_freq_pulse` are passed to `snapshot()` in the overlay's bubble render path.
- [x] Confirm `bubble_stream_speed`, `bubble_stream_reactivity`, `bubble_drift_*`, `bubble_rotation_amount` all reach `tick()`.
- [x] **Fix pulse strength:** raise multipliers 0.3→0.8 (big) / 0.2→0.6 (small), add smoothed `pulse_energy` per bubble with fast attack / slow decay.

### 11.4 Bubble Travels When Paused / Travel Speed Not Music-Reactive

**Symptom:** Bubbles continue moving when playback is paused. Travel speed is not affected by music at all.

**Root cause:**
- `tick()` is called with `dt` derived from wall-clock time, not gated on `self._playing`. When paused, `dt` is still positive and bubbles move.
- `stream_reactivity` is read from settings but `effective_speed = stream_speed * (1.0 - stream_reactivity + stream_reactivity * overall)`. If `overall` energy is always 0 when paused (correct) but `stream_reactivity` is 0.0 (default or mis-wired), then `effective_speed = stream_speed * 1.0` — always full speed regardless of music.

**Fix:**
- **Pause gate:** In the overlay's bubble tick call, pass `dt = 0.0` when `self._playing` is False. This freezes all bubble positions.
- **Reactivity wiring:** Confirm `bubble_stream_reactivity` is wired through all 8 layers and reaches `tick()` settings dict.
- **Important user note:** Speed should instantly increase but have a longer decay period before slowing down so that if music is rapid it does not end up jerking, travel/speed must always appear smooth not jarring.

**Implementation Checklist:**
- [x] Gate `dt` to 0.0 in bubble tick call when `self._playing` is False.
- [x] Verify `bubble_stream_reactivity` wiring end-to-end. **Confirmed wired through all 8 layers.**
- [ ] Verify energy bands (`overall`) are actually non-zero during playback and zero when paused. *(Runtime verification needed)*

### 11.5 Border Thickness Scaling With Bubble Size

**Symptom:** Small bubbles have border that is too thick relative to their size. Big bubbles are ~0.5px too thick overall.

**Root cause:** `bubble.frag` uses a fixed `u_outline_thickness` (or hardcoded value) for all bubble sizes regardless of radius.

**Fix:**
- In `bubble.frag`, scale the outline thickness proportionally to the bubble's radius: `float thickness = base_thickness * (r / reference_radius)` where `reference_radius` is the mid-range big bubble radius (~0.04).
- Reduce the base outline thickness for big bubbles by ~0.5px equivalent in UV space.

**Implementation Checklist:**
- [x] Read current outline thickness logic in `bubble.frag`.
- [x] Add radius-proportional thickness scaling: `stroke_px = 1.2 * (r / 0.04)`, clamped 0.5–1.8px.
- [x] Reduce big bubble base thickness by ~0.3px (was 1.5px, now 1.2px at reference radius).

---

## Task 12: All Visualizers — Maximum Height 5.0x

**Goal:** Raise the maximum user-configurable growth factor from 4.0x to 5.0x for all visualizer modes.

> *User:* "All visualizers should have their maximum height at 5.0x not 4.0x."

### Complexity Analysis
- **Current code:** `card_height.py` line 73: `growth_factor = max(0.5, min(5.0, float(growth_factor)))` — the clamp already allows 5.0. The `MAX_HEIGHT = 600` hard cap may be the real limiter.
- **UI slider:** The growth factor slider in `widgets_tab_media.py` likely has a `setMaximum(400)` (representing 4.0x with 0.01 step). This is the actual constraint.
- **Fix:** Change the slider maximum from 400 → 500 (or equivalent) in the UI builder for each mode's growth factor slider.

### Implementation Checklist
- [x] Find growth factor slider(s) in `ui/tabs/media/` builders and change `setMaximum` from 400 to 500.
  - Changed in: `spectrum_builder.py`, `oscilloscope_builder.py`, `sine_wave_builder.py`, `blob_builder.py`, `helix_builder.py`, `starfield_builder.py`
  - Also updated config refresh clamps in `widgets_tab_media.py` (6 occurrences of `min(400,...)` → `min(500,...)`)
- [x] Verify `card_height.py` clamp already allows 5.0 (it does — line 73).
- [x] Verify `MAX_HEIGHT = 600` is sufficient for 5.0x at typical base heights (80px × 5.0 = 400px < 600 ✓).
- [ ] Update any tooltip or label text that says "max 4.0x". (None found — sliders show dynamic labels.)

Additional:
1. ~~Bubbles are not part of the double click visualizer swap, this is a mistake, they should be.~~
   **DONE:** Added `VisualizerMode.BUBBLE` to `_CYCLE_MODES` in both `mode_transition.py` and `spotify_visualizer_widget.py`.
2. ~~Gl Compositor has had many edits and is large now, audit it and implement your suggested findings.~~
   **DONE:** Extracted metrics to `gl_compositor_pkg/compositor_metrics.py` (−154 lines, 1926→1772). Added missing burn warmup. See `Audits/gl_compositor_audit.md`.
3. ~~Bubble visualizer was missing Card Height slider.~~
   **DONE:** Added `bubble_growth` slider to `bubble_builder.py`, wired save/refresh in `widgets_tab_media.py`. Pipeline was already complete (model, creators, config_applier, widget, card_height).
4. ~~Burn transition missing from Settings GUI combo, context menu, and TransitionType enum.~~
   **DONE:** Added `"Burn"` to `transitions_tab.py` (combo, type_keys, GL-only lists), `context_menu.py` (default list), `models.py` (`TransitionType.BURN`). Already present in `defaults.py` (pool=True, duration=8000ms), `transition_factory.py` (`_CONCRETE_TYPES`), and `Spec.md`.
---

## Upcoming: Feature Plans

- [x] **Bubble Visualizer** — Phases 1–5 COMPLETE. Phase 6 (testing) in progress. See `Bubble_Vizualiser_Plan.md`.
  - Key bug fix: simulation-only kwargs were being passed to `set_state()` causing TypeError fallback to spectrum.
  - Card height added (3.0x growth factor).
  - All card heights raised +1.0x across all modes.
- [x] **Burn Transition** — Phases 1–3 code COMPLETE. Phase 3 UI controls + Phase 4 testing pending. See `Burn_Transition_Plan.md`.
- [x] **Visualizer Presets System** — Phases 1–2 COMPLETE. Phase 3 (preset definitions) pending. See `Docs/Visualizer_Presets_Plan.md`.
  - `VisualizerPresetSlider` widget (4-notch slider) integrated into all 7 mode builders.
  - All mode controls wrapped in `_<mode>_advanced` container, shown only on Custom.
  - Save/load wired in `widgets_tab_media.py`. Preset overlay applied in `from_mapping()`.
  - Auto-switch to Custom: only fires from advanced container sender, not already Custom.
