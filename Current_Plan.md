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

- **Date:** `2026-04-11`
- **Status:** Reddit Helper scheduled-task authority is runtime-proven. Spectrum vocal-lane, energy arrows, recent preset-switch hitch work, and the settings-shell border-radius compromise are all archived in history. The live work now is Bubble/Blob finish-up, the final visualizer isolation/runtime pass, and preparing the Sine/Osc six-line expansion cleanly.
- **Most important open historical thread:** [Docs/Historical_Bugs.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Historical_Bugs.md) -> `2026-04-10 — Bubble / Blob Signal-Contract Trap`
- **Preset pipeline:** Source tree -> repair tool -> shipped regeneration -> tests
- **Visualizer sweep reference:** [Docs/Visualizer_Change_Checklist.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_Change_Checklist.md)

---

## Active Tasks

### 0. Visualizer Preset/Custom Override Bug Investigation

**Status:** `[~]` Bugs #1/#2 fixed, Bug #3 (call-site merge) fixed — awaiting runtime validation
**Priority:** Critical
**Documentation:** [Docs/Visualizer_Preset_Override_Bug_Investigation.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_Preset_Override_Bug_Investigation.md)
**History:** [Docs/Historical_Bugs.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Historical_Bugs.md) -> `2026-04-11 — Visualizer Preset Override Bug (MERGE Semantics + Cross-Mode Pollution)`

**Summary:**
- **BUG #1 - MERGE Semantic (FIXED):** `apply_preset_to_config()` used `merged.update(preset_settings)` which only overwrote keys present in preset. Fixed with CLEAR-then-APPLY pattern.
- **BUG #2 - Cross-Mode Pollution (FIXED):** `save_media_settings()` collected settings from ALL modes. Fixed to only collect current mode settings.
- **BUG #3 - Call-Site MERGE (FIXED 2026-04-12):** Even after Bug #1 was fixed inside `apply_preset_to_config`, the two callers (`_on_visualizer_preset_changed` in `widgets_tab.py` and `cycle_visualizer_preset` in `widget_manager.py`) used `.update()` to merge the result back into the live config. `.update()` only adds/overwrites keys — it never removes stale mode-specific keys (e.g. `blob_shaper_enabled`) that `apply_preset_to_config` had cleared on its internal copy. This caused custom settings like the blob shaper to "stick" across preset switches, making it impossible to exit shaped-blob mode.
  - **Reasoning:** `apply_preset_to_config` returns a clean dict with stale mode keys removed, but `.update()` merges it as an overlay. The stale keys in the original dict survive untouched.
  - **Fix:** Both call sites now use `restore_visualizer_snapshot()` instead of `.update()`. This function does proper in-place CLEAR-then-APPLY: it removes mode-specific keys not present in the applied result, then writes the new values.
  - **Files changed:** `ui/tabs/widgets_tab.py` (line 1484), `rendering/widget_manager.py` (line 490)
  - **Regression tests:** `test_runtime_cycle_purges_stale_mode_keys_on_preset_switch`, `test_runtime_cycle_custom_roundtrip_preserves_known_custom_keys` in `tests/test_visualizer_preset_cycling_runtime.py`

**All Phases:**
- [x] Phase 1: Root Cause Analysis - THREE distinct bugs identified
- [x] Phase 2: Fix Implementation - ALL THREE BUGS FIXED
- [x] Phase 3: Regression Tests - 11 cycling tests pass, 295 broader tests pass
- [x] Phase 4: Cross-Mode Verification - Manual verification complete for Bugs #1/#2
- [ ] Phase 5: Runtime validation of Bug #3 fix — confirm shaped blob no longer locks in, confirm custom presets survive round-trips through curated presets

**User Guidance:**
Users who saved custom presets during the buggy period may need to re-save them to remove pollution from other modes' default values.

### 1. Bubble / Blob Runtime Stability Follow-Up

**Status:** `[~]` Awaiting runtime validation
**Priority:** High
**History:** [Docs/Historical_Bugs.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Historical_Bugs.md) -> `2026-04-10 — Bubble / Blob Signal-Contract Trap: Dead Smoothed Hold vs Raw-Energy Blowout`

