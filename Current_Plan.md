# Current Plan

Update this after every significant change.

## Guardrails (always active)

- Keep this aligned with [Index.md](Index.md), [Spec.md](Spec.md), [Docs/Defaults_Guide.md](Docs/Defaults_Guide.md), and [Docs/Visualizer_Debug.md](Docs/Visualizer_Debug.md).
- Do not mark runtime or visual-feel issues as fixed without user confirmation.
- Treat `presets/visualizer_modes` as the only authored visualizer preset source tree.
- Treat `release/main_mc.dist/presets/visualizer_modes*` as generated artifacts only.
- Do not introduce Curve again (for Spectrum).
- Do not change render methods or move Spectrum to a non-GL path.
- Do not treat passing tests as visual sign-off.
- Do not make global/shared math changes unless explicitly requested.
- Do not reduce FPS caps below current configured values.
- Whenever dead/dirty/messy/violating/architecturally poor code is discovered during unrelated work, note it here for later cleanup.
- Keep checkboxes honest:
  - `[x]` landed and validated
  - `[~]` partially proven / still needs runtime eyes
  - `[ ]` not done

---

## Snapshot

- **Date:** `2026-04-09`
- **Status:** Spectrum cleanup through 3.1 remains complete. Bubble now has the same shared bucketing treatment as Spectrum, Blob, Oscilloscope, and Sine Wave, and the bucket work has runtime user validation for logic, neatness, and persistence. Reddit Helper link handoff is now runtime-proven with a reusable scheduled-task authority, so authored planning focus is back on Spectrum cleanup plus preset-location/preset-repair follow-up.
- **Organs synthetic:** Green against current authored `Preset 1` (user-modified version).
- **Preset pipeline:** Source tree -> repair tool -> shipped regeneration -> all green.

---

## Completed Work (Historical Summaries)

### H1. Baseline Stabilization (§0)
Preset source tree recovered after revert damage. `core/settings/defaults.py` now returns a normalized visualizer section; `SettingsManager._ensure_widgets_defaults()` canonicalizes fresh insertion. Fresh startup is repair-free. `--fresh` switch clears logs before `setup_logging()`. Commits: baseline recovery + `--fresh` switch.

### H2. Preset / Schema Guardrails (§1)
Documented hard-won lessons: authored source tree vs generated artifacts, AppData drift, baseline commit checklist. `tools/visualizer_preset_repair.py` stays flexible. Curated preset names not hardcoded in tests. Runtime cache is generated state.

### H3. Spectrum Width Reclaim (§2.1)
Reclaimed wasted horizontal side space for BARS and SEGMENTS without overshooting into borders. Regression coverage in `tests/test_spectrum_shaping.py`.

### H4. Replace Single Piece Mode (§2.2)
Removed `Single Piece Mode`, replaced with explicit `SEGMENTS` / `BAR` toggle buttons. `spectrum_render_mode` is canonical key. Runtime bridge translates to older widget boolean. `spectrum_unique_colors` remains the canonical unique-colour key.

### H5. Spectrum Buckets (§2.3)
Replaced loose section headings with real collapsible buckets. Normal: `Appearance`, `Shape`. Advanced: `Render`, `Audio`, `Ghost`. Commit: `ad63b29`.

### H6. Border Colour Participation (§3.1)
Audited why borders were excluded from rainbow. Added `spectrum_rainbow_border` (bool, default `False`) with UI checkbox `Rainbow Borders` in Render bucket. Wired through all 8 layers + shader uniform `u_rainbow_border` in both SINGLE PIECE and SEGMENTED paths. Tests: 92 passed in plumbing suite.

### H7. Reddit Helper Scheduled-Task Authority
Reddit handoff is now working in real runtime through a durable interactive scheduled task plus session-lived helper model. Final shape: saver queues URL and exits normally; helper launch authority comes from a reusable Task Scheduler task; helper waits for shell readiness, opens the URL, and self-exits. The winning registration path uses native Task Scheduler COM XML with `InteractiveToken`, with the XML owning the principal and the COM registration call passing empty user/password variants. Repo harness coverage now exists for register/query/run/delete of that authority layer.

---

## Active Tasks

