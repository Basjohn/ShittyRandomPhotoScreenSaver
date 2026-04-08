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

- **Date:** `2026-04-08`
- **Status:** Spectrum cleanup through 3.1 remains complete. Immediate next work is still UI cleanup/consolidation around Oscilloscope and Sine Wave, with planning now expanded to include helper reliability, settings-shell polish, and remaining visualizer follow-on items.
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

---

## Active Tasks

### 1. Spectrum Energy Arrows (was §3.2)

**Status:** `[ ]` Not started
**Priority:** Medium

Replace redundant Spectrum energy-strength sliders with vertical strength arrows above the energy lanes in the Spectrum Shaper.

- [ ] Design arrow interaction model so drag length controls energy weight and the visual direction communicates up/down influence
- [ ] Identify exactly which existing sliders become redundant once arrows exist
- [ ] Keep arrow length scoped to contribution strength only
- [ ] Keep time-behavior controls such as `drop_speed` and `profile_floor` outside the editor
- [ ] Preserve Organs behavior by measuring against the synthetic fence before and after
- [ ] Record the interaction rationale and mental model in docs
- [ ] Review adjacent Spectrum controls at the same time and feed overlap/redundancy findings into Task 2

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

### 3. Reddit Helper Reliability / Link Handoff

**Status:** `[ ]` Not started
**Priority:** Medium-High

Reddit Helper link opening is still unreliable and has reportedly been "fixed" multiple times without holding. Treat this as a real reliability task, not a cosmetic cleanup.

- [ ] Audit the current secure-desktop -> helper -> browser handoff flow end to end
- [ ] Review `C:\\ProgramData\\SRPSS\\` state, queues, and related runtime clues before changing behavior
- [ ] Re-read the Winlogon / session-handoff assumptions that justified the current design
- [ ] Evaluate whether the helper can safely wait/poll for confirmed screensaver shutdown before launching URLs
- [ ] Compare the current helper path against the simpler MC-build approach using `QDesktopServices` and browser-foreground handoff
- [ ] Reduce needless complexity only if it does not weaken cleanup, security posture, or AV trust
- [ ] Investigate whether screensaver closure itself can be made faster without risking threads, memory cleanup, or shutdown ordering
- [ ] Validate with repeated real-world link launches, not a single happy-path test

Design guardrails:
- Avoid solutions likely to look suspicious to antivirus or OS trust systems
- Do not replace robust shutdown guarantees with a race-prone "seems fast enough" handoff
- Prefer the simplest proven launch path once session ownership and shutdown timing are genuinely understood

### 4. Oscilloscope UI Bucket Cleanup

**Status:** `[ ]` Not started
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

Tasks:
- [ ] Refactor `oscilloscope_builder.py` to use `_make_bucket()` pattern (same as Spectrum/Blob)
- [ ] Group controls into the proposed buckets above, refining only if implementation reveals a better fit
- [ ] Keep all control attribute names unchanged so binding tests remain valid
- [ ] Keep default expanded state for Normal buckets and collapsed state for Advanced buckets
- [ ] Validate: `python -m pytest tests/test_widgets_tab.py tests/test_visualizer_settings_plumbing.py -k "osc" -q`

### 5. Sine Wave UI Bucket Cleanup

**Status:** `[ ]` Not started
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

Tasks:
- [ ] Refactor `sine_wave_builder.py` to use `_make_bucket()` pattern
- [ ] Group controls into the proposed buckets, refining during implementation if needed
- [ ] Evaluate promoting Heartbeat from Advanced -> Normal
- [ ] Evaluate whether Micro Wobble should be hidden, deprecated, or left alone as a legacy control
- [ ] Keep all control attribute names unchanged
- [ ] Validate: `python -m pytest tests/test_widgets_tab.py tests/test_visualizer_settings_plumbing.py -k "sine" -q`

### 6. Bucket State Persistence (was IDEA BOX #1)

**Status:** `[ ]` Not started
**Priority:** Medium

Bucket collapsed/open state does not persist across settings dialog open/close.

- [ ] Audit how buckets are created via `_make_bucket()` and whether they already share enough structure for centralized persistence
- [ ] Choose a persistence approach:
  - Option A: store bucket states in `SettingsManager` under `ui.bucket_states` keyed by `objectName`
  - Option B: store states in a lightweight UI-only cache file to avoid polluting primary settings
- [ ] Implement save-on-collapse/expand signal handling
- [ ] Implement restore-on-build
- [ ] Default first-encounter behavior to all buckets collapsed unless a mode-specific UX reason justifies otherwise
- [ ] Apply the solution to all bucketed modes: Spectrum, Blob, and after Tasks 4 and 5, Oscilloscope and Sine Wave

### 7. Non-Mirrored Spectrum Shaper Vocal Lane (was IDEA BOX #2)

**Status:** `[ ]` Not started
**Priority:** Low

Non-mirrored Spectrum Shaper currently lacks a vocal lane. In mirrored mode, the center region naturally maps to vocals. In linear mode, there is no equivalent.

Decision already captured:
- [x] Linear mode should auto-insert a vocal region rather than require manual placement

Remaining tasks:
- [ ] Determine the default vocal position in linear mode (likely around `0.4-0.5` normalized, but verify)
- [ ] Define whether the auto-inserted vocal region should remain user-adjustable after insertion
- [ ] If manual placement is still supported in any form, ensure the notch label system supports `Vocal`
- [ ] Update the Spectrum Shaper editor and runtime contract accordingly
- [ ] Update docs

### 8. Settings Shell Outer Border Radius

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

### 9. Settings Dialog Close / Teardown Polish

**Status:** `[ ]` Not started
**Priority:** Low

When closing the settings dialog, some elements visibly deconstruct before the shell is gone. The goal is for the close to feel atomic, or at least visually shell-first.

- [ ] Audit current shutdown ordering for the settings dialog shell and child elements
- [ ] Determine whether the visible deconstruction comes from fade timing, layout teardown, QWidget destruction order, or delayed shell close
- [ ] Prefer a solution where everything appears to vanish together; second-best is shell-first disappearance
- [ ] Confirm no cleanup, memory, or shutdown correctness regressions are introduced

### 10. Blob Energy Balance / Glow Drive Follow-up

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

### 11. Bubble UI Bucket Cleanup

**Status:** `[ ]` Not started
**Priority:** Low

The Bubble builder (`ui/tabs/media/bubble_builder.py`) currently has no collapsible buckets. Lower priority since Bubble is newer and less control-dense, but it should still be bucketed for consistency.

- [ ] Audit the current Bubble builder layout
- [ ] Propose bucket groupings, likely around Appearance, Behavior, and Layout
- [ ] Implement using `_make_bucket()` pattern
- [ ] Validate tests

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

---

## Baseline Commit Prep

**Status:** `[~]` In progress

- [x] Preset audit green
- [x] Shipped-tree regeneration green
- [x] Organs synthetic green
- [x] Runtime creator bridge fixed
- [x] Settings-tab live-config guard fixed
- [x] `cache/reddit/*.json` removed from tracked content
- [ ] Rewrite/align living docs with recovery lessons
- [ ] Stage only repo-relevant files
- [ ] Create commit: `Baseline Pre-Consolidation Clean`

---

## Idea Box

> Raw ideas that have not yet been shaped into active tasks. Promote them once they have a concrete goal, scope, and guardrails.

- Empty for now. New raw ideas should be captured here before they become numbered tasks above.
