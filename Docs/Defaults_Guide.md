# Defaults Guide

Last updated: 2026-05-22

Canonical guidance for defaults, reset behavior, and safe default changes.

## 1. Source of Truth
- Canonical defaults are defined in `core/settings/default_settings.py`.
- `core/settings/defaults.py` provides normalized defaults and preserve-on-reset rules.
- Generated snapshot artifacts are derived outputs, not independent sources of truth.

## 2. Settings Structure
Defaults are organized under structured roots such as:
- `display`
- `input`
- `queue`
- `sources`
- `timing`
- `transitions`
- `widgets`
- `ui`

Key runtime reality:
- Standard and MC builds use separate persisted profiles through the storage-path contract.
- The `widgets` root is the canonical persistence surface for widget families, CUSTOM layout payloads, authored-layout restore routes, and visualizer/media routing state.

## 3. Reset/Preservation Contract
- Reset logic preserves explicitly whitelisted user-specific keys (defined in `core/settings/defaults.py`).
- Do not implement parallel preserve lists in other modules.
- Settings-dialog mutations and runtime mutations should use the same canonical widgets-map helpers when changing `widgets`, even if one caller intentionally suppresses live change emission.

## 4. Legacy Key Policy
- Retired global preset keys (`preset`, `custom_preset_backup`) are not part of modern defaults.
- Import/migration paths should tolerate old files but not re-emit retired schema keys.

Additional current migration rules:
- Persisted visualizer payloads are version-gated through the settings schema model and should not rely on perpetual legacy normalization.
- Invalid visualizer `Custom + ALL` routing is not a valid steady-state and must be corrected or suppressed rather than preserved as a normal default-like case.

## 5. Safe Default Change Workflow
When changing a default:
1. update canonical defaults,
2. update model/load/save plumbing where applicable,
3. update normalization/contract helpers if impacted,
4. update affected UI load/save behavior,
5. add/update tests for fresh + existing settings behavior,
6. refresh related docs.

## 6. Visualizer Default Changes
For visualizer defaults, also update:
- mode registry/contract assumptions,
- preset repair/audit expectations,
- curated preset payloads if schema/content requires it,
- visualizer-focused tests and docs.

## 7. Widget Defaults vs CUSTOM Contracts
- Base widget defaults remain canonical even when a widget family is using `Custom`.
- CUSTOM move/resize is an overlay contract on top of authored defaults; it does not replace the authored defaults model.
- If a saved settings control becomes derived/no-op while a widget family is in `Custom`, lock that control in the UI rather than inventing a second hidden defaults surface.
- Authored-layout restore must route through the shared authored-route restore helper, not through ad hoc per-dialog or per-runtime reset logic.
