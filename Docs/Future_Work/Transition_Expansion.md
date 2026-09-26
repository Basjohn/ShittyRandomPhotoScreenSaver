# Transition expansion | visual rework

This plan owns the still-open visual correction and acceptance work for the promoted transition expansion. `Docs/Reference/Transitions.md` owns implemented transition behavior; `Current_Plan.md` owns sequencing.

## Current correction target

Two rejected Melt forms establish binding negative controls: detached spherical masses do not read as liquid, and full-image directional pseudo-volume distortion shreds the photograph. A later narrow wet-band front was rejected by the operator (2026-09-23) because it did not look like the image melting; the superseding decision is that the photograph itself melts from a chosen origin under gravity. The negative controls still bind: no detached bulb/capsule geometry, no ray-marched pseudo-volume, and no seams that cut the photograph into slabs (a float hash once cut Melt's field into rectangles; see the Melt item below). Visual acceptance is open. Tendril Reveal was rejected and is now fully retired from the capability registry, defaults, Settings, runtime implementation and shaders; legacy persisted state is pruned by canonical transition normalization. Do not reintroduce it as a hidden or greyed capability.

- [~] Crumble's separate crack-formation stage now propagates strokes on actual fracture borders while the source image stays still, before chunks and seam debris fall. Debris is now smaller and deterministically shape/size-varied rather than a repeated primitive. Retain solid thickness, bevels and rough sides; operator visual acceptance remains open.

## Corrective scope

Earlier appearance testing rejected flat/opaque shard treatment, premature in-viewport shrink, weak tile depth/impulse and mask-like organic effects. Technical integration never substitutes for aesthetic acceptance. Tendril Reveal is retired; Pixel Accretion and Slide are outside this corrective slice.

- [x] Glass: closed extruded fracture prisms with bevel normals, visible thickness under tumble, screen-space transmission/refraction, optional dispersion and sheen. Expose thickness, transparency, refraction, dispersion and sheen independently in canonical Settings. Replace shrink retirement with continuous trajectories carrying the entire solid beyond the viewport; preserve image continuity before release.
- [~] **Glass collisions and in-flight re-shattering (operator 2026-09-23).** Two options, off by default. Decision: they are solved once per run at build time on COMPUTE (`rendering/quick/transitions/glass_dynamics.py`), not simulated per frame — the shader still evaluates every piece analytically in progress, now with a per-piece visibility window, velocity kick and spin kick that start at the event time, so the "no evolving CPU simulation, analytic GPU motion" rule holds. The solver replicates `GLASS_VERTEX`'s centre path, finds first contacts that are real, visible crashes (apart beforehand, closing at ≥20% of their speed, both on screen, before 0.80), resolves them as equal-mass bounces (restitution 0.45) with a spin kick, and caps them at 12% of shards pairing up. Re-shattering cuts a shard into 2–3 convex children that follow the parent exactly until the split; a child can crack once more (a second event stage: 45% shortly after an impact with collisions on, 30% later in flight without), inheriting the first stage exactly. Any kick that would leave a piece in view at the end is scaled back or turned outward. Cost: solve 5–14 ms at 95 shards (≤32 ms at 180); vertex build with the options on 27–37 ms at 95 shards, on COMPUTE; options off 13.8 ms (was 11.3 before the event floats). Glass is in the Random pool by default. Guards: `tests/test_qtquick_glass_dynamics.py` (tiling, ~30% random split, collision-only splits, budget, determinism, exit at extreme aspects, no pop at event times, options change the flight). Physical: operator judges the look in motion at authored durations.
- [x] Tiles: proportionate beveled solids, distinct front/side materials, strong out-of-plane tumble, explosive impulse and gravity. Expose thickness and force. Every tile must leave the frame geometrically; no premature shrink/fade substitute.
- [x] Additional operator request: upgrade existing Crumble to closed irregular wall chunks with visible broken sides, gravity-driven support failure, and surrounding solid debris chips. Share the pure fracture prism geometry with Glass; retain Crumble's identity, piece count, crack complexity and release weighting. Add depth/thickness/debris controls. Replace the old fullscreen/mosaic shader, with no fallback or duplicate owner. Bound per-run chunks and debris; retire through offscreen motion and the existing GL owner. Validate side geometry, debris-zero dormancy, release weighting, temporal continuity and actual artwork motion.
- [x] Melt rework (operator 2026-09-23; accepted the same day, activated and pooled by default at 8500 ms): the photograph melts from an origin — Top Left/Center/Right, Center Out, Center In (Random resolves one per run; retired edge directions in old profiles resolve as Random) — with accelerating sag under weight, soft drip columns, smear and a thinning film that reveals the destination, plus film relief, fold darkening and a soft cast shadow. The melt-time noise uses an exact integer lattice hash: the previous chaotic float hash gave one lattice corner different values in neighbouring cells and cut the image into hard-edged rectangles and straight lines (`test_melt_field_has_no_seams`). Exact source at 0; exact destination from 0.94. The Settings WIP label was removed on acceptance.
- [x] Ink: swirling pigment, irregular wet lobes and a raised lit boundary with materially distinct interior; expose depth/gloss alongside detail. Avoid a generic feathered mask with a renamed identity.
- [x] Validate production rendering with detailed image fixtures, inspected mid/late motion, near-endpoint continuity, authored material isolation, full-geometry departure, finite topology, resource retirement and inherited GL state. Update stale tests which explicitly blessed the rejected shrink mechanism.
- [x] Reconcile the validated material/geometry contract into the current transition reference and tests.
- [ ] Awaiting operator acceptance after correction: actual-duration aesthetics, both displays and heavy-load freshness. Automated image differences are not aesthetic acceptance.

All new material values resolve once through canonical defaults/UI/request admission. Renderers retain existing context resources and monotonic progress; no clocks, evolving CPU fluid simulations, parallel surfaces or fallback effects. Mesh geometry is static within a run; deformation/motion and Melt volume evaluation are analytical on the GPU. The existing mesh helper may support concrete shared needs only. Performance evidence must distinguish cold geometry/shaders from warm draws.

## Control rework (operator decisions 2026-09-23)

Measurements from the 2026-09-23 runtime-audit research (`Docs/Future_Work/Runtime_Audit/08_Open_Items_Research.md`) showed three authored controls with near-dead ranges. The operator kept every concept and admitted stronger visible effects; this is transition product work, separate from runtime cleanup.

- [~] **Crumble — Slabs Collide (operator 2026-09-26).** Implemented, off by default: the collapse is simulated once per run on COMPUTE and baked into a per-chunk motion table the shader interpolates (`Docs/Reference/Transitions.md`); slabs no longer pass through each other while in view, and a struck standing slab is knocked loose. Physical: turn it on at default and low Collapse Depth and judge the pile-up in motion at authored durations.
- [~] **Crumble — crack complexity and debris.** Implemented 2026-09-23: `crumble_cells` (seeded pattern families: impact point, stress clusters, organic warp; every family also warped), complexity-scaled over 0.5–2.0, convex Voronoi cells with a minimum site spacing; debris gets a per-run grain (fine/mixed/chunky) and crack hot spot, and the amount drives count and size. Measured: mean piece-size irregularity 0.342 → 0.503 → 0.691 → 0.851 → 0.996 across 0.5 → 2.0 (old: 0.31 → 0.38, flat above ≈1.26); coverage exact for every seed; 128-piece build 29.6 ms off-thread; Glass geometry unchanged. The strict xfail became a monotonic-shape bar and the `[debris-1.0]` oracle passes. Remaining: operator visual acceptance (the 1.8 default is now strongly mutated — CV ≈0.93 vs 0.39 before — so revisit the default if it reads too broken).
  - **Intent.** Complexity must visibly mutate the fracture shape/pattern much more; it owns fracture topology and shape. Debris owns the secondary broken-off material and must visibly change debris density and/or chip size, dispersion and flight. Debris stays recognisably debris, not another alias for complexity.
  - **Evidence.** Irregularity (cell-area CV, 12 seeds, 35 pieces) is 0.306 at 0.5, 0.351 at 1.0 and 0.382 flat from ≈1.26 to 2.0 (site spread clamps at .48), so half the slider, including the 1.8 default, does nothing. An unclamped spread remap reaches only 0.388: a remap cannot deliver the decision. Debris 0.65 → 0 or 1 changes ≤0.22% of pixels at any progress.
  - **Geometry options** (combine; built in `run_geometry`/Crumble shaders and prepared off-thread as today):
    1. jagged shared fracture edges — subdivide each shared edge into k segments with seeded perpendicular offsets derived from its endpoints, so both neighbours get the identical polyline; complexity drives k and amplitude (the strongest visible change);
    2. clustered/Poisson site distribution mixing large slabs with small shards;
    3. secondary micro-cracks in the crack-formation stage (fissures that do not split pieces), density scaled by complexity;
    4. optional anisotropy along the fall direction at high complexity.
  - **Debris.** Rework debris inside the same slice; do not spend a separate slice polishing the current, nearly invisible implementation.
  - **Bars.**
    - Gap-free seams (coverage/seam oracle); crack-stage strokes follow the polyline.
    - Byte-identical geometry per seed.
    - Each complexity step changes shape metrics monotonically, replacing the strict xfail `test_crack_complexity_is_live_across_its_whole_range` and the pinned calibrated pixel oracles.
    - Debris min/mid/max visibly distinct, replacing `test_real_driver_each_crumble_control_changes_the_volume[debris-1.0]`.
    - Jagged edges raise vertex counts, so benchmark the 128-piece geometry build (off-thread) and draw cost. The D1 soak showed the old 11–40 ms first-frame class gone after off-thread preparation; keep it gone.
- [x] **Melt — gloss and detail.** Reworked with the Melt rework. Measured on real photographs at 40% (inside the melting region, 60–70% of the frame): detail 0.5↔2.0 changes 43–50/255 mean, depth 0↔1 14–17/255, gloss 0↔1 16–21/255 (wet sheen plus highlights; silhouette unchanged). Both former reds (`test_liquid_material_controls_affect_the_melt[gloss]`, `test_authored_controls_change_rendered_pixels[melt_drip-detail-2.0]`) are green. Accepted with the Melt rework.

## Current owners and invariants

- `rendering/transition_registry.py` owns identities/activation participation; `core/settings/default_settings.py` owns values, with existing Settings UI/model/schema integration.
- `rendering/quick/transitions/parameter_resolution.py` resolves settings, direction and seeds once before immutable `TransitionRequest` admission. `state.py` owns monotonic progress/exactly-once completion; effects never create clocks or CPU simulation loops.
- `implementation_registry.py` lazily resolves implementations; `render_host.py` owns the context-local lifetime and inherited GL-state fence. The existing display render node remains the sole presentation surface.
- `implementations/block_spins.py` and `rendering/gl_programs/blockspin_program.py` prove mesh/depth resources inside Quick. Voxel Sphere is an independent consumer to inspect for small identical resource seams, not a transition foundation or base class.
- Existing transition tests, `tools/qtquick_render_node_smoke.py` and `tools/qtquick_phase_c_effect_smoke.py` provide production host, endpoint, fence and real-GL seams.

## Scope and authored identities

1. **Glass Shatter:** seeded irregular fracture cells, coherent directional/radial release, original-image UV continuity, arbitrary-axis rotation, perspective and depth, cool Fresnel edges, restrained sheen/transmission, full destination underlay. Bounded mesh generated/uploaded once per run; analytic motion on GPU.
2. **Exploding Tiles:** shallow solid cuboids instanced from a static mesh, coherent release wave, real rotation/Z launch, lit side faces. Distinct from irregular glass and existing Block Flip.
3. **Directional Pixel Accretion:** bounded adaptive micro-tile grid, one event direction, destination tiles physically translate and settle over source; subtle height/oversize while landing. Eight directions plus Random resolved once. Never a pixel dissolve.
4. **Slide Perspective Push:** an option in existing Slide, restrained perspective/yaw/pitch and depth with sealed source/destination coverage. Existing modifiers retain behavior.
5. **Ink Bloom and Melt/Drip:** a raised pigment mesh and a bounded cohesive liquid front. They retain distinct spreading/transport and gravity/viscous-drain identities; Melt melts the photograph itself from an origin under gravity, never with detached droplet primitives, a ray-marched volume or seams that shred the photograph. No evolving CPU masks or fluid simulation. Tendril Reveal is retired and is not part of the capability set.

New transition capabilities start deactivated by canonical default. Existing activations, selections, durations and authored settings remain intact. Manual visual acceptance and representative heavy-load/mixed-display evidence remain separate from automated correctness.

## Resource design

Feature-local: fracture topology and metadata, tile motion/material shaders, growth formulas, per-run seeds, image mapping. Justified shared primitives may include a small context-local mesh/program holder and fullscreen image underlay used by the actual new mesh consumers. They must stay lazy, own no clock, preserve failed-cleanup handles and support partial-allocation cleanup. Do not build a scene engine, generic physics, material hierarchy or always-live 3D subsystem. Instancing derived from `gl_InstanceID` needs no per-frame instance upload.

Depth clears must stay within the transition viewport and restore scissor state; the existing host restores depth/cull/program/VAO/buffer/texture state on success and failure. Resources retire on disable/context retirement using the existing legal owner. Per-run buffers may be reused only while their geometry key matches.

## Current implementation and acceptance

- [x] Glass Shatter vertical slice: registry/default/Settings/request, lazy renderer and deterministic fracture. Appearance reopened above.
- [x] Exploding Tiles and Pixel Accretion: bounded instancing, Settings/request integration, no per-frame mesh upload. Tile appearance reopened above.
- [x] Slide Perspective Push: same identity, unchanged established styles, coverage and visual proof.
- [x] Organic effects: canonical integration and bounded shaders. Appearance rejected; reopened above.
- [x] Focused dormancy/activation, default parity, request, lifecycle/fence and real-GL checks. Existing build scripts include both implementation and shader packages; frozen/installed validation remains an operator gate.
- [x] Reconcile live docs/backlog into `Docs/Reference/Transitions.md`.
- [~] Awaiting operator validation: aesthetic quality/motion at actual duration, extreme aspects/DPR, both displays, repeated interruption and representative heavy-load Visualizer freshness. Do not declare these passed from shader compilation or screenshots.

## Acceptance evidence

Deterministic/source: reproducible seeds, cell coverage/non-overlap, bounded counts, coherent activation rank, eight-direction accretion, exact endpoints, sensitivity to authored options. Test negative cases that would admit a static dissolve or generic wipe.

Lifecycle: lazy import/resource dormancy, partial initialization failure, legal release and idempotence, disable/re-enable, GL-state restoration including scissor/depth on exceptions. Existing monotonic run/generation fences must continue passing.

Real GL: render through `QuickTransitionRenderHost`, inspect a progression/contact sheet with textured image fixtures, verify endpoints and destination/source underlays, GL errors and release. Exercise portrait and landscape, variant/direction changes, repeat seed reproducibility, and compile every shader on installed driver.

Performance: bounded vertices/instances and static uploads; measure cold generation/initialization separately from warmed rendering at representative sizes. Use nonblocking GPU timing/readback only in test tools, never runtime. Heavy external-load and mixed-display physical acceptance remains open until actual evidence arrives; do not tune Visualizer cadence or reaction to compensate.

## Remaining acceptance

The current material/geometry implementation has deterministic regression, Settings/default-authority and real-GL smoke coverage for its topology, bounded/static allocation, failed-cleanup retry, material round-trip, endpoint continuity and resource retirement. Re-run the affected focused gates after any transition code/settings change; do not preserve a stale aggregate pass count in this plan. Prior two-display smoke establishes lifecycle/rendering evidence only, not representative-load or perceptual acceptance.

- [ ] Operator: accept/reject appearance and timing with actual photos at authored durations, including new optics and depth controls. Rejected Melt forms remain negative controls; no automated check establishes aesthetic acceptance.
- [ ] Operator: repeat with both displays connected and active music/representative heavy external load; compare Visualizer freshness, frame-spacing tails and transition first-use behavior.
- [ ] Operator: verify the installed/frozen build including activation/Settings round-trip and repeated switch/interrupt/retire.

Cold shader/geometry admission remains measurable work. Offscreen timing is not evidence of performance neutrality under representative load.
