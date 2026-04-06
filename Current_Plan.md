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
- Whenever you come across dead/dirty/messy/violating/architecturally poor code while working on other things make a note of it in the current plan for later improvements. This is a general policy rule.
- Keep checkboxes honest:
  - `[x]` landed and validated
  - `[~]` partially proven / still needs runtime eyes
  - `[ ]` not done

---

## Snapshot

- **Date:** `2026-04-06`
- **Status:** Spectrum cleanup complete through 3.1. Oscilloscope and Sine Wave UI neatening is next priority alongside remaining Spectrum follow-on tasks.
- **Organs synthetic:** Green against current authored `Preset 1` (user-modified version).
- **Preset pipeline:** Source tree → repair tool → shipped regeneration → all green.

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
Audited why borders were excluded from rainbow. Added `spectrum_rainbow_border` (bool, default `False`) with UI checkbox "Rainbow Borders" in Render bucket. Wired through all 8 layers + shader uniform `u_rainbow_border` in both SINGLE PIECE and SEGMENTED paths. Tests: 92 passed in plumbing suite.

---

## Active Tasks

### 1. Spectrum Energy Arrows (was §3.2)

**Status:** `[ ]` Not started
**Priority:** Medium

Replace redundant Spectrum energy-strength sliders with vertical strength arrows above the energy lanes in the Spectrum Shaper.

- [ ] Design arrow interaction model (drag length = energy weight, visual direction = up/down)
- [ ] Identify exactly which sliders become redundant once arrows exist (Bass Influence, Mid Dampening, Reactivity are candidates)
- [ ] Arrow length controls energy contribution strength only
- [ ] This does **not** replace all Spectrum controls — time-behavior (Drop Speed, Profile Floor) stays outside the editor
- [ ] Preserve Organs behavior by measuring against the synthetic fence before/after
- [ ] Record planning/mental-model rationale in docs


Design guardrails:
- This is not a Blob transplant
- Spatial ownership stays in the Spectrum editor
- Time-behavior controls still belong outside the editor
- Make sure to check for other redundant/overlapping controls simultaneously and propose consolidation where helpful into 2.2

### 2. Spectrum Consolidation Pass (was §3.3)

**Status:** `[ ]` Not started
**Priority:** Medium

- [ ] Prepare an exact proposed list of Spectrum control merges/removals
- [ ] Confirm each merge/removal with the user before editing
- [ ] Preserve Organs behavior directly or through automatic remapping
- [ ] Focus on shimmer-at-mid-height as a future tuning target, not gut feel

Design notes:
- Mid-height shimmer ≠ quiet-floor jitter. Stabilise mid-height shimmer on 60fps without losing big high/low movements. (Consider why this is worse on 60hz displays than 165hz displays, if this change should be relevant only to one or if both would improve)
- `drop_speed` alone is too blunt — Spectrum wants big rises and big falls.
- Likely fix area: smarter gating/hysteresis once bars are materially elevated.

### 3. Oscilloscope UI Bucket Cleanup

**Status:** `[ ]` Not started
**Priority:** Medium-High

The Oscilloscope builder (`ui/tabs/media/oscilloscope_builder.py`, 438 lines) uses a flat `_normal_layout` / `_adv_layout` split with no collapsible buckets. Controls are interleaved without clear grouping.

**Current flat layout:**
- Normal: Glow (toggle, intensity, reactivity, reactive), Ghost (toggle, intensity), Amplitude, Smoothing, Speed
- Advanced: Dim Lines, Line Offset Bias, Vertical Shift, Line/Glow Color, Multi-line (count, line 2/3 colors, ghost per-line), Card Height

**Proposed bucket structure:**

Normal surface:
- **Appearance** — Line Color, Glow Color, Glow toggle + intensity + reactivity + reactive checkbox
- **Behavior** — Amplitude, Smoothing, Speed, Ghost toggle + intensity

Advanced surface:
- **Multi-Line** — Multi-line toggle, Line Count, Line 2/3 colors + glow colors + ghost per-line, Dim Lines 2/3
- **Layout** — Line Offset Bias, Vertical Shift, Card Height

Tasks:
- [ ] Refactor `oscilloscope_builder.py` to use `_make_bucket()` pattern (same as Spectrum/Blob)
- [ ] Group controls into proposed buckets above (refine if needed during implementation)
- [ ] Keep all control attribute names unchanged (UI binding tests must stay green)
- [ ] Keep default expanded state for Normal buckets, collapsed for Advanced
- [ ] Validate: `python -m pytest tests/test_widgets_tab.py tests/test_visualizer_settings_plumbing.py -k "osc" -q`

