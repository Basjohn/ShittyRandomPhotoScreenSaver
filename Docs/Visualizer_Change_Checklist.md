# Visualizer Change Checklist

Last updated: 2026-07-16

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
- Accepted-frame packet ownership belongs in `widgets/spotify_visualizer/frame_transport.py` and `tick_pipeline.py`; display routing belongs in `rendering/display_image_ops.py`; final state copy/clamp/render ownership belongs in context-agnostic `SpotifyVisualizerGLRenderer` within `widgets/spotify_bars_gl_overlay.py`.
- Reused frame packets and mode-local extras are synchronous scratch storage. Run generation/activation/required-waveform and hidden-primer checks before filling/pushing them, clear extras before reuse, and never queue or retain a mutable packet.
- Renderer math belongs in the mode renderer/shader files.
- Visualizer ticks stay owned by the dedicated recurring timer, not transition animation callbacks.

## 5. Surface And Compositor Ownership
- Normal rendering belongs to `rendering/gl_compositor_pkg/spotify_visualizer_layer.py` inside the display-owned `GLCompositorWidget`; do not add another realized GL surface, timer, packet queue, readback loop, or repaint rescue.
- Keep front/back FBO storage display-context-local and keyed by logical size plus DPR. Position-only geometry changes must reuse buffers; replacement must be transactional so a failed allocation preserves the prior complete pair and a successful replacement retains the old front until the first new-size generation publishes.
- Render a new visualizer FBO generation only after a new accepted renderer state. Higher-frequency compositor paints should reuse the front texture.
- Compositor startup prewarms every supported visualizer mode plus the required stencil mask while hidden. Do not compile a missing compositor mode program from visible paint.
- Required rounded-card stencil failure must suppress the current frame or retain last-good pixels; never display unclipped or simplified content.
- The legacy `SpotifyBarsGLOverlay` adapter is allowed only for explicit rollback, a deliberately non-OpenGL backend, or a classified hard compositor-layer failure before first reveal. Transient readiness, shared renderer/shader failure, unexpected normal-path setup failure, and post-reveal failures must not create or switch to legacy.
- A runtime failure retains last-good compositor pixels when available and retries through bounded no-timer preparation on ordinary compositor work. It must not blank then switch surfaces.
- Dimming, card/visualizer, and PERF HUD order belongs to one post-image compositor scene session.
- ResourceManager ownership must include every texture, framebuffer, stencil renderbuffer, program, VAO, and VBO exactly once, with invalid-context abandonment instead of unsafe deletion.

## 6. Geometry And CUSTOM
- Outer visualizer card policy belongs in `widgets/spotify_visualizer/card_geometry.py`.
- Painted-card stencil math belongs in `overlay_mask.py` / `overlay_frame_shell.py`.
- Committed CUSTOM geometry is replayed through shared runtime/CUSTOM layout ownership, not re-derived from live mode/preset height policy.
- Normal-path edit capture uses the compositor layer's explicit card-plus-front-FBO snapshot. It must not grab the whole display or add recurring readback; legacy framebuffer capture remains rollback compatibility only.
- If card size, placement, border, or stencil behavior changes, keep `tests/test_stencil_mask_alignment.py` and relevant first-frame/reset tests in scope.

## 7. Tests
Add or update focused coverage for:
- settings/model round trip,
- `from_mapping()` vs `from_settings()` parity for changed families,
- normalization and migration,
- runtime kwargs/application,
- preset parse/apply/import/export behavior,
- mode switch/preset switch reset isolation,
- first-frame/fresh-frame authority when touched,
- packet reuse without stale mode/source keys or delayed retention,
- paused latency suppression without masking a live playing probe,
- compositor-vs-legacy renderer-target selection and strict fallback authorization,
- terminal normal-path renderer setup suppressing short startup retries without creating legacy,
- all-mode hidden prewarm plus no visible-path shader compile,
- required stencil refusal, FBO size/DPR isolation, generation reuse, transactional allocation, last-good retention, and no lower-fidelity substitute,
- explicit CUSTOM compositor snapshot and exactly-once framebuffer/renderbuffer cleanup,
- passive renderer paint-gap/accepted-update/FBO telemetry without new repaint, timer, packet, GL-query, or allocation pressure when that seam changes,
- and authored curated preset runtime oracles when the visible mode behavior changes.

Before touching shared visualizer/audio/activation/render/transition paths, run the focused visualizer reactivity lock from `Docs/Harness_Index.md`; rerun it after the change.

## 8. Docs And Closure
- Refresh `Spec.md`, `Index.md`, `Docs/Visualizer_Reference.md`, and `Docs/TestSuite.md` when contracts or validation inventory change.
- Keep `Docs/Compositor_Architecture.md` and the single-surface harness in `Docs/Harness_Index.md` aligned whenever renderer hosting, FBOs, fallback, startup, or instrumentation changes.
- Update `Docs/Historical_Bugs.md` or `Docs/Regression_Notes.md` only for real regression lessons.
- Visual/timing-sensitive work is not closed by tests alone; state the remaining runtime validation clearly.
