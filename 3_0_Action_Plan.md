# 3.0 Action Plan

## Architecture Guardrails (Always Apply)

- **Threading:** `ThreadManager` only — no raw `threading.Thread`, `ThreadPoolExecutor`, or `QThread` for business logic.
- **UI thread:** All Qt widget updates via `invoke_in_ui_thread()`.
- **Settings:** Every new setting through all 8 layers: model dataclass → `from_settings()` → `from_mapping()` → `to_dict()` → creator kwargs → widget init → extra dict → GL overlay state. See `Docs/Defaults_Guide.md`.
- **Transitions:** Must end on a final frame matching the fully-rendered wallpaper at progress 1.0.
- **Monolith avoidance:** Modules approaching 1700+ lines → schedule refactor.
- **Painting:** Use `update()` not `repaint()`. Gate high-frequency ops behind `SRPSS_PERF_METRICS`.

---

## Completed Snapshot (Archived)

Key wins locked in for v3.0:
- **Visualizer polish:** Taste The Rainbow exemptions, Spectrum per-bar hues, Oscilloscope ghosting, Sine Wave amplitude/micro-wobble fixes, Bubble spawn/stream upgrades.
- **Transitions:** Burn v2 shader + new UI, ripple/rain-drip parity, crumble/particle cleanups.
- **UI platform:** NoWheelSlider adoption, multi-monitor wake fixes, Spotify visualizer settings audit, ColorSwatchButton migration (all widget tabs + burn glow).

*(See git history for full details of tasks #1–31.)*

---

## Priority Focus (High ROI / Next Up)

1. **Widget Card Border Refresh (1px enhancement)**  
   Goal: visually align every widget/transition card with a consistent 1px border that reads on both light/dark content.  
   Scope: update shared card styles (Clock/Weather/Media/Visualizer tabs, transitions tab) to use a theme token for border width + color, ensure drop shadows survive DPI scaling, add regression checklists in `Docs/Widget_Style.md`.

2. **Control Halo Polish (PF-2)**  
   Goal: make the interaction halos feel purposeful and accurate.  
   Scope: cursor triangle hotspot alignment, drop-shadow consistency across all six shapes, diamond inner-dot indicator, shadow/fade verification pass.  
   Suggested execution order: (a) hotspot math in `cursor_halo.py`, (b) shared shadow constants in `display_input.py`, (c) visual QA on all shapes with logging screenshot refs.

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
- User: STILL DOES NOT WORK PER BAR. Colours for per bar work when checkbox is checked BUT they do not shift colours when taste the rainbow is enabled, that only works when individual bars is unselected.
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

- [x] Exempt Sine Wave line colours from Taste The Rainbow (glows still rainbow-shifted) and keep Oscilloscope line colour fixed. Blob shader now rainbow-shifts fill/glow/outline but leaves the edge highlight exempt so the bright rim stays user-selected. (shader fixes in `sine_wave.frag`, `oscilloscope.frag`, `blob.frag`)

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

---



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
- [ ] User to confirm thermite glow looks correct (bright white-hot ignition, then receding line no, not bright at all.).
- [ ] User to confirm sparks are visible and controllable. (No, nothing visible)
- [ ] User to confirm Burn Settings panel appears when Burn is selected.
No sparks, no ash, dull pathetic glow.

**Files:** `burn_program.py`, `transitions_tab.py`, `transition_factory.py`

---




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

### PF-3: Settings Export/Import Coverage Audit

**Status:** PLANNED

**Goal:** Ensure the preset export/import pipeline captures every new setting introduced post-v2.5 (bubble stream knobs, swatch migrations, Burn extras, etc.).

**Scope:**
- [ ] Diff `save_*_settings()` outputs against `settings_v2.json` exports to confirm keys exist.
- [ ] Run export/import round-trip; confirm Spotify visualizer, transitions, widgets all restore latest options.
- [ ] Document verified keys + remaining gaps in `Docs/Visualizer_Presets_Plan.md`.

**Files:** `settings_manager.py`, `ui/tabs/widgets_tab_media.py`, `Docs/Visualizer_Presets_Plan.md`

---

### PF-4: Logging Noise Cleanup (Spam)

**Status:** PLANNED

**Goal:** Reduce amount of logging for simply --debug runs, identify spamming sources, minimize to most useful metrics.



---

### PF-3: Visualizer Presets — Phase 3 (Preset Definitions)
(Deferred, developer/user will supply json exports of settings later on, simply make sure our export feature works to include relevant settings)
Preset slider infrastructure complete (phases 1–2). Phase 3 pending:
- [ ] Define actual preset values for each mode (1/2/3/Custom notches).
- [ ] See `Docs/Visualizer_Presets_Plan.md`.

---

### PF-5: Multi-Monitor Sleep/Wake — Needs Live Test

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

