# R-47 — Oscilloscope Diagnostic Cleanup Broke Every Frame Push

Date: 2026-07-15  
Status: Resolved

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

## Observed Failure

Hotswapping to Oscilloscope produced no visible mode, and starting directly in Oscilloscope left the visualizer absent. Startup eventually logged a reveal-watchdog expiry while waiting for its first valid frame.

## Root Cause

Blob retirement correctly deleted the Blob-only portion of the Oscilloscope diagnostic signature, but accidentally removed the entire local `sig` assignment while leaving the shared throttle and assignment references intact. With visualizer diagnostics enabled, every `SpotifyBarsGLOverlay.set_state()` call raised `NameError` after state preparation. The display push failed before startup staging could observe a valid frame; the reviewed run emitted 78 copies of the same frame-boundary exception.

## Fix

Restored a Blob-free Oscilloscope signature from supported mode-owned state: line speed, waveform blend, ghost-ring occupancy/delay/alpha, and transient-width mix. The existing bounded diagnostic throttle and render behavior are unchanged. No timer, repaint, retry, fallback, visual retuning, or exception suppression was added.

## Bars

Diagnostics-enabled coverage now executes repeated Oscilloscope calls, proves unchanged state is throttled, proves a supported-state change logs again, and would fail on the deleted assignment. The focused Clock/factory/diagnostic suite passed `45/45`; the supported visualizer lock remains required before closure.

## Runtime Validation Target

Start in Oscilloscope and hotswap into it from two supported modes under `--viz --perf`. Require first-frame reveal, continuous frame pushes, bounded `[SPOTIFY_VIS][OSC]` logs, no push traceback/watchdog expiry, and unchanged waveform/ghost/transient visuals.

## Validation

The user validated both direct Oscilloscope startup and hotswap behavior. The current-good supported visualizer reactivity/smoothness lock remains the regression safeguard; no mode-specific validation task remains active.

## Migration Record

This file is the standalone detailed record copied from the original `R-47` entry in `Docs/Historical_Bugs.md`. The monolithic source entry remains unchanged during the copy-first migration and will be replaced by a compact index summary only after the historical-bug set has been migrated and mechanically checked.
