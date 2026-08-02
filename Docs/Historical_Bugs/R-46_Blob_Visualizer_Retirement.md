# R-46 — Failed Blob Visualizer Retired End To End

Date: 2026-07-15  
Status: Resolved

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

## Why Retirement Was Necessary

Blob was already classified as a failed, soon-to-be-retired mode, but its temporary dev gate left a second-class architecture spread across 115 files, thousands of source matches, 267 collected tests, typed settings, curated presets, runtime transport, renderers, shaders, diagnostics, packaging, and CLI/test escape hatches. Continuing to repair or quarantine that surface would spend shared-visualizer budget on a mode that was not intended to ship.

## Migration Boundary

Visualizer settings schema version 3 maps a saved/imported `mode: blob` to the registry-owned supported default, strips `blob_*` and `preset_blob` leaves before model normalization, preserves sibling widget data, and never re-emits retired fields. Normal/MC canonical defaults and generated JSON/SST artifacts contain no Blob leaves. Curated tree scanning, manifests, folder/ZIP import, and release mirroring accept only registered modes while still pruning stale retired preset files from managed destinations.

## Removal

Deleted the gate, descriptor, defaults/model fields, Settings controls/builders/bindings, presets, CLI option, runtime state and transport, solvers, renderers, shaders, diagnostics, package-facing registrations, dedicated tests, and temporary pytest skip/escape hatch. Shared audio, activation, compositor, animation, card geometry, and the five supported modes were not redesigned or retuned.

## Bars

The migration/absence suite covers plain, dotted, and persisted settings; sibling preservation; clean defaults; no re-emission; and retired preset import/pruning. The supported visualizer reactivity/runtime lock passed before removal and again after production teardown (`17 passed`); the integrated changed-file gate finished at `907 passed, 20 skipped`, and Defaults Foundry/settings/default/manifest/transfer suites remained green. A production-scope search retains only the explicit migration token; historical bug prose remains documentation, not executable ownership.

## Guardrail

Blob may appear only as a migration input or historical record. Do not restore its dev gate, defaults, presets, tests, render branches, shaders, or package assets. Any future visualizer must establish its own active descriptor, settings, visual identity, supported-mode regression bars, and release intent rather than inheriting retired Blob code.

## Migration Record

This file is the standalone detailed record copied from the original `R-46` entry in `Docs/Historical_Bugs.md`. The monolithic source entry remains unchanged during the copy-first migration and will be replaced by a compact index summary only after the historical-bug set has been migrated and mechanically checked.
