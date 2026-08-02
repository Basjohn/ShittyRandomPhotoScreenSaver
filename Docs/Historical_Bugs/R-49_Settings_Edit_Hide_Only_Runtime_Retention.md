# R-49 — Settings/Edit Hide-Only Pause Retained Old GL Runtime And Shadowed Cleanup

Date: 2026-07-28  
Status: Resolved

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

## Observed Failure Family

The Settings path claimed a full-style restart but `stop(exit_app=False)` only quiesced, cleared, and hid the old display stack. Settings was constructed while the old widgets, compositor contexts, visualizer overlays, deferred warmups, and image callbacks still existed. Cleanup happened only after the dialog closed. Context failures were routinely suppressed and handles reset, so apparent teardown could not prove resource deletion.

## Root Causes

The pause/reconfigure contract was hide/reuse rather than full stop; `DisplayWidget._on_destroyed` was defined twice and the later no-op replaced the real delegate; the legacy overlay helper cleared attributes on the child instead of the display; async image/startup/display-ready/deferred-warmup publications lacked one engine-runtime identity; compositor/texture cleanup treated invalid context/deletion failure as a best-effort reset.

## Fix

Settings and committed CUSTOM Edit now cross `teardown_display_runtime()` before dialog/reload work. One engine generation plus exact `DisplayManager` identity rejects late publications. `DisplayManager.cleanup()` calls explicit synchronous `DisplayWidget.cleanup_runtime()`, which stops producers/visualizer overlays, then strictly deletes compositor textures/PBOs/programs/buffers with the GUI thread and owning context verified, calls `doneCurrent()`, asserts zero live compositor resources, and only then destroys surfaces/QObjects. Failed deletion retains ownership and the compositor remains `DESTROYING`.

## Bars

`tools/phase3_lifecycle_harness.py` completed 50 Settings, 50 Edit, and 50 mixed cycles with active transition, Spectrum/Bubble, in-flight decode, and resolution change. All 150 stale callbacks were rejected; stopped GL bytes/resources, timers, workers, and callbacks returned to zero; teardown order stayed valid. The focused lifecycle gate passed, image pipeline/worker regressions passed, and the real Windows Qt GL cleanup test passed without skip.

## Guardrail

Never restore hide-only Settings pauses, post-dialog display cleanup, destroyed-signal ownership, handle-clearing on failed deletion, or generation-only callbacks that omit exact manager identity. Partial reinitialization requires a separate approved architecture proposal.

## Evidence

- `Docs/phase_reports/P03_GL_LIFECYCLE_AND_RECONFIGURATION.md`
- `Docs/phase_reports/artifacts/P03/lifecycle_churn_report.json`

## Migration Record

This file is the standalone detailed record copied from the original `R-49` entry in `Docs/Historical_Bugs.md`. The monolithic source entry remains unchanged during the copy-first migration and will be replaced by a compact index summary only after the historical-bug set has been migrated and mechanically checked.
