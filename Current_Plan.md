# Current Plan

Update this after every significant change.

## Guardrails

- Keep this aligned with [Index.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Index.md), [Spec.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Spec.md), [Docs/Defaults_Guide.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Defaults_Guide.md), [Docs/Visualizer_Debug.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_Debug.md), and [Docs/Historical_Bugs.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Historical_Bugs.md).
- Do not mark runtime or visual-feel issues as fixed without user confirmation.
- Treat `presets/visualizer_modes` as the only authored visualizer preset source tree.
- Treat `release/main_mc.dist/presets/visualizer_modes*` as generated artifacts only.
- Do not treat passing tests as visual sign-off.
- Do not make global/shared math changes unless explicitly requested.
- Do not reduce FPS caps below current configured values.
- Do not revive retired visualizer sidecar toggles such as `_use_raw_energy`.
- Do not solve Bubble/Blob by merely swapping one failure family for the opposite one.
- Do not split Bubble directional boot fixes by axis family. Horizontal and vertical directional streams must rise or fall together; if the startup treatment is wrong for one, neither keeps the special case.
- Failures at fixing are to be kept summarised in an issue until the user states the issue is solved.
- Keep checkboxes honest:
  - `[x]` landed and validated by user if visual
  - `[~]` landed or partially proven, still needs runtime eyes
  - `[ ]` not done

---

## Critical / Active
FIXED. HISTORICAL BUGS this and remove from this document.
### 1. Visualizer Custom Settings Lost on Save / Navigation / Runtime Round-Trip

**Status:** `[~]` Root cause identified and fixed — awaiting user runtime validation
**Priority:** CRITICAL — User data loss, affects ALL visualizer modes and ALL settings

This is the project's most significant open bug. Every visualizer mode is affected. Settings edited in the builder/GUI revert after entering runtime or navigating to another mode's custom slot.

**Canonical reproduction:**
1. Edit Blob Custom → set Body Response to 2.0x
2. Edit Sine Custom → set Line 1 Glow Colour to Red
3. Enter runtime → return to settings
4. **Result:** Sine Line 1 Glow remains Red, but Blob Body Response is back at 1.0x
5. This pattern repeats for ALL settings across ALL modes

**Root causes (confirmed 2026-07-25 / 2026-04-13):**

**BUG #6 — Cross-mode save wipe (fixed 2026-07-25):**
`_save_settings_now()` replaced the entire `spotify_visualizer` section with fresh current-mode-only data, wiping all inactive-mode settings on every save. Fixed to merge into existing config before normalizing.
- **File:** `ui/tabs/widgets_tab.py` lines 1287-1303

**BUG #7 — Model serialization gap for lines 4-6 (fixed 2026-04-13, TRUE ROOT CAUSE for Issue 1):**
`SpotifyVisualizerSettings.from_mapping()`, `from_settings()`, and `to_dict()` all read/wrote lines 1-3 but **completely omitted lines 4-6** for both Sine and Oscilloscope modes. The normalization pass (`normalize_visualizer_section_mapping`) goes through `from_mapping()` → `to_dict()`, which silently dropped all line 4-6 keys even when they were correctly collected by `collect_sine_wave_mode_settings()`.

