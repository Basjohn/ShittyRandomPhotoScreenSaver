# Parity Plan Document

## Objective
Rollback to the last stable commit baseline and rebuild only the high-value visualizer settings/features in a controlled sequence that protects mode parity and prevents uniform/kwargs regressions.

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

### Phase 1 - Baseline Sanity Validation
- [ ] Validate blob mode baseline render path (mode switch + ghost default behavior).
- [ ] Validate sine mode baseline render path (confirm no spectrum fallback).
- [ ] Validate bubble baseline size behavior (observe large-bubble envelope at defaults).
- [ ] Log baseline pass/fail notes in `Current_Plan.md`.

### Phase 2 - Reintroduce Settings in Safe Slices
- [ ] Slice A: Reintroduce spectrum ghost setting trio end-to-end.
- [ ] Slice B: Reintroduce sine ghost setting trio end-to-end.
- [ ] Slice C: Reintroduce bubble size controls (`bubble_big_contraction_bias`, `bubble_big_size_clamp`) end-to-end.
- [ ] Slice D: Reintroduce bubble ghost setting trio end-to-end.
- [ ] Slice E: Add `bubble_big_specular_max_size` end-to-end and cap pulse-driven specular growth in bubble rendering.

### Phase 3 - Regression Armor for Each Slice
- [ ] Add/update tests before advancing to next slice.
- [ ] Assert mapping continuity across: UI load/save -> `apply_vis_mode_kwargs` -> widget attrs -> `build_gpu_push_extra_kwargs` -> overlay -> renderer/shader uniforms.
- [ ] Fail slice if any fallback path is triggered unexpectedly.

### Phase 4 - Idea Box Tasks (Integrated)
- [ ] Spectrum swatch persistence sweep across all swatch-backed controls.
- [ ] Full per-mode leakage hunt beyond ghosting (all high-impact visual/technical controls).
- [ ] Add Spectrum-only deep-drop/de-pin tuning control.
- [ ] Add Spectrum graph editor lower bass/mid/vocal adjustability controls (Spectrum-only + persistence + runtime tests).
- [ ] Assess and fix QTTool MC key handling (media keys + keyboard input) while preserving no-taskbar/no-Alt-Tab behavior and avoiding AV-suspicious patterns.

### Phase 5 - Finalization
- [ ] Re-run targeted visualizer checks for blob/sine/bubble after all slices.
- [ ] Update `Index.md` with final routing ownership locations.
- [ ] Update `Spec.md` with accepted setting contracts/defaults.
- [ ] Update `Current_Plan.md` with completion state + deferred items.

---

## Execution Rules for This Recovery
- Treat any fallback activation as a defect.
- No instrumentation expansion unless needed to unblock a failing parity gate.
- No bundling multiple parity slices in a single unverified change.
- No new setting ships without matching route verification and tests.
