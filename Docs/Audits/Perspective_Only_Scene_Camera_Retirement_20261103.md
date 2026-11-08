# SRPSS camera authority | Perspective-only scene cameras | 3 November 2026

> **Orthographic removed 5 Nov 2026 (operator):** Perspective is the only camera projection in the whole project. Orthographic, its Projection control, raster-slab fit and parallel-ray paths are deleted; any Orthographic passage below is historical and superseded.

**Status:** Binding operator decision; documentation-only plan update, **not an already completed source migration**. Applies on top of `SRPSS_Waveform_Recovery_Studio_Replan_2026-11-03.zip` and original dirty GODZIP `0d69f4ae77`. Extract at repository root, replacing **only the listed documents**. Do not delete unlisted paths; do not treat missing private references/assets/presets as deletions. No source files, camera values, renderer, presets, settings, defaults, themes or operator-authored EB appearance have been edited by this ZIP.

## Decision and boundaries

- **Perspective is the ONLY user-facing/artistic projection for framed 3D visualizers** (Waveform, EB, Neon Lake and future modes). Orthographic is retired/removed as a product authoring option; it is not an alternative, deferred, fallback, equal-parity, or a future-mode default. Do not continue evaluating Waveform in both projections.
- **EB is accepted and stays alone.** The operator specifically rejected further EB visual/camera/FOV/distortion tuning. The policy change alone does not reopen EB and requires no EB art experiment. EB historical source documents retain past findings as historical evidence.
- Keep the existing physical camera, actual perspective FOV and framing, pose controls, projection-aware reflections, world-space effects and preset camera-save behavior. Distortion in EB at viewport extremes is known context, **not** an active defect ticket.
- `orthographic_matrix`, orthographic shadow maps, parallel-ray geometry tools and archived diagnostic images may remain if a real technical user needs them. Their existence does not obligate authored Orthographic scene support.
- Older documents, screenshots, experiments and tests asserting “Orthographic default”, “Perspective optional”, “both camera modes”, “EB Orthographic parity later”, or “switch projections to test mist” are superseded. Preserve forensic evidence but do not use those claims as a live work mandate.

## Planned source retirement checklist (not accomplished in this docs-only ZIP)

- [ ] **CAM-1:** identify actual typed projection owner, mode declarations, generated bindings, UI selection, canonical defaults, preset import/repair and Studio interfaces; ensure *effective* public scene projection is Perspective only. No one-option selector required.
- [ ] **CAM-2:** conservatively normalize historic Orthographic values on load; retain legacy source bytes on read, avoid implicit rewrites/deletions of curated presets, and preserve intentional operator-save semantics. Document any read-only compatibility field vs actual effective Perspective rendering.
- [ ] **CAM-3:** remove dual-projection acceptance/tuning gates from Waveform/Studio and future framed 3D work; regression-check Waveform perspective preview/production and unchanged accepted EB/Neon Lake perspective behaviour. No EB new visual work.
- [ ] If dead-code removal is hazardous during active Waveform recovery, do narrow safe UI/canonical retirement now and isolate legacy internals for later deletion. The operator still sees/edits **Perspective only**.

## Documentation changes included

This pack intentionally revises live `Current_Plan.md`, the two Waveform plans, visual authority and mist investigation, global `Spec.md`/`Future_Work.md`/`Index.md`, shared camera/visualizer/lab guides and only **supersession notes** in historical EB and ribbon-path technical references. None of these revisions should be interpreted as code completion or as a request to regenerate the entire current-plan backlog.
