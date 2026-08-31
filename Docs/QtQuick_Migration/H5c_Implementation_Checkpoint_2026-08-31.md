# H5c Implementation Checkpoint — Visualizer Reactivity / Preset-Source Parity

Date: 2026-08-31  
Behavioral oracle: `3fe5df687387b6b6a121142372c43a7719442386`  
Execution authority: `Current_Plan.md`  
Detailed audit authority: `H5c_Visualizer_Reactivity_Parity_Audit_Decomposition_2026-08-31.md`  
Evidence matrix: `Visualizer_Reactivity_Historical_Current_Evidence_Matrix_2026-08-31.md`

## Purpose of this checkpoint

This file marks the first source-changing safety point in the historical-vs-Qt-Quick visualizer reactivity audit. It intentionally freezes the implementation before physical remeasurement changes the next hypothesis.

The checkpoint contains **source-proven repairs plus bounded diagnostics**. It does **not** claim that Bubble/Oscillo/Sine/DevCurve/Spectrum physical parity is now complete.

## Implemented in this checkpoint

- [x] Restored the three stranded Bubble logical preset controls to the current logical owner:
  - `bubble_group_drift`
  - `bubble_collision_pop_mode`
  - `bubble_big_visual_smoothing`
- [x] Restored historical canonical Spectrum topology translation:
  - `spectrum_render_mode="bars"` -> continuous/single-piece authored topology
  - `spectrum_render_mode="segment"` -> segmented authored topology
  - canonical key wins over the old boolean alias
- [x] Restored historical Spectrum color-topology translation:
  - `spectrum_unique_colors` -> presentation `rainbow_per_bar`
- [x] Added one presentation-neutral source-config applier for the **existing single BeatEngine**.
- [x] Restored the historical shared source/engine configuration block:
  - `spectrum_mirrored`
  - `spectrum_shape_nodes`
  - mirrored + linear notch positions
  - mirrored + linear lane strengths
  - `spectrum_wave_amplitude`
  - `spectrum_profile_floor`
  - `spectrum_drop_speed`
- [x] Preserved the historically important fact that those Spectrum-named source settings configure the **shared pre-mode audio pipeline even while another visualizer mode is active**.
- [x] Restored the historical Spectrum final renderer transfer: bars and peaks are multiplied by `0.55` exactly once at the Quick shader-input seam; authored/DSP values stay canonical.
- [x] Added bounded visualizer diagnostics without adding a timer, cadence owner, queue, source, or renderer polling path:
  - `[VIS_SOURCE_CONFIG]`
  - `[VIS_TECH_CONFIG]`
  - `[VIS_REACTIVITY]`
  - `[VIS_PLAYBACK_EDGE]` T0-T7 chain
- [x] Added one focused new test file only: `tests/test_qtquick_visualizer_reactivity_config_parity.py`.
- [x] Added focused coverage for the technically dangerous zero/false settings contract.

## Important source-proven cross-mode defect repaired

The missing shared source configuration is not merely a Spectrum renderer issue.

Historical full-model activation applied the Spectrum notch/shaping family to the single shared BeatEngine regardless of the visible mode. The unchanged FFT path uses configured notch positions before mode-specific state to derive shared bass/mid/treble lanes.

Without that configuration, current Quick could fall back to fixed split indices `4/10`. With the preset/default normalized notches, representative intended boundaries are approximately:

| authored bar domain | missing-config fallback | preset-normalized example |
|---:|---:|---:|
| 48 (Bubble example) | 4 / 10 | ~14 / 31 |
| 40 (Sine example) | 4 / 10 | ~12 / 26 |
| 32 (Oscillo/DevCurve example) | 4 / 10 | ~9 / 20 |
| 33 (Spectrum example) | 4 / 10 | ~9 / 21 |

Those lanes then participate in noise-floor/expansion, transient and AGC-related behavior before mode-specific presentation. This repair can therefore materially change real music response in every mode without changing any global gain constant.

## Reactivity-critical technical settings audited and already correct before this checkpoint

The audit separately traced the existing Quick technical owner and the unchanged worker implementation. These settings were **not missing** and are deliberately **not duplicated** by the new source-config applier:

- [x] per-mode `bar_count`
- [x] explicit `audio_block_size`
- [x] `dynamic_floor`
- [x] `manual_floor`
- [x] `adaptive_sensitivity`
- [x] manual `sensitivity`
- [x] dynamic-range enable -> historical energy-boost mapping
- [x] `input_gain`
- [x] `agc_strength`
- [x] kick/transient technical controls already owned by the Quick technical path

Critical zero/false semantics were checked explicitly:

- [x] `agc_strength=0.0` reaches the worker as exact zero.
- [x] unchanged `_apply_adaptive_normalization()` exits immediately below `0.01`, so zero still means **no AGC / raw output**, not "missing -> default AGC".
- [x] `dynamic_floor=False` remains manual-floor mode.
- [x] explicit nonzero audio block sizes remain explicit requests.
- [x] bar-count reconfiguration continues to use the one existing BeatEngine/controller domain and does not replace the restored notch configuration.

## Why previous goldens could remain GREEN

