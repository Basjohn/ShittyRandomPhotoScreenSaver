# Transition expansion | active implementation

Operator request: implement the transitions in `Future_Work.md`, most ambitious first, emphasizing real 3D and visual quality. Comparison HEAD: `25bf2c103b325b568139984bd84192167410d8dd`. Unrelated operator `.sst` edits are outside these checkpoints.

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
5. **Ink Bloom, Tendril Reveal, Melt/Drip:** finite shader formulas with distinct connected spreading, branching/thickening and gravity/stretch identities. No evolving CPU masks or fluid simulation.

New transition capabilities start deactivated by canonical default. Existing activations, selections, durations and authored settings remain intact. Manual visual acceptance and representative heavy-load/mixed-display evidence remain separate from automated correctness.

## Resource design

Feature-local: fracture topology and metadata, tile motion/material shaders, growth formulas, per-run seeds, image mapping. Justified shared primitives may include a small context-local mesh/program holder and fullscreen image underlay used by the actual new mesh consumers. They must stay lazy, own no clock, preserve failed-cleanup handles and support partial-allocation cleanup. Do not build a scene engine, generic physics, material hierarchy or always-live 3D subsystem. Instancing derived from `gl_InstanceID` needs no per-frame instance upload.

Depth clears must stay within the transition viewport and restore scissor state; the existing host restores depth/cull/program/VAO/buffer/texture state on success and failure. Resources retire on disable/context retirement using the existing legal owner. Per-run buffers may be reused only while their geometry key matches.

## Resumable checkpoints

- [x] Trace current source and pin comparison HEAD; commit this decomposition before substantial implementation.
- [x] Glass Shatter vertical slice: registry/default/Settings/request, lazy renderer, deterministic fracture and visual proof.
- [x] Exploding Tiles and Pixel Accretion: bounded instancing, Settings/request integration, no per-frame mesh upload, visual proof.
- [x] Slide Perspective Push: same identity, unchanged established styles, coverage and visual proof.
- [x] Organic effects: canonical integration and distinct bounded shaders with visual proof.
- [x] Focused dormancy/activation, default parity, request, lifecycle/fence and real-GL checks. Existing build scripts include both implementation and shader packages; frozen/installed validation remains an operator gate.
- [x] Reconcile live docs/backlog into `Docs/Reference/Transitions.md`.
- [~] Awaiting operator validation: aesthetic quality/motion at actual duration, extreme aspects/DPR, both displays, repeated interruption and representative heavy-load Visualizer freshness. Do not declare these passed from shader compilation or screenshots.

## Acceptance evidence

Deterministic/source: reproducible seeds, cell coverage/non-overlap, bounded counts, coherent activation rank, eight-direction accretion, exact endpoints, sensitivity to authored options. Test negative cases that would admit a static dissolve or generic wipe.

Lifecycle: lazy import/resource dormancy, partial initialization failure, legal release and idempotence, disable/re-enable, GL-state restoration including scissor/depth on exceptions. Existing monotonic run/generation fences must continue passing.

Real GL: render through `QuickTransitionRenderHost`, inspect a progression/contact sheet with textured image fixtures, verify endpoints and destination/source underlays, GL errors and release. Exercise portrait and landscape, variant/direction changes, repeat seed reproducibility, and compile every shader on installed driver.

Performance: bounded vertices/instances and static uploads; measure cold generation/initialization separately from warmed rendering at representative sizes. Use nonblocking GPU timing/readback only in test tools, never runtime. Heavy external-load and mixed-display physical acceptance remains open until actual evidence arrives; do not tune Visualizer cadence or reaction to compensate.

## Current evidence and remaining work

All seven effects have driver-rendered textured progressions, exact and near-endpoint checks, seed/option sensitivity, repeatability and disable cleanup. Glass has portrait capture; both instanced effects have 4K captures with bounded grids. Each effect passes the production threaded QQuickWindow smoke across two generations and hide/show on the currently connected single display (DPR 1.5). The request for two windows reported only one physical screen, so it does not close two-display acceptance.

- [ ] Operator: activate each new capability in Transitions SETUP, select it and tune/accept duration, glass sheen/depth, tile density and organic detail using actual photos.
- [ ] Operator: repeat with both displays connected and active music/representative heavy external load; compare Visualizer freshness, frame-spacing tails and transition first-use behavior to the accepted baseline. Cold shader/mesh admission remains measurable work, not an established performance-neutral claim.
- [ ] Operator: verify the installed/frozen build including activation/Settings round-trip and repeated switch/interrupt/retire.

The new generic lazy Settings transaction also fixes external-update hydration and explicit external-deactivation retirement. Existing operator `.sst` changes were preserved; only new transition additions belong to this implementation checkpoint.
