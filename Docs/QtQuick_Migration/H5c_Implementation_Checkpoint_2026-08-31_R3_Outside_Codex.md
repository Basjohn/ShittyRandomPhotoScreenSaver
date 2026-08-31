# H5c Implementation Checkpoint R3 — Outside-Codex Viewport Scaling

Outside of Codex Work Began @ `61decb33f6ebb107b2997928077e9d56d5faa8a1`

This checkpoint continues from the operator-supplied real-tree ZIP after Codex Sol Ultra quota exhaustion. The ZIP contains source and tools but no `.git`, no complete maintained `tests/` tree, and this execution environment has no PySide6. Treat the focused source-only tests below as supplemental; the normal project test profile and physical Windows/Qt Quick run remain required.

> **SUPERSEDED CHECKPOINT / PROVENANCE ONLY.** Do not use this file as live repair or status authority. `Current_Plan.md` owns sequence; R6 native-`QCursor` Halo and R7 image/prefetch/seam work supersede the pointer/image-pipeline portions. Preserve only findings explicitly carried forward by current living docs.

## Applied / deterministic GREEN

- [x] Bubble rebound impulse: canonical/wide/tall falsifier proved `1 / domain_axis` visible loss; impulse application now projects once into the expanded logical axis.
- [x] Bubble collision: two-bubble falsifier disproved the earlier height-domain geometry assumption. Pair radius/gap/distance policy now runs in canonical renderer-content space; correction vectors project back into expanded storage.
- [x] Bubble spawn overlap/pre-entry guard uses the same content-space policy.
- [x] Bubble collision hot path precomputes reciprocal domain axes and margins; no per-pair divide/helper-call scaling tax, no extra collision pass.
- [x] Bubble swirl and motion-tail projection re-falsified GREEN across canonical/wide/tall/2x2 and approximately the operator's `1.724x2.914` viewport.
- [x] Bubble outline changed from fixed `1.2 px @ r=.04` weighting to radius-proportional ~3.75% with authored-pixel safety bounds. This is physically informed by the operator report that the old outline was correct only at the very tall viewport; physical revalidation is still required.
- [x] Spectrum duplicate height transfer removed: Python resolves the capped height scale once; shader consumes it once; independent historical `0.55` upload transfer preserved.
- [x] Oscilloscope/Sine `Vertical Shift`: fixed `20..80 px` placement clamp now scales with logical viewport-height extent; line/glow stroke scale remains independent.
- [x] DevCurve authored outline/specular bounds are applied before baseline/current projection; Quick shader floors/bounds follow the same axis projection rather than snapping back to canonical normalized constants.
- [x] DevCurve specular X->Y derived lobe radius now uses one CPU-resolved normalized-axis ratio; AA safety floor follows Y projection. No per-fragment division or extra pass.
- [x] Focused source-only viewport profile: `12/12` GREEN.
- [x] Changed Python modules syntax-compile GREEN.

## Open / deliberately not papered over

- [ ] Bubble Ghost: UI promises a fading afterimage and exposes `bubble_ghost_decay`, but retained Quick consumes only Ghost alpha and the shared Bubble shader draws a static `1.18x` halo. Do not wire decay into the halo as a fake repair. **AWAITING HISTORICAL ORACLE / PHYSICAL CONTRACT DECISION.**
- [ ] Bubble outline: **AWAITING VALIDATION** at normal/small/very-tall viewport sizes.
- [ ] Bubble rebound/collision/transient stream+drift/wake appearance: **AWAITING VALIDATION**.
- [ ] Spectrum continuous + segmented canonical/tall comparison: **AWAITING VALIDATION**.
- [ ] Oscilloscope/Sine canonical/tall Vertical Shift + general preset comparison: **AWAITING VALIDATION**.
- [ ] DevCurve canonical/tall/wide outline AA + specular comparison: **AWAITING VALIDATION**.
- [ ] Last Codex-run maintained `h-destination` was `84/84` at the SHA anchor above; rerun in the normal PySide6 environment after applying this checkpoint.

## Performance architecture watch

- [x] No new clock, cadence owner, render pass, worker, large-array owner, repaint loop, or per-frame allocation was introduced by these viewport repairs.
- [x] Osc/Sine add one scalar viewport uniform and constant shader arithmetic.
- [x] DevCurve adds a normalized-scale vec2 + one scalar X->Y ratio. Cross-axis division is done once on CPU, not per fragment.
- [x] Bubble noncanonical collision adds two reciprocal multiplications per pair after precomputing reciprocals once per call; asymptotic pair work/pass count is unchanged.
- [ ] Supplied runtime logs still show healthy authored cadence near 90 Hz alongside measurable presentation skips and tens-of-ms GC stalls. Keep this as measured J/performance debt; investigate earlier only if it obstructs H validation.
- [ ] The viewport-scaling implementation already present when outside-Codex work began may itself have changed GPU/presentation cost. No trustworthy pre-scaling A/B is available in this source ZIP; later Git/log archaeology should compare the pre-scaling boundary against the handoff SHA instead of treating the handoff as a performance-neutral baseline.

## Next physical checkpoint

Run all five modes under real music and resize from canonical to deliberately aggressive wide/tall CUSTOM extents. Include DevCurve (absent from the supplied run). Exercise Bubble rebound/collisions, stream/drift transients, motion tail/wake, normal-vs-huge outline and Ghost controls; Spectrum continuous + segmented; Oscilloscope/Sine Vertical Shift; DevCurve outline/specular. Preserve ordinary + verbose/QML/perf logs. Any rejected slice reopens only that slice; do not add a global compensating viewport multiplier.