### 1. Spectrum Energy Arrows (was §3.2)

**Status:** `[ ]` Not started
**Priority:** Medium

Replace redundant Spectrum energy-strength sliders with vertical strength arrows above the energy lanes in the Spectrum Shaper.

- [ ] Write down the exact problem being solved: Spectrum currently splits one mental model across two surfaces
- [ ] Keep the node/notch editor as the owner of spatial placement and lane ownership
- [ ] Move only lane-contribution authoring into the editor; do not smuggle timing/smoothing controls into it
- [ ] Define the 0–100% lane-power contract so arrow travel maps directly to real lane contribution strength
- [ ] Decide whether arrow values are stored by lane label, by normalized lane center, or by layout-specific slot
- [ ] Make mirrored and non-mirrored arrow semantics equivalent even though the visible lane count differs
- [ ] Preserve Organs behavior by measuring against the synthetic fence before and after
- [ ] Record the interaction rationale and mental model in docs
- [ ] Review adjacent Spectrum controls at the same time and feed overlap/redundancy findings into Task 2

Current diagnosis:
- Spectrum shaping is still doing two different jobs in two different places:
  - the editor owns contour and lane boundaries
  - sliders own lane contribution / overall motion feel
- That split is why Spectrum feels partially spatial and partially abstract compared with Blob shaping
- The current runtime contract is not yet a true per-lane arrow contract; it still revolves around scalar fields such as `spectrum_bass_emphasis`, `spectrum_mid_suppression`, and `spectrum_wave_amplitude`
- There is also still a stale legacy seam in runtime apply code around `spectrum_vocal_position`, even though vocal ownership is supposed to come from notch layout now
- That means Energy Arrows is not just a widget swap; it needs a small but explicit authored/runtime contract cleanup

Recommended interaction model to prototype first:
- Put one vertical arrow above each active lane region, visually centered over the current lane span derived from the notch layout
- Arrows should move only on the Y axis
- Arrow travel should map directly to real lane power on a `0–100%` scale
- `0%` should mean the lane can collapse away if its source energy is absent
- `100%` should mean full lane power, not just a cosmetic editor hint
- Arrow length should represent contribution strength only; it must not silently absorb `drop_speed`, smoothing, or floor behavior
- Moving notch boundaries should move the arrow anchors with the lane, but the stored meaning should stay attached to the lane identity rather than the old pixel position

Explicit control-boundary decision:
- `drop_speed` stays outside the editor
- `profile_floor` stays outside the editor
- `Card Height`, glow, ghost, colour, and render-style controls stay outside the editor
- The editor should only own:
  - silhouette nodes
  - lane boundaries / notch splits
  - lane contribution arrows
- First implementation should treat `spectrum_wave_amplitude` carefully rather than assuming it belongs in the editor just because it affects feel

Current best-fit migration direction:
- Replace `spectrum_bass_emphasis` with a lane-native Bass arrow
- Replace `spectrum_mid_suppression` with lane-native mid/vocal attenuation authored directly where the user sees those regions
- Remove redundant lane-power sliders once true lane arrows are in place; do not leave the user with two authored surfaces for the same concept
- Keep only controls that still own a genuinely different concept after the arrow upgrade
- Treat `spectrum_wave_amplitude` as removable only if the arrow contract genuinely subsumes it; otherwise keep it explicitly as a separate global reactivity control

Implementation planning that should happen before code:
- [ ] Audit the current runtime math in `bar_computation.py` and identify exactly how bass, mids, vocal-center hinting, and global reactivity are mixed today
- [ ] Decide whether the new persisted contract should be mirrored/linear-specific or label-driven across both layouts
- [ ] Decide whether non-mirrored needs five arrows (`Bass`, `Low-Mid`, `Vocal`, `Hi-Mid`, `Treble`) while mirrored keeps four (`Mid`, `Vocal`, `Low-Mid`, `Bass`)
- [ ] Confirm how lane identity should survive notch dragging and label migration
- [ ] Specify how untouched legacy presets/settings are promoted into initial arrow values without flattening Organs
- [ ] Remove or formally retire the stale `spectrum_vocal_position` runtime seam during the same cleanup, not later
- [ ] Define whether arrows visually grow upward only or use a centered stem while still storing a strict `0–100%` value
- [ ] Decide whether arrows need text/value affordances or whether hover/selection feedback is enough

