# Transition expansion | visual rework

Operator request: implement the transitions in `Future_Work.md`, most ambitious first, emphasizing real 3D and visual quality. Comparison HEAD: `25bf2c103b325b568139984bd84192167410d8dd`. Unrelated operator `.sst` edits are outside these checkpoints.

## Latest operator direction

The operator rejected Melt again: detached balls and the body still lack convincing organic liquid behavior. Leave Melt unchanged for possible user rework. Tendril is rejected and scheduled for removal; disable and grey it out now, retaining its identity only to explain unavailability until cleanup. Do not continue Tendril visual redesign.

- [ ] Restore Crumble's separate crack-formation stage: strokes must propagate on actual fracture borders while the source image stays still, then chunks and their seam debris fall. Retain solid thickness, bevels, rough sides and debris.
- [ ] Verify Tendril is visibly unavailable and cannot enter fixed or Random runs from saved activation. Keep removal of dormant implementation/settings/test files as explicit pending work.

## Reopened after operator rejection

The operator rejected the appearance of Glass Shatter, Exploding Tiles, Ink Bloom, Tendril Reveal and Melt Drip at `dec139da`. Earlier rendering checks establish technical integration only; they do not establish aesthetic acceptance. Supplied screenshots show flat opaque shards and a soft stretched wipe. Source confirms planar glass, premature in-viewport shrink, weak tile impulse/thickness, and fullscreen mask-only organic effects. Pixel Accretion and Slide are outside this corrective slice.

- [x] Glass: closed extruded fracture prisms with bevel normals, visible thickness under tumble, screen-space transmission/refraction, optional dispersion and sheen. Expose thickness, transparency, refraction, dispersion and sheen independently in canonical Settings. Replace shrink retirement with continuous trajectories carrying the entire solid beyond the viewport; preserve image continuity before release.
- [x] Tiles: proportionate beveled solids, distinct front/side materials, strong out-of-plane tumble, explosive impulse and gravity. Expose thickness and force. Every tile must leave the frame geometrically; no premature shrink/fade substitute.
- [x] Additional operator request: upgrade existing Crumble to closed irregular wall chunks with visible broken sides, gravity-driven support failure, and surrounding solid debris chips. Share the pure fracture prism geometry with Glass; retain Crumble's identity, piece count, crack complexity and release weighting. Add depth/thickness/debris controls. Replace the old fullscreen/mosaic shader, with no fallback or duplicate owner. Bound per-run chunks and debris; retire through offscreen motion and the existing GL owner. Validate side geometry, debris-zero dormancy, release weighting, temporal continuity and actual artwork motion.
- [ ] Visually rejected Melt: replaced the rejected sheet/column approaches with ray-intersected 3D liquid, rounded wet film, curved narrowing ligaments and detached gravity-driven drops. Photo coordinates advect through the volume; no opacity-wipe or terminal cut. Direction remains authored; expose depth/gloss alongside detail.
- [ ] Pending removal (no further redesign): Tendril has curling parent/child growth with round cross-sections, depth and occlusion, varied branching and coherent destination reveal. Expose depth/gloss alongside detail.
- [x] Ink: swirling pigment, irregular wet lobes and a raised lit boundary with materially distinct interior; expose depth/gloss alongside detail. Avoid a generic feathered mask with a renamed identity.
- [x] Validate production rendering with detailed image fixtures, inspected mid/late motion, near-endpoint continuity, authored material isolation, full-geometry departure, finite topology, resource retirement and inherited GL state. Update stale tests which explicitly blessed the rejected shrink mechanism.
- [x] Checkpoint the validated material/geometry pass and reconciled references.
- [ ] Awaiting operator acceptance after correction: actual-duration aesthetics, both displays and heavy-load freshness. Automated image differences are not aesthetic acceptance.

All new material values resolve once through canonical defaults/UI/request admission. Renderers retain existing context resources and monotonic progress; no clocks, evolving CPU fluid simulations, parallel surfaces or fallback effects. Mesh geometry is static within a run; deformation/motion and Melt volume evaluation are analytical on the GPU. The existing mesh helper may support concrete shared needs only. Performance evidence must distinguish cold geometry/shaders from warm draws.

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
5. **Ink Bloom, Tendril Reveal (pending removal), Melt/Drip (rejected):** a raised pigment mesh, closed growing branch tubes tied to their canopy, and a bounded implicit liquid volume. Distinct spreading/transport, branch growth and gravity/pinch-off identities; no evolving CPU masks or fluid simulation.

New transition capabilities start deactivated by canonical default. Existing activations, selections, durations and authored settings remain intact. Manual visual acceptance and representative heavy-load/mixed-display evidence remain separate from automated correctness.

## Resource design

Feature-local: fracture topology and metadata, tile motion/material shaders, growth formulas, per-run seeds, image mapping. Justified shared primitives may include a small context-local mesh/program holder and fullscreen image underlay used by the actual new mesh consumers. They must stay lazy, own no clock, preserve failed-cleanup handles and support partial-allocation cleanup. Do not build a scene engine, generic physics, material hierarchy or always-live 3D subsystem. Instancing derived from `gl_InstanceID` needs no per-frame instance upload.

Depth clears must stay within the transition viewport and restore scissor state; the existing host restores depth/cull/program/VAO/buffer/texture state on success and failure. Resources retire on disable/context retirement using the existing legal owner. Per-run buffers may be reused only while their geometry key matches.

## Resumable checkpoints

- [x] Trace current source and pin comparison HEAD; commit this decomposition before substantial implementation.
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

## Current evidence and remaining work

The corrective pass has inspected artwork progressions and animated previews. Glass and Crumble share closed beveled fracture solids; material controls have driver-pixel discrimination. Crumble emits solid chips from parent polygon seams with matching release timing. Ink transports pigment across a raised mesh. Tendril uses round aspect-correct tubes and canopy segments sampled from the same curves; canopy expansion and relief settle continuously. The rejected Melt curtain and column prototypes were discarded; the replacement intersects an actual implicit volume with wet shading, narrowing necks and falling detached masses.

The combined focused gate passes 312 tests. Focused regression checks cover closed prism topology, bounded/static allocation, failed cleanup retry, material save/reopen/external update/Reset, exact/near endpoints and removal without a late cut. The combined Settings/GL tests use the shared QApplication fixture: allowing an earlier standalone QGuiApplication made later QWidget checks abort; that test setup defect was corrected. Defaults snapshot/SST authority audits pass. The material pass preserves operator settings/installer changes.

- [x] Final closed-tile departure review and Quick smoke; all six corrected effects pass two generations, hide/show and resource retirement on the two connected physical displays.
- [ ] Operator: accept/reject appearance and timing with actual photos at authored durations, including new optics and depth controls. Intermediate Melt rejection remains part of the rationale; no automatic check establishes aesthetic acceptance.
- [ ] Operator: repeat with both displays connected and active music/representative heavy external load; compare Visualizer freshness, frame-spacing tails and transition first-use behavior. The current smoke exercised both MSI G321Q (~165 Hz) and LG TV (60 Hz), both at DPR 1.5. This establishes two-display lifecycle/rendering evidence, not representative-load or perceptual acceptance.
- [ ] Operator: verify the installed/frozen build including activation/Settings round-trip and repeated switch/interrupt/retire.

Cold shader/geometry admission remains measurable work. Offscreen timing is not evidence of performance neutrality under representative load.
