# R-36 — Blob Mighty / Shaped Contours Reached Healthy Audio But Lost Visible Motion Inside Blob-Local Geometry

Date: 2026-07-12  
Status: Resolved in code; runtime validation pending

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [x] AWAITING VALIDATION
- [ ] SOLVED

## Observed Failure Pattern

Mighty no longer exposed the earlier full circular core after its first repair, but maximum or near-maximum contour controls still produced mostly whole-body size changes. Wobble was barely perceptible, Stretch did not read as a growing tendril, and earlier deformations could look like rotating radial cuts. Shaped reached its authored goal and then appeared almost static apart from glow; mutation, warping, fixed-angle wobble, and lighter tendrils were not materially visible.

## Forensic Boundary

Current logs showed healthy Blob input throughout the failure. Live bands repeatedly occupied roughly `0.5..1.5`, kicks/snares/transients fired, the active concrete shader matched source, and there was no shader fallback, shared-audio starvation, or subtype bleed. The failure was therefore kept entirely Blob-owned; shared audio and the other visualizer modes were not retuned.

## Mighty Root Causes

- Scalar pulse coefficients could move the complete radius by far more pixels than the contour, making a functioning profile look like a size-only reaction.
- The Blob-local energy compressor collapsed much of the useful `0.5..1.5` live range, while autonomous phase breathing accounted for too much of the remaining motion.
- Target rounding, slew, spring smoothing, and shader sampling formed a multi-stage attenuation stack.
- Inward and outward containment were coupled, so one protected inward valley reduced every outward tendril.
- The solved contour was passed through nonlinear containment a second time on every frame, erasing more than half of quiet-to-hot transfer.
- An angle-varying hard solver floor rebuilt from the living base then clipped dozens of samples, producing flat/cut shoulder junctions even though the target was already safe.

## Shaped Root Causes

The authored reaction goal saturated too early, unconditional goal-floor mixing made it nearly static during sustained audio, residual mutation authority was sub-pixel after solver smoothing, and some transient routes consumed continuous pressure rather than the actual Blob transient envelopes.

## Settings-Authority Contributors

Subtype sliders could leave a curated preset authoritative instead of switching to Custom, and the typed visualizer setter serialized dotted keys one at a time with `blob_type` late. Normalization could therefore strip the incoming subtype values before the type flip completed, making valid edits appear dead or reset.

## Final Fixes

- Both concrete Blob programs now consume one 128-sample CPU-solved profile directly; Mighty has no post-profile amplifier or circular support floor.
- Mighty uses a wider Blob-local energy mapping, fixed/slow-sway organic tendrils that grow and relax at anchored sites, reduced scalar pulse authority, one-time target rounding, independent containment authority, faster target/spring response, no post-solver re-fit, and a global `0.84` solver safety floor instead of the angle-varying clamp.
- Shaped uses anchored amplitude-breathing warps, stronger bounded mutation beyond the authored goal, real transient envelopes, lighter music-driven tendril tips, responsive release, and zero-shift-dominant motion rather than traveling deformation phases.
- Subtype controls switch curated authority to Custom before saving, and visualizer settings are written as one normalized section so the new `blob_type` and its owned values commit atomically.
- Subtype state, shader programs, presets, settings, and diagnostic profiles remain Blob-owned; no shared audio contract changed.

## Measurable Closure Evidence

- A high-authority 128-sample Mighty stress vector retains `99.89%` of quiet-to-hot target motion through the settled runtime solver; the representative contour moves about `16.96 px RMS / 36.49 px max` on a 940 px inner card, isolated Stretch reaches about `21.77 px`, and the scalar pulse delta is about `33.99 px` rather than overwhelming contour motion by an order of magnitude.
- Mighty attack reaches `90%` in about `0.32 s`, release returns to `10%` in about `0.42 s`, every tested temporal pair prefers circular shift `0/128`, and the idle/quiet contour remains materially non-circular.
- Representative 128-sample Shaped authored cases mutate beyond their no-motion goal by more than `0.075` profile units (at least `13.5 px` at a 180 px contour radius), move at fixed angles over time, remain bounded, and preserve their authored goal identity.

## Regression Bars

- `tests/test_blob_unshaped_geometry.py`
- `tests/test_blob_shaper_plumbing.py`
- `tests/test_blob_pockets.py`
- `tests/test_blob_intensity_reserve.py`
- `tests/test_blob_inward_liquid.py`
- `tests/test_blob_type_runtime.py`
- `tests/test_blob_shader_compile.py`
- `tests/test_visualizer_reactivity_quality.py`
- `tests/test_visualizer_overlay_kwargs.py`
- `tests/test_overlay_render_dispatch.py`
- `tests/test_startup_shader_warmup.py`
- `tests/test_settings_manager.py -k blob`
- `tests/test_widgets_tab.py -k blob`
- `tests/test_visualizer_settings_plumbing.py -k blob`

## Keep-Closed Rule

Measure target-to-runtime transfer, fixed-angle motion, pixel-scale mutation, and circular-shift preference. Helper variance or a large static profile spread is not sufficient. Do not lock the temporary showcase presets' exact creative JSON as the behavior contract; use synthetic controls/nodes that reproduce the failure shape, while preset tests remain responsible for schema and slot integrity.

## Runtime Validation Target

Under `-devblob`, confirm Mighty visibly grows and releases rounded tendrils without a circular center or cut-like shoulders, and confirm Shaped visibly mutates around—then returns to—its authored goal. Check startup, settings round-trip, hot subtype switches, curated payloads, and Custom. A clean result must not add shared-mode reactivity drift or first-frame poison.

## Migration Record

This file is the standalone detailed record copied from the original `R-36` entry in `Docs/Historical_Bugs.md`. The monolithic source entry remains unchanged during the copy-first migration and will be replaced by a compact index summary only after the historical-bug set has been migrated and mechanically checked.
