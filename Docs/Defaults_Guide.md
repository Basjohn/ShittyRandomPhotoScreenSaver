# Defaults Guide

Last updated: 2026-06-30

Canonical guidance for defaults, reset behavior, snapshots, and import safety.

## 1. Sources Of Truth
- Canonical defaults: `core/settings/default_settings.py`.
- Defaults API, normalization, and preserve-on-reset rules: `core/settings/defaults.py`.
- Generated parity artifacts: `core/settings/defaults_snapshot.py`, `defaults_snapshot.json`, and `defaults_generated.py`.
- Persistent settings store: `JsonSettingsStore` through `SettingsManager`.

Generated artifacts are derived outputs. Regenerate them with the project tool instead of hand-editing them.

## 2. Storage Shape
- Standard profile settings file: `%APPDATA%/SRPSS/settings_v2.json`.
- MC profile settings file: `%APPDATA%/SRPSS_MC/settings_v2.json`.
- Storage-path ownership: `core/settings/json_store.py` and `core/settings/storage_paths.py`.
- Structured roots include `widgets`, `transitions`, and `ui`; older flat/dotted keys remain accepted through `SettingsManager` APIs where needed.

Use public `SettingsManager` accessors for active settings paths. Do not reach into the backing store from UI code.

## 3. Reset And Import Preservation
- Preserve-on-reset keys live in `core/settings/defaults.py`.
- Reset/import flows must reuse the shared preservation and normalization contracts.
- SST import/export is a transport layer over the current JSON settings architecture.
- Root `widgets` writes, widgets-map helpers, and SST imports must share visualizer normalization/schema behavior.

## 4. Legacy Policy
- Retired global preset keys such as `preset` and `custom_preset_backup` are migration inputs only.
- Modern defaults and exports must not emit retired schema keys.
- Persisted visualizer schema migration should be version-gated and converge to current payloads rather than rerunning old normalization forever.

## 5. Safe Default Change Workflow
When changing a user-facing default:
- update `core/settings/default_settings.py`,
- update typed models or normalization helpers where applicable,
- update UI load/save behavior,
- regenerate defaults snapshot artifacts,
- run defaults parity tests,
- add migration/import coverage if existing user settings are affected,
- and refresh `Spec.md`, `Index.md`, or focused docs only when live contracts changed.

## 6. Visualizer Defaults
Visualizer default changes also need:
- mode-registry and `_spotify_visualizer.py` grouped field-spec review,
- curated preset expectations reviewed where authored payloads rely on old values,
- visualizer preset repair/import/export coverage when schema shape changes,
- and runtime-shaped validation when the change affects visible mode behavior.

## 7. CUSTOM And Widget Defaults
- Authored defaults remain the fallback even when a widget uses `Custom`.
- Committed CUSTOM geometry overlays authored defaults; it is not a replacement defaults surface.
- If a settings control becomes derived or locked under `Custom`, lock it in UI rather than inventing a hidden alternate default.