The existing deterministic visualizer replay/presentation goldens are mostly downstream tests. They begin with already-authored `FeatureFrame` / energy / bars / waveform state and then exercise logical evolution and retained presentation.

They therefore protect many important semantics **after feature state exists**, but they do not prove the production chain:

```text
resolved preset/model
-> Quick ownership routing
-> BeatEngine/audio-worker configuration
-> live FFT/band derivation
```

That is the exact seam that was broken. No golden baseline was regenerated in this checkpoint. The repair adds focused configuration reachability tests instead.

## Deliberately NOT changed yet

These remain open because the source comparison has not yet proven the correct repair:

- [ ] Do not weaken/remove the per-mode `source_ready` identity fence yet.
- [ ] Do not change the historical BeatEngine 1.5 s cold-start Play ramp yet.
- [ ] Do not add a Play/Pause workaround timer/debounce.
- [ ] Do not globally raise visualizer gain/sensitivity.
- [ ] Do not retune Bubble physics/energy constants to compensate for missing upstream semantics.
- [ ] Do not fake Sine idle motion with QML animation or another timer.
- [ ] Do not restore old `*_growth` sizing controls.
- [ ] Do not resurrect QWidget/GL presentation architecture or any compatibility presenter.
- [ ] Do not add a second BeatEngine/audio worker/logical owner/pacer.

## Diagnostic-ready unresolved work

### All-mode physical reactivity

- [ ] Re-run Bubble, Oscillo, Curve/DevCurve, Sine and Spectrum with real music after this shared-source repair.
- [ ] Compare whether the cross-mode magnitude defect materially improves before changing any mode constants.

### Bubble B0-B9

- [ ] Trace raw source magnitude -> source readiness -> Bubble authored energy/pulses -> immutable logical state -> Quick bridge -> renderer geometry.
- [ ] If the first bad stage is upstream/shared, fix it once.
- [ ] If authored Bubble state is healthy, continue downstream instead of changing gain.

### `source_ready`

- [ ] Use `[VIS_REACTIVITY]` to prove whether current valid audio is actually rejected or delayed.
- [ ] Preserve stale-frame fencing unless a concrete identity mismatch is demonstrated.

### Play/Pause startup delay

Collect one warm resume and one true cold start using `[VIS_PLAYBACK_EDGE]`:

```text
T0 Media canonical playback truth observed
T1 Quick visualizer owner receives edge
T2 BeatEngine playback state committed
T3 first current source frame after edge
T4 mode runtime reports source ready
T5 materially reactive logical frame published
T6 matching Quick snapshot publication
T7 retained Quick item consumes the edge
```

- [ ] First late interval determines the next repair owner.
- [ ] Separate legitimate historical cold ramp from migration-added latency.
- [ ] Do not infer transport timing from visual appearance alone.

### Sine idle

- [ ] Trace paused `SineFrameRuntime` animation/shift evolution.
- [ ] Prove whether changing paused state reaches immutable snapshot.
- [ ] Prove whether Quick receives changing idle uniforms/time.
- [ ] Fix the earliest broken transport/presentation seam only.

### Spectrum

The current checkpoint repairs three independent classes plus the color-topology translation:

- [x] canonical topology mapping
- [x] shared BeatEngine/source shaping
- [x] historical `0.55` final renderer transfer
- [x] unique-colors presentation translation
- [ ] physical S0-S7 remeasurement still required
- [ ] do not declare H5b closed until Spectrum is both visually recognizable and genuinely reactive under music

## Validation state at packaging

- [x] Modified/new Python files syntax-compile successfully.
- [x] Source diff audited to preserve current single-owner/single-engine/single-cadence architecture.
- [x] Existing source line-ending styles restored where edits had accidentally converted CRLF to LF.
- [x] No unchanged historical/old test suite files are included merely for completeness.
- [x] Only the new focused parity test file is part of this checkpoint's test delta.
- [ ] Full pytest execution is **not** claimed: the audit container does not provide `PySide6`.
- [ ] Normal project-environment focused test execution remains required.
- [ ] Maintained H/BTF profile remains required after application.
- [ ] Physical all-mode + T0-T7 logs remain required.

## Performance / architecture invariants preserved by this checkpoint

- [x] one product-level visualizer owner
- [x] one BeatEngine/audio worker
- [x] one authored cadence owner
- [x] retained Quick presentation architecture unchanged
- [x] source/preset configuration performed only on existing configuration/activation edges
- [x] no settings/preset resolution added to the ~90 Hz hot path
- [x] no FIFO/catch-up state queue
- [x] no QML polling/timer workaround
- [x] no second accelerated surface
- [x] diagnostics are opt-in and bounded

## Recommended next handoff

Apply this checkpoint, run the normal focused tests/H profile, then provide one physical log covering:

1. visualizer diagnostics enabled;
2. real music already playing long enough to be steady;
3. several seconds each of Bubble, Oscillo, Curve/DevCurve, Sine and Spectrum;
4. one Pause -> Play warm resume;
5. if practical, one true cold-start Play case;
6. one paused Sine interval long enough to observe whether idle animation exists.

Use the resulting source-ready/raw/resolved/T0-T7 evidence to choose the next repair. Do not reopen constants already exonerated unless that trace gives a source reason.
