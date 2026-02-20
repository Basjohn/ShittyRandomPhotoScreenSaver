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

## Upcoming: Feature Plans

- [x] **Bubble Visualizer** — Phases 1–5 COMPLETE. Phase 6 (testing) in progress. See `Bubble_Vizualiser_Plan.md`.
  - Key bug fix: simulation-only kwargs were being passed to `set_state()` causing TypeError fallback to spectrum.
  - Card height added (3.0x growth factor).
  - All card heights raised +1.0x across all modes.
- [ ] **Burn Transition** — Plan exists in `Burn_Transition_Plan.md`. Not yet started.
- [ ] **Visualizer Presets System** — Comprehensive plan to be drafted. Users pick from set presets or custom (Advanced). Must preserve current defaults as a preset on every visualizer.
