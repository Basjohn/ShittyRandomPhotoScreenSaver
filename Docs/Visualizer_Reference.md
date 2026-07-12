# Visualizer Reference

Last updated: 2026-07-12

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

### 2.1 Persistence And Settings Ownership

- `core/settings/visualizer_blob_contract.py` owns subtype values, normalization, and inactive-payload stripping. The default is `mighty`.
- `normal`, `unshaped`, and `blob_shaper_enabled` are forward-migration inputs only. Canonical defaults, snapshots, presets, model serialization, and GPU payloads emit `blob_type` only.
- Canonical Blob snapshots/presets carry shared Body, Appearance, Layout, Glow, Ghost, and inward-liquid settings plus only the selected subtype's creative fields. Mighty drops Shaped contour data; Shaped drops Mighty procedural-contour data.
- `SettingsManager.set_spotify_visualizer_settings()` persists the complete typed visualizer section through one normalized `widgets`-root transaction. Do not write `blob_type` and subtype fields as separate dotted operations: an intermediate old-subtype normalization can otherwise discard the incoming fields.
- Default/startup merges treat an absent inactive subtype family as intentional. They must not restore stripped fields from defaults and create a repair/rewrite loop.
- The Settings UI is split across `blob_builder.py` (shared buckets and Blob Type selector), `blob_mighty_builder.py`, and `blob_shaped_builder.py`. Inactive subtype controls are hidden and disabled.

### 2.2 Runtime Contour Authority

- Runtime dispatch selects `blob_mighty` or `blob_shaped`, with subtype owners in `renderers/blob_mighty.py` and `renderers/blob_shaped.py`. `renderers/blob_common.py` carries neutral paint/energy/glow/inward-liquid state.
- `blob_mighty.frag` and `blob_shaped.frag` are distinct compiled programs that include the shared `blob.frag` body with a fixed variant. The runtime no longer selects subtype behavior through `u_blob_shaper_enabled`.
- Both subtypes CPU-solve a final 128-sample contour and upload only `u_blob_runtime_profile` as contour shape authority. The shader samples that profile directly for its fixed-variant SDF; it does not rebuild a second motion stack from subtype control scalars.
- Mighty is contour-first: stable angular sites own broad living deformation, vocal outline wobble, event-pocket pressure, and rounded tendrils that grow and release rather than orbit. Scalar stage growth remains secondary; the solved profile must stay smoothly non-circular, preserve body mean, avoid raw-circle/deep-pinch collapse, and reach the SDF without shader-side amplification or hard clipping into radial fans.
- Shaped preserves authored base/reaction/energy-node identity and filled/ring topology while remaining alive beyond the authored goal. Its idle warp, standing vocal wobble, rounded light tendrils, and music/transient mutations own bounded but materially visible deviation, followed by clean release instead of a static goal lock or Mighty-style behavior.
- Both paths keep the body fill visibly audio-reactive through shared live/stage/transient paint drive. This is separate from the optional inward-liquid appearance effect.

### 2.3 Transients, Startup, And Boundaries

- Blob deformation consumes existing transient state only inside Blob-owned code. Mighty uses typed event pockets; Shaped routes authored `transient` energy nodes from the Blob transient envelope, never from continuous `overall` energy. This transport must not change shared transient extraction or any other visualizer mode.
- `rendering/display_image_ops.prewarm_spotify_visualizer_overlay()` seeds both the resolved startup mode and canonical `blob_type` before the first GL program compile. A Shaped cold start must not prewarm Mighty from a stale/default overlay subtype.
- A subtype switch resets both solver/profile families, targets, velocities, timestamps, ghost/peak silhouette, and pocket state before the new frame is accepted. `[SPOTIFY_VIS][BLOB][TYPE_RESET]` is the expected diagnostic at a real boundary.

## 3. Settings And Activation

- Settings-model source of truth: `core/settings/models/_spotify_visualizer.py`.
- Mapping normalization: `core/settings/visualizer_settings_snapshot.py`.
- Legacy/technical normalization: `core/settings/visualizer_settings_contract.py`.
- Blob subtype normalization: `core/settings/visualizer_blob_contract.py`.
- Preset index fallback/lookup: `core/settings/visualizer_preset_indices.py`.
- Runtime activation payload: `core/settings/visualizer_presets.resolve_visualizer_activation_payload()`.

Runtime and saved settings use mode-owned keys. Legacy global visualizer keys may be accepted as import/migration inputs, but normalized payloads should not re-emit them.

