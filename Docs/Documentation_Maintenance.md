# Documentation Maintenance

Last updated: 2026-06-30

Lightweight drift-check routine for SRPSS's active documentation set.

## Purpose
- Keep `Spec.md`, `Index.md`, `Docs/Contracts.md`, `Docs/Guardrails.md`, and focused reference docs aligned with code that actually ships.
- Keep `Current_Plan.md` as active work only. It is not a changelog, release note, or historical ledger.
- Remove stale concepts, dead file references, and old "recently changed" wording before they become accidental contracts.

## Document Roles
- `Spec.md`: canonical architecture and behavior contracts.
- `Index.md`: live module map and ownership lookup.
- `Docs/Contracts.md`: short routing index for major subsystem contracts.
- `Docs/Guardrails.md`: engineering rules and anti-regression policy.
- `Docs/Historical_Bugs.md`: dated regression stories and lessons.
- `Docs/Regression_Notes.md`: smaller resolved regression notes that should stay visible but do not merit a full historical entry.
- `Docs/Harness_Index.md`: recurring harnesses, probes, and runtime-shaped validation routes.
- Focused guides/checklists: defaults, widget creation, visualizer changes, transition changes, and shared UI style.

## When To Run This
- After a shared architecture change.
- After a settings/defaults/import/export change.
- After visualizer, transition, widget-descriptor, logging, or storage-path work.
- Before closing a large task that touched both code and docs.

## Drift Check

### 1. Verify Navigation
- Every long-lived doc should be reachable from `Index.md` or a focused guide that clearly owns the workflow.
- Removed docs must disappear from `Index.md`, `Spec.md`, `Docs/00_PROJECT_OVERVIEW.md`, and test reference guards.
- New code modules that carry ownership should be added to `Index.md` when they are part of the public architecture map.

Useful commands:
```powershell
rg -n "OldDocName|RemovedDocName|rebuild_visualizer_presets" Index.md Spec.md Docs tests
rg --files Docs core widgets ui rendering tools tests
```

### 2. Verify Ownership Claims
- Settings persistence should route through `SettingsManager`, `JsonSettingsStore`, canonical defaults, and `core/settings/storage_paths.py`.
- Visualizer identity, settings, presets, activation, and runtime transport should route through the registry/model/preset/activation modules named in `Spec.md` and `Index.md`.
- Transition identity, labels, aliases, random/cycle participation, and warmup metadata should route through `rendering/transition_registry.py`.
- Widget family metadata should route through `rendering/widget_descriptors.py`.

Useful commands:
```powershell
rg -n "JsonSettingsStore|get_settings_dir|get_log_dir|export_to_sst|import_from_sst" core ui Docs
rg -n "resolve_visualizer_activation_payload|visualizer_preset_transfer|visualizer_mode_registry|_spotify_visualizer" core ui widgets Docs
rg -n "transition_registry|TransitionType|random pool|warmup" rendering ui engine Docs
```

### 3. Keep Active Work Clean
- If implementation is complete and validation passed, remove it from `Current_Plan.md`.
- If a real regression lesson remains, move it to `Docs/Historical_Bugs.md` or `Docs/Regression_Notes.md`.
- If a future idea is real but not active, use `Future_Cleanup.md` instead of leaving scratch notes in the plan.

### 4. Refresh Tests And Harness References
- Update `Docs/TestSuite.md` when important test inventory or validation routes change.
- Update `Docs/Harness_Index.md` when a recurring runtime investigation gains or loses a harness.
- Prefer runtime-shaped validation for visual, timing, focus, multi-monitor, secure-desktop, transition, and visualizer behavior.

## Good Outcome
- Navigation points only at live docs.
- Architecture truth is stated once in the strongest owner document.
- `Current_Plan.md` contains only unfinished active work.
- Historical notes explain regressions, not ordinary feature completion.
