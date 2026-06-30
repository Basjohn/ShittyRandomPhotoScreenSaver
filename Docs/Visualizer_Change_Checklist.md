# Visualizer Change Checklist

Last updated: 2026-06-30

Use this checklist whenever visualizer settings, presets, activation, runtime transport, renderer behavior, or card geometry changes.

## 1. Identity And UI
- Mode ids, labels, prefixes, and gates come from `core/settings/visualizer_mode_registry.py`.
- User-facing controls live in `ui/tabs/widgets_tab.py` and `ui/tabs/media/*_settings_binding.py`.
- Keep mode-specific UI changes mode-owned unless a shared visualizer contract truly changes.
- Do not build dev-gated mode UI when the mode is not available in the registry.

## 2. Defaults, Model, And Persistence
- Add user-facing defaults in `core/settings/default_settings.py`.
- Keep generated defaults snapshot artifacts derived, not hand-authored.
- Update `core/settings/models/_spotify_visualizer.py` grouped defaults/build/serialize specs together so `from_settings()`, `from_mapping()`, and `to_dict()` stay one contract.
- Update `visualizer_settings_snapshot.py`, `visualizer_settings_contract.py`, and `visualizer_preset_indices.py` when normalization or preset-index behavior changes.
- Root `widgets` writes, SST imports, and visualizer imports must converge on the same normalized visualizer schema.

## 3. Presets And Import/Export
- Curated preset loading/apply behavior belongs in `core/settings/visualizer_presets.py`.
- Curated tree import/export belongs in `core/settings/visualizer_preset_transfer.py`.
- Manifest ownership belongs in `core/visualizer_preset_manifest.py`.
- Preset repair/audit/reindex behavior belongs in `tools/visualizer_preset_repair.py`.
- Reindex logic may normalize slot numbering and filenames; it must not rewrite authored creative intent.

## 4. Runtime Bridge
- Activation must use `resolve_visualizer_activation_payload()`.
- Runtime config application belongs in `widgets/spotify_visualizer/config_applier.py`, `activation_runtime.py`, `technical_config.py`, and `runtime_config.py`.
- Overlay transport belongs in `widgets/spotify_bars_gl_overlay.py` and the extracted overlay helpers.
- Renderer math belongs in the mode renderer/shader files.
- Visualizer ticks stay owned by the dedicated recurring timer, not transition animation callbacks.

## 5. Geometry And CUSTOM
- Outer visualizer card policy belongs in `widgets/spotify_visualizer/card_geometry.py`.
- Painted-card stencil math belongs in `overlay_mask.py` / `overlay_frame_shell.py`.
- Committed CUSTOM geometry is replayed through shared runtime/CUSTOM layout ownership, not re-derived from live mode/preset height policy.
- If card size, placement, border, or stencil behavior changes, keep `tests/test_stencil_mask_alignment.py` and relevant first-frame/reset tests in scope.

## 6. Tests
Add or update focused coverage for:
- settings/model round trip,
- `from_mapping()` vs `from_settings()` parity for changed families,
- normalization and migration,
- runtime kwargs/application,
- preset parse/apply/import/export behavior,
- mode switch/preset switch reset isolation,
- first-frame/fresh-frame authority when touched,
- and authored curated preset runtime oracles when the visible mode behavior changes.

Before touching shared visualizer/audio/activation/render/transition paths, run the focused visualizer reactivity lock from `Docs/Harness_Index.md`; rerun it after the change.

## 7. Docs And Closure
- Refresh `Spec.md`, `Index.md`, `Docs/Visualizer_Reference.md`, and `Docs/TestSuite.md` when contracts or validation inventory change.
- Update `Docs/Historical_Bugs.md` or `Docs/Regression_Notes.md` only for real regression lessons.
- Visual/timing-sensitive work is not closed by tests alone; state the remaining runtime validation clearly.