Testing / validation fence:
- [ ] Add structural tests for arrow persistence, mirrored/non-mirrored save/load, and notch-motion ownership
- [ ] Add runtime math tests proving lane arrows actually affect the intended lanes instead of acting like a renamed global slider
- [ ] Keep `Preset 1 (Organs)` synthetic baselines in the loop before and after migration
- [ ] Manually validate that a user can understand and edit the feature without needing the old scalar sliders beside it
- [ ] Treat passing tests as schema/math proof only, not interaction sign-off

Decision notes to preserve:
- This is not a Blob-shaper transplant
- The goal is a cleaner Spectrum mental model, not feature symmetry for its own sake
- Spatial ownership stays in the Spectrum editor
- Time-behavior controls still belong outside the editor
- If the first pass cannot clearly beat the existing scalar controls, stop and reassess instead of forcing arrows in because the idea sounds elegant

Design guardrails:
- This is not a Blob-shaper transplant
- Spatial ownership stays in the Spectrum editor
- Time-behavior controls still belong outside the editor

### 2. Spectrum Consolidation Pass (was §3.3)

**Status:** `[ ]` Not started
**Priority:** Medium

- [ ] Prepare an exact proposed list of Spectrum control merges, removals, and deprecations
- [ ] Confirm each merge/removal with the user before editing
- [ ] Preserve Organs behavior directly or through automatic remapping
- [ ] Keep shimmer-at-mid-height as a defined tuning target rather than a vibe-based cleanup
- [ ] Defer shimmer assessment/fix until the rest of this plan has landed cleanly, but do not defer ordinary consolidation work that can proceed safely now

Captured tuning notes:
- Mid-height shimmer is not the same problem as quiet-floor jitter
- The target is steadier mid-height motion at 60 fps without flattening large high/low movements
- Compare behavior on `<=60 Hz` displays versus `165 Hz` displays and decide whether the eventual fix should improve one, both, or both differently
- `drop_speed` alone is too blunt; Spectrum needs room for large rises and large falls

User guidance to preserve:
- Research whether optional interpolation, motion blur, or related display-side presentation techniques are standard for reducing shimmer on lower-refresh displays
- The problem is most noticeable on Spectrum because it is visually rigid, but some shimmer is still visible even at `165 Hz`
- A promising direction is per-lane hysteresis once a lane reaches a materially stable height, requiring more visual movement before it visibly shifts again
- Important guardrail: do not further smooth the underlying music/math signal; only improve the visual motion presented to the user
- Drops should be encouraged through a less flickery presentation method than simply increasing `drop_speed`
- Higher internal resolution appears to reduce shimmer but increases latency and does not eliminate the issue

### 3. Oscilloscope UI Bucket Cleanup

**Status:** `[x]` Landed and user-validated
**Priority:** Medium-High

The Oscilloscope builder (`ui/tabs/media/oscilloscope_builder.py`, 438 lines) uses a flat `_normal_layout` / `_adv_layout` split with no collapsible buckets. Controls are interleaved without clear grouping.

**Current flat layout:**
- Normal: Glow (toggle, intensity, reactivity, reactive), Ghost (toggle, intensity), Amplitude, Smoothing, Speed
- Advanced: Dim Lines, Line Offset Bias, Vertical Shift, Line/Glow Color, Multi-line (count, line 2/3 colors, ghost per-line), Card Height

**Proposed bucket structure:**

Normal surface:
- **Appearance** - Line Color, Glow Color, Glow toggle + intensity + reactivity + reactive checkbox
- **Behavior** - Amplitude, Smoothing, Speed, Ghost toggle + intensity

Advanced surface:
- **Multi-Line** - Multi-line toggle, Line Count, Line 2/3 colors + glow colors + ghost per-line, Dim Lines 2/3
- **Layout** - Line Offset Bias, Vertical Shift, Card Height

