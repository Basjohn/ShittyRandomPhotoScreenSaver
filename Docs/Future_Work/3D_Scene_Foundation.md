# 3D Scene Foundation — decomposition (live checklist)

`Current_Plan.md` owns sequencing. This file owns only the technical decomposition for the **remaining** scene3d
program and is deleted when the last active slice closes. Landed architecture belongs in
`Docs/Reference/Scene3D_Resources.md`, `Docs/Reference/Transitions.md`,
`Docs/Reference/Visualizer_Reference.md` and `Docs/Reference/Sphere_Visualizer.md`.

## Goal

One shared, high-fidelity OpenGL 4.6 GPU substrate whose meaningful cost is zero when no consumer uses it. 3D
transitions and 3D Visualizers may reuse low-level resource/material/post/compute plumbing while each effect retains
its own authored motion, reaction, look and Settings. Voxel Sphere is promoted onto that substrate without turning its
behavioural model into a generic base class.

## Landed substrate required by the remaining slices

These are prerequisites, not open work and not a second completion ledger:

- strict OpenGL 4.6 Core / GLSL 460 runtime admission;
- neutral `rendering/quick/scene3d/` ownership for shared meshes, targets, state fences, camera/projection helpers and
  common shader support;
- bounded per-run/per-context resource lifetime with `park()`/mode retirement and no per-frame allocation;
- canonical 3D Detail resolution plus accepted transition migrations, bloom/motion blur/trails/photo-reflection and
  next-transition warm-up contracts;
- DSA/immutable storage/multi-bind resource construction where it reduces bind/query ceremony without weakening Qt
  inherited-state restoration;
- GPU/CPU mirror and state-fence tests routed from the current Reference/TestSuite documents.

If remaining work discovers a defect in a landed prerequisite, fix it at that owner and update the durable reference;
do not reopen S1-S13 as a historical checklist.

## Ownership rules

- **State:** analytic from admitted inputs; no render-rate CPU simulation or uploads of evolving Python arrays. Per-run
  work is solved once at request/COMPUTE preparation or held in bounded GPU state.
- **Time:** transitions derive from run progress/real authored seconds; Visualizers use only logical snapshot time.
  Compute may not become a second simulation clock.
- **Settings:** canonical defaults and resolution happen before admission; renderers never read Settings.
- **GPU resources:** context-local, consumer-owned, bounded and exactly retired. Failed deletion keeps handles for retry;
  no frame cadence is invented to service cleanup.
- **State fences:** every inherited/touched GL state remains restored even when DSA removes local bind/query ceremony.
- **Sphere:** behaviour/state/presets/cohort/tracer semantics remain Sphere-owned. Shared infrastructure is plumbing only.

## Remaining slices, in order

### S14 — Persistent mapped stream + SSBO foundation
- [ ] Add one bounded context-local persistent/coherent (or explicitly flushed) mapped ring for small changing frame
  payloads. Fence/reuse segments safely; no map/unmap/allocation per frame and no busy polling.
- [ ] Add schema-owned SSBO helpers for structured instance, event, history, material and compact work data. Reflection/
  layout tests compare Python packing with driver-reported/std430 layout where applicable.
- [ ] Migrate only data that benefits: large structured arrays, many instances/events or data shared across passes.
  Tiny fixed frame values may remain uniforms/UBOs if cheaper.
- **Reward:** removes texture-table contortions and repeated Python uniform calls, enables compute/indirect consumers.
- **Hazards:** overwrite-in-flight stalls, alignment/stride drift, runaway capacities. Rings/capacities are fixed/bounded.
- **Bars:** no GPU sync stall in steady traces, exact retirement, no per-frame allocation, CPU submit before/after.

### S15 — Compute, image load/store and atomic primitives
- [ ] Shared compute program/resource helpers with explicit dispatch dimensions, barriers and deterministic GPU test
  harnesses. Add image load/store and atomic/atomic-counter wrappers only as concrete consumers need them.
