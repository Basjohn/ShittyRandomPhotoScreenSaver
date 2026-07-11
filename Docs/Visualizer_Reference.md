# Visualizer Reference

Last updated: 2026-07-11

Focused architecture reference for the Spotify visualizer subsystem.

## 1. Mode Identity
Source of truth: `core/settings/visualizer_mode_registry.py`.

| Internal ID | User Label | Status |
|---|---|---|
| `spectrum` | Spectrum | active |
| `oscilloscope` | Oscilloscope | active |
| `sine_wave` | Sine Waves | active |
| `bubble` | Bubble | active |
| `blob` | Blob | dev-gated (`-devblob`) |
| `devcurve` | Spline Curve | active |

`devcurve` remains the internal id for Spline Curve. `--devcurve` remains accepted as a compatibility no-op.

## 2. Blob Subtypes

Blob keeps the stable internal mode id `blob` and remains dev-gated by `-devblob`. Its presets and Custom state choose one explicit subtype:

| Persisted value | User label | Creative authority |
|---|---|---|
| `mighty` | Mighty Blob | Procedural organic contour, living wobble, music-reactive wobble/tendrils, and bounded inward give |
| `shaped` | Shaped Blob | Authored base/reaction/energy-node contour, local living/music mutation, and filled/ring topology |

- `core/settings/visualizer_blob_contract.py` owns subtype values, normalization, and inactive-payload stripping. The default is `mighty`.
- `normal`, `unshaped`, and `blob_shaper_enabled` are forward-migration inputs only. Canonical defaults, snapshots, presets, model serialization, and GPU payloads emit `blob_type` only.
- Canonical Blob snapshots/presets carry shared Body, Appearance, Layout, Glow, Ghost, and inward-liquid settings plus only the selected subtype's creative fields. Mighty drops Shaped contour data; Shaped drops Mighty procedural-contour data.
- The Settings UI is split across `blob_builder.py` (shared buckets and Blob Type selector), `blob_mighty_builder.py`, and `blob_shaped_builder.py`. Inactive subtype controls are hidden and disabled.
- Runtime dispatch selects `blob_mighty` or `blob_shaped`, with subtype owners in `renderers/blob_mighty.py` and `renderers/blob_shaped.py`. `renderers/blob_common.py` carries neutral paint/energy/glow/inward-liquid state.
- `blob_mighty.frag` and `blob_shaped.frag` are distinct compiled programs that include the shared `blob.frag` body with a fixed variant. The runtime no longer selects subtype behavior through `u_blob_shaper_enabled`.
- Mighty must remain smoothly non-circular at rest, add outward-biased music tendrils without destabilizing body mean, and clamp inward motion away from raw-circle/deep-pinch failure shapes.
- Shaped must preserve the authored goal contour, accept bounded local living/music deviations, and release smoothly back toward the goal instead of snapping or drifting into Mighty behavior.
- Both paths keep the body fill visibly audio-reactive through shared live/stage/transient paint drive. This is separate from the optional inward-liquid appearance effect.
- A subtype switch resets both solver/profile families, targets, velocities, timestamps, ghost/peak silhouette, and pocket state before the new frame is accepted. `[SPOTIFY_VIS][BLOB][TYPE_RESET]` is the expected diagnostic at a real boundary.

## 3. Settings And Activation

- Settings-model source of truth: `core/settings/models/_spotify_visualizer.py`.
- Mapping normalization: `core/settings/visualizer_settings_snapshot.py`.
- Legacy/technical normalization: `core/settings/visualizer_settings_contract.py`.
- Blob subtype normalization: `core/settings/visualizer_blob_contract.py`.
- Preset index fallback/lookup: `core/settings/visualizer_preset_indices.py`.
- Runtime activation payload: `core/settings/visualizer_presets.resolve_visualizer_activation_payload()`.

Runtime and saved settings use mode-owned keys. Legacy global visualizer keys may be accepted as import/migration inputs, but normalized payloads should not re-emit them.

## 4. Presets

- Active curated tree: `core/settings/visualizer_presets.get_visualizer_presets_dir()`.
- Packaged/bundled tree: `get_packaged_visualizer_presets_dir()`.
- Manifest helpers: `core/visualizer_preset_manifest.py`.
- Import/export helpers: `core/settings/visualizer_preset_transfer.py`.
- Repair/audit/reindex tool: `tools/visualizer_preset_repair.py`.

Curated presets are mode folders containing JSON payloads. Folder/zip imports replace the curated tree; loose JSON imports are parsed, canonicalized, and written into the inferred mode/slot.

## 5. Runtime Pipeline

- `widgets/spotify_visualizer_widget.py`: coordinator/lifecycle.
- `widgets/spotify_visualizer/activation_runtime.py`: activation replay.
- `widgets/spotify_visualizer/config_applier.py`: settings/model to runtime kwargs.
- `widgets/spotify_visualizer/technical_config.py`: per-mode technical cache/application.
- `widgets/spotify_visualizer/runtime_config.py`: engine/thread/process/audio-block coordination.
- `widgets/spotify_bars_gl_overlay.py` plus overlay helpers: GL state transport and render envelope.
- Mode renderers/shaders: renderer-owned math and uniforms.
- `widgets/spotify_visualizer/overlay_state.py`: mode and Blob-subtype reset ownership.

Visualizer tick cadence has one steady-state owner: the dedicated recurring timer.

## 6. CUSTOM Geometry

- Outside `Custom`, visualizer display routing follows Media.
- In `Custom`, the visualizer may own its own display/monitor route while visibility still follows Media availability.
- `Custom + ALL` is not a valid steady-state routing result.
- Outer-card geometry policy lives in `widgets/spotify_visualizer/card_geometry.py`.
- Committed CUSTOM rect replay lives in shared CUSTOM/runtime ownership and must not be recalculated from mode/preset height policy.
- Stencil clipping lives in `overlay_mask.py` / `overlay_frame_shell.py` and should stay separate from outer-card placement.

## 7. Diagnostics And Validation

- Use `--viz` for ordinary visualizer diagnostics.
- `--viz-diagnostics` and `--viz-diag` remain compatibility aliases.
- Use `--geo` for CUSTOM route/geometry questions.
- Use `--perf` when visualizer work may affect frame or tick cadence.
- For shared visualizer/runtime changes, run the focused visualizer reactivity lock from `Docs/Harness_Index.md`.
- For Blob subtype/settings/renderer/shader changes, run the Blob Mighty / Shaped architecture lock from `Docs/Harness_Index.md`, then validate both paths live under `-devblob`.

## 8. Common Drift Risks

- settings/model/default omissions,
- preset parser/import/export divergence,
- runtime kwargs accepted but not applied,
- overlay state stored but not rendered,
- mode-owned caches surviving activation boundaries,
- Blob aliases/legacy booleans or inactive subtype fields surviving canonicalization,
- Blob type changes reusing the other subtype's profile/ghost/pocket state,
- shader dispatch compiling one Blob program but uploading the other subtype's uniforms,
- CUSTOM committed rects being overwritten by widget-local sizing,
- and generic helper tests passing while authored curated preset behavior regresses.