Blob subtype changes are section-level persistence operations: build the selected subtype's complete canonical section, strip the inactive family, then commit it atomically while preserving sibling widgets. Per-key ordering is not a valid subtype transition mechanism.

## 4. Presets

- Active curated tree: `core/settings/visualizer_presets.get_visualizer_presets_dir()`.
- Packaged/bundled tree: `get_packaged_visualizer_presets_dir()`.
- Manifest helpers: `core/visualizer_preset_manifest.py`.
- Import/export helpers: `core/settings/visualizer_preset_transfer.py`.
- Repair/audit/reindex tool: `tools/visualizer_preset_repair.py`.

Curated presets are mode folders containing JSON payloads. Folder/zip imports replace the curated tree; loose JSON imports are parsed, canonicalized, and written into the inferred mode/slot.

The dev-gated Blob set may include temporary showcase presets used to exercise Mighty and Shaped reactivity. Their presence, names, count, ordering, and creative values are evaluation material rather than a stable compatibility contract.

## 5. Runtime Pipeline

- `widgets/spotify_visualizer_widget.py`: coordinator/lifecycle.
- `widgets/spotify_visualizer/activation_runtime.py`: activation replay.
- `widgets/spotify_visualizer/config_applier.py`: settings/model to runtime kwargs.
- `widgets/spotify_visualizer/technical_config.py`: per-mode technical cache/application.
- `widgets/spotify_visualizer/runtime_config.py`: engine/thread/process/audio-block coordination.
- `widgets/spotify_bars_gl_overlay.py` plus overlay helpers: GL state transport and render envelope.
- Mode renderers/shaders: renderer-owned math and uniforms.
- `widgets/spotify_visualizer/overlay_state.py`: mode and Blob-subtype reset ownership.
- `widgets/spotify_visualizer/blob_math.py` and `blob_pockets.py`: Mighty contour, anchored event growth/release, and containment ownership.
- `widgets/spotify_visualizer/renderers/blob_unshaped_runtime.py`: Mighty 128-sample solver state and profile handoff.
- `widgets/spotify_visualizer/renderers/blob_shaper_runtime.py`: Shaped authored routing, independent mutation envelope, true transient-node routing, and release solver.
- `widgets/spotify_visualizer/renderers/blob_common.py`, `blob_mighty.py`, and `blob_shaped.py`: neutral paint transport, subtype profile upload, and Blob profile diagnostics.

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
- `[SPOTIFY_VIS][BLOB][PROFILE_TRANSPORT]` records the selected subtype, uniform location, and 128-sample upload contract when transport identity changes.
- Low-rate `[SPOTIFY_VIS][BLOB_PROFILE]` records live bands, transient peak, subtype controls, contour and target spread, solver transfer, temporal RMS/max/mean deltas, and estimated pixel motion. It is the primary evidence for distinguishing healthy audio from contour attenuation or static-goal behavior.
- `[SPOTIFY_VIS][BLOB][TYPE_RESET]` should appear only at real subtype boundaries. `[SPOTIFY_VIS][FIRST_FRAME_PRIMER]` means an unready activation frame was blanked/primed; investigate repeated occurrences or any subsequent first-frame bleed rather than accepting it as normal contour output.

## 8. Common Drift Risks

- settings/model/default omissions,
- preset parser/import/export divergence,
- runtime kwargs accepted but not applied,
- overlay state stored but not rendered,
- mode-owned caches surviving activation boundaries,
- Blob aliases/legacy booleans or inactive subtype fields surviving canonicalization,
- typed subtype saves occurring as ordered per-key writes or default merges reintroducing the inactive family,
- Blob type changes reusing the other subtype's profile/ghost/pocket state,
- Blob startup prewarming a concrete program before the resolved subtype is seeded,
- a profile upload using any sample count other than the matching CPU/shader 128-sample contract,
- Mighty motion rotating around fixed amplitude instead of anchored grow/release, or shader math re-amplifying its solved contour,
- Shaped reaching its authored goal but losing independent idle/vocal/music/transient mutation beyond that goal,
- continuous overall energy activating Shaped transient nodes or Blob changes leaking into shared transient extraction,
- shader dispatch compiling one Blob program but uploading the other subtype's uniforms,
- CUSTOM committed rects being overwritten by widget-local sizing,
- and generic helper tests passing while authored curated preset behavior regresses.
