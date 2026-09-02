# Visualizer extreme-viewport scaling audit — 2026-09-02

Status: **source audit complete; Spectrum R-76 implemented / awaiting physical validation; other modes assessment-only**.

## Why this audit exists

Operator evidence exposed a repeatable failure mode: a visualizer can have correct audio/logical values yet become jumpy, weak, or over-smoothed only at an extreme CUSTOM aspect because normalized response, viewport geometry and temporal filtering were coupled incorrectly. Spectrum's old larger-axis smoothing rule could make a width-only change alter vertical temporal response, while the actual Quick owner had no viewport treatment at all.

This audit therefore reviews the retained Quick path by **effect axis**, not by generic card size.

## Audit method

For each mode, trace:

```text
source / logical value
-> mode-owned temporal state
-> normalized/world geometry
-> viewport_extent + uniform_visual_scale
-> renderer transfer
-> physical pixel displacement
```

Then ask:

- Does width alter a Y-only smoothing/decay/hysteresis decision?
- Does height alter an X-only decision?
- Does renderer density secretly become a temporal coordinate?
- Is an authored pixel-like radius/stroke scaled by viewport extent instead of uniform scale?
- Is a second viewport compensation compressing already-normalized response?
- Does a fix alter source magnitude instead of the presentation seam?

A plain increase in physical pixel travel on a larger canvas is **not** by itself a defect.

## Spectrum — proven defect, R-76

R-76 fixed two independent seams in the live Quick path:

1. main visual smoothing is now height-only and owned by `SpectrumFrameRuntime`;
2. continuous/single-piece hysteresis uses a canonical internal segment domain instead of renderer height-derived segment count.

Canonical and canonical-height wide response remain arithmetic-identical. Tall response gets one conservative temporal correction; BeatEngine/DSP, the historical `0.55` upload transfer, height/amplitude boost, renderer segment density and peak lifetime remain unchanged.

## Bubble — no new defect found

Bubble already has the strongest viewport contract in the codebase. The expanded logical domain carries X/Y spatial truth, collision/spawn/motion distances are mapped through that domain, and retained rendering normalizes once. R-69 is binding: head/Ghost response must not receive a global inverse-viewport compressor. BTF and the existing viewport tests cover the dangerous seams.

Result: **no new change recommended**. Large physical motion/radius at large viewports is authored response unless a specific upper visual tail is separately proven problematic.

## Oscilloscope — audited watchpoint, no proven bug

The waveform is continuous and antialiased. Its normalized Y values occupy the current inner height, so a taller card naturally turns the same normalized delta into more physical pixels. Energy attack/release (roughly 60/120 ms) and waveform blend remain viewport-neutral. Vertical Shift placement intentionally follows viewport height; line/glow thickness follows `uniform_visual_scale` rather than edge extent.

Unlike pre-R-76 Spectrum, the audit found **no viewport-dependent temporal branch, renderer-density hysteresis, max-axis multiplier or reset seam**. Pre-emptive height smoothing would therefore be speculative and could weaken the desired large-view response.

Watchpoint: if extreme-tall Oscilloscope is physically observed to strobe, trace the Y pixel trajectory under a recorded waveform before adding one height-local presentation correction.

## Sine — two axis watchpoints, no proven bug

Sine amplitude is normalized into current height and phase/travel spans current width. This means:

- taller -> more physical Y displacement for the same normalized amplitude change;
- wider -> more physical X travel for the same normalized phase/travel rate.

Its energy/transient/reactivity envelopes are authored time-domain values and do not switch branches based on viewport size. Vertical line spacing deliberately scales with height; stroke/glow thickness remains uniform-scale owned.

Result: **assessment only**. Extreme-wide phase speed and extreme-tall amplitude motion are worth physical falsifiers, but there is no source proof that either is wrong. Do not introduce a generic `max(width,height)` smoother or global sensitivity reduction.

## DevCurve — normalized travel watchpoint, renderer pixel geometry already corrected

DevCurve solves 96-sample normalized curves with normalized-domain energy smoothing, spatial smoothness/slope limiting and foreground/specular travel. The Quick renderer already computes independent baseline/current normalized X/Y scales for outline/specular pixel-like geometry and an X-to-Y ratio for lobes; this is the correct kind of axis-aware presentation treatment.

A very wide viewport still makes a normalized X travel rate cover more physical pixels/second, and a tall viewport makes normalized Y change cover more pixels. No viewport-dependent temporal branch/reset or second response compressor was found.

Result: **assessment only**. The strongest future falsifier is foreground/specular X travel at extreme-wide size. Do not retune the solver or energy amplitude without physical evidence.

## Cross-mode conclusion

No additional source-proven scaling bug was found beyond Spectrum R-76. The absence of a generic viewport multiplier in Oscilloscope/Sine/DevCurve is not itself missing treatment: continuous normalized visuals are allowed to become physically larger on a larger authored viewport. The next bug, if one appears physically, must be localized by axis and channel before correction.

Binding rule: **viewport adaptation may preserve presentation quality; it may not silently compress authored musical response. One proven seam -> one correction.**
