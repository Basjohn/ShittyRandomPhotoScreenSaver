# R-76 — Spectrum viewport temporal scaling used the wrong axis and the wrong owner

Date: 2026-09-02  
Status: **Implemented / awaiting physical validation**

## Operator evidence

Current retained Quick Spectrum is physically good at ordinary aspect and at an extreme-wide viewport, while an extreme-tall viewport becomes visibly jumpy/flickery. Earlier attempts to smooth one extreme could damage the other.

## Source findings

Two independent migration/scaling seams explain that pattern.

### 1. The accepted viewport multiplier was stranded in the old presenter helper

`widgets/spotify_visualizer/spectrum_presentation_smoothing.py` still carried a large-viewport rule, but the production Quick logical path resolves Spectrum through `SpectrumFrameRuntime`. The live runtime used the same `2..14 ms` presentation one-pole at every viewport height.

The stranded helper also used:

```text
max(width / 420, height / 280)
```

That is the wrong geometry for Spectrum temporal response. Bar values move vertically. Doubling viewport width changes distribution/bar width, not the number of vertical pixels traversed by a bar-value change. The old rule could therefore over-smooth a wide card while still leaving the authoritative Quick owner untreated.

### 2. Solid-bar hysteresis changed temporal semantics with viewport height

The continuous/single-piece renderer has no visible segment topology, but its display hysteresis used the height-derived renderer segment count as an internal temporal coordinate. Around canonical height that domain is about `53` segments; an extreme-tall viewport reaches the `64` cap.

That caused the same normalized source delta to cross different micro/normal/fast hysteresis thresholds solely because the viewport became taller. A representative `0.300 -> 0.329` step is about `1.38` canonical helper segments but `1.67` tall helper segments: canonical selects the normal branch while tall selects the fast branch. Height changes could also reset the helper state when the derived segment count changed.

## Implemented correction

### Authoritative Quick smoothing

`SpectrumFrameRuntime` now consumes the new pure `spectrum_temporal_contract.py`.

The existing visual smoothing time constant is multiplied only by the expanded vertical bar-field ratio:

```text
vertical_ratio = (viewport_height - 12) / (280 - 12)
```

with a floor of `1.0` and the historical safety cap of `4.0`.

This is intentionally conservative rather than an exact pixel-speed clamp. At the default smoothing strength and ~90 Hz authored cadence:

```text
canonical 280 high: alpha ~0.751
560 high:           alpha ~0.493
816 high:           alpha ~0.371
```

For a representative `0.30 -> 0.70` bar step, the first visible vertical jump grows only about `1.3x` at ~2x height and `1.4x` at ~3x height instead of roughly `2x/3x`. Tall cards therefore retain visibly stronger/larger travel without turning viewport height into proportional one-tick jumps.

Canonical height is arithmetic-identical to the pre-fix runtime. Extreme-wide with canonical height is also arithmetic-identical.

### Solid-bar hysteresis

Single-piece hysteresis now uses one canonical internal segment domain (`53`) independent of viewport height. The Quick renderer still resolves its own height-derived segment count for actual segmented presentation; only the invisible temporal helper domain is canonicalized.

This removes a tall-only rate-zone acceleration/reset seam rather than stacking another smoothing multiplier.

## Deliberately unchanged

The correction does **not** modify:

- BeatEngine smoothing or FFT/bar computation;
- input gain, floor, AGC, sensitivity or source shaping;
- logical cadence/publication/presentation cadence;
- the historical `0.55` Spectrum shader-input transfer;
- `compute_spectrum_height_scale()` or authored bar amplitude;
- renderer segment count/density for actual segmented mode;
- peak/ghost decay timing;
- first-frame/generation/stall snap freshness fences.

Peak persistence was audited and intentionally left alone in this slice: scaling it in addition to body smoothing would lengthen ghost lifetime and risk compounding the temporal correction without operator evidence that the peak tail is the defect.

## Regression contract

`tests/test_spectrum_viewport_temporal_scaling.py` is a source-only profile that runs without PySide6 and pins:

- canonical/short ratio = `1.0`;
- height-only expansion and `4x` cap;
- no width-based smoothing authority;
- canonical/wide exact response equivalence;
- bounded tall physical jump growth without amplitude compression;
- current `SpectrumFrameRuntime` consuming the height-aware alpha;
- single-piece hysteresis using one canonical internal segment domain across canonical/tall viewports;
- the compatibility helper no longer reasserting the old max-axis rule.

Current audit result: **6/6 GREEN**.

## Physical acceptance still required

- canonical continuous Spectrum unchanged;
- extreme-wide continuous Spectrum unchanged;
- extreme-tall continuous Spectrum smooth without obviously delayed musical attack;
- canonical/wide/tall segmented Spectrum remains responsive and does not acquire new visible quantization pumping;
- mode/preset switch freshness snaps remain clean;
- no new latency/cadence/backlog behavior.

If tall still flickers after this correction, inspect the actual segmented pixel pitch / renderer quantization and source-to-visible trace before increasing the visual smoothing multiplier again. Do not compensate by reducing source magnitude or renderer amplitude.