This means:
1. User edits Line 4 color → `collect_sine_wave_mode_settings()` reads it correctly ✓
2. `_save_settings_now()` merges it into existing config correctly ✓ (after BUG #6 fix)
3. `normalize_visualizer_section_mapping()` round-trips through the model → **line 4-6 keys silently dropped** ✗
4. Normalized result written to JSON without line 4-6 → settings lost

**Fix applied:**
- [x] Added all sine lines 4-6 keys to `from_mapping()` (colors, glow colors, travel, shift, ghost enabled)
- [x] Added all sine lines 4-6 keys to `from_settings()` (same set)
- [x] Added all sine lines 4-6 keys to `to_dict()` (same set)
- [x] Added all osc lines 4-6 keys to `from_mapping()` (colors, glow colors, ghost enabled)
- [x] Added all osc lines 4-6 keys to `from_settings()` (same set)
- [x] Added all osc lines 4-6 keys to `to_dict()` (same set)
  - **File:** `core/settings/models.py`
- [x] Verified normalization round-trip preserves line 4-6 keys

**BUG #8 — Runtime config bridge missing lines 4-6 kwargs (fixed 2026-04-13):**
`apply_spotify_vis_model_config()` passed only lines 2-3 kwargs to `vis.apply_vis_mode_config()`. Lines 4-6 colors, glow colors, travel, shifts, ghost enabled were never forwarded to the runtime widget even when the model held correct values. Also missing: `sine_smoothing`, `sine_glow_reactivity`, `osc_glow_reactivity`, osc lines 4-6 colors/glow/ghost.
- **Files:** `rendering/spotify_widget_creators.py`, `rendering/widget_manager.py` (fallback path)

**BUG #9 — Shift updaters used wrong attribute name + shift rows not conditionally visible (fixed 2026-04-13):**
Lines 4-6 shift `bind_setting_signal` updaters wrote to `_sine_lineN_horizontal_shift` but the collect function reads `_sine_lineN_shift` (from slider value directly, so this was harmless for save but incorrect). Shift rows for all lines (2-6) used `_aligned_row()` instead of `_aligned_row_widget()`, making them invisible to the visibility function — they always showed regardless of line count.
- **File:** `ui/tabs/media/sine_wave_builder.py`

**Investigation checklist:**
- [x] Trace the full save→persist→reload cycle for a single setting change in one mode while another mode's custom is active
- [x] Determine whether the snapshot written to `settings_v2.json` is correct at write time vs corrupted at read time → **Corrupted at normalization time (model gap)**
- [x] Verify `build_normalized_custom_snapshot()` scopes to current mode only → Yes, correct
- [x] Verify `restore_visualizer_snapshot()` preserves other modes' custom slots untouched → Yes, correct
- [ ] Runtime validation: settings survive cross-mode navigation round-trip
- [ ] Runtime validation: settings survive runtime→settings→runtime cycle
- [ ] Runtime validation: Line 4-6 colors/shifts survive settings→runtime→settings

---

## Awaiting Validation

### 3. Visualizer Mode Isolation / Bleed Audit

**Status:** `[~]` Mostly landed, final runtime confirmation still open
**Priority:** High

**Landed:**
- [x] Dedicated Blob/Bubble/Spectrum/Oscilloscope/Sine renderer ownership audited
- [x] Dedicated visualizer math/helper ownership audited
- [x] Static isolation fences added for dedicated mode-owned modules
- [x] Shared visualizer change checklist established in [Docs/Visualizer_Change_Checklist.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_Change_Checklist.md)
- [x] Preset/save/repair/regeneration paths aligned with current mode ownership
- [x] Shared beat-engine bar-count hitch fix moved onto one startup/runtime-parity rebuild path
- [x] Shared technical cache replay now no-ops when a mode entry is missing instead of silently borrowing foreign technical state
- [x] GPU extra kwargs now stay mode-local rather than carrying unrelated payload clutter

**Still open:**
- [~] Shared seams in `config_applier`, `spotify_visualizer_widget`, and `spotify_bars_gl_overlay` are much cleaner but remain the highest-risk bleed area
- [ ] Finish a live runtime spot-check across shaper-capable modes once Bubble/Blob validation is calmer

**Lesson:** The remaining bleed risk lives in the shared transport/reset/apply seams, not in the dedicated renderer files.

### 4. Shared Preset Install / Save Location Across SCR and MC

**Status:** `[~]` Landed in code, awaiting live coexistence validation
**Priority:** Medium

- [x] Frozen SCR and MC resolve active curated presets through the shared ProgramData tree
- [x] Packaged assets remain the replacement/bootstrap source rather than the active runtime root
- [x] Normal SCR uninstall no longer deletes the shared curated tree out from under MC
- [x] Focused tests for frozen shared-root resolution and replacement routing landed
- [ ] Validate install, upgrade, and coexistence behavior with both builds present on one machine

---

## Planned

### 5. Blob Organic Core / Deformation Redesign

**Status:** `[ ]` Implementation failed visual validation, redesign required
**Priority:** High — Feature non-functional, but not data-loss
**Scope:** Unshaped blob ONLY (`u_blob_shaper_enabled == 0`)

**Visual evidence (2026-04-12):**
- **Yellow blob:** Perfect circular core extremely visible — star-like protrusions sit on an unmistakable circular base. Golden-ratio harmonic deformation not producing visible distortion.
- **Blue blob:** Sharp cut/seam on left side — classic `atan()` discontinuity at π/-π boundary.

Screenshots: `temp/Example 1.png`, `temp/Example 2.png`, `temp/Example 3.png`

**Why it failed:**
1. Additive deformation on a perfect circle cannot break the circle's visual dominance
2. 10% magnitude is invisible against 90% preserved circle
3. `atan()` discontinuity at left edge creates sharp seam
4. Core, wobble, and stretch calculated independently then summed — should be one coherent system

**User design vision:**
- Valleys should resemble **")" and "("** — gentle, curved, organic, interconnected
- The perfect circular core is the root problem — base itself should be organically shaped, ideally it should be PART OF THE DEFORMATION but with safeguards to prevent sharp indents or pinching.
- **Anti-pinching:** NEVER allow deep pinching. Soft )( curves only, not sharp V-dents. )o( = Good, >< = TERRIBLE

**Redesign plan:**
1. Replace additive `organic_deform` with multiplicative `organic_base_shape` (0.85–1.15 range)
2. Use lower-frequency harmonics (1.0, 2.0, 3.0) phase-shifted to align valleys between stretch protrusions
3. Integrate wobble/stretch as modulation on the already-organic base — one coherent system
4. Hard anti-pinch: `final_radius >= staged_r * 0.85`
5. Fix `atan()` seam — ensure angle wrapping in all trig calculations
6. Additionally run blob pocket tests to confirm pocketing reactions still functions.
   
### 6. Preset Tooling Source-Tree Authority

**Status:** `[ ]` Planned, not started
**Priority:** Medium

**Goal:** Prevent repair/regenerate tooling from overwriting authored presets or resurrecting retired presets.

**Known issues:**
- `tools/visualizer_preset_repair.py --repair-all` backfills keys that may have been intentionally omitted
- Regenerate tooling can resurrect retired presets if source tree was cleaned but generated tree wasn't
- No guard prevents adding back explicitly removed keys

**Plan:**
- [ ] Audit `_sanitize_settings` for backfill logic that adds keys not present in authored payload
- [ ] Add `--source-authoritative` mode (or make default) — remove junk but never add missing keys
- [ ] Ensure `regenerate_visualizer_shipped_presets.py` only mirrors source tree — no resurrection
- [ ] Add a test that authored presets survive a repair round-trip without gaining new keys

---

## Deferred

### 7. Shaped Blob Reaction Variety

**Status:** `[ ]` Deferred until bug-free
**Priority:** Lowest
**Documentation:** [Docs/Visualizer_Preset_Override_Bug_Investigation.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_Preset_Override_Bug_Investigation.md) → `Shaped Blob Reaction Variety (Polish Phase LOWEST PRIORITY)`

**Goal:** Add more reaction variety to shaped blob — currently too uniform.

**Constraints:** Never rearchitecture towards raw energy. Do not over-complicate.

**Ideas:**
1. **Outer Border Wobble** — outermost border wobbles like non-shaped based on energy
2. **Directional Energy Deformation** — energy inside reactive shape causes wobble/deformation along direction
3. **Localized Pulse** — energy nodes cause localized pulse/wobble with decay
4. **Edge Ripple** — energy at edge creates ripple traveling along edge

**Guardrails:** Only begin after custom modes, preset saving/loading, and OSC/SINE 6-line expansion are perfectly healthy for all modes. OSC/SINE extra lines must reference both existing line implementations and [Docs/Visualizer_Change_Checklist.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_Change_Checklist.md).

---

## Historical Reference — Preset Override Bug Investigation (Failed Fixes)

These fixes were attempted for the settings-loss bug (Tasks 1 & 2 above) but **did not resolve the core issue**. Kept as context to avoid re-treading the same ground.

**Documentation:** [Docs/Visualizer_Preset_Override_Bug_Investigation.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_Preset_Override_Bug_Investigation.md)
**History:** [Docs/Historical_Bugs.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Historical_Bugs.md) → `2026-04-11 — Visualizer Preset Override Bug`

- **BUG #1:** `apply_preset_to_config()` used merge overlay → Fixed with CLEAR-then-APPLY
- **BUG #2:** `save_media_settings()` collected all modes → Fixed to current mode only
- **BUG #3:** Call-site `.update()` left stale keys → Fixed to use `restore_visualizer_snapshot()`
  - Files: `ui/tabs/widgets_tab.py`, `rendering/widget_manager.py`
  - Tests: `tests/test_visualizer_preset_cycling_runtime.py`
- **BUG #4:** Technical keys lost when switching presets → `TECHNICAL_CONTROL_KEYS` preservation added
  - Files: `core/settings/visualizer_presets.py`
- **BUG #5:** Technical keys from ALL modes leaked into saves → `current_mode` parameter added
  - Files: `core/settings/visualizer_presets.py`
- **BUG #6:** `_save_settings_now()` replaced entire `spotify_visualizer` section with fresh current-mode-only data → Fixed to merge into existing config before normalizing
  - Files: `ui/tabs/widgets_tab.py`
  - Secondary: `ui/tabs/media/sine_wave_builder.py` — 10 color button lambdas converted to `bind_color_button()`
- **BUG #7:** `SpotifyVisualizerSettings.from_mapping()`, `from_settings()`, and `to_dict()` omitted all sine/osc lines 4-6 keys → normalization silently dropped them
  - Files: `core/settings/models.py` — added ~40 missing keys across all three methods
- **BUG #8:** `apply_spotify_vis_model_config()` only forwarded lines 2-3 kwargs to the runtime widget → lines 4-6 always used defaults at runtime
  - Files: `rendering/spotify_widget_creators.py`, `rendering/widget_manager.py`
- **BUG #9:** Shift updaters wrote `_sine_lineN_horizontal_shift` (wrong attr name) + shift rows used untracked `_aligned_row()` so visibility function couldn't hide them
  - Files: `ui/tabs/media/sine_wave_builder.py`
- **BUG #10:** `SpotifyBarsGLOverlay.set_state()` accepted `sine_line4/5/6_shift` and `sine_travel_line4/5/6` as parameters but **never stored them to `self`** → always used default 0 at GL level despite model and widget having correct values
  - Files: `widgets/spotify_bars_gl_overlay.py`
  - Full detail: [Docs/Historical_Bugs.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Historical_Bugs.md) → `2026-04-13`

**Status:** BUGs #6-#10 all fixed. #6 = cross-mode save wipe, #7 = model serialization gap, #8 = runtime config bridge gap, #9 = shift updater attr name + row visibility, #10 = overlay set_state dropped shift/travel for lines 4-6. Awaiting user runtime validation.

---

### 3. Bubble Bounce Physics

**Status:** `[ ]` Not started — promoted from Idea Box

**Goal:** Bubbles should bounce gently off each other instead of overlapping. This should be an adjustable setting. The existing `_apply_soft_separation()` in `bubble_simulation.py` already pushes overlapping bubbles apart with class-based strength — but it uses a pure position-correction approach (no velocity reflection). The result is that overlapping bubbles separate but don't visually *bounce*.

**Proposed Architecture:**

The bounce system replaces `_apply_soft_separation()` with `_apply_bounce_physics()`. On collision, each bubble pair has its velocity reflected along the collision normal (elastic collision), scaled by a bounce strength factor. Bubbles that don't bounce (governed by the Bounce % slider) fall through to the existing soft-push behavior so they still separate gently without bouncing.

**Settings to add:**

| Setting key | Type | Range | Default | Description |
|---|---|---|---|---|
| `bubble_bounce_big_pct` | int (slider) | 0–100 | 70 | % of big bubble collisions that bounce (rest overlap/soft-push) |
| `bubble_bounce_small_pct` | int (slider) | 0–100 | 30 | % of small bubble collisions that bounce |
| `bubble_bounce_big_speed` | float (slider) | 0.0–2.0 | 0.8 | Bounce speed multiplier for big bubbles (0 = no rebound, 2 = full elastic) |
| `bubble_bounce_small_speed` | float (slider) | 0.0–2.0 | 0.5 | Bounce speed multiplier for small bubbles |

**Files to touch:**

1. **`widgets/spotify_visualizer/bubble_simulation.py`**
   - Add `bounce_big_pct`, `bounce_small_pct`, `bounce_big_speed`, `bounce_small_speed` to `tick()` settings read
   - Replace `_apply_soft_separation(dt)` with `_apply_bounce_physics(dt, settings)` or extend it
   - Collision logic: for each overlapping pair, determine if this collision bounces (RNG seeded per-pair per-frame against the appropriate % slider). If bounce: reflect velocity components along collision normal, scale by speed multiplier. If not: apply existing soft-push.
   - `BubbleState` already has `vx`, `vy` — these drive stream velocity. Bounce should add to them as impulse, then let existing damping/stream logic decay the impulse over subsequent frames.

2. **`widgets/spotify_visualizer/config_applier.py`**
   - Add `_bubble_bounce_big_pct`, `_bubble_bounce_small_pct`, `_bubble_bounce_big_speed`, `_bubble_bounce_small_speed` to the bubble kwargs in `apply_vis_mode_config`
   - Add to `_append_bubble_visual_extras()` so they flow into the `build_gpu_push_extra_kwargs` pipeline (not needed for GPU but needed for sim settings)

3. **`widgets/spotify_visualizer/tick_pipeline.py`**
   - Add `bubble_bounce_big_pct`, `bubble_bounce_small_pct`, `bubble_bounce_big_speed`, `bubble_bounce_small_speed` to `sim_settings` dict in `dispatch_bubble_simulation()`

4. **`core/settings/models.py`**
   - Add 4 new fields to `SpotifyVisualizerSettings` dataclass
   - Add to `from_mapping()`, `from_settings()`, `to_dict()`

5. **`core/settings/defaults.py`**
   - Add defaults for the 4 new keys

6. **`ui/tabs/media/bubble_builder.py`**
   - Add a new collapsible bucket "Bounce" in the normal layout (after Motion)
   - 4 sliders: Big Bounce %, Small Bounce %, Big Bounce Speed, Small Bounce Speed
   - Wire with `bind_setting_signal`

7. **`ui/tabs/media/bubble_settings_binding.py`**
   - Add the 4 keys to `collect_bubble_mode_settings()`

8. **`rendering/spotify_widget_creators.py`** + **`rendering/widget_manager.py`**
   - Add the 4 kwargs to `apply_spotify_vis_model_config()` and fallback

9. **`widgets/spotify_bars_gl_overlay.py`**
   - Add the 4 fields to `__init__`, `set_state` signature and body

10. **`tools/visualizer_preset_repair.py`**
    - Run `--repair-all` after implementation to update curated presets

**Checklist:**
- [ ] Implement `_apply_bounce_physics()` in `bubble_simulation.py`
- [ ] Add 4 settings to model, defaults, and serialization
- [ ] Add Bounce bucket to `bubble_builder.py`
- [ ] Wire settings collection in `bubble_settings_binding.py`
- [ ] Wire runtime config bridge (config_applier, widget_creators, widget_manager, overlay)
- [ ] Wire tick pipeline `sim_settings`
- [ ] Run preset repair
- [ ] Test: big bubbles at 100% bounce + high speed → visible elastic rebounds
- [ ] Test: 0% bounce → same as current behavior
- [ ] Test: persistence round-trip

---

## Runtime Watchlist

- [ ] `%APPDATA%/SRPSS/settings_v2.json` repair line repeating indefinitely
- [ ] Source curated tree vs generated shipped tree drift
- [ ] Misleading helper/UI preview exceptions
- [ ] Bubble/Blob slipping back into the signal-contract trap documented in [Docs/Historical_Bugs.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Historical_Bugs.md)

---

## Idea Box

1. Add a shimmer/flicker regression test for Spectrum once the actual shimmer task is active using synthetic audio that shows it, then adjust it to user results until a solution is found.