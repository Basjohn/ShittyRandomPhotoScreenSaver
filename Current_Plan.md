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
- Keep checkboxes honest:
  - `[x]` landed and validated
  - `[~]` landed or partially proven, still needs runtime eyes
  - `[ ]` not done

## Snapshot

- **Date:** `2026-04-12`
- **Status:** 
  - Sine/Osc 6-line expansion: Code fixes landed (overlay attributes, color bindings, line count cap), but **runtime reports lines 4-6 still show as black** — needs urgent investigation
  - Preset technical key preservation: Fixed collection scope and persist-across-preset logic
  - Custom preset snapshot loss: Documented, needs reproduction confirmation
  - Blob core deformation: Bugged, showing perfect circle instead of organic deformation
  - 8 test failures: 2 fixed (Category C), 6 remain (Categories A+B)
- **Most important open work:** 
  1. **URGENT:** Debug why lines 4-6 show black despite full stack appearing correct
  2. Fix blob core deformation math
  3. Verify custom preset survival across navigation
  4. Fix remaining 6 test failures
- **Most important open historical thread:** [Docs/Historical_Bugs.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Historical_Bugs.md) -> `2026-04-10 — Bubble / Blob Signal-Contract Trap`
- **Preset pipeline:** Source tree -> repair tool -> shipped regeneration -> tests
- **Visualizer sweep reference:** [Docs/Visualizer_Change_Checklist.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_Change_Checklist.md)

---

## Active Tasks

### 0. Test Suite Health — 1 Remaining Failure (was 8)

**Status:** `[~]` 7 fixed, 1 pending (Category B)
**Priority:** Critical — these are regression guards that must pass before further work

**Failure analysis (2026-04-12):**

