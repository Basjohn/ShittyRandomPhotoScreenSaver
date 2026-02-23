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
- **Bubble mode speed-cap scaling (PF-12):** Slider/UI clamps raised to 0.5–4.0× with a hardened gating curve, so idle drift stays calm while high-energy passages can still reach the new ceiling without instantly pegging.

*(See git history for full details of tasks #1–31.)*

---

## Priority Focus (High ROI / Next Up)

1. **Widget Card Border Refresh (1px enhancement)**  DONE
   Goal: visually align every widget/transition card with a consistent 1px border that reads on both light/dark content.  
   Scope: update shared card styles (Clock/Weather/Media/Visualizer tabs, transitions tab) to use a theme token for border width + color, ensure drop shadows survive DPI scaling, add regression checklists in `Docs/Widget_Style.md`.

2. **Control Halo Polish (PF-2)** — ✅ Fixed Feb 23 (kept here for reference)  
   Cursor triangle hotspot now aligns with the OS pointer, every halo shape shares the refreshed gradient + drop-shadow styling, and the diamond received an inner dot indicator. Verified across all six shapes with Ctrl-held interaction + hard-exit coverage; no further action unless UX feedback regresses.

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

**Status:** PARTIALLY FIXED — `_rainbow_per_bar` was the only missing init attribute. PER BAR STILL BROKEN.

**Root cause:** `_rainbow_per_bar` was never initialised in `SpotifyVisualizerWidget.__init__`. When the setting wasn't in the JSON, `config_applier` never set it, and `getattr(widget, '_rainbow_per_bar', False)` always returned `False`.

**Fix:** Added `self._rainbow_per_bar: bool = False` to `__init__`. Full audit (BUG-4) confirmed this was the ONLY missing attribute out of 102.

- [x] `_rainbow_per_bar` initialised in `__init__`.
- [x] Full audit: all 102 config_applier attributes now have `__init__` defaults.
- [ ] User to verify per-bar rainbow works with both checkboxes enabled.
- User: STILL DOES NOT WORK PER BAR. Colours for per bar work when checkbox is checked BUT they do not shift colours when taste the rainbow is enabled, that only works when individual bars is unselected.
**Files:** `spotify_visualizer_widget.py`



---



---

---



---

## Active Features (HIGH PRIORITY)

### FEAT-1: Burn Transition — Thermite Glow + Sparks

**Status:** Needs rework.

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

**Status:** ✅ Completed Feb 23

**Summary:**
- Cursor triangle hotspot now matches the top-left tip exactly, so Ctrl-clicks land where users expect.
- All halo shapes share the new gradient/shadow treatment routed through `_shape_anchor_offset()` helpers, keeping DPI tracking precise.
- Diamond halo picked up an inner dot indicator plus a thicker (0.5 px) outline for clarity across themes.
- Verified all six shapes across DPI scales with hard-exit gating and halo forwarding checks.

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

