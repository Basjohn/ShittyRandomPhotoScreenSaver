# Defaults Guide

Last updated: 2026-04-23

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

## 3. Reset/Preservation Contract
- Reset logic preserves explicitly whitelisted user-specific keys (defined in `core/settings/defaults.py`).
- Do not implement parallel preserve lists in other modules.

## 4. Legacy Key Policy
- Retired global preset keys (`preset`, `custom_preset_backup`) are not part of modern defaults.
- Import/migration paths should tolerate old files but not re-emit retired schema keys.

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