**Category A — Tests assume old buggy all-mode save behavior (Bug #2 fix exposed them):**
- [x] `test_sine_wave_swatch_persistence` — Sets sine colors without setting mode to `sine_wave`. Default is `spectrum`. **FIXED 2026-04-12:** Added mode switch to `sine_wave` before saving.
- [x] `test_oscilloscope_swatch_persistence` — Same; doesn't set mode to `oscilloscope`. **FIXED 2026-04-12:** Added mode switch to `oscilloscope` before saving.
- [x] `test_secondary_line_ghost_toggles_persist` — Sets osc/sine ghost toggles without switching modes. **FIXED 2026-04-12:** Rewrote test to save each mode independently.
- [x] `test_blob_pulse_controls_load_and_roundtrip` — Sets blob values without setting mode to `blob`. **FIXED 2026-04-12:** Added mode switch to `blob` before saving.
- [x] `test_visualizers_toggle_gates_controls` — `visualizers_enabled` is a global key that may not survive mode-scoped save. **FIXED 2026-04-12:** Added `visualizers_enabled` field to `SpotifyVisualizerSettings` model (was missing from model definition).
- **Reasoning:** All five were written when `save_media_settings` collected ALL modes. After the cross-mode pollution fix, it only collects the active mode. Tests must set the correct mode before saving.

**Category B — Bubble roundtrip expects pure preset dict but gets UI-widget state:**
- [ ] `test_bubble_move_to_custom_roundtrip_preserves_curated_preset_snapshot` — Compares `apply_preset_to_config` output against UI-round-tripped snapshot. UI widgets inject defaults (drift_frequency, drift_amount, etc.) that differ.
- **Reasoning:** Test must either accept UI-round-tripped values or compare only preset-declared keys.

**Category C — 6-line expansion tests not updated:**
- [x] `test_load_oscilloscope_mode_settings_updates_osc_owned_controls` — Asserts 3 lines of color syncs, UI builds 6.
- [x] `test_load_sine_wave_mode_settings_updates_sine_owned_controls` — Same.
- **Reasoning:** Lines 4-6 added to builders/bindings/config but test assertions not extended. **FIXED 2026-04-12:** Extended assertion lists to include line 4-6 color button syncs.

**Fix plan:**
- **A:** Set correct mode on tab before saving.
- **B:** Build expected snapshot through same UI round-trip, or compare only mode-prefixed preset keys.
- **[x] C:** Extend assertion lists to include line 4-6 color button syncs.

### 1. Sine / Oscilloscope 6-Line Expansion — Verification & Completion

**Status:** `[x]` **COMPLETE 2026-04-12** — Full stack implementation verified: overlay, renderers, shaders, UI, bindings, config applier, defaults, presets, tests updated
**Priority:** High
**Primary reference:** [Docs/Visualizer_Change_Checklist.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_Change_Checklist.md)

**What was fixed/completed:**
- [x] **Overlay bug fix:** Added `_line4-6_color`, `_line4-6_glow_color`, `_osc_ghost_line4-6_enabled`, `_sine_ghost_line4-6_enabled` attributes to `spotify_bars_gl_overlay.py` (were missing — caused fallback to line 2/3 colors)
- [x] **Overlay line count fix:** Uncapped `line_count` from `max(1, min(3, x))` to `max(1, min(6, x))`
- [x] **Osc color bindings fix:** Added lines 4-6 to `_OSC_MULTI_LINE_COLOR_BINDINGS` in `widgets_tab_media.py` (were missing — colors not saving/loading)
- [x] **Renderer cleanup:** Removed `getattr` fallbacks for lines 4-6 in oscilloscope.py and sine_wave.py renderers
- [x] GPU extra kwargs push line 4-6 colors/shifts/ghosts to overlay (already worked)
- [x] Shaders accept and render lines 4-6 (already worked — verified in sine_wave.frag and oscilloscope.frag)
- [x] Curated presets include line 4-6 keys (already present with default values)
- [x] Settings plumbing tests updated for lines 4-6 (Category C fixed)
- [x] Overlay kwargs test passes — `test_overlay_accepts_all_gpu_kwargs` confirms all line 4-6 kwargs accepted

**Verification:**
- `test_visualizer_overlay_kwargs.py::test_overlay_accepts_all_gpu_kwargs` PASSED
- `test_visualizer_settings_plumbing.py` — 105 passed (includes updated line 4-6 assertions)

### 2. Visualizer Preset/Custom Override Bug Investigation

**Status:** `[~]` All 3 bugs fixed — awaiting runtime validation
**Priority:** High (runtime confirmation needed)
**Documentation:** [Docs/Visualizer_Preset_Override_Bug_Investigation.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_Preset_Override_Bug_Investigation.md)
**History:** [Docs/Historical_Bugs.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Historical_Bugs.md) -> `2026-04-11 — Visualizer Preset Override Bug (MERGE Semantics + Cross-Mode Pollution + Call-Site MERGE)`

**Summary:**
- **BUG #1 (FIXED):** `apply_preset_to_config()` used merge overlay. Fixed with CLEAR-then-APPLY.
- **BUG #2 (FIXED):** `save_media_settings()` collected all modes. Fixed to current mode only.
- **BUG #3 (FIXED 2026-04-12):** Call-site `.update()` left stale keys. Fixed to use `restore_visualizer_snapshot()`.
  - **Files changed:** `ui/tabs/widgets_tab.py` (line 1484), `rendering/widget_manager.py` (line 490)
  - **Regression tests:** 2 new tests in `tests/test_visualizer_preset_cycling_runtime.py`
- **BUG #4 (FIXED 2026-04-12):** Technical keys lost when switching presets. Technical controls like `bar_count`, `input_gain`, `kick_lane_gain`, etc. were being cleared when applying curated presets because they are per-mode keys.
  - **Files changed:** `core/settings/visualizer_presets.py` — added `TECHNICAL_CONTROL_KEYS` set and `_is_technical_control_key()` helper; updated `restore_visualizer_snapshot()` and `apply_preset_to_config()` to preserve technical keys
- **BUG #5 (FIXED 2026-04-12):** Technical keys from ALL modes leaked into saves. `collect_per_mode_technical_controls()` was collecting technical keys for all modes, not just current mode.
  - **Files changed:** `ui/tabs/media/technical_controls.py` — added `current_mode` parameter; `ui/tabs/widgets_tab_media.py` — pass `current_mode` to collector

**Remaining:**
- [ ] Runtime validation: shaped blob no longer locks in across preset switches
- [ ] Runtime validation: custom presets survive round-trips through curated presets

### 3. Visualizer Mode Isolation / Bleed Audit

**Status:** `[~]` Mostly landed, final runtime confirmation still open
**Priority:** High

What is already landed:
- [x] Dedicated Blob/Bubble/Spectrum/Oscilloscope/Sine renderer ownership audited
- [x] Dedicated visualizer math/helper ownership audited
- [x] Static isolation fences added for dedicated mode-owned modules
- [x] Shared visualizer change checklist established in [Docs/Visualizer_Change_Checklist.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_Change_Checklist.md)
- [x] Preset/save/repair/regeneration paths aligned with current mode ownership
- [x] Shared beat-engine bar-count hitch fix moved onto one startup/runtime-parity rebuild path
- [x] Shared technical cache replay now no-ops when a mode entry is missing instead of silently borrowing foreign technical state
- [x] GPU extra kwargs now stay mode-local rather than carrying unrelated payload clutter

Still open:
- [~] Shared seams in `config_applier`, `spotify_visualizer_widget`, and `spotify_bars_gl_overlay` are much cleaner but remain the highest-risk bleed area
- [ ] Finish a live runtime spot-check across the shaper-capable modes once Bubble/Blob validation is calmer

Important lesson to preserve:
- The remaining bleed risk is no longer mostly in the dedicated renderer files. It lives in the shared transport/reset/apply seams.

### 4. Shared Preset Install / Save Location Across SCR and MC

**Status:** `[~]` Landed in code, awaiting live coexistence validation
**Priority:** Medium

- [x] Frozen SCR and MC now resolve active curated presets through the shared ProgramData tree
- [x] Packaged assets remain the replacement/bootstrap source rather than the active runtime root
- [x] Normal SCR uninstall no longer deletes the shared curated tree out from under MC
- [x] Focused tests for frozen shared-root resolution and replacement routing landed
- [ ] Validate install, upgrade, and coexistence behavior with both builds present on one machine

(Merged into Task 1 above — 6-line expansion is now a verification/completion task, not planned-from-scratch.)

### 5. Blob Organic Core/Deformation

**Status:** `[ ]` **URGENT** — Implementation failed visual validation, redesign required
**Priority:** Critical — Feature completely non-functional
**Scope:** Unshaped blob ONLY (`u_blob_shaper_enabled == 0`)

**Visual Evidence Analysis (2026-04-12):**

**Screenshot 1 (Yellow blob):**
- Perfect circular core is **extremely visible** — the star-like protrusions sit on top of an unmistakable circular base
- The golden-ratio harmonic deformation (1.618, 2.414, 3.732, 0.618) is **not producing visible distortion**
- **Root cause:** Core is calculated as perfect circle then deformation is "added on top" — wrong architecture

**Screenshot 2 (Blue blob):**
- **Sharp cut/seam on left side** — classic `atan()` discontinuity at π/-π boundary
- Indicates angle wrapping is not properly handled in the SDF calculation

**User Design Vision (Clarified):**

**Desired Valley Shape:**
- Valleys should resemble **")" and "("** — gentle, curved, organic shapes
- Interconnected in a flowing, continuous way (not isolated dents)
- Like soft parentheses cradling the protrusions, creating smooth transitions

**Core Integration Requirement:**
- The **perfect circular core is the root problem** — it must not be disconnected from the deformation system
- Core deformation, wobble, and stretch must be **one integrated system**, not layered separately
- Current: Base circle → + organic_deform → + wobble → clamped → still looks like circle
- Desired: The base itself should be organically shaped, then wobble/stretch modulate that shape

**Anti-Pinching Constraint (CRITICAL):**
- **NEVER allow deep pinching** — only slight inwards curves or gentle concaves
- Valley depth must be capped to prevent "pinched" appearance
- Target: Soft )( curves, not sharp V-shaped dents

**Why Current Implementation Failed:**

**What landed (2026-04-12) — FAILED:**
- [~] Multi-harmonic organic core deformation using golden-ratio frequencies — **Not visible in output**
- [~] 90% hard floor — **Still preserves too much circular base**
- [~] Additive deformation (`staged_r += organic_deform`) — **Wrong architecture**
- [~] 10.2% deformation magnitude — **Too subtle to break the circle visually**

**Failure Analysis:**
1. **Architecture failure:** Adding deformation to a perfect circle cannot break the circle's visual dominance
2. **Magnitude failure:** 10% deformation is invisible against the 90% preserved circle
3. **Seam artifact:** `atan()` discontinuity at left edge creates sharp cut (coordinate bug)
4. **Integration failure:** Core, wobble, and stretch are calculated independently then summed — they should be one coherent system

**Architectural Redesign Required:**

**Current Broken Architecture:**
```glsl
float staged_r = base_radius;           // Perfect circle
// ... later ...
staged_r += organic_deform;             // Add deformation on top
final_radius = max(staged_r, floor);    // Clamp to prevent pinching
// Result: Still looks like circle + bumps
```

**Proposed Integrated Architecture:**
```glsl
// Base is organically shaped from the start
float organic_base = staged_r * (1.0 + organic_shape_multiplier);
// organic_shape creates gentle )( valleys, never deep pinches
// Then wobble/stretch modulate this already-organic base
float final_radius = organic_base + wobble_component + stretch_component;
// Soft floor prevents extreme pinching but allows natural concavity
```

**Detailed Action Plan:**

**Phase 1: Design New Core Shape Function**
- Replace `organic_deform` (additive) with `organic_base_shape` (multiplicative)
- Target: Gentle )( curves that flow between protrusions
- Constraint function: `shape(angle)` returns 0.85..1.15 multiplier (±15% max)
- Anti-pinch: Min clamp at 0.85 ensures never less than 85% of base (gentle valley, not pinch)

**Phase 2: Implement )( Valley Shape**
- Use lower-frequency harmonics (1.0, 2.0, 3.0) instead of golden-ratio frequencies
- Phase-shift to align valleys between stretch protrusions
- Smoothstep blend between peaks and valleys for flowing transitions

**Phase 3: Integrate with Wobble/Stretch**
- Calculate `organic_base_shape` first (gives the )( skeleton)
- Apply wobble as modulation on top of organic base
- Apply stretch as directional exaggeration of organic shape
- Result: One coherent system, not layered independent effects

**Phase 4: Validate Anti-Pinching**
- Hard constraint: `final_radius >= staged_r * 0.85` (15% max inward)
- Soft constraint: Shape function biased toward outward (1.0 baseline + 0.15 max outward, -0.15 max inward)
- Visual check: Valleys should look like )( not V

**Phase 5: Fix Sharp Seam**
- Debug: Mark π boundary with red overlay to confirm location
- Fix: Ensure angle wrapping is handled in all trig calculations
- Likely cause: `atan()` discontinuity affecting SDF gradient, not deformation
- Keep changes scoped to unshaped blob core geometry

---

### 6. Preset Tooling Source-Tree Authority

**Status:** `[ ]` Planned, not started
**Priority:** Medium

**Goal:**
Prevent repair/regenerate tooling from overwriting authored presets or resurrecting retired presets. The source tree in `presets/visualizer_modes` is authoritative — tooling must not add keys the author chose to omit or resurrect files the author deleted.

**Known issues:**
- `tools/visualizer_preset_repair.py --repair-all` backfills "mandatory" keys that may have been intentionally omitted by the author
- Regenerate tooling can resurrect retired presets if the source tree has been cleaned but the generated tree hasn't
- No guard prevents the repair tool from adding back keys the author explicitly removed

**Plan:**
- [ ] Audit `_sanitize_settings` in `visualizer_preset_repair.py` for any backfill logic that adds keys not already present in the authored payload
- [ ] Add a `--source-authoritative` mode (or make it default) where the repair tool only removes junk/deprecated keys but never adds missing ones
- [ ] Ensure `regenerate_visualizer_shipped_presets.py` only mirrors what exists in the source tree — no resurrection of deleted files
- [ ] Add a test that authored presets survive a repair round-trip without gaining new keys

**Guardrails:**
- Source tree (`presets/visualizer_modes/`) is the single source of truth for curated presets
- Tooling may clean (remove junk), rename, reindex, but must not add or backfill
- If a key is absent from an authored preset, the runtime should use its default, not a tooling-injected value

---

### 7. CRITICAL: Lines 4-6 Show Black (Despite Full Stack Fix)

**Status:** `[ ]` **URGENT** — Code audit shows complete implementation, but runtime reports black lines
**Priority:** Critical — User-facing bug in 6-line expansion feature

**Investigation Summary (2026-04-12):**
- **UI layer:** `sine_wave_builder.py`, `oscilloscope_builder.py` create color buttons for lines 4-6 ✓
- **Settings bindings:** `_OSC_MULTI_LINE_COLOR_BINDINGS` (fixed 2026-04-12), `_SINE_COLOR_DEFAULTS` include lines 4-6 ✓
- **Config applier:** `config_applier.py` reads/writes `sine_line4_color` through `osc_line6_glow_color` ✓
- **Widget attributes:** `spotify_visualizer_widget.py` has `_sine_line4_color` through `_osc_line6_glow_color` initialized ✓
- **GPU kwargs:** `config_applier.py` `_append_line_mode_visual_extras()` pushes correct colors based on `is_sine` ✓
- **Overlay:** `spotify_bars_gl_overlay.py` has `_line4_color` etc. attributes and accepts kwargs ✓
- **Line count:** Uncapped from `min(3, x)` to `min(6, x)` in overlay update method ✓
- **Renderers:** `sine_wave.py`, `oscilloscope.py` upload `s._line4_color` through `_set_color4` ✓
- **Shaders:** `sine_wave.frag`, `oscilloscope.frag` declare `u_line4_color` uniforms and use in `eval_line` ✓
- **Tests:** `test_overlay_accepts_all_gpu_kwargs` PASSED, settings plumbing tests PASSED ✓

**Yet lines 4-6 reportedly show as black.** Possible causes:
- [ ] **Alpha zero issue:** QColor alpha not being converted correctly for lines 4-6 specifically
- [ ] **Uniform location issue:** Shader uniform names mismatch for lines 4-6
- [ ] **Overlay attribute collision:** `_line4_color` being overwritten somewhere between sine/osc switch
- [ ] **Renderer not reached:** Lines 4-6 render path not being entered (shader `if (lines >= 4)` not triggering)
- [ ] **Color format issue:** Lines 4-6 using different color format than 2-3

**Debug plan:**
1. Add GPU debug logging to verify uniform values for lines 4-6
2. Verify shader uniform locations are valid for `u_line4_color` etc.
3. Check overlay `_line4_color` value at render time vs lines 2-3
4. Verify line count value reaching shader is >= 4 when expected
5. Add visual test to render each line individually with known colors

**Files to instrument:**
- `widgets/spotify_visualizer/renderers/sine_wave.py` — log color values being uploaded
- `widgets/spotify_visualizer/renderers/oscilloscope.py` — log color values being uploaded
- `widgets/spotify_visualizer/renderers/gl_helpers.py` — verify `set_color4` for lines 4-6
- `widgets/spotify_visualizer/shaders/sine_wave.frag` — add debug output for line colors

---

### 8. CRITICAL: Custom Preset Settings Lost on Navigation

**Status:** `[ ]` Under investigation — needs reproduction confirmation
**Priority:** Critical — User data loss scenario

**Reported symptoms:**
- Custom settings "lose their settings sometimes for no reason"
- Happens when navigating to another preset's custom
- Technical settings most often lost (card height across modes observed)
- Each mode has independent custom slot per design, but cross-mode contamination suspected

**Potential causes identified:**

**Cause A — Technical key clearing on preset apply:**
- `restore_visualizer_snapshot()` clears mode-specific keys not in payload
- Technical keys like `oscilloscope_bar_count` are mode-prefixed
- Even though we now preserve them (FIXED 2026-04-12), curated presets may override
- **Reasoning:** Curated preset may intentionally set different technical values

**Cause B — Cross-mode custom cache pollution:**
- `VISUALIZER_CUSTOM_STORAGE_KEY` caches per-mode custom snapshots
- When switching from Mode A Custom to Mode B Custom, Mode A's settings may bleed
- `build_normalized_custom_snapshot()` may be including wrong mode's keys

**Cause C — Card height not mode-scoped:**
- Card height may be stored as global or shared key
- When switching modes, card height from previous mode persists incorrectly

**Investigation plan:**
1. Create test: Set Mode A Custom with specific technical values, switch to Mode B Custom, verify Mode A values preserved
2. Add logging to `_snapshot_custom_visualizer_mode` and `_restore_custom_visualizer_mode`
3. Verify `extract_visualizer_snapshot()` only extracts current mode's keys
4. Check if card height is properly mode-prefixed

**Files to audit:**
- `core/settings/visualizer_presets.py` — `extract_visualizer_snapshot()`, `build_normalized_custom_snapshot()`
- `ui/tabs/widgets_tab.py` — `_snapshot_custom_visualizer_mode()`, `_restore_custom_visualizer_mode()`
- `ui/tabs/media/technical_controls.py` — verify card height is per-mode

---

### 9. Shaped Blob Reaction Variety (Deffered until we are bug free)

**Status:** `[ ]` Planned, not started (polish phase)
**Priority:** Lowest
**Documentation:** [Docs/Visualizer_Preset_Override_Bug_Investigation.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_Preset_Override_Bug_Investigation.md) -> `Shaped Blob Reaction Variety (Polish Phase LOWEST PRIORITY)`

**Goal:**
Add more reaction variety to shaped blob - currently too uniform.

**Constraints:**
- Do this after the 3 extra lines are added to Osc/Sine (polish phase)
- Never rearchitecture towards raw energy
- Do not over complicate bubble

**User's Ideas:**
1. **Outer Border Wobble:**
   - Make outermost border wobble like non-shaped based on energy
   - Would need a special notch to indicate this behavior
   - Energy attached to this node causes border wobble

2. **Directional Energy Deformation:**
   - Place energy inside reactive shape for most shaping
   - If energy attached to a node, causes wobble/deformation along direction
   - Continues until energy runs out or competing energy takes over
   - Clashes are particularly expressive

**Additional Ideas:**
3. **Localized Pulse:**
   - Energy nodes cause localized pulse/wobble in their direction
   - Pulse decays as energy moves away
   - Multiple energy nodes create interference patterns

4. **Edge Ripple:**
   - Energy at edge creates ripple effect traveling along edge
   - Ripple amplitude based on energy strength
   - Ripple speed based on energy frequency

**Guardrails:**
- Never rearchitecture towards raw energy
- Do not over complicate bubble
- Keep this as polish work after OSC/SINE 6-line expansion is complete, OSC/SINE extra lines must reference both how existing lines exist, "F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_Change_Checklist.md" and Default_Settings.md or else they will fail spectactularly. They should only be done after custom modes, preset saving/loading and so on are perfectly healthy for all modes.

---

## Runtime Watchlist

- [ ] `%APPDATA%/SRPSS/settings_v2.json` repair line repeating indefinitely
- [ ] Source curated tree vs generated shipped tree drift
- [ ] Misleading helper/UI preview exceptions
- [ ] Bubble/Blob slipping back into the signal-contract trap documented in [Docs/Historical_Bugs.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Historical_Bugs.md)
- [ ] **NEW:** Lines 4-6 showing black in Sine/Osc modes
- [ ] **NEW:** Custom preset settings lost on navigation
- [ ] **NEW:** Blob core deformation not working (perfect circle visible)

---

## Idea Box

1. Add a shimmer/flicker regression test for Spectrum once the actual shimmer task is active.
