# R-14 — 2026-04-17 — Blob Inward-Liquid Runtime Handoff Broke GL Overlay Push (Resolved In Code, Visual Validation Pending)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [x] AWAITING VALIDATION
- [ ] SOLVED

**Symptoms**
- Blob could appear to fall back or fail to react correctly right after the inward-liquid settings landed.
- Runtime logs showed repeated overlay push failures during normal visualizer updates instead of a clean Blob frame handoff.
- The noisy symptom was easy to misread as a mode/render fallback, but the logs pointed at a state-transport exception instead.

**What the logs actually showed**
- `SpotifyBarsGLOverlay.set_state()` raised:
  - `unexpected keyword argument 'blob_inward_liquid_color'`
  - then on the retry path `unexpected keyword argument 'blob_inward_liquid_enabled'`
- This happened inside the runtime overlay push path in `rendering/display_image_ops.py`, so the new Blob extras were reaching the handoff boundary but the overlay contract was out of sync.

**Root Cause**
1. The inward-liquid settings had already been added to settings/defaults/model/config/widget/GPU-extra plumbing.
2. `build_gpu_push_extra_kwargs()` correctly included the new `blob_inward_liquid_*` payload.
3. `SpotifyBarsGLOverlay.set_state()` had not been updated to accept/store those kwargs, so the overlay push failed at runtime.
4. The Blob shader already declared the inward-liquid uniforms, but the GL overlay uniform-location table and Blob uniform uploader also needed to be taught about the new fields to complete the handoff intentionally.

**Fixes**
- Updated `SpotifyBarsGLOverlay.set_state()` to accept and store:
  - `blob_inward_liquid_color`
  - `blob_inward_liquid_enabled`
  - `blob_inward_liquid_reactivity`
  - `blob_inward_liquid_max_size`
- Added the matching inward-liquid uniform names to the overlay GL lookup table in `widgets/spotify_bars_gl_overlay.py`.
- Added Blob renderer uniform upload support in `widgets/spotify_visualizer/renderers/blob.py` so the shader receives the new values deliberately rather than by accident or omission.
- Added a focused regression in `tests/test_visualizer_overlay_kwargs.py` so future Blob GPU extras and Blob uniform declarations stay aligned with the overlay/frame-push contract.
- While validating this, two stale tests were corrected to reflect the current Blob/Bubble guardrail: their continuous body signal intentionally stays on the cooler standard energy snapshot, not the hotter pre-AGC snapshot.

**Status**
- Fixed in code and covered by focused regressions.
- Live visual confirmation is still required because the issue was a runtime/visual handoff seam, not just a serialization seam.

**Takeaways**
- A new visualizer field is not "done" when it exists in settings and widget state; it must also survive the explicit overlay/frame-push boundary.
- `SpotifyBarsGLOverlay.set_state()` is a manual contract. New runtime kwargs must be added to both the signature and the body.
- Shader support alone is insufficient; the GL uniform lookup table and mode-specific uploader must also know about the new fields.
- When logs suggest a visualizer "fell back", verify whether the real failure is a shared transport exception before diagnosing the renderer itself.

## Record Provenance

This standalone file preserves the complete former inline `R-14` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.
