# Visualizer Change Checklist

Last updated: 2026-05-14

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
- Update the relevant serialization paths under `core/settings/models/`:
  - mode/widget-owned model classes,
  - `from_settings`,
  - `from_mapping`,
  - `to_dict`.
- If the change touches `core/settings/models/_spotify_visualizer.py`, update the grouped field-spec/default/build/serialize maps together and preserve ordered grouped section merges. Do not add a new handwritten one-off family if an existing grouped seam can own it.

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
- If the change touches visualizer card height or card geometry ownership, explicitly assess:
  - `widgets/spotify_visualizer/card_geometry.py`
  - `widgets/spotify_visualizer/card_height.py`
  - `widgets/spotify_visualizer/mode_transition.py`
  - `rendering/widget_manager.py`
  - `widgets/spotify_visualizer/overlay_mask.py`
  - `widgets/spotify_visualizer/overlay_frame_shell.py`
  and confirm the outer-card geometry decision does not break stencil inset math, painted-card border alignment, perceived mode scale, or future custom layout/resize extensibility.

## 6. Presets and Tooling
- Update curated preset payloads if required.
- Update `core/settings/visualizer_presets.py` for loading/apply behavior changes.
- Update repair/audit/reindex logic in `tools/visualizer_preset_repair.py` when schema contracts change.

## 7. Tests
Add/update coverage for:
- settings/model round-trip,
- active-mode parity between `from_mapping()` and `from_settings()` for the changed family when applicable,
- normalization behavior,
- runtime bridge transport,
- preset repair/reindex contract,
- compatibility with future/unknown-style mode key prefixes.
- If card height, card shell, or visualizer geometry changes are involved, keep `tests/test_stencil_mask_alignment.py` green and re-run the relevant visualizer runtime reset/first-frame subsets before sign-off.

## 8. Docs
Refresh related docs in the same change:
- `Spec.md`
- `Index.md`
- `Docs/Visualizer_Reference.md`
- `Docs/TestSuite.md` (when coverage changes)
- `Current_Plan.md` and `Docs/Historical_Bugs.md` when relevant.

## 9. Closure Rule
- For visual/timing-sensitive behavior changes, require runtime verification in addition to passing tests.
- If the change can affect first-bar / first-frame authority or preset/settings drift, explicitly keep the R-22 family closure checks in view:
  - run the targeted `tests/test_spotify_visualizer_widget.py` first-frame / stale-reset subset,
  - keep `tests/test_spotify_visualizer_mode_transition.py` and `tests/test_ghost_isolation.py -k "TestOverlayModeResetIsolation"` green,
  - sweep logs for `FIRST_FRAME_GUARD`, `before_first_overlay_push`, `after_first_overlay_push`, `MODE_RESET_ASSERT`, and `No technical config available`.

## 10. New Dev-Gated Mode Checklist
When introducing or changing a dev-gated visualizer mode, update all of these seams together:
- `core/dev_gates.py`
  Add the gate flag, import-time argv parsing, and `force_gate(...)` plumbing for tests.
- `main.py`
  Register the CLI compatibility flag or real gate flag so startup parsing stays aligned.
- `core/settings/visualizer_mode_registry.py`
  Add the mode descriptor, label, key prefix, and gate ownership so settings/UI/runtime all agree on the identity.
- Runtime renderer path
  Wire the mode into the relevant runtime seams such as `widgets/spotify_visualizer_widget.py`, `widgets/spotify_bars_gl_overlay.py`, `widgets/spotify_visualizer/config_applier.py`, and any mode-specific renderer or shader loader.
- Tests and docs
  Update `Docs/TestSuite.md`, add/expand coverage for registry/plumbing/runtime contracts, and refresh `Spec.md` / `Index.md` if the mode becomes part of the canonical product surface.
