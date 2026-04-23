# Visualizer Change Checklist

Last updated: 2026-04-23

Use this checklist whenever a visualizer setting is introduced, removed, renamed, split, or significantly retuned.

## 1. UI and Builder Surface
- Update mode builder UI (`ui/tabs/media/*_builder.py`).
- Update labels/tooltips/visibility rules.
- Ensure user-facing mode naming matches mode registry labels.

## 2. Settings Binding
- Update mode load/collect bindings (`*_settings_binding.py`).
- Ensure load/save symmetry.

## 3. Defaults and Model
- Update `core/settings/default_settings.py`.
- Update model serialization paths in `core/settings/models.py`:
  - `from_settings`
  - `from_mapping`
  - `to_dict`

## 4. Normalization and Contracts
- Update any impacted contracts:
  - `visualizer_settings_snapshot.py`
  - `visualizer_settings_contract.py`
  - `visualizer_preset_indices.py` (if preset index behavior changes)

## 5. Runtime Bridge
- Update runtime kwargs and application paths:
  - `widgets/spotify_visualizer/config_applier.py`
  - `widgets/spotify_visualizer_widget.py`
  - `widgets/spotify_bars_gl_overlay.py`
  - relevant renderer module

## 6. Presets and Tooling
- Update curated preset payloads if required.
- Update `core/settings/visualizer_presets.py` for loading/apply behavior changes.
- Update repair/audit/reindex logic in `tools/visualizer_preset_repair.py` when schema contracts change.

## 7. Tests
Add/update coverage for:
- settings/model round-trip,
- normalization behavior,
- runtime bridge transport,
- preset repair/reindex contract,
- compatibility with future/unknown-style mode key prefixes.

## 8. Docs
Refresh related docs in the same change:
- `Spec.md`
- `Index.md`
- `Docs/Visualizer_Reference.md`
- `Docs/TestSuite.md` (when coverage changes)
- `Current_Plan.md` and `Docs/Historical_Bugs.md` when relevant.

## 9. Closure Rule
- For visual/timing-sensitive behavior changes, require runtime verification in addition to passing tests.