What is landed:
- [x] Bubble no longer uses the retired persisted raw-energy toggle path
- [x] Bubble overdrive now uses stricter entry/hold rules instead of the earlier over-permissive gate
- [x] Bubble big-bubble sustained support has been cooled so ordinary hot passages are less likely to pin the ceiling
- [x] Bubble refill now has post-startup spawn budgets so missing-count backlogs are not allowed to dump in one tick
- [x] Bubble spawn spacing is now size-aware so big bubbles do not legally spawn as tightly packed as before
- [x] Ordinary stream-mode Bubble no longer uses the same full-card cold-start fill that was immediately exposing dense authored counts in-card
- [x] Bubble promotions are still preserved, but ordinary stream modes now only allow a tiny short-lived promotion assist once the real big-bubble lane is already hot
- [x] Promoted stream bubbles now use a much weaker sustained bass support so they read as fresh accent noise instead of counterfeit extra big bubbles
- [x] Directional stream startup now uses a real entry-side trickle contract instead of the earlier fake in-card depth seed attempt
- [x] Blob still keeps the non-shaped concurrent pocket architecture rather than going back to one shared decay bucket
- [x] Blob calm-window unwind remains tightened from the recent signal-contract pass
- [x] Blob now has a non-circular pinch guard in shader space so wobble cannot subtract arbitrarily below the preserved body floor
- [x] Focused regression coverage now exists for Bubble backlog refill behavior and the earlier overdrive/plateau family

What still needs real eyes:
- [ ] Confirm Bubble no longer forms the new startup stream columns / entry-lane stacks now showing up across directional presets
- [~] Confirm Bubble no longer piles visible big-bubble or mixed refill waves into one entry region
- [ ] Confirm Bubble startup distribution feels naturally pre-flowing within the first visible passes instead of taking `3-4` columns to normalize
- [ ] Confirm Bubble big bubbles no longer live at max size or feel permanently in overdrive
- [ ] Confirm Bubble big bubbles actually breathe between hits instead of hovering hot and only barely contracting
- [ ] Confirm Bubble overlap stays aesthetically rare, especially for big-bubble vs big-bubble contact
- [ ] Confirm Bubble grouping is no longer overly uniform; small bubbles may cluster, but big bubbles should not read like a second permissive cluster layer
- [~] Confirm Bubble specular sizing now reads coupled to the bubble again instead of grotesquely oversized
- [~] Confirm non-shaped Blob inward pinching is no longer a practical live possibility
- [~] Confirm non-shaped Blob still feels reactive and organic after the pinch-floor guard

Current best theory to preserve:
- Bubble’s remaining risk is now concentrated in the live overdrive/ceiling/refill contract, not in stale raw-energy persistence.
- The old decorative `2-3` cluster path was not the whole story; the worse “looks like 9 arrived together” symptom likely came from refill backlog stacking at the same entry lane.
- Blob’s remaining inward-pinch risk looked less like stale preset junk and more like final wobble being free to subtract past the preserved stretch/body floor.
- Latest runtime evidence now sharpens the Bubble split further:
  - spiral/swirl variants still look materially healthier in both spawning and reactivity
  - non-spiral stream variants remain the true disaster zone
  - that points suspicion toward edge-spawn + stream-lane refill + ordinary travel contracts more than toward Bubble as a whole
- Older comparison anchors now matter here:
  - `a87a46f` (`2026-03-05`, `Bubble And Burn, The Obvious Combination.`)
  - `5b82c63` (`2026-03-18`, `The Unfuckening Part 2wo`)
  - both predate the current stream-mode clutter family and are more useful Bubble baselines than the much newer April commits
- The strongest current Bubble theory from those older comparisons:
  - older stream-mode Bubble did not use the same full-card initial fill path now exposing authored dense counts immediately on mode entry/reset
  - older stream-mode Bubble also did not use the current temporary small->big promotion path that lets ordinary small bubbles behave like extra bass-driven big bubbles during beat bursts
  - together those newer paths can explain why spiral/swirl still look healthier while ordinary stream presets now read as overstuffed, wrongly sized, and visually "too big" even before pure overdrive math is considered
- The newest live regression split to preserve:
  - removing ordinary stream in-card cold fill was directionally correct, but it exposed a second missing piece: directional presets now cold-start from a shallow edge lane, so multiple bubbles can visibly stack into startup columns before travel depth has built up
  - separately, big-bubble breathing is still not solved because the current snapshot contract is still too inflation-heavy relative to how little `bubble_big_contraction_bias` is allowed to pull the bubble back down
  - those are two different Bubble bugs and must not be re-merged into one vague "Bubble still bad" bucket
- The user added an explicit guardrail after the startup experiments:
  - horizontal and vertical directional streams must not be treated as two different product classes for boot fixes
  - if the startup method is wrong for one axis family, it is wrong for both and should be removed or redesigned symmetrically
