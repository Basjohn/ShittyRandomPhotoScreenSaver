# R-150 | Sphere analysis-only DSP, Shockwave shaping audit

**Status:** Source correction landed; Windows tests and a short Sphere/ Shockwave/ Spectrum physical acceptance still pending. 2026-10-09. Baseline `8448717216`, supersedes R149 as a full dirty working tree.

## Actual defect

R149's Windows trace records 189 suppressed `KeyError('Treble')` exceptions during Sphere capture. `source_config_applier.resolve_mode_source_config()` correctly projected Sphere-owned `sphere_analysis_notch_positions` into the existing worker's zone split, but also projected unused canonical Spectrum shape fields, and the engine configured those fields, while `bar_computation.fft_to_bars()` unconditionally performed shape interpolation. Sphere's selected `Bass/Mid/Treble/End` analysis labels do not belong to Spectrum's independent authored lane strengths. `_build_lane_energy_profile()` used strict `strengths[str(label)]`, and the broad `fft_to_bars` exception handler returned zero bars. Changing or relaxing authored lane weights to hide that error would be incorrect.

## Correction

- At activation, the descriptor's existing `analysis_notch_setting` marks Sphere `'_source_analysis_only'`; every other mode explicitly clears that policy in the single shared engine. This is a transient source routing value, not a persisted Setting, migration or preset.
- Sphere's source projection omits **all Spectrum shaper source keys** and carries only its own normalized analysis boundaries plus a transient analysis-only policy. `apply_engine_vis_mode_kwargs()` applies those boundaries and enables analysis-only on the same BeatEngine/worker. It does **not** send Sphere through Spectrum shape-node, lane-strength, mirroring or drop-speed setters. Spectrum, Extruded, and Shockwave still run their own authored shaper. Other carded modes clear the analysis-only policy too.
- `bar_computation.fft_to_bars()` still computes log-frequency bin levels, mode-owned zone splits, floor/expansion, pre-AGC control and live lanes, and the existing transient bus. Only after these publications does Sphere short-circuit before shape interpolation, bar gates, smoothing, post-shape kick/AGC work. It returns the same zero-height bar contract that the old failed shaper returned, preserving the formerly observed post-shape channel without making that channel a new energy authority. The immutable `_freq_values` copy is still demand-published at verified BeatEngine commit.
- `_analysis_only_audio` is snapshot-scoped with the existing serial compute-lane generation; the owning engine fences outstanding work on policy changes. No new worker, timer, queue, polling or presentation authority.
- OpenBLAS and Qt thread-retention optimizations (R-97/R-99) are untouched.

## Shockwave finding: no matching defect

Shockwave deliberately owns `shockwave_grid_shape_nodes`, lane strengths, notch positions and smoothing. It is a Spectrum-frame family member; `rendering/quick/visualizer/implementations/shockwave_grid.py` explicitly uploads its shaped `logical.common.bars` through `uBars` to drive the horizon, while transient onsets separately author shockwave events. Its Settings UI describes the bar field. Removing this shaping would **break** a mode-authored visual feature. Shockwave must remain a full-shaper consumer, and a Sphere -> Shockwave mode switch must restore its own profile and disable analysis-only.

## Acceptance / regression tests

`tests/test_audio_analysis_only_isolation.py` uses synthetic PCM and test-owned shape/notch/weight configurations. It ensures Sphere retains meaningful pre-AGC energies and FFT samples without executing shape-lane interpolation, detached compute snapshots retain policy, Shockwave calls the real shape interpolation with its own test profile, and Sphere <-> Shockwave -> Spectrum transitions restore their mode-specific DSP. The pre-existing Sphere source/recorder contract tests are updated to forbid passing Spectrum shape settings to Sphere's engine. No curated preset values are frozen as tests.

**Pending:** Windows four-chunk regression and actual Sphere/ Shockwave/ Spectrum audio switching, ensuring no `KeyError('Treble')`, no loss of pre-AGC Sphere reactions, and no lost Shockwave horizon response. Native Qt-based tests cannot run in a PySide6-free environment; do not represent static checks as Windows acceptance.
