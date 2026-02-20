# 3.0 Action Plan

## Architecture Guardrails (Always Apply)

- **Threading:** `ThreadManager` only — no raw `threading.Thread`, `ThreadPoolExecutor`, or `QThread` for business logic.
- **UI thread:** All Qt widget updates via `invoke_in_ui_thread()`.
- **Settings:** Every new setting through all 8 layers: model dataclass → `from_settings()` → `from_mapping()` → `to_dict()` → creator kwargs → widget init → extra dict → GL overlay state. See `Docs/Defaults_Guide.md`.
- **Transitions:** Must end on a final frame matching the fully-rendered wallpaper at progress 1.0.
- **Monolith avoidance:** Modules approaching 1700+ lines → schedule refactor.
- **Painting:** Use `update()` not `repaint()`. Gate high-frequency ops behind `SRPSS_PERF_METRICS`.

---

## Completed (Archived)

31 tasks completed through v3.0 development. Key milestones:
- Taste The Rainbow (global hue-shift), Spectrum rainbow per-bar, Oscilloscope ghosting
- Sine Wave: micro-wobble, heartbeat (localised spikes at zero-crossings), width-reaction, line positioning
- Bubble: spawn fix, clustering, pulse, specular, diagonal movement, motion trails
- Burn transition: shader v2 (thin receding line), UI panel, factory cleanup
- Control halo shapes, volume slider fix, media double-click refresh
- Settings GUI: NoWheelSlider, viz preset defaults (Custom=3), multi-monitor sleep/wake fix
- All visualizer max height raised to 5.0x

