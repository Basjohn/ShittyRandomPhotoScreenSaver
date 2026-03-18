# Parity Plan Document

## Objective
Rollback to the last stable commit baseline and rebuild only the high-value visualizer settings/features in a controlled sequence that protects mode parity and prevents uniform/kwargs regressions.

## Tracking Rule

- `Current_Plan.md` is the **single exhaustive checklist** for all active tasks.
- This document is parity-oriented scope only (sequence, guardrails, parity-specific slices).

## Snapshot: What Was Added in the Regressed Working Tree (Before Rollback)

### 1) Additional Settings and Their Goal

#### Spectrum mode
- `spectrum_ghosting_enabled`
- `spectrum_ghost_alpha`
- `spectrum_ghost_decay`
- **Goal:** isolate spectrum ghost behavior so it no longer depends on global ghost defaults and cannot be overwritten by cross-mode state.

#### Sine wave mode
- `sine_ghosting_enabled`
- `sine_ghost_alpha`
- `sine_ghost_decay`
- **Goal:** provide independent sine-wave trail behavior and ensure ghost parameters route through sine mode specifically.

#### Bubble mode sizing
- `bubble_big_contraction_bias`
- `bubble_big_size_clamp`
- `bubble_big_specular_max_size` (planned parity addition)
- **Goal:** control large-bubble expansion/contraction envelope, cap radius growth, and prevent unstable tiny/oversized bubble rendering.

#### Bubble mode ghosting
- `bubble_ghosting_enabled`
- `bubble_ghost_alpha`
- `bubble_ghost_decay`
- **Goal:** add explicit bubble ghost trail controls instead of inheriting generic ghost behavior.

### 2) Other Positive Improvements Seen in the Diff (Goal Only)
1. **Per-mode GPU kwargs expansion in applier pipeline**  
   Goal: improve end-to-end mapping fidelity between UI/config and shader-facing overlay state.

2. **Mode-specific ghost override selection in tick pipeline**  
   Goal: enforce correct ghost source per visualization mode and eliminate global override leakage.

3. **Bubble simulation payload alignment with size controls**  
   Goal: keep simulation constraints in sync with user-configured bubble clamp/contraction values.

4. **Renderer/shader updates in bubble and sine paths**  
   Goal: reduce mismatches between CPU-side config and GPU-side uniforms.

5. **Broader visualizer regression tests (plumbing/overlay/preset pathways/full UI->kwarg/uniform wiring/plumbing tests for the entire visualizer mode system)**  
   Goal: catch key drop/miswire regressions earlier.

6. **Audit tooling/docs updates for visualizer setting routing**  
   Goal: improve traceability of UI -> config -> widget -> overlay -> shader path.

---

## Ordered Plan of Operation (Live)

### Phase 0 - Baseline Recovery (Complete)
- [x] Reset tracked files to last commit (`git reset --hard HEAD`).
- [x] Remove untracked excess files (`git clean -fd`).
- [x] Confirm clean git state.

### Phase 1 - Baseline Sanity Validation (Complete)
- [x] Validate blob mode baseline render path (mode switch + ghost default behavior).
- [x] Validate sine mode baseline render path (confirm no spectrum fallback).
- [x] Validate bubble baseline size behavior (observe large-bubble envelope at defaults).
- [x] Log baseline pass/fail notes in `Current_Plan.md`.

### Phase 2 - Reintroduce Settings in Safe Slices (Complete)
- [x] Slice A: Reintroduce spectrum ghost setting trio end-to-end.
- [x] Slice B: Reintroduce sine ghost setting trio end-to-end.
- [x] Slice C: Reintroduce bubble size controls (`bubble_big_contraction_bias`, `bubble_big_size_clamp`) end-to-end.
- [x] Slice D: Reintroduce bubble ghost setting trio end-to-end.
- [x] Slice E: Add `bubble_big_specular_max_size` end-to-end and cap pulse-driven specular growth in bubble rendering.
- [x] Slice F: Strip deprecated Helix & Starfield modes completely (see Phase 2F below).

### Phase 2F - Strip Helix & Starfield (Complete)
Removed all traces of deprecated Helix and Starfield visualizer modes:
- Removed `HELIX`/`STARFIELD` from `VisualizerMode` enum (5 modes remain: Spectrum, Oscilloscope, Blob, Sine Wave, Bubble).
- Deleted renderer modules (`renderers/helix.py`, `renderers/starfield.py`).
- Deleted shader files (`shaders/helix.frag`, `shaders/starfield.frag`).
- Deleted UI builder modules (`ui/tabs/media/helix_builder.py`, `ui/tabs/media/starfield_builder.py`).
- Removed from: `card_height.py`, `models.py` (dataclass + from_settings + from_mapping + to_dict), `default_settings.py`, `defaults_generated.py`, `defaults_snapshot.py`, `presets.py`, `visualizer_presets.py`, `spotify_widget_creators.py`, `config_applier.py`, `spotify_visualizer_widget.py`, `spotify_bars_gl_overlay.py` (init + set_state params + body + uniform names + travel integration + valid_modes), `widgets_tab_media.py` (build + load + save + preset map + rainbow modes), `widgets_tab.py` (color picker + maps + containers + save config), `beat_engine.py`, `energy_bands.py`, `gl_helpers.py`.
- Updated 7 test files to remove helix/starfield expectations.
- Old user settings JSON files may still contain helix/starfield keys — harmless, ignored at load time.

### Phase 3 - Regression Armor for Each Slice (Complete)
- [x] Add/update tests before advancing to next slice.
- [x] Assert mapping continuity across: UI load/save -> `apply_vis_mode_kwargs` -> widget attrs -> `build_gpu_push_extra_kwargs` -> overlay -> renderer/shader uniforms.
- [x] Fail slice if any fallback path is triggered unexpectedly.
- [x] Mode isolation audit completed — see `Audits/phase3_mode_isolation_audit.md`.

### Phase 4 - Finalization (In Progress)
- [ ] Re-run targeted visual checks for blob/sine/bubble after all slices.
- [ ] Verify no fallback mode activation in normal operation.
- [x] Update `Current_Plan.md` with completion state.
- [ ] Update `Index.md` with final routing ownership locations.
- [ ] Update `Spec.md` with accepted setting contracts/defaults.

---

## Execution Rules for This Recovery
- Treat any fallback activation as a defect.
- No instrumentation expansion unless needed to unblock a failing parity gate.
- No bundling multiple parity slices in a single unverified change.
- No new setting ships without matching route verification and tests.