### 4. Sine Wave UI Bucket Cleanup

**Status:** `[ ]` Not started
**Priority:** Medium-High

The Sine Wave builder (`ui/tabs/media/sine_wave_builder.py`, 706 lines) uses a flat layout with many controls. It has the most controls of any waveform mode and benefits most from bucketing.

**Current flat layout:**
- Normal: Glow section (toggle, intensity, reactivity, color, reactive), Ghost section (toggle, opacity, decay), Line Color, Sensitivity, Speed, Travel, Wave Effect, Micro Wobble, Crawl, Width Reaction
- Advanced: Density, Heartbeat, Displacement, Vertical Shift, Line 1 Shift, Multi-line (count, line 2/3 colors + glow + travel + ghost + shift), Line Offset Bias, Card Adaptation, Card Height

**Proposed bucket structure:**

Normal surface:
- **Appearance** — Line Color, Glow (toggle + intensity + reactivity + color + reactive), Ghost (toggle + opacity + decay)
- **Motion** — Speed, Travel, Wave Effect, Crawl, Micro Wobble (legacy, consider hiding behind toggle or deprecating in §2)
- **Response** — Sensitivity, Width Reaction, Heartbeat (promote from Advanced — it's a user-facing feel control)

Advanced surface:
- **Multi-Line** — Multi-line toggle, Line Count, Line 2/3 (colors, glow colors, travel, ghost, horizontal shift), Displacement
- **Layout** — Density, Vertical Shift, Line 1 Shift, Line Offset Bias, Card Adaptation, Card Height

Tasks:
- [ ] Refactor `sine_wave_builder.py` to use `_make_bucket()` pattern
- [ ] Group controls into proposed buckets (refine during implementation)
- [ ] Consider promoting Heartbeat from Advanced → Normal (it's a feel control users want easy access to)
- [ ] Consider whether Micro Wobble should be hidden/deprecated (legacy, superseded by Crawl)
- [ ] Keep all control attribute names unchanged
- [ ] Validate: `python -m pytest tests/test_widgets_tab.py tests/test_visualizer_settings_plumbing.py -k "sine" -q`

### 5. Bucket State Persistence (was IDEA BOX #1)

**Status:** `[ ]` Not started
**Priority:** Medium

Bucket collapsed/open state does not persist across settings dialog open/close. Default should be all buckets collapsed.

- [ ] Audit how buckets are created (`_make_bucket()` in each builder) and whether they use a shared widget class or are ad-hoc
- [ ] Design persistence approach:
  - Option A: Store bucket states in `SettingsManager` under `ui.bucket_states` dict (keyed by objectName)
  - Option B: Store in a lightweight UI-only cache file (avoids polluting settings)
- [ ] Implement save-on-collapse/expand signal
- [ ] Implement restore-on-build
- [ ] Default: all buckets collapsed on first encounter
- [ ] Applies to all modes with buckets: Spectrum, Blob, and (after §3/§4) Oscilloscope, Sine Wave

### 6. Non-Mirrored Spectrum Shaper Vocal Lane (was IDEA BOX #2)

**Status:** `[ ]` Not started
**Priority:** Low

Non-mirrored Spectrum Shaper currently lacks a vocal lane. In mirrored mode, the center region naturally maps to vocals. In linear mode, there is no equivalent.

- [x] Decide if linear mode should auto-insert a vocal notch or if the user should place it manually (User: AUTO - Vocal is critical to music.)
- [ ] If auto-insert: determine default vocal position in linear mode (likely ~0.4–0.5 normalized)
- [ ] If manual: ensure the notch label system supports "Vocal" as a user-placeable label
- [ ] Update Spectrum Shaper editor to handle this
- [ ] Update docs

### 7. Bubble UI Bucket Cleanup

**Status:** `[ ]` Not started
**Priority:** Low

The Bubble builder (`ui/tabs/media/bubble_builder.py`) currently has no collapsible buckets. Lower priority since Bubble is the newest mode and less control-dense, but should be bucketed for consistency.

- [ ] Audit current Bubble builder layout
- [ ] Propose bucket groupings (likely: Appearance, Behavior, Layout)
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

Known items:
- [~] `%APPDATA%/SRPSS/settings_v2.json` may contain older visualizer-era state that SettingsManager heals on load. Confirm whether a user-side save permanently clears the repair path.
- [~] Blob `Preset 1` synthetic drift is expected — user personally modified Blob Preset 1. That baseline test should only run just before/after Blob work, not continuously.

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

## IDEA / PROBLEM BOX

> Promoted items move into numbered Active Tasks above. Keep this box for raw ideas that haven't been shaped yet.

_(empty — all items promoted)_