- Latest runtime evidence also says Bubble is still not practically solved:
  - still overdrives too often
  - still sticks high/max too often
  - still produces weirdly sized elements/specular feel
  - still forms oversized groups of big bubbles, which should be rare at most
- Latest runtime evidence (2026-04-11 newest user pass) sharpened the directional-stream failure:
  - startup now shows obvious vertical/entry-lane columns in every directional stream preset instead of a believable already-flowing field
  - first attempted answer was an off-card ramp / seeded travel-depth contract, but that still created obvious multi-column birth patterns and was therefore the wrong shape of fix
  - current direction is stricter: directional startup should simply trickle from the real entry side with restrained early spawn budgets rather than trying to pre-distribute visible depth
  - an intermediate attempt that only special-cased left/right startup behavior is now explicitly rejected by product guardrail and must not survive as the “solution” if up/down still suffers
  - big bubbles are also still not giving the intended pulse-then-deep-breath behavior; they remain too maxed and do not visibly contract enough between hits
- Latest runtime evidence (2026-04-11 later user pass) sharpened the grouping contract:
  - Bubble overlap is still too permissive in practice
  - grouping now reads too uniform, which makes the remaining startup columns even more obvious
  - the intended visual class split is now explicit:
    - small bubbles may cluster with each other and around big bubbles
    - big bubbles should avoid other big bubbles as much as possible
    - promoted small bubbles must inherit big-bubble overlap rules while promoted
- Preset-specific offenders the user called out from the latest run:
  - `Preset 3 (Orange Soda)`
  - `Preset 6 (Lava Flow)`
- Latest Blob note:
  - Blob still does not convincingly reach higher stages as music changes, but that currently looks more likely to be preset/baseline tuning than a clear new architectural failure

Validation/tests now covering this:
- [x] `tests/test_bubble_reactivity.py`
- [x] `tests/test_visualizer_reactivity_quality.py`
- [x] `tests/test_bubble_reactivity.py::TestInitialFillContract`
- [x] `tests/test_bubble_reactivity.py::TestSmallBubblePromotion`

Follow-up if validation still fails:
- [ ] Re-check directional startup budgets/entry cadence if columns still appear; do not go back to synthetic depth seeding unless there is stronger proof than before
- [ ] Remove any leftover axis-specific boot special-casing if live validation confirms the user-observed “horizontal and vertical fail together” rule still holds
- [ ] Tune Bubble refill cadence separately from Bubble cluster flavor if runtime still shows lane pile-ups
- [ ] Rework Bubble overlap/grouping so it matches the intended visual classes:
  - smalls permissive
  - bigs avoid big-big overlap strongly
  - promoted smalls obey big-bubble spacing while promoted
- [ ] Rebalance Bubble breathing directly:
  - reduce big-bubble pulse inflation toward the older healthier range
  - make `bubble_big_contraction_bias` materially affect quiet-state radius instead of only shaving a token amount
- [ ] Re-audit Bubble specular-size coupling if ceiling behavior is calmer but highlights still look detached
- [ ] Revisit Blob pinch floor fraction only if live runtime still shows ugly inward dents
- [ ] Trace why ordinary stream modes still fail while spiral modes behave better; compare edge-spawn travel/refill flow instead of tuning all Bubble modes blindly together
- [ ] Compare current Bubble non-spiral flow against the older known-better commit before doing more broad tuning
- [ ] Cut back stream-mode Bubble inflation paths first:
  - remove or sharply limit full-card initial fill for ordinary stream presets
  - remove or sharply limit temporary small->big promotion for ordinary stream presets
- [ ] Decide whether curated Blob/Bubble presets need authored retunes after the runtime contract is accepted
- [ ] Create dedicated Blob and Bubble sentinel presets once runtime behavior is trusted again

### 2. Visualizer Mode Isolation / Bleed Audit

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

### 3. Spectrum Consolidation Pass

**Status:** `[~]` Partially landed
**Priority:** Medium

Already landed:
- [x] Creative `Reactivity` / `Shape Floor` language separated from technical sensitivity/noise-floor language
- [x] Misleading `Adaptive Sensitivity` wording replaced with the explicit recommended-sensitivity path
- [x] Mode-aware audio block-size tooltip guidance added
- [x] Shared `AGC Strength` recommendation marker added through the centralized slider styling layer
- [x] Sine/Oscilloscope copy clarified so renderer-side controls stop reading like duplicates of technical sensitivity
- [x] Bubble swirl hides ordinary stream/drift rows while active

