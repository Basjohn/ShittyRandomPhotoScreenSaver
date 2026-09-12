# R-80 — ABC event-loop rolling history contaminated named steady windows

**Date:** 2026-09-12  
**Status:** FIXED IN ORACLE / PRODUCT ROOT CAUSE STILL OPEN

## Symptom

The Visualizer P4 A/B/C harness classified the 25-switch exposure as `swap_sensitive` and appeared to show that a saved-layout Quick-runtime recreation cleared the resulting event-loop tail.

## Root cause

`EventLoopStallRecorder` sampled every 50 ms and retained 2,048 values, so each logged percentile represented about **102.4 seconds of rolling history**. The ABC driver excluded only 15 seconds after the final switch/recreation before opening a named scored window. The harness then treated each rolling p99 summary inside that window as if it described only post-boundary samples.

Switch-period stalls therefore remained mathematically present for most of `steady_B` / `steady_C_pre` and were repeatedly counted as a persistent settled regression.

The preserved C runs falsified the recreation claim directly: `steady_C_pre` returned to roughly 4–5 ms p99 before the recreation occurred. C-post was clean, but C-pre had already recovered.

## Correction

- keep the ordinary rolling event-loop diagnostic view;
- add an independent non-overlapping `period_*` summary for each report interval;
- reset recorder scoring history exactly at each ABC named scored-window boundary;
- tag period summaries with the named scoring window;
- score only matching window-local periods;
- fail old rolling-only ABC logs closed for causal scoring;
- measure p99 persistence from consecutive represented report durations, not repeated observations of one rolling history.

## What remains valid

The stress run still proved useful boundedness facts: the exact switch sequence (Sphere included) retired inactive render implementations cleanly, presentation/request counts stayed bounded, and the measured GL-state isolation/sync-present paths did not grow with switch count. Those are anti-leak facts only; they do not prove or disprove the original long-residency user-visible hitch.

## Guardrail

A named causal window may not score a metric whose retained history crosses the window boundary unless the scorer explicitly subtracts/slices that history. A post-boundary exclusion is not a substitute for resetting/slicing a longer rolling metric.