- [ ] Compute may prepare/compact/evaluate GPU work but may **not** become a second simulation clock. Transition compute
  derives from run progress/real authored seconds. Visualizer compute consumes logical revision/time and bounded snapshot
  history; repeated renders of one logical revision cannot advance state again.
- [ ] Useful first jobs: particle evaluation/compaction, procedural bolt/branch tables, volume injection/advection,
  post-processing kernels, light/cluster lists, active-piece masks and GPU-generated indirect counts.
- **Reward:** moves genuinely parallel work away from Python without introducing render-rate semantics.
- **Hazards:** missing barriers, hidden persistent state, dispatch overprovisioning, readback. No ordinary CPU readbacks.
- **Bars:** CPU mirror/negative controls where feasible, logical-revision replay determinism, measured dispatch/GPU cost.

### S16 — Indirect/multi-draw and GPU compaction
- [ ] Allow compute/CPU-once prepared work to produce bounded indirect draw commands and compacted active-instance lists.
  Use `glMultiDraw*Indirect` only when it replaces material Python submit/draw loops.
- [ ] Stable instance IDs/seeds survive compaction so authored randomness does not shimmer when population changes.
- [ ] No CPU readback of the generated count in the ordinary path; the GPU consumes its own bounded command buffer.
- **Reward:** thousands of active particles/pieces can remain one/few Python submissions.
- **Bars:** same deterministic population/placement as reference; no overrun beyond allocated command/instance capacity.

### S17 — Active-only high-fidelity scene buffers, lighting and materials
- [ ] Extend `SceneTarget` with opt-in RGBA16F HDR and optional normal/material/depth/history attachments. Allocation key
  includes only requested capabilities; ordinary/cheap effects keep the existing minimal target or direct draw.
- [ ] Shared material/light block: energy-conserving GGX/Cook-Torrance BRDF, roughness, metalness/specular, emissive,
  bounded directional/point/spot lights, BRDF LUT and photo/environment image-based lighting.
- [ ] Shared real 3D shadow option: depth map(s), bounded PCF/PCSS-style softness/contact treatment. Keep planar shadows
  where they are both cheaper and visually appropriate. Optional GTAO/contact AO is active-only.
- [ ] Shared transparent path: depth-aware soft particles and weighted blended OIT for smoke/spark/glass-heavy consumers.
- [ ] Shared glass path: thickness/depth-aware screen-space refraction, Fresnel reflection, rough transmission and
  restrained optional dispersion, using owned scene/environment textures rather than mutating lent presentation images.
- **Reward:** coherent high-end materials/light interaction rather than bespoke approximations per effect.
- **Hazards:** full-screen attachment bandwidth/memory. Every attachment/pass has an explicit requesting feature/tier.
- **Bars:** disabled/cheap path allocates none of the new buffers; exact endpoints and existing looks stay untouched.

### S18 — GPU particles, lightning, smoke/fire and volumetrics
- [ ] **Particles:** bounded SSBO pool, deterministic seeded spawn, compute evaluation/compaction, indirect instanced draw,
  soft sprites/streaks/ribbons, optional simple analytic/SDF collision, depth fade and OIT. No CPU object per particle.
- [ ] **Lightning:** stable seeded branching topology per admitted event, travelling intensity/forks, hot emissive core,
  bloom, secondary arcs, short afterglow and optional local-light injection into geometry/smoke. Never rerandomise the
  entire bolt at render cadence.
- [ ] **Smoke/fog/fire:** active-only half/quarter-resolution density/temperature volume or procedural field; bounded curl
  noise/advection/vorticity, event injection, depth-aware raymarch, temporal reprojection, absorption/scattering and
  emissive fire/embers. Quality tiers own volume resolution, ray steps and light samples.
- [ ] **Energy/field effects:** compute/image-driven shockwaves, plasma/nebula, reaction-diffusion surfaces, heat haze and
  force fields with deterministic event/history input.
- **Reward:** the foundation starts producing effects that are awkward or CPU-hostile in Python-driven render paths.
- **Hazards:** volume memory, temporal ghosting, accidental render-rate simulation. Dormant means no allocation/dispatch.
- **Bars:** fixed logical replay gives fixed frames, resource retirement to zero, frame/GPU budget measured by tier.

