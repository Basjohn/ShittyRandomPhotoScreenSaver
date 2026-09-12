# R-80 — ABC event-loop rolling history contaminated named steady windows

**Date:** 2026-09-12  
**Status:** **FIXED / LIVE-VALIDATED / PERFORMANCE INVESTIGATION CLOSED**

## Symptom

The Visualizer P4 A/B/C harness classified the 25-switch exposure as `swap_sensitive` and appeared to show that a saved-layout Quick-runtime recreation cleared a persistent post-switch event-loop tail.

## Root cause

`EventLoopStallRecorder` sampled every 50 ms and retained 2,048 values, so each ordinary logged percentile represented about **102.4 seconds of rolling history**. The ABC driver excluded only 15 seconds after the final switch/recreation before opening a named scored window. The harness then treated each rolling p99 summary inside that window as if it described only post-boundary samples.

Real switch-period stalls therefore remained mathematically present for most of `steady_B` / `steady_C_pre` and were repeatedly counted as a persistent settled regression.

The preserved C runs falsified the recreation claim directly: `steady_C_pre` returned to roughly 4–5 ms p99 before recreation occurred. C-post was clean, but C-pre had already recovered.

## Correction

- keep the ordinary rolling event-loop diagnostic view for general `--perf` observation;
- add an independent non-overlapping `period_*` summary for each report interval;
- reset recorder scoring history exactly at each ABC named scored-window boundary;
- tag period summaries with the named scoring window;
- score only matching window-local periods;
- fail old rolling-only ABC logs closed for causal scoring;
- measure p99 persistence from consecutive represented report durations, not repeated observations of one rolling history.

The harness auto-launch path was also corrected to parse `--run-cmd` platform-aware: POSIX `shlex.split()` had stripped backslashes from native Windows executable paths such as `C:\Python311\pythonw.exe`. Windows parsing now preserves backslash paths and quoted paths with spaces; focused regression tests cover both forms.

## Corrected live validation

A fresh corrected A/B pair used `main_mc.py`, saved geometry slot 1, four contention workers, `--usage --viz --perf --life`, the same 15 s settle exclusion and a 120 s scored Bubble hold. B performed `Sphere -> Spectrum -> Oscilloscope -> Sine -> Bubble` x5 before scoring.

- A mean window-local p99: **5.87 ms**
- B mean window-local p99: **6.80 ms**
- delta: **+0.93 ms / +15.8%**, below both investigation regression gates (+2 ms absolute, +35% relative)
- >25 ms events: **3 vs 3**
- Visualizer revision: **89.91 vs 89.86 Hz**
- Bubble integration: **1.000 vs 1.000**
- draw rate: **60.65 vs 59.98 fps**
- B independent p99 periods: **6.74, 7.10, 6.87, 6.17, 7.93, 6.75, 6.01 ms**

Therefore the automated **persistent 25-switch poisoned-runtime hypothesis is not reproduced for this build/load**. C is not warranted because corrected B has no settled regression for recreation to reverse.

The rapid switch burst itself still produced real transient stalls before the scored-window reset (period p99 **82.67 ms**, then **28.21 ms**, max **696.74 ms**). Those are expected bounded switch/transition costs in an intentionally abusive 25-switch sequence, not persistent post-switch poisoning and not a backlog item by themselves.

## Closure boundary

No Visualizer performance investigation remains active from this incident. The original long-run user-visible hitch was not re-established with trustworthy window-local evidence, so it is not an actionable current defect and no scheduled soak/probe branch is warranted. Future work may reopen performance only when normal use or logs produce a persistent, growing or otherwise traceable issue that survives the triggering activity.

**Closed investigation reference:** `Docs/Reference/Visualizer_Post_Switch_Performance_Investigation.md`

## Guardrail

A named causal window may not score a metric whose retained history crosses the window boundary unless the scorer explicitly subtracts/slices that history. A post-boundary exclusion is not a substitute for resetting/slicing a longer rolling metric.