Still open:
- [ ] Decide whether `AGC Strength` can be reduced further in scope or presentation without removing real expert tuning
- [ ] Decide whether Spectrum should keep the recommended/manual sensitivity toggle at all
- [ ] Keep shimmer-at-mid-height as a specific future target
- [ ] When shimmer work starts, add a behavior-level regression test in the same spirit as the Blob reactivity tests

Preserve these notes:
- `Input Gain` is non-negotiable and must stay.
- Do not “solve” shimmer by smoothing away the underlying signal.

### 4. Shared Preset Install / Save Location Across SCR and MC

**Status:** `[~]` Landed in code, awaiting live coexistence validation
**Priority:** Medium

- [x] Frozen SCR and MC now resolve active curated presets through the shared ProgramData tree
- [x] Packaged assets remain the replacement/bootstrap source rather than the active runtime root
- [x] Normal SCR uninstall no longer deletes the shared curated tree out from under MC
- [x] Focused tests for frozen shared-root resolution and replacement routing landed
- [ ] Validate install, upgrade, and coexistence behavior with both builds present on one machine

### 5. Raise Sine / Oscilloscope Authored Line Ceiling From 3 To 6

**Status:** `[ ]` Planned, not started
**Priority:** Medium
**Primary reference:** [Docs/Visualizer_Change_Checklist.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_Change_Checklist.md)

Goal:
- Raise the authored line-count ceiling for both Sine Wave and Oscilloscope from `3` to `6`, while keeping their mode ownership isolated and without reviving the old shared-setting/bleed behavior.

Non-negotiable guardrails:
- Do not let Sine and Oscilloscope silently share authored per-line state again.
- Do not land a UI-only line-count increase; startup, runtime, presets, repair, regeneration, and tests must all agree on the same ceiling.
- Do not add legacy shims that keep old dead keys alive forever. Migrate or repair authored payloads cleanly instead.
- Do not change visualizer math for unrelated modes while doing this pass.
- Do not treat horizontal/vertical Bubble startup experiments as precedent for per-mode special-casing elsewhere; this task is about a clean authored-capacity upgrade only.

Areas that must be touched if this proceeds:
- [ ] Canonical settings model/defaults
  - `core/settings/models.py`
  - `core/settings/default_settings.py`
  - `core/settings/defaults_snapshot.json`
- [ ] Settings UI / bindings
  - `ui/tabs/media/sine_wave_builder.py`
  - `ui/tabs/media/oscilloscope_builder.py`
  - `ui/tabs/media/sine_wave_settings_binding.py`
  - `ui/tabs/media/oscilloscope_settings_binding.py`
- [ ] Runtime config application / widget handoff
  - `widgets/spotify_visualizer/config_applier.py`
  - `widgets/spotify_visualizer_widget.py`
  - any renderer/overlay path that currently assumes only `line1..line3`
- [ ] Renderer / math consumers
  - Sine and Oscilloscope runtime line iteration, line-color/shift/width ownership, and any GPU kwargs or cached payloads that are presently hard-capped at `3`
- [ ] Preset pipeline
  - `presets/visualizer_modes/*` for curated authored payloads if the schema changes
  - `core/settings/visualizer_presets.py`
  - `tools/visualizer_preset_repair.py`
  - shipped-artifact regeneration after curated source changes
- [ ] Tests
  - settings plumbing and round-trip save/load
  - runtime application of authored lines `4-6`
  - preset repair/migration coverage so old payloads are upgraded or cleaned rather than half-read
- [ ] Docs
  - `Spec.md`
  - `Index.md`
  - `Docs/TestSuite.md`
  - this plan entry once the task starts

Specific implementation risks to account for:
- Any current “three explicit slots” code path will need to be found, not just obvious UI builders.
- If per-line settings are currently named as fixed keys (`line1`, `line2`, `line3`), the expansion needs one authoritative contract that every layer follows.
- Preset repair/regeneration must be updated in the same pass so authored presets, custom saves, and shipped artifacts cannot drift into different ceilings.
- Runtime cache replay must still no-op on missing mode entries rather than borrowing foreign technical state.
- If this reveals more shared Sine/Osc technical state than expected, stop and split ownership first instead of papering over it.

Definition of done:
- User can author and save up to `6` lines in both Sine and Oscilloscope.
- Runtime, restart, preset cycle, repair tool, and shipped regeneration all preserve those extra lines.
- No reintroduction of Sine/Osc shared-setting bleed.
- Docs and tests reflect `6` as the real supported authored ceiling.

### 6. Blob Organic Core/Deformation

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

### 7. Shaped Blob Reaction Variety

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

### 8. Preset Tooling Source-Tree Authority

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
