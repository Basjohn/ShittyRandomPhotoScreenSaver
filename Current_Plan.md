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

### 1. Visualizer Custom Settings Lost on Save / Navigation / Runtime Round-Trip

**Status:** `[ ]` Under active investigation
**Priority:** CRITICAL — User data loss, affects ALL visualizer modes and ALL settings

This is the project's most significant open bug. Every visualizer mode is affected. Settings edited in the builder/GUI revert after entering runtime or navigating to another mode's custom slot.

**Canonical reproduction:**
1. Edit Blob Custom → set Body Response to 2.0x
2. Edit Sine Custom → set Line 1 Glow Colour to Red
3. Enter runtime → return to settings
4. **Result:** Sine Line 1 Glow remains Red, but Blob Body Response is back at 1.0x
5. This pattern repeats for ALL settings across ALL modes

**Potential root causes:**

- **A — `restore_visualizer_snapshot()` clearing mode-specific keys not in payload:**
  Mode-prefixed technical keys (e.g. `oscilloscope_bar_count`) get wiped when applying a snapshot that doesn't contain them. The 2026-04-12 technical-key preservation fix may be incomplete or bypassed in some code paths.
- **B — Cross-mode custom cache pollution:**
  `VISUALIZER_CUSTOM_STORAGE_KEY` caches per-mode custom snapshots. When switching from Mode A Custom → Mode B Custom, Mode A's snapshot may be built with wrong-mode keys via `build_normalized_custom_snapshot()`.
- **C — Save path collecting wrong scope:**
  `save_media_settings()` or its callers may still be writing a stale or cross-contaminated snapshot for modes other than the currently active one.

**Relationship to other tasks:**
- Task 2 (Sine/Osc lines 4-6) is likely a specific manifestation of this same bug — lines 4-6 use direct lambda save paths instead of `bind_setting_signal`, which may be failing silently within the same broken pipeline.
- The old "Preset Override Bug Investigation" (see Historical Reference below) attempted fixes that did NOT resolve this. Those fixes are preserved below as context.

**Next steps:**
- [ ] Trace the full save→persist→reload cycle for a single setting change in one mode while another mode's custom is active
- [ ] Determine whether the snapshot written to `settings_v2.json` is correct at write time vs corrupted at read time
- [ ] Verify `build_normalized_custom_snapshot()` scopes to current mode only
- [ ] Verify `restore_visualizer_snapshot()` preserves other modes' custom slots untouched
- [ ] Runtime validation: settings survive cross-mode navigation round-trip
- [ ] Runtime validation: settings survive runtime→settings→runtime cycle

---

### 2. Sine / Oscilloscope Lines 4-6 Settings Do Not Save or Persist

**Status:** `[ ]` Broken — likely a subset of Task 1
**Priority:** CRITICAL
**DO NOT MARK AS FIXED UNLESS USER GIVES VISUAL VALIDATION.**

Lines 4-6 colour swatches, horizontal shifts, and ghost settings do not save. Changes made in the builder revert upon entering runtime or reopening settings. Identical behavior in both Sine and Oscilloscope modes.

**Key evidence (user-found):**
Lines 2-3 use `bind_setting_signal` while lines 4-6 use direct lambda. There is no sane reason for the difference — 2-3 work, 4-6 don't.

**Failed fix:** A previous attempt to align 4-6 with 2-3's save mechanism still did not persist. Either the alignment was incomplete or the underlying pipeline (Task 1) discards the writes downstream.

**Investigation path:**
- [ ] Compare the exact `bind_setting_signal` wiring for lines 2-3 against lines 4-6 lambda wiring — identify every divergence
- [ ] If wiring is now identical, the root cause is Task 1's save pipeline — fix there first
- [ ] If wiring still differs, complete the alignment and retest
- [ ] Runtime validation: change Line 4 colour → enter runtime → return to settings → colour persisted

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
- The perfect circular core is the root problem — base itself should be organically shaped
- **Anti-pinching:** NEVER allow deep pinching. Soft )( curves only, not sharp V-dents. )o( = Good, >o< = TERRIBLE

**Redesign plan:**
1. Replace additive `organic_deform` with multiplicative `organic_base_shape` (0.85–1.15 range)
2. Use lower-frequency harmonics (1.0, 2.0, 3.0) phase-shifted to align valleys between stretch protrusions
3. Integrate wobble/stretch as modulation on the already-organic base — one coherent system
4. Hard anti-pinch: `final_radius >= staged_r * 0.85`
5. Fix `atan()` seam — ensure angle wrapping in all trig calculations

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
  - Files: `ui/tabs/media/technical_controls.py`, `ui/tabs/widgets_tab_media.py`

**Status:** All 5 fixes landed but the root settings-loss problem persists. These may be correct partial fixes or may be masking the actual cause.

---

## Runtime Watchlist

- [ ] `%APPDATA%/SRPSS/settings_v2.json` repair line repeating indefinitely
- [ ] Source curated tree vs generated shipped tree drift
- [ ] Misleading helper/UI preview exceptions
- [ ] Bubble/Blob slipping back into the signal-contract trap documented in [Docs/Historical_Bugs.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Historical_Bugs.md)

---

## Idea Box

1. Add a shimmer/flicker regression test for Spectrum once the actual shimmer task is active.
2. Can Bubbles be made to bounce gently off each other instead of overlapping? Could this be an adjustable setting? Such as 70% of Bubbles Bounce (30% Overlap) and Bounce Speed X%. The speed they bounce away, grouped in a "Bounce" bucket. Separate sliders for Big and Small Bubbles in this bucket.