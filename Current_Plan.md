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
- **Status:** Reddit Helper scheduled-task authority remains runtime-proven, Spectrum vocal-lane and Energy Arrow work are user-validated, the shared preset/repair flow is now on the modern lane-map contract, and the settings shell now uses an accepted forged-corner outer-border compromise that is visually almost bleed-free without disturbing acrylic or the custom title bar. Spectrum consolidation remains partially open for deeper control-pruning decisions.
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

### H8. Spectrum Energy Arrows / Lane Contract Cleanup
Spectrum now uses lane-native vertical energy arrows in the shaper as the real authored lane-power surface. The old scalar lane controls are retired from live settings/presets/runtime, the shaper persists label-driven mirrored/non-mirrored lane-strength maps, curated Spectrum presets were rewritten onto that contract, and the repair tool now does one-time scalar-to-lane promotion only when cleaning genuinely old authored payloads. User runtime validation confirmed the arrows are working better than expected.

---

## Active Tasks

### 1. Spectrum Consolidation Pass (was §3.3)

**Status:** `[~]` Partially landed / deeper cleanup still open
**Priority:** Medium

- [x] Clarify the highest-confusion Spectrum overlaps without changing the runtime math contract
- [x] Separate authored `Reactivity` / `Shape Floor` copy from Technical sensitivity/noise-floor copy
- [x] Replace misleading `Adaptive Sensitivity` wording with an explicit recommended fixed-sensitivity path
- [x] Add mode-aware audio block size guidance with lower/higher tradeoffs and a Spectrum recommendation
- [ ] Decide whether `Output Lift`, `AGC Strength`, and `Input Gain` can be reduced further without removing genuinely useful expert tuning
- [ ] Decide whether Spectrum should keep the recommended/manual sensitivity toggle at all or collapse fully to a single manual slider path
- [ ] Keep shimmer-at-mid-height as a defined tuning target rather than a vibe-based cleanup
- [ ] Defer shimmer assessment/fix until the rest of this plan has landed cleanly, but do not defer ordinary consolidation work that can proceed safely now

What landed in this pass:
- Spectrum authored Audio copy now explicitly separates creative motion controls from Technical signal tuning
- `Profile Floor` is now presented as `Shape Floor` so it stops reading like the same thing as Technical noise floor
- Shared Technical UI now calls the checkbox `Use Recommended Sensitivity` because the underlying worker path is a fixed tuned multiplier, not live adaptive analysis
- Shared Technical audio-block tooltip now explains lower-vs-higher tradeoffs and shows a per-mode recommendation (`128` for Spectrum/Oscilloscope/Sine Wave, `256` for Blob/Bubble)

Why the task stays open:
- Spectrum still has a real expert-layer overlap question around `Output Lift`, `AGC Strength`, and `Input Gain`
- The shimmer work is still intentionally deferred and should not get bundled into these copy/ownership cleanups by accident

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

### 2. Oscilloscope UI Bucket Cleanup

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

### 3. Sine Wave UI Bucket Cleanup

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

### 4. Bucket State Persistence (was IDEA BOX #1)

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

### 5. Settings Dialog Close / Teardown Polish

**Status:** `[ ]` Not started
**Priority:** Low

When closing the settings dialog, some elements visibly deconstruct before the shell is gone. The goal is for the close to feel atomic, or at least visually shell-first.

- [ ] Audit current shutdown ordering for the settings dialog shell and child elements
- [ ] Determine whether the visible deconstruction comes from fade timing, layout teardown, QWidget destruction order, or delayed shell close
- [ ] Prefer a solution where everything appears to vanish together; second-best is shell-first disappearance
- [ ] Confirm no cleanup, memory, or shutdown correctness regressions are introduced

### 6. Blob Energy Balance / Glow Drive Follow-up

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

### 7. Bubble UI Bucket Cleanup

**Status:** `[x]` Landed and user-validated
**Priority:** Low

The Bubble builder (`ui/tabs/media/bubble_builder.py`) previously had no collapsible buckets. Lower priority since Bubble is newer and less control-dense, but it still needed the same consistency treatment.

Landed:
- [x] Audited the Bubble builder layout and replaced raw text-section headings with shared collapsible buckets
- [x] Grouped Bubble into `Appearance`, `Motion`, `Reactivity`, `Population`, `Layout`, and `Ghost`
- [x] Implemented Bubble using the shared bucket helper/persistence path
- [x] Validated: `python -m pytest tests/test_widgets_tab.py tests/test_visualizer_settings_plumbing.py -k "bubble" -q`

### 9. Shared Preset Install / Save Location Across SCR and MC

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
- [~] Spectrum lane-strength arrows are now the live contract; keep watching for any remaining legacy scalar-lane drift or preset remap edge cases that would make runtime behavior disagree with the editor

---

## Idea Box

> Raw ideas that have not yet been shaped into active tasks. Promote them once they have a concrete goal, scope, and guardrails.

- Empty for now. New raw ideas should be captured here before they become numbered tasks above.
