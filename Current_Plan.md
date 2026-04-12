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
- **Status:** All three preset MERGE bugs fixed. Blob organic core deformation landed. Sine/Osc 6-line expansion partially implemented (UI, bindings, config applier, defaults done — tests stale). Eight test failures root-caused and queued for fix.
- **Most important open work:** Fix 8 stale tests, verify/complete Sine/Osc 6-line expansion end-to-end.
- **Most important open historical thread:** [Docs/Historical_Bugs.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Historical_Bugs.md) -> `2026-04-10 — Bubble / Blob Signal-Contract Trap`
- **Preset pipeline:** Source tree -> repair tool -> shipped regeneration -> tests
- **Visualizer sweep reference:** [Docs/Visualizer_Change_Checklist.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_Change_Checklist.md)

---

## Active Tasks

### 0. Test Suite Health — 8 Known Failures

**Status:** `[ ]` Root-caused, fix pending
**Priority:** Critical — these are regression guards that must pass before further work

**Failure analysis (2026-04-12):**

**Category A — Tests assume old buggy all-mode save behavior (Bug #2 fix exposed them):**
- [ ] `test_sine_wave_swatch_persistence` — Sets sine colors without setting mode to `sine_wave`. Default is `spectrum`.
- [ ] `test_oscilloscope_swatch_persistence` — Same; doesn't set mode to `oscilloscope`.
- [ ] `test_secondary_line_ghost_toggles_persist` — Sets osc/sine ghost toggles without switching modes.
- [ ] `test_blob_pulse_controls_load_and_roundtrip` — Sets blob values without setting mode to `blob`.
- [ ] `test_visualizers_toggle_gates_controls` — `visualizers_enabled` is a global key that may not survive mode-scoped save.
- **Reasoning:** All five were written when `save_media_settings` collected ALL modes. After the cross-mode pollution fix, it only collects the active mode. Tests must set the correct mode before saving.

**Category B — Bubble roundtrip expects pure preset dict but gets UI-widget state:**
- [ ] `test_bubble_move_to_custom_roundtrip_preserves_curated_preset_snapshot` — Compares `apply_preset_to_config` output against UI-round-tripped snapshot. UI widgets inject defaults (drift_frequency, drift_amount, etc.) that differ.
- **Reasoning:** Test must either accept UI-round-tripped values or compare only preset-declared keys.

**Category C — 6-line expansion tests not updated:**
- [ ] `test_load_oscilloscope_mode_settings_updates_osc_owned_controls` — Asserts 3 lines of color syncs, UI builds 6.
- [ ] `test_load_sine_wave_mode_settings_updates_sine_owned_controls` — Same.
- **Reasoning:** Lines 4-6 added to builders/bindings/config but test assertions not extended.

**Fix plan:**
- **A:** Set correct mode on tab before saving.
- **B:** Build expected snapshot through same UI round-trip, or compare only mode-prefixed preset keys.
- **C:** Extend assertion lists to include line 4-6 color button syncs.

### 1. Sine / Oscilloscope 6-Line Expansion — Verification & Completion

**Status:** `[~]` Partially landed — UI, bindings, config applier, defaults have lines 4-6; tests stale; renderer/presets/repair status unclear
**Priority:** High
**Primary reference:** [Docs/Visualizer_Change_Checklist.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_Change_Checklist.md)

**What appears already landed:**
- [x] UI builders create line 4-6 widgets (`oscilloscope_builder.py`, `sine_wave_builder.py`)
- [x] Settings bindings load/collect line 4-6 state (`oscilloscope_settings_binding.py`, `sine_wave_settings_binding.py`)
- [x] Config applier reads/writes line 4-6 kwargs (`config_applier.py`)
- [x] Default settings include line 4-6 keys with colors and ghost toggles (`default_settings.py`)
- [x] Multi-line visibility handles lines 4-6 in both builders
- [x] GPU extra kwargs push line 4-6 colors/shifts to overlay

**What still needs verification/completion:**
- [ ] Renderer line iteration — do Sine/Osc renderers iterate over lines 4-6 or hard-capped at 3?
- [ ] GPU shader — does the shader accept and render lines 4-6?
- [ ] Overlay kwargs test — `tests/test_visualizer_overlay_kwargs.py` may need line 4-6 coverage
- [ ] Preset pipeline — do curated presets include line 4-6 keys? Does repair tool handle them?
- [ ] Settings plumbing tests — Category C failures (extend assertions)
- [ ] Round-trip save/load tests for lines 4-6

**Non-negotiable guardrails:**
- Do not let Sine and Oscilloscope silently share authored per-line state.
- Startup, runtime, presets, repair, regeneration, and tests must all agree on the same ceiling.
- Do not add legacy shims for dead keys.

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

**Remaining:**
- [ ] Runtime validation: shaped blob no longer locks in across preset switches
- [ ] Runtime validation: custom presets survive round-trips through curated presets

### 4. Visualizer Mode Isolation / Bleed Audit

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

### 6. Shared Preset Install / Save Location Across SCR and MC

**Status:** `[~]` Landed in code, awaiting live coexistence validation
**Priority:** Medium

- [x] Frozen SCR and MC now resolve active curated presets through the shared ProgramData tree
- [x] Packaged assets remain the replacement/bootstrap source rather than the active runtime root
- [x] Normal SCR uninstall no longer deletes the shared curated tree out from under MC
- [x] Focused tests for frozen shared-root resolution and replacement routing landed
- [ ] Validate install, upgrade, and coexistence behavior with both builds present on one machine

(Merged into Task 1 above — 6-line expansion is now a verification/completion task, not planned-from-scratch.)

### 7. Blob Organic Core/Deformation

**Status:** `[~]` Implemented — awaiting runtime visual validation
**Priority:** Medium

**Goal:**
Improve unshaped blob to have a more organic core so the circle is not visible as often, while **absolutely avoiding the pinch inward stretch** from before.

**What landed (2026-04-12):**
- [x] Replaced the ineffective curvature-detection approach (5% max, 2-harmonic detection, 95% floor) with a proper multi-harmonic organic core deformation in `blob.frag`
- [x] Uses 4 low-frequency sine waves at golden-ratio angular frequencies (1.618, 2.414, 3.732, 0.618) that never align with existing wobble/stretch harmonics
- [x] Deformation scales proportionally to `staged_r` (blob base size)
- [x] Slight outward bias (+1.2% of staged_r) so average radius doesn't shrink
- [x] Floor changed from `core_radius * 0.95` to `staged_r * 0.90` — allows up to 10% visible inward dips while making pinch physically impossible
- [x] No new uniforms needed — uses only existing `motion_angle`, `time`, `staged_r`, `u_blob_shaper_enabled`
- [x] Shaped blob path completely unaffected (guarded by `u_blob_shaper_enabled == 0`)

**Design rationale:**
- **Reasoning:** The old curvature-detection approach tried to find where the circle was visible and add tiny inward dips there. This failed because: (a) it only sampled 2 wobble harmonics, missing the full shape; (b) the 5% max was too subtle; (c) the 95% floor negated most of the effect. The new approach makes the entire base shape non-circular everywhere using slowly-evolving asymmetric distortion. Valleys between protrusions naturally show the organic base instead of a perfect circle.
- **Reasoning:** Golden-ratio angular frequencies ensure the organic pattern never aligns with the integer-harmonic wobble (2, 3, 5, 7) or stretch frequencies, maximizing the circle-breaking effect.
- **Reasoning:** Floor anchored to `staged_r` (unstretched base) rather than `core_radius` (includes stretch). This means protrusions are unconstrained while valleys can dip up to 10% inward.

**What still needs real eyes:**
- [ ] Confirm the visible circular core is gone or substantially reduced in the examples the user provided
- [ ] Confirm the organic deformation looks natural and doesn't create harsh edges
- [ ] Confirm no pinch or inward denting is possible under any playback conditions
- [ ] Confirm the blob doesn't look smaller on average (outward bias should compensate)
- [ ] Confirm the deformation evolves smoothly over time without jumps or static patterns

**Guardrails:**
- Absolutely avoid the pinch inward stretch from before
- Must never have the ability to pinch — hard floor at 90% of staged_r
- Keep changes scoped to unshaped blob core geometry

### 8. Shaped Blob Reaction Variety

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

### 9. Preset Tooling Source-Tree Authority

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

## Runtime Watchlist

- [ ] `%APPDATA%/SRPSS/settings_v2.json` repair line repeating indefinitely
- [ ] Source curated tree vs generated shipped tree drift
- [ ] Misleading helper/UI preview exceptions
- [ ] Bubble/Blob slipping back into the signal-contract trap documented in [Docs/Historical_Bugs.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Historical_Bugs.md)

---

## Idea Box

1. Add a shimmer/flicker regression test for Spectrum once the actual shimmer task is active.