### S19 — Voxel Sphere promotion onto scene3d
- [ ] Run the existing Sphere promotion golden **before** refactoring: Glass Current + Voxel Bloom persisted snapshots,
  hidden technical profile, deterministic FeatureFrame replay (silence/flat/vocal/kick/sustained), logical outputs,
  representative captures and extreme CUSTOM geometry.
- [ ] Preserve Sphere's descriptor, `sphere_*` state, Settings/presets, logical runtime, section drives, tracer/cohort
  semantics, authored projection and reactivity. Sphere is not a generic 3D base class.
- [ ] Replace only duplicate low-level GPU plumbing with scene3d equivalents: resource lifetime/fences, frame/target,
  DSA buffers, SSBO/instance transport, shared material/light/post pieces and particle/shadow helpers when parity proves
  they are mathematically/visually identical.
- [ ] Sphere becomes an ordinary shared-foundation 3D Visualizer consumer with the standard 3D capability/tier lifecycle.
  Non-selected Sphere remains dormant. After parity, delete superseded Sphere-local low-level infrastructure.
- [ ] New fidelity options (HDR emissive lighting, better shadow interaction, compute particles, smoke/electric coupling)
  come **after** the migration golden and are explicit look changes, never smuggled into the refactor.
- **Bars:** promotion gate in `Docs/Reference/Sphere_Visualizer.md`; zero material change without operator approval.

### S20 — Vertical consumers: make the foundation earn its complexity
- [ ] Page Curl and Blinds → 3D Slats: adaptive surface/material/shadow proofs.
- [ ] Extruded Spectrum: first ordinary 3D Visualizer, SSBO instancing + common material/light proof.
- [ ] Shockwave Grid: displaced grid + bounded event SSBO + emissive/HDR/bloom proof.
- [ ] Reactive Particle Field: compute/compaction/indirect/OIT proof.
- [ ] Spectrum Terrain/Skyline/Tunnel, Waveform Ribbon, Deformable Blob Sphere, Accordion Fold, Relief Rise, Cube Turn.
- [ ] Bubble Depth Field only under Bubble Temporal Fidelity/R-69; depth cannot damp or retime authored response.
- [ ] Once primitives are individually accepted, combine them deliberately: electrical storm terrain, smoke-lit voxel
  fracture, ember/dust destruction, refractive glass lit by bolts, volumetric shockwaves and photo-colour IBL.
- **Rule:** a vertical feature may request foundation extraction, but speculative generic engine layers remain forbidden.

## Cross-cutting performance hazards

Binding lessons from the landed slices (measuring, rendering, motion, settings) live in
`Docs/Reference/Transitions.md` ("3D foundation lessons"); every slice adds what it learned there.


- Render-thread Python GL calls hold the GIL (R-87 freshness, Visualizer hitch evidence): count calls per frame and
  measure CPU submit for every slice that adds a pass.
- No allocation, compile or texture copy per frame; per run or per size bucket only.
- Memory: a transition's scene textures are per display and held from its warm-up (it is the next transition)
  until `park()` after its run; a Visualizer mode's while it is active. Never hold textures for transitions that
  are not next. Every new attachment is measured and justified.
- State: every GL state the foundation touches is fence-restored (framebuffers, blend, uniform-buffer binding).
- Endpoints: every post effect is exactly zero at progress 0 and 1 and at the near-endpoint checks.
- Time: real seconds only for real-time rates; Visualizers only logical time.
- R-63: nothing may expose uncovered frame edges.

## Physical acceptance (open as material slices land)

- [ ] High / Balanced / Performance on both displays with active Visualizers: freshness/frame-spacing tails, first-use
  and warm-run cost, parked memory and transition-end behaviour.
- [ ] New lighting/material/particle/volume features on real photos and representative music, including extreme CUSTOM
  card shapes for Visualizers. Disabled features remain visually and materially cost-neutral.
- [ ] Voxel Sphere migration gets a dedicated before/after golden pass before any new Sphere look option is judged.
