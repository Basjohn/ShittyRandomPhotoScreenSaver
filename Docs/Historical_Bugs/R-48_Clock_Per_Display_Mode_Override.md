# R-48 — Clock Double-Click Replaced Per-Display Mode With Shared Setting

Date: 2026-07-15  
Status: Resolved

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

## Observed Failure

A Clock routed to all displays could no longer remain analogue on one display and digital on another. Double-click visibly toggled the selected instance, but the choice was persisted into the shared Clock setting and therefore became the baseline for every display on the next settings event/rebuild.

## Root Cause

R-45 correctly removed behavior authority from per-display CUSTOM geometry payloads, but the surviving double-click persistence path still wrote `display_mode` and `clock_analog_mode` into the shared widget section. Removing the stale geometry authority therefore exposed the older global-write assumption and erased a useful mixed-display runtime contract.

## Fix

The Settings value remains the global baseline. Double-click now persists an explicit `display_mode_overrides` entry keyed by the existing stable screen signature, and `ClockWidgetFactory` applies that override only when creating the matching display instance. CUSTOM entries continue to contain only `font_size` and `geometry_variant`; no behavior field was restored to geometry payloads. The local mode and mode-shaped rect still update immediately, and persistence uses `emit_change=False`, so no cross-display rebuild or UI-pressure path was added.

## Bars

Clock tests prove digital-to-analogue and analogue-to-digital CUSTOM transformations preserve the shared baseline while writing only the current screen override; factory coverage proves a matching signature selects the override. The focused Clock/factory/diagnostic suite passed `45/45`.

## Runtime Validation Target

Route one Clock to ALL, double-click only one display, then exercise unrelated Settings refresh, engine rebuild, and restart. Require one analogue and one digital instance, stable per-display geometry, no global mode flip, no duplicate widget creation, and no DT/paint burst.

## Validation

The user validated Clock behavior in every requested scenario, including mixed analogue/digital display ownership. The live plan no longer carries a Clock runtime-validation task.

## Migration Record

This file is the standalone detailed record copied from the original `R-48` entry in `Docs/Historical_Bugs.md`. The monolithic source entry remains unchanged during the copy-first migration and will be replaced by a compact index summary only after the historical-bug set has been migrated and mechanically checked.
