# Defaults Guide

Last updated: 2026-07-14

Canonical guidance for defaults, reset behavior, snapshots, and import safety.

## 1. Sources Of Truth
- Canonical defaults: `core/settings/default_settings.py`.
- MC-only differences: `core/settings/default_profile_overrides.py`.
- Defaults API, normalization, and preserve-on-reset rules: `core/settings/defaults.py`.
- Generated parity artifacts: `core/settings/defaults_snapshot.py`, `defaults_snapshot.json`, and `defaults_generated.py`.
- Generated distribution artifacts: `Docs/SRPSS_Settings_Screensaver.sst` and `Docs/SRPSS_Settings_Screensaver_MC.sst`.
- Persistent settings store: `JsonSettingsStore` through `SettingsManager`.

Generated artifacts are derived outputs. Regenerate them with the project tool instead of hand-editing them.

Normal/Screensaver defaults are not an override layer. `default_settings.py` is their authoritative base. `Screensaver_MC` resolves that base plus only the compact MC differences in `default_profile_overrides.py`.

The current MC differential changes only `display.show_on_monitors`, `input.interaction_mode`, `widgets.gmail.monitor`, and `widgets.media.monitor`. That list is descriptive rather than a competing authority: the Foundry-owned differential source defines future intentional additions or removals, and parity tests derive the actual changed leaf set from it.

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
- User/runtime SST exports may carry operational settings metadata. The two checked-in default SSTs instead carry stable artifact metadata and are generated directly from `build_sst_defaults_snapshot(profile)`, whose pure projection matches fresh-reset/export shape without retaining redundant nested-plus-dotted compatibility leaves; they never open a settings store or migration source.

## 4. Legacy Policy
- Retired global preset keys such as `preset` and `custom_preset_backup` are migration inputs only.
- Modern defaults and exports must not emit retired schema keys.
- Persisted visualizer schema migration should be version-gated and converge to current payloads rather than rerunning old normalization forever.

## 5. Safe Default Change Workflow
When changing a user-facing default:
- update `core/settings/default_settings.py` directly or use `tools/default_settings_editor.py`,
- update typed models or normalization helpers where applicable,
- update UI load/save behavior,
- regenerate defaults snapshot artifacts,
- run defaults parity tests,
- add migration/import coverage if existing user settings are affected,
- and refresh `Spec.md`, `Index.md`, or focused docs only when live contracts changed.

A successful Defaults Foundry **Save and Regenerate Defaults** establishes the new authoritative Normal base and MC differential. Existing tests, generated artifacts, and policy text must be updated to follow that saved value; they may reject or revert it only when a reproducible runtime, safety, migration, or compatibility regression proves the value harmful. Tests are guards around the defaults contract, not a second defaults authority.

## 6. Defaults Foundry
- Run `python tools/default_settings_editor.py` for the standalone styled editor.
- The tree recursively discovers every editable leaf in the canonical base. New settings therefore appear without a handwritten Foundry form.
- Normal edits rewrite `default_settings.py`. MC edits serialize only values that differ from resolved Normal defaults.
- Boolean, integer, decimal, JSON, font-family, and RGBA colour values use type-aware controls. Colour controls use the application's alpha-capable swatch picker.
- **Import SST / JSON Into Selected Profile** merges a main-application SST or `settings_v2.json` snapshot into the selected Normal or MC model before save.
- Imports strip Steam and generic credential fields, preserve reset-owned source/weather values, reject machine-local absolute path values, and exclude `widgets.custom_layout` plus `widgets.layout_slots` as active profile/machine-local state. Import never changes the current user profile and does not write defaults until Save and Regenerate is pressed.
- Every text leaf tooltip identifies registered finite values or describes the accepted free-text domain; font leaves continue to use the installed-font chooser.
- Save and single-level undo are transactional across the canonical base, MC overlay, and regenerated JSON/SST artifacts. Undo state lives under `%LOCALAPPDATA%/SRPSS/DefaultSettingsEditor`, outside the repository.
- Default SST regeneration does not construct `SettingsManager` at all. It builds each profile directly from the canonical defaults API, validates full snapshot equality and private-field absence, writes atomically, and emits deterministic metadata. The Foundry must never inspect, migrate, reset, validate, or rewrite installed `%APPDATA%/SRPSS*` `settings_v2.json` files; existing installation settings remain valid and untouched when defaults change.
- Run `python tools/regenerate_defaults_snapshot_artifacts.py` and `python tools/regenerate_sst_defaults.py` after an intentional source change. Two unchanged SST runs must be byte-identical; `tests/test_regenerate_sst_defaults.py` and `tests/test_settings_defaults_parity.py` enforce profile parity, the canonical MC differential, deterministic metadata, no preserve-only Weather coordinates, and no credential/private fields.
- Retired `preset` and `custom_preset_backup` payloads remain hidden compatibility data and preserve their values when the Foundry rewrites editable defaults.

## 7. Visualizer Defaults
Visualizer default changes also need:
- mode-registry and `_spotify_visualizer.py` grouped field-spec review,
- curated preset expectations reviewed where authored payloads rely on old values,
- visualizer preset repair/import/export coverage when schema shape changes,
- and runtime-shaped validation when the change affects visible mode behavior.

## 8. CUSTOM And Widget Defaults
- Authored defaults remain the fallback even when a widget uses `Custom`.
- Committed CUSTOM geometry overlays authored defaults; it is not a replacement defaults surface.
- Canonical `widgets.layout_slots` starts empty. Saved slots belong to an installation profile and must not be promoted into defaults or checked-in snapshots.
- If a settings control becomes derived or locked under `Custom`, lock it in UI rather than inventing a hidden alternate default.