Landed:
- [x] Refactored `oscilloscope_builder.py` onto the shared collapsible-bucket helper path
- [x] Grouped controls into `Appearance`, `Behavior`, `Multi-Line`, and `Layout`
- [x] Kept control attribute names unchanged so existing bindings still work
- [x] Normal buckets default expanded; Advanced buckets default collapsed
- [x] Validated: `python -m pytest tests/test_widgets_tab.py tests/test_visualizer_settings_plumbing.py -k "osc" -q`

### 4. Sine Wave UI Bucket Cleanup

**Status:** `[x]` Landed and user-validated
**Priority:** Medium-High

The Sine Wave builder (`ui/tabs/media/sine_wave_builder.py`, 706 lines) uses a flat layout with many controls. It has the most controls of any waveform mode and benefits most from bucketing.

**Current flat layout:**
- Normal: Glow section (toggle, intensity, reactivity, color, reactive), Ghost section (toggle, opacity, decay), Line Color, Sensitivity, Speed, Travel, Wave Effect, Micro Wobble, Crawl, Width Reaction
- Advanced: Density, Heartbeat, Displacement, Vertical Shift, Line 1 Shift, Multi-line (count, line 2/3 colors + glow + travel + ghost + shift), Line Offset Bias, Card Adaptation, Card Height

**Proposed bucket structure:**

Normal surface:
- **Appearance** - Line Color, Glow (toggle + intensity + reactivity + color + reactive), Ghost (toggle + opacity + decay)
- **Motion** - Speed, Travel, Wave Effect, Crawl, Micro Wobble (legacy; review whether it should stay visible)
- **Response** - Sensitivity, Width Reaction, Heartbeat (candidate to promote from Advanced because it is a user-facing feel control)

Advanced surface:
- **Multi-Line** - Multi-line toggle, Line Count, Line 2/3 colors + glow colors + travel + ghost + horizontal shift, Displacement
- **Layout** - Density, Vertical Shift, Line 1 Shift, Line Offset Bias, Card Adaptation, Card Height

Landed:
- [x] Refactored `sine_wave_builder.py` onto the shared collapsible-bucket helper path
- [x] Grouped controls into `Appearance`, `Motion`, `Response`, `Multi-Line`, and `Layout`
- [x] Promoted `Heartbeat` from Advanced into the Normal `Response` bucket
- [x] Left `Micro Wobble` visible for now as a legacy control; do not treat that deprecation decision as settled
- [x] Kept control attribute names unchanged
- [x] Validated: `python -m pytest tests/test_widgets_tab.py tests/test_visualizer_settings_plumbing.py -k "sine" -q`

### 5. Bucket State Persistence (was IDEA BOX #1)

**Status:** `[x]` Landed and user-validated
**Priority:** Medium

Bucket collapsed/open state does not persist across settings dialog open/close.

Landed:
- [x] Replaced ad-hoc per-builder bucket wiring with a shared collapsible-bucket helper in `builder_scaffold.py`
- [x] Extended `WidgetsTab` with persisted per-mode bucket state storage in settings
- [x] Implemented save-on-collapse/expand and restore-on-build
- [x] Applied the shared solution to Spectrum, Blob, Oscilloscope, and Sine Wave
- [x] Preserved existing UX defaults where they were already established instead of forcing a surprise global-collapse reset
- [x] Validated via targeted widget/plumbing suites for `osc`, `sine`, `spectrum`, and `blob`

### 6. Non-Mirrored Spectrum Shaper Vocal Lane (was IDEA BOX #2)

**Status:** `[~]` Reworked after failure / awaiting visual validation
**Priority:** Low

Non-mirrored Spectrum Shaper currently lacks a vocal lane. In mirrored mode, the center region naturally maps to vocals and is fully adjustable. In linear mode, there is no equivalent.

Decision already captured:
- [x] Linear mode should auto-insert a vocal region rather than require manual placement

Remaining tasks:
- [x] Determine the default vocal position in linear mode (`0.46` normalized) so it sits in the editable mid/vocal band without hard-centering it
- [x] Keep the auto-inserted vocal region user-adjustable after insertion; that flexibility is the point of adding it automatically rather than hard-locking placement
- [x] Ensure the notch label system supports `Vocal`
- [x] Update the Spectrum Shaper editor and runtime contract accordingly
- [x] Promote untouched legacy linear defaults into the new vocal-lane layout without overriding user-customized notch layouts
- [x] Update docs / plan notes through the live plan
- [x] Validate: `python -m pytest tests/test_visualizer_settings_plumbing.py tests/test_spectrum_shaping.py tests/test_widgets_tab.py -k "spectrum" -q`