*(See git history for full details of tasks #1–31)*

---

## Active Bugs (HIGH PRIORITY)

### BUG-1: Bubble Gradient Bleeds Outside Card Border

**Status:** FIXED — rounded-rect SDF discard implemented.

**Fix:** Replaced simple rectangular margins with a proper rounded-rect SDF discard in `bubble.frag`. Content is inset by `border_w=2px`, corners use `inner_radius=6px` (card_radius 8 - border 2). Each corner is checked with circle SDF and discarded if outside. Gradient and bubbles are now tightly contained within the card border.

- [x] Rounded-rect SDF discard matching card border-radius.
- [x] User to verify no bleed at corners.

**Files:** `bubble.frag`

---

### BUG-2: Spectrum Rainbow + Per-Bar Colours Not Working

**Status:** FIXED — `_rainbow_per_bar` was the only missing init attribute.

**Root cause:** `_rainbow_per_bar` was never initialised in `SpotifyVisualizerWidget.__init__`. When the setting wasn't in the JSON, `config_applier` never set it, and `getattr(widget, '_rainbow_per_bar', False)` always returned `False`.

**Fix:** Added `self._rainbow_per_bar: bool = False` to `__init__`. Full audit (BUG-4) confirmed this was the ONLY missing attribute out of 102.

- [x] `_rainbow_per_bar` initialised in `__init__`.
- [x] Full audit: all 102 config_applier attributes now have `__init__` defaults.
- [ ] User to verify per-bar rainbow works with both checkboxes enabled.
- User: STILL DOES NOT WORK PER BAR.
**Files:** `spotify_visualizer_widget.py`

---

### BUG-3: Sine Wave Lines 2/3 Misaligned + Poor Bass Reaction + Shader Compile Regression

**Status:** FIXED — 3 root causes identified and resolved.

**Root causes:**
1. Lines 2/3 used different energy bands (mid/high-heavy) while line 1 used bass-heavy → different amplitudes at LOB=0.
2. Lines 2/3 used unique wave effect and micro wobble frequency/time constants → visual divergence even at LOB=0.
3. `bass_pulse` multiplier was only 1.1× with default sensitivity 0.1 → effective bass contribution was 0.11×.

**Fixes:**
- [x] All 3 lines now share the same base energy formula `e_base`. Lines 2/3 blend toward their unique band mix only as LOB increases (`mix(e_base, own_band, lob * 0.4)`).
- [x] Wave effect and micro wobble for lines 2/3 now use `mix(line1_value, own_value, lob)` — at LOB=0 they are identical to line 1.
- [x] `bass_pulse` multiplier raised from 1.1× to 2.0× for much stronger bass reactivity.
- [x] **Regression fix:** GLSL forward-reference — `lob` was declared after `e2_band`/`e3_band` which used it. Moved `lob` declaration before all energy calculations. Shader now compiles correctly.
- [ ] User to verify lines overlap at LOB=0/VShift=0 and diverge naturally as LOB increases.
- [ ] Sine Wave reactivity still extremely poor. Requires very high sensitivity to get any movement but that pins the sine waves to the top and bottom of the card, they never go low/tight.
- [ ] Microwobble does not cause extra line snake like effect desires whatsoever, fix.
- [ ] Width reaction does NOTHING visually at any setting, fix.

- [ ] Exempt Sine Wave Line Colours from Taste The Rainbow. Glows etc still effected. Also Exclude Blob Outline only.

**Files:** `sine_wave.frag`

---

### BUG-5: White Flash in Rainbow Mode (Spectrum / Oscilloscope)

**Status:** FIXED

**Root cause:** `u_rainbow_hue_offset` is computed as `(accumulated_time * speed * 0.1) % 1.0`. At the exact wrap-around point (value = 0.0), the shader's `<= 0.001` dead-zone guard fires and returns the original colour (white) for one frame — causing a brief white flash.

**Fix:** When rainbow is enabled, if `raw < 0.001` push `(raw + 0.002) % 1.0` instead, skipping the dead zone. Same fix applied to per-bar slow cycle.

- [x] Dead-zone skip applied in `spotify_bars_gl_overlay.py` for both rainbow and per-bar paths.
- [ ] User to confirm white flash no longer occurs.

**Files:** `spotify_bars_gl_overlay.py`

---

### BUG-4: Settings Audit & Normalisation (SYSTEMIC)

**Status:** COMPLETE — both phases done.

**Phase 1 result:** Automated audit of all 102 attributes set by `config_applier.py` against `SpotifyVisualizerWidget.__init__`. Only 1 was missing: `_rainbow_per_bar` (now fixed).

**Phase 2 result:** Cross-referenced `save_media_settings()` ↔ `config_applier` ↔ `models.py` ↔ `spotify_widget_creators.py`. Found 3 pipeline gaps where settings were saved/loaded by the UI but never reached the widget at startup:

| Setting | Gap | Fix |
|---|---|---|
| `spectrum_rainbow_per_bar` | Missing from `apply_spotify_vis_model_config()` creator call | Added `spectrum_rainbow_per_bar=model.spectrum_rainbow_per_bar` |
| `bubble_trail_strength` | Missing from model dataclass, `from_settings`, `from_mapping`, `to_dict`, and creator | Added to all 5 locations |
| `sine_line_dim` | Same as above — missing from model entirely | Added to all 5 locations |

- [x] All 102 `config_applier` keys have `__init__` defaults.
- [x] `save_media_settings()` ↔ `config_applier` cross-referenced — no orphaned save keys.
- [x] `build_gpu_push_extra_kwargs()` — all 64 direct widget attrs confirmed to have `__init__` defaults.
- [x] 3 pipeline gaps fixed in `models.py` and `spotify_widget_creators.py`.

**Files:** `spotify_visualizer_widget.py`, `config_applier.py`, `widgets_tab_media.py`, `models.py`, `spotify_widget_creators.py`

---

## Active Features (HIGH PRIORITY)

### FEAT-1: Burn Transition — Thermite Glow + Sparks

**Status:** CODE COMPLETE — awaiting live test.

**What's done:**
- Shader v3: thermite startup delay (first 5% of progress = glow builds to max brightness before front moves), thermite brightness multiplier (1.4× during ignition), additive bloom for HDR-like white-hot core.
- Optional sparks via `u_smoke_enabled` toggle — bright flickering particles near burn front, intensity controlled by `u_smoke_density` slider.
- UI labels updated: "Smoke Particles" → "Sparks", "Smoke Density" → "Spark Intensity".
- All Burn settings wired: direction (4 + Random), jaggedness, glow intensity, char width, glow colour picker, sparks toggle + intensity, ash toggle + density.

**Remaining:**
- [ ] User to confirm thermite glow looks correct (bright white-hot ignition, then receding line).
- [ ] User to confirm sparks are visible and controllable.
- [ ] User to confirm Burn Settings panel appears when Burn is selected.

**Files:** `burn_program.py`, `transitions_tab.py`, `transition_factory.py`

---

### FEAT-2: Visualizer Mode Switch vs Launch-Start Reactivity Difference

**Status:** FIXED — beat engine smoothing state now resets on mode switch.

**Root cause:** `set_visualization_mode()` only reset display bars and GPU geometry cache. The shared `_SpotifyBeatEngine` retained stale `_smoothed_bars`, `_energy_bands`, and `_waveform` from the previous mode, dampening the new mode's initial reactivity.

**Fix:**
- [x] Added `reset_smoothing_state()` to `_SpotifyBeatEngine` — clears smoothed bars, energy bands, waveform, and resets smoothing timestamp.
- [x] `set_visualization_mode()` now calls `engine.reset_smoothing_state()` on mode change.
- [ ] User to verify Oscilloscope/Blob are equally reactive when switched to at runtime vs launch.

**Files:** `beat_engine.py`, `spotify_visualizer_widget.py`

---

## Pending Features (MEDIUM PRIORITY)

### PF-1: Colour Picker Button Standardisation

**Status:** PLANNED

**Goal:** Replace all colour picker buttons across the settings GUI with the Burn-style preview swatch (coloured rectangle that opens QColorDialog on click). All should have white outlines and subtle drop shadows.

**Scope:**
- [ ] Audit all colour picker usages across all settings tabs.
- [ ] Create a reusable `ColourSwatchButton` widget (white outline, drop shadow, opens QColorDialog).
- [ ] Replace existing colour buttons with `ColourSwatchButton` everywhere.
- [ ] Verify Burn glow colour picker already matches this pattern (it does — use as reference).
- [ ] Give all widget cards 1px thicker borders (that already have borders)

**Files:** All `*_tab.py` files, `shared_styles.py`

---

### PF-2: Control Halo Improvements

**Status:** PLANNED

**Scope:**
- [ ] Cursor triangle: make top-left point the actual clickable hotspot (like a real cursor).
- [ ] All halo shapes: add drop shadows and consistent visual effects.
- [ ] Diamond shape: add inner dot indicator showing exact click point.
- [ ] Verify all 6 shapes render correctly with shadow and fade.

**Files:** `cursor_halo.py`, `display_input.py`

---

### PF-3: Visualizer Presets — Phase 3 (Preset Definitions)
(Deferred, developer/user will supply json exports of settings later on, simply make sure our export feature works to include relevant settings)
Preset slider infrastructure complete (phases 1–2). Phase 3 pending:
- [ ] Define actual preset values for each mode (1/2/3/Custom notches).
- [ ] See `Docs/Visualizer_Presets_Plan.md`.

---

### PF-4: Multi-Monitor Sleep/Wake — Needs Live Test

**Status:** Fix implemented (Tasks 2.1 + 2.2). Not yet verified on hardware.

- [ ] Test: sleep both monitors, wake, confirm compositor re-anchors to correct screen.
- [ ] Test: media widget stays visible after wake with Spotify playing.

---

## Deferred / Low Priority

| Item | Reason deferred |
|------|----------------|
| `spotify_visualizer_widget.py` monolith split | High risk, many entangled paths |
| `gl_compositor` further refactor | Already extracted metrics module; remainder stable |
| FFT worker removal | 18 files entangled |
| `overlay_timers` → ThreadManager | Frame-timing critical, risky |

