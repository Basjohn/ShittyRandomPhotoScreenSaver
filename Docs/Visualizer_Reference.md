# Visualizer Reference

Last updated: 2026-07-15

Focused architecture reference for the Spotify visualizer subsystem.

## 1. Mode Identity

Source of truth: `core/settings/visualizer_mode_registry.py`.

| Internal ID | User Label | Status |
|---|---|---|
| `spectrum` | Spectrum | active |
| `oscilloscope` | Oscilloscope | active |
| `sine_wave` | Sine Waves | active |
| `bubble` | Bubble | active |
| `devcurve` | Spline Curve | active |

`devcurve` remains the internal id for Spline Curve. `--devcurve` remains accepted as a compatibility no-op.

## 2. Retired Modes

Blob was removed end to end on 2026-07-15 and is not selectable, gated, rendered, preset-owning, or packaged.

- `core/settings/visualizer_retired_modes.py` is the only active Blob-related production seam.
- A saved/imported `mode: blob` resolves to the registry-owned default.
- Every `blob_*` and `preset_blob` leaf is stripped before model normalization and never re-emitted.
- Historical subtype names and controls are migration evidence only, not active settings or runtime contracts.
- `tests/test_visualizer_retired_modes.py` protects selection fallback, plain/dotted stripping, sibling-preserving schema migration, and canonical-default absence.

## 3. Settings And Activation

- Settings-model source of truth: `core/settings/models/_spotify_visualizer.py`.
- Mapping normalization: `core/settings/visualizer_settings_snapshot.py`.
- Legacy/technical normalization: `core/settings/visualizer_settings_contract.py`.
- Retired-mode migration: `core/settings/visualizer_retired_modes.py`.
- Preset index fallback/lookup: `core/settings/visualizer_preset_indices.py`.
- Runtime activation payload: `core/settings/visualizer_presets.resolve_visualizer_activation_payload()`.

Runtime and saved settings use mode-owned keys. Legacy global visualizer keys may be accepted as import/migration inputs, but normalized payloads must not re-emit them. `SettingsManager.set_spotify_visualizer_settings()` persists one normalized visualizer section through an atomic `widgets`-root write while preserving sibling widgets.

## 4. Presets

- Active curated tree: `core/settings/visualizer_presets.get_visualizer_presets_dir()`.
- Packaged/bundled tree: `get_packaged_visualizer_presets_dir()`.
- Manifest helpers: `core/visualizer_preset_manifest.py`.
- Import/export helpers: `core/settings/visualizer_preset_transfer.py`.
- Repair/audit/reindex tool: `tools/visualizer_preset_repair.py`.

Curated presets are supported-mode folders containing JSON payloads. Folder/zip imports replace the curated tree; loose JSON imports are parsed, canonicalized, and written into the inferred mode/slot.

## 5. Runtime Pipeline

- `widgets/spotify_visualizer_widget.py`: coordinator and lifecycle.
- `widgets/spotify_visualizer/activation_runtime.py`: activation replay.
- `widgets/spotify_visualizer/config_applier.py`: settings/model to runtime kwargs.
- `widgets/spotify_visualizer/technical_config.py`: per-mode technical cache/application.
- `widgets/spotify_visualizer/runtime_config.py`: engine/thread/process/audio-block coordination.
- `widgets/spotify_bars_gl_overlay.py` plus overlay helpers: GL state transport and render envelope.
- `widgets/spotify_visualizer/overlay_state.py`: mode reset and activation/generation handoff.
- Mode renderers/shaders: mode-owned math and uniforms.

Visualizer tick cadence has one steady-state owner: the dedicated recurring timer. Shared audio extraction, timer cadence, compositor ownership, and accepted mode tuning must not change as a side effect of retired-mode cleanup.

## 6. CUSTOM Geometry

- Outside `Custom`, visualizer display routing follows Media.
- In `Custom`, the visualizer may own its own display/monitor route while visibility still follows Media availability.
- `Custom + ALL` is not a valid steady-state routing result.
- Outer-card geometry policy lives in `widgets/spotify_visualizer/card_geometry.py`.
- Committed CUSTOM rect replay lives in shared CUSTOM/runtime ownership and must not be recalculated from mode/preset height policy.
- Stencil clipping lives in `overlay_mask.py` / `overlay_frame_shell.py` and stays separate from outer-card placement.

## 7. Diagnostics And Validation

- Use `--viz` for ordinary visualizer diagnostics.
- `--viz-diagnostics` and `--viz-diag` remain compatibility aliases.
- Use `--geo` for CUSTOM route/geometry questions.
- Use `--perf` when visualizer work may affect frame or tick cadence.
- Before and after shared visualizer/runtime changes, run the focused supported-mode reactivity lock from `Docs/Harness_Index.md`.
- `[SPOTIFY_VIS][FIRST_FRAME_PRIMER]` means an unready activation frame was blanked/primed; investigate repetition or subsequent first-frame bleed rather than accepting stale authority.

## 8. Common Drift Risks

- settings/model/default omissions,
- preset parser/import/export divergence,
- runtime kwargs accepted but not applied,
- overlay state stored but not rendered,
- mode-owned caches surviving activation boundaries,
- retired mode ids or owned keys reappearing in defaults, presets, UI, runtime, or packages,
- CUSTOM committed rects being overwritten by widget-local sizing,
- and generic helper tests passing while authored curated preset behavior regresses.
