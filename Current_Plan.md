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

---

## Runtime Watchlist

- [ ] `%APPDATA%/SRPSS/settings_v2.json` repair line repeating indefinitely
- [ ] Source curated tree vs generated shipped tree drift
- [ ] Misleading helper/UI preview exceptions
- [ ] Bubble/Blob slipping back into the signal-contract trap documented in [Docs/Historical_Bugs.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Historical_Bugs.md)

---

## Idea Box

1. Add a shimmer/flicker regression test for Spectrum once the actual shimmer task is active.