Runtime validation failure:
- [x] User confirmed the non-mirrored UI still does not show a visible vocal lane in practice
- [x] The currently shown notch set still reads like `Bass / Low / Mid / Hi-Mid / Treble`, with no visible `Vocal` lane
- [x] Re-check whether the editor/runtime is still rendering legacy linear notch labels/positions despite the migration logic
- [x] Found the likely leak: only the exact stock old linear notch list was being promoted, so drifted old `Bass / Low / Mid / Hi-Mid / Treble` layouts could survive forever; a stale runtime/widget default also still carried the old labels
- [x] Broadened the migration so old five-lane linear families without `Vocal` are promoted even when the user previously nudged the boundaries
- [x] Preserve user boundary positions during that promotion when the saved layout is legacy-shaped but no longer byte-for-byte equal to the old stock default
- [x] Updated stale widget/model defaults so fresh/runtime paths no longer reintroduce `Low` / `Mid`
- [x] Added focused regression coverage for both exact legacy defaults and drifted legacy linear labels
- [x] Latest available visualizer log review was inconclusive because the live vis logs did not emit notch labels/families directly
- [x] A later saved-settings spot-check was taken from the normal runtime/settings context, but the user's actual validation run was done from the MC build, so that evidence is not strong enough to close this task
- [x] Explicit rule: do not validate/remove this task until the emitted notch family is confirmed from the same build context the user actually tested
- [ ] Verify whether the lane is now visibly correct in the real editor UI and whether runtime behavior also follows the upgraded layout

### 7. Settings Shell Outer Border Radius

**Status:** `[ ]` Not started
**Priority:** Low

Explore a very light rounded outer edge for the settings shell without introducing corner bleed, masking regressions, or collateral QSS breakage.

- [ ] Fully understand the current custom styling stack before attempting changes, including QSS, SVG assets, frame layering, clipping, and any mask behavior
- [ ] Investigate whether a radius of `2` or `3` is safer/easier; prefer `3` only if it is genuinely equal-risk
- [ ] Prototype the outermost shell rounding only
- [ ] Validate specifically for corner bleed, border artifacts, and theme regressions
- [ ] Do not proceed to "done" until user validation confirms no bleed

Design guardrails:
- This is a polish task, not a styling-system rewrite
- Do not endanger any other custom styling behavior to gain rounded corners
- Analysis must be deep before implementation; this task is deliberately risk-averse

### 8. Settings Dialog Close / Teardown Polish

**Status:** `[ ]` Not started
**Priority:** Low

When closing the settings dialog, some elements visibly deconstruct before the shell is gone. The goal is for the close to feel atomic, or at least visually shell-first.

- [ ] Audit current shutdown ordering for the settings dialog shell and child elements
- [ ] Determine whether the visible deconstruction comes from fade timing, layout teardown, QWidget destruction order, or delayed shell close
- [ ] Prefer a solution where everything appears to vanish together; second-best is shell-first disappearance
- [ ] Confirm no cleanup, memory, or shutdown correctness regressions are introduced

### 9. Blob Energy Balance / Glow Drive Follow-up

**Status:** `[ ]` Not started
**Priority:** Low

Blob `Constant Energy` reportedly overpowers reactive/vocal energy in the non-shaped Blob path and likely needs retuning there only. There is also a product question around Glow Drive inputs.

- [ ] Audit the current non-shaped `Body Response` balance for constant, reactive, and vocal energy
- [ ] Confirm the shaped Blob path is unaffected before making any tuning changes
- [ ] Try a first tuning pass on the non-shaped path that halves constant energy and increases reactive/vocal energy by roughly `20%`
- [ ] Validate whether that ratio is directionally right rather than assuming the first guess is final
- [ ] Review the `Glow Drive` selection list for useful additions such as `Transient`
- [ ] Preserve Blob identity and do not accidentally make it behave like another mode
- [ ] Keep shaped and non-shaped behavior isolated so no cross-over tuning is introduced

