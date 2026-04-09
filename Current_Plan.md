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
- **Status:** Spectrum cleanup through 3.1 remains complete. Bubble now has the same shared bucketing treatment as Spectrum, Blob, Oscilloscope, and Sine Wave, and the bucket work has runtime user validation for logic, neatness, and persistence. Reddit Helper link handoff is now runtime-proven with a reusable scheduled-task authority and harness coverage. The non-mirrored Spectrum vocal lane is now user-validated and closed. The first Spectrum Energy Arrows pass is landed in code, with the old lane-power sliders removed in favor of lane-native arrows, and now awaits real runtime/feel validation before consolidation decisions are finalized. Preset follow-up also moved forward: frozen SCR and MC now target one shared ProgramData curated preset tree, and the repair/audit flow now explicitly catches and repairs stale non-mirrored Spectrum linear lane families.
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

**Status:** `[~]` First pass landed in code; runtime/user validation still needed
**Priority:** Medium

Replace redundant Spectrum energy-strength sliders with vertical strength arrows above the energy lanes in the Spectrum Shaper.

- [x] Kept the node/notch editor as the owner of spatial placement and lane ownership
- [x] Moved lane-contribution authoring into the editor without smuggling timing/smoothing controls into it
- [x] Defined the persisted lane-power contract as label-driven mirrored/non-mirrored maps stored on a real `0.0-1.0` scale
- [x] Made mirrored and non-mirrored semantics equivalent while still letting mirrored use four arrows and linear use five
- [x] Removed the redundant authored lane-power sliders from the Spectrum Audio bucket
- [x] Retired the stale authored/runtime `spectrum_vocal_position` seam from the live contract during the same cleanup
- [x] Recorded the interaction/runtime contract in code, tests, and repo docs
- [~] Preserve Organs behavior and current authored feel through synthetic/runtime validation, not assumption
- [~] Decide whether the current editor height increase is enough or whether the shaper still feels cramped in real use
- [~] Feed any remaining overlap/redundancy findings into Task 2 after real usage

Landed in code:
- The Spectrum editor now draws one vertical energy arrow above each active lane, centered over the current lane span derived from the notch layout
- Arrow travel maps directly to real lane power on a `0-100%` mental model, with stored values persisted as normalized strengths
- Moving notch boundaries reanchors the arrows with the lane while keeping stored meaning attached to lane identity rather than stale pixel position
- Mirrored layouts now persist `Mid / Vocal / Low-Mid / Bass` strengths separately from linear `Bass / Low-Mid / Vocal / Hi-Mid / Treble`
- Spectrum runtime now consumes those lane-strength maps directly in `bar_computation.py` instead of relying on authored scalar fields such as `spectrum_bass_emphasis` or `spectrum_mid_suppression`
- `spectrum_wave_amplitude` and `profile_floor` remain explicit global controls outside the editor
- Spectrum builder cleanup removed redundant lane sliders and updated the bucket helper copy so the shaper is the obvious lane-power surface
- The editor height/padding was increased to make room for arrows without collapsing the authored silhouette area

Testing / validation fence:
- [x] Added structural tests for arrow persistence, mirrored/non-mirrored save/load, and notch-motion ownership
- [x] Added runtime math tests proving lane strengths affect the intended lanes instead of acting like renamed global sliders
- [x] Kept `Preset 1 (Organs)` synthetic baselines in the loop during the contract migration work
- [ ] Manually validate that the arrows are readable, not cramped, and clearly better than the old scalar sliders in real UI use
- [ ] Validate that current authored presets, especially Organs-like Spectrum motion, still feel right under the new lane-power contract
- [ ] Decide whether hover-only percentage feedback is enough or whether persistent text/value affordances are still needed
- [ ] Treat passing tests as schema/math proof only, not interaction sign-off

Design guardrails:
- This is not a Blob-shaper transplant
- Spatial ownership stays in the Spectrum editor
- Time-behavior controls still belong outside the editor
- If the first pass does not clearly beat the old scalar controls in real use, stop and reassess instead of forcing arrows forward for elegance alone

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

### 6. Settings Shell Outer Border Radius

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

### 7. Settings Dialog Close / Teardown Polish

**Status:** `[ ]` Not started
**Priority:** Low

When closing the settings dialog, some elements visibly deconstruct before the shell is gone. The goal is for the close to feel atomic, or at least visually shell-first.

- [ ] Audit current shutdown ordering for the settings dialog shell and child elements
- [ ] Determine whether the visible deconstruction comes from fade timing, layout teardown, QWidget destruction order, or delayed shell close
- [ ] Prefer a solution where everything appears to vanish together; second-best is shell-first disappearance
- [ ] Confirm no cleanup, memory, or shutdown correctness regressions are introduced

### 8. Blob Energy Balance / Glow Drive Follow-up

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

### 9. Bubble UI Bucket Cleanup

**Status:** `[x]` Landed and user-validated
**Priority:** Low