### 10. Bubble UI Bucket Cleanup

**Status:** `[x]` Landed and user-validated
**Priority:** Low

The Bubble builder (`ui/tabs/media/bubble_builder.py`) previously had no collapsible buckets. Lower priority since Bubble is newer and less control-dense, but it still needed the same consistency treatment.

Landed:
- [x] Audited the Bubble builder layout and replaced raw text-section headings with shared collapsible buckets
- [x] Grouped Bubble into `Appearance`, `Motion`, `Reactivity`, `Population`, `Layout`, and `Ghost`
- [x] Implemented Bubble using the shared bucket helper/persistence path
- [x] Validated: `python -m pytest tests/test_widgets_tab.py tests/test_visualizer_settings_plumbing.py -k "bubble" -q`

### 11. Shared Preset Install / Save Location Across SCR and MC

**Status:** `[ ]` Not started
**Priority:** Medium

MC and SCR/NORMAL builds should use the same shipped/user preset location so dual-install users are not split across two preset worlds.

- [ ] Audit where SCR/NORMAL currently installs shipped presets and where MC currently installs shipped presets
- [ ] Move MC install placement onto the same durable preset location used by SCR/NORMAL
- [ ] Ensure MC custom preset saves also target that same shared location
- [ ] Confirm both builds can coexist without overwriting each other's runtime-only generated artefacts
- [ ] Validate install, upgrade, and save behavior with both builds present on one machine

Design guardrails:
- Use one reliable preset location for authored/shipped/user preset state where possible
- Do not break existing user custom presets during migration
- Keep authored source tree vs generated release artefacts clearly separated in repo semantics even if installed locations converge

### 12. Preset Repair Tool Follow-Up For Spectrum Vocal Lanes And Energy Arrows

**Status:** `[ ]` Not started
**Priority:** Medium

The preset repair tool is heavily relied on and must stay aligned with current authored/runtime contracts, especially after the non-mirrored vocal-lane work and the upcoming Energy Arrows refactor.

- [ ] Validate the repair tool against the landed non-mirrored vocal-lane migration rules
- [ ] Ensure repaired presets preserve legitimate user-authored boundary drift while still promoting stale legacy linear label families
- [ ] Add an explicit post-Energy-Arrows follow-up pass once the new lane-power contract lands
- [ ] Confirm the tool does not flatten Organs or other authored presets while healing schema drift
- [ ] Add/refresh focused tests so future Spectrum contract changes cannot silently break repair behavior

Design guardrails:
- The repair tool must remain permissive enough to preserve user-authored variation
- Do not hardcode brittle exact-shape assumptions that will break as Spectrum evolves
- Treat this tool as infrastructure, not cleanup glue; it needs the same care as runtime code

---

## Runtime / Log Watchlist

**Status:** `[~]` Ongoing

Keep watching for:
- [ ] Roaming AppData visualizer normalization repair line repeating indefinitely
- [ ] Creator bridge drift between canonical settings model and widget kwargs
- [ ] Source curated tree vs generated shipped tree drift
- [ ] Stale defaults snapshot drift
- [ ] UI preview/live-config helper paths throwing misleading exceptions
- [ ] Reddit Helper queue/heartbeat/state drift that could mask the actual link-handoff failure mode
- [ ] Settings dialog shutdown logs that indicate shell/child teardown ordering regressions

Known items:
- [~] `%APPDATA%/SRPSS/settings_v2.json` may contain older visualizer-era state that `SettingsManager` heals on load. Confirm whether a user-side save permanently clears the repair path.
- [~] Blob `Preset 1` synthetic drift is expected because the user personally modified Blob Preset 1. That baseline test should only run immediately before/after Blob work, not continuously.
- [ ] Spectrum runtime still carries a stale `spectrum_vocal_position` apply/config seam even though notch layout is supposed to own vocal placement now; resolve that as part of Energy Arrows / Spectrum consolidation rather than letting it drift longer

---

## Idea Box

> Raw ideas that have not yet been shaped into active tasks. Promote them once they have a concrete goal, scope, and guardrails.

- Empty for now. New raw ideas should be captured here before they become numbered tasks above.