The Bubble builder (`ui/tabs/media/bubble_builder.py`) previously had no collapsible buckets. Lower priority since Bubble is newer and less control-dense, but it still needed the same consistency treatment.

Landed:
- [x] Audited the Bubble builder layout and replaced raw text-section headings with shared collapsible buckets
- [x] Grouped Bubble into `Appearance`, `Motion`, `Reactivity`, `Population`, `Layout`, and `Ghost`
- [x] Implemented Bubble using the shared bucket helper/persistence path
- [x] Validated: `python -m pytest tests/test_widgets_tab.py tests/test_visualizer_settings_plumbing.py -k "bubble" -q`

### 10. Shared Preset Install / Save Location Across SCR and MC

**Status:** `[~]` Landed in code / awaiting dual-install runtime validation
**Priority:** Medium

MC and SCR/NORMAL builds should use the same shipped/user preset location so dual-install users are not split across two preset worlds.

- [x] Audited where SCR/NORMAL currently installs shipped presets and where MC currently installs shipped presets
- [x] Moved frozen runtime loading onto the shared ProgramData curated tree instead of build-local frozen roots
- [x] Added one-time frozen bootstrap so a missing shared ProgramData tree is repopulated from bundled assets instead of silently falling back forever
- [x] Updated MC install flow to refresh the same ProgramData curated tree used by SCR/NORMAL while still keeping a packaged backup copy for `Replace Visualizers`
- [x] Updated `Replace Visualizers` source resolution to prefer packaged/bundled assets and keep the shared ProgramData tree as the active target
- [x] Removed the normal SCR uninstall cleanup that would have deleted the shared preset tree out from under a co-installed MC build
- [x] Added focused tests for frozen shared-root resolution and packaged-source replacement routing
- [ ] Validate install, upgrade, and coexistence behavior with both builds present on one machine

Design guardrails:
- Use one reliable preset location for authored/shipped/user preset state where possible
- Do not break existing user custom presets during migration
- Keep authored source tree vs generated release artefacts clearly separated in repo semantics even if installed locations converge

Implementation notes to preserve:
- Shared active curated root is now `ProgramData\SRPSS\presets\visualizer_modes` for frozen SCR and MC
- Script mode still uses the repo source tree directly
- Packaged/bundled preset trees are now replacement/bootstrap sources, not the active frozen runtime root
- `Replace Visualizers` must keep restoring from packaged assets, not from the already-active shared target
- We still do not have a separate on-disk custom visualizer preset library; the trailing `Custom` slot remains settings-backed rather than file-backed

### 11. Preset Repair Tool Follow-Up For Spectrum Vocal Lanes And Energy Arrows

**Status:** `[~]` Vocal-lane follow-up landed / post-arrow repair pass still pending
**Priority:** Medium

The preset repair tool is heavily relied on and must stay aligned with current authored/runtime contracts, especially after the now-landed non-mirrored vocal-lane work and the new Energy Arrows lane-strength contract.

- [x] Validated the repair tool against the landed non-mirrored vocal-lane migration rules
- [x] Ensured repaired presets preserve legitimate user-authored boundary drift while still promoting stale legacy linear label families
- [x] Added explicit audit reporting for stale Spectrum linear label families so they fail loudly instead of drifting silently
- [x] Repaired the current curated Spectrum preset pack so shipped presets no longer keep the old non-mirrored `Low / Mid` family alive
- [x] Confirmed the tool does not flatten Organs or other authored presets while healing schema drift, at least at the current structural/schema fence level
- [x] Added/refreshed focused tests so future Spectrum contract changes cannot silently break repair behavior
- [ ] Add an explicit post-Energy-Arrows follow-up pass now that the new lane-power contract has landed, so stale scalar-lane keys and repaired preset naming/migration edge cases are re-audited together

Design guardrails:
- The repair tool must remain permissive enough to preserve user-authored variation
- Do not hardcode brittle exact-shape assumptions that will break as Spectrum evolves
- Treat this tool as infrastructure, not cleanup glue; it needs the same care as runtime code

Implementation notes to preserve:
- The repair tool now uses the same linear-notch promotion logic as runtime/model loading for stale non-mirrored Spectrum families
- The new audit seam should remain structural: it is meant to catch legacy lane-family drift, not to freeze authored Spectrum shapes
- The explicit post-Energy-Arrows follow-up still belongs here now that lane-power arrows replaced the old scalar lane controls, because repair/remap edge cases are easiest to miss after the runtime migration is already green

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
- [~] Spectrum lane-strength arrows are now the live contract; keep watching for any remaining legacy scalar-lane drift or preset remap edge cases that would make runtime behavior disagree with the editor

---

## Idea Box

> Raw ideas that have not yet been shaped into active tasks. Promote them once they have a concrete goal, scope, and guardrails.

- Empty for now. New raw ideas should be captured here before they become numbered tasks above.
