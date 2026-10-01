# Future Work

The single live router for **deferred** features and architectural horizons. `Current_Plan.md` owns active work. The
2026-09-30 operator direction promoted the OpenGL 4.6 / modern scene3d / Voxel Sphere / high-fidelity effects program,
so those items no longer live here as dormant backlog; their active order is in `Current_Plan.md` and their technical
decomposition is in `Docs/Future_Work/3D_Scene_Foundation.md`.

## 1. Authority and activation

This file is not active sequencing. An agent may implement an item only when the operator explicitly asks for it or
`Current_Plan.md` has no important active work. A real prerequisite may become the opening slice of a requested item;
unfinished unrelated work is not a reason to refuse an explicit operator request.

For substantial work, create or reuse one focused live decomposition that inventories the current foundation, pins a
rollback/comparison HEAD, defines state/cadence/resource/Settings ownership, separates automated/performance/physical
acceptance, and is deleted when the feature closes. Build a vertical feature first; extract shared infrastructure only
where the implementation proves reuse.

## 2. Admission rules for new effects

### 2.1 Every transition or Visualizer idea

- Record the visual/temporal contract and rollback reference before coding.
- Classify it as a new transition, an option of an existing transition, or a distinct Visualizer mode.
- Use the one Qt Quick scene, canonical descriptors/defaults/Settings, lazy implementation resolution and existing
  retirement owners. No parallel experimental engine, private scheduler or Settings shadow tree.
- Deterministic seeds/inputs, bounded state, context-loss/resource retirement and disabled dormancy are required.
- A shader compiling or an offline preview is not acceptance. Use real Quick rendering, measured frame/GPU/CPU cost,
  real photos and multi-display evidence where material.
- Rejected experiments are removed cleanly. Do not keep dead branches for hypothetical future revival.

### 2.2 Transitions

Transitions consume the monotonic transition run and may evaluate analytic geometry/physics from it. They do not own a
second clock. Per-run geometry/options are solved once at request/COMPUTE preparation or lazily once in the renderer.
Exact endpoints, near-endpoint continuity, R-63 black=0 and existing departure rules remain binding.

### 2.3 Visualizer modes

Each mode has one descriptor, one lazy logical/runtime/renderer/Settings implementation and explicit clip policy.
`VisualizerLogicalRuntime` remains authored time. A renderer or compute dispatch may not turn display refresh into
simulation cadence. History remains bounded and restartable from the immutable logical snapshot contract. Bubble's
temporal/amplitude golden remains binding even when shared 3D presentation is used.

### 2.4 Shared 3D foundation

The shared foundation is now active work, not future work. The durable architectural rule remains:

- one shared low-level GPU/resource/material/post/compute substrate;
- effect/mode-specific motion, reaction and Settings stay local;
- no generic always-resident scene graph/physics engine;
- no Python object/draw call per particle/shard/voxel;
- every expensive target/buffer/volume/history exists only while an active consumer needs it;
- `park()` or Visualizer retirement releases consumer-owned transient resources;
- quality tiers bound sample counts, grid/volume resolution, particle counts and post work;
- no timer/poller/forced frame to service graphics work.

Voxel Sphere promotion is explicitly active as of 2026-09-30: share the GPU substrate, not the Sphere behavioural model.

## 3. Graphics API horizon after OpenGL 4.6

Do **not** begin this while modern OpenGL meets the product's needs. The 4.6 program exists specifically to avoid paying
for a backend abstraction before a concrete ceiling appears.

A future backend program becomes justified only by measured need that OpenGL 4.6 cannot reasonably satisfy, such as:

- hardware ray tracing / path-traced reflections, GI or large-area soft shadows;
- a proven need for explicit asynchronous compute/transfer queues;
- a driver/platform compatibility problem that materially affects users;
- GPU submission/memory control that remains a bottleneck after DSA, persistent mapped buffers, SSBOs, compute and
  indirect draws are already used correctly;
- a platform target where OpenGL support itself is the blocker.

If that gate opens, investigate **one QRhi-based renderer substrate**, not separate handwritten GL/D3D/Vulkan engines.
Prove identical rendering/resource semantics first on OpenGL, then D3D11/12 or Vulkan as appropriate. Native Vulkan or
D3D12 escape hatches are justified only for a capability QRhi cannot expose (for example hardware ray tracing), and
must remain isolated rather than contaminating ordinary render ownership.

## 4. Deferred visual ideas beyond the active first wave

The current plan already promotes Page Curl, 3D Slats, Extruded Spectrum, Shockwave Grid, Reactive Particle Field,
Spectrum Terrain/Skyline/Tunnel, Waveform Ribbon, Deformable Blob Sphere, Accordion Fold, Relief Rise, Cube Turn and
Bubble Depth Field. The following ideas remain future-only until that active wave proves the relevant primitives:

- **Volumetric music chamber** — persistent but bounded 3D fog volume with light shafts and spectrum-driven emitters;
  only if the active smoke/lighting work proves temporal reprojection and volume cost are healthy.
- **Audio aurora / ribbon volume** — layered translucent ribbons with OIT, anisotropic glow and slow logical-history
  advection; must not become a render-rate simulation.
- **Photo fracture portal** — source image becomes a depth-bearing shell around a destination-space portal; needs robust
  depth/refraction/material work before it is more than a gimmick.
- **Voxel morph field** — blocks rearrange between deterministic shapes or spectrum topology using SSBO/compute
  compaction. Keep distinct from accepted Voxel Sphere reaction semantics.
- **Fluid lens transition** — refractive displaced surface with caustic-style highlights; requires active refraction and
  HDR work to prove quality without excessive full-screen cost.
- **Holographic depth slices** — photo/spectrum sampled into layered depth planes with scanline/light-volume treatment;
  useful only if it reads as real depth rather than a stack of cards.
- **Procedural storm scene** — lightning, rain streaks, smoke/fog and reflected light integrated into one Visualizer;
  admission waits until each primitive is independently cheap and lifecycle-safe.

## 5. Other deferred product work

- **Settings FlowContainer polish [LOW]** — only for a demonstrated Settings layout problem; improve alignment/space
  use without restructuring lazy ownership.
- **Wallpaper feed consolidation** — reuse FEEDS normalization/image-candidate primitives only where that simplifies the
  wallpaper engine without merging its cache/scheduling authority into FEEDS last-good state.
- **Optional persistent shader/program cache** — consider only for a measured residual cold-compile hitch on current
  drivers after the existing gradual warm-up. Admission requires improvement beyond the warm-up already implemented.
- **Bindless/sparse texture extensions** — extension-only research, never a baseline dependency. Revisit only when a
  concrete consumer would materially benefit and a portable fallback would not become permanent duplicate complexity.

## 6. Not backlog

Implemented/accepted work stays in `Spec.md` / `Docs/Reference/`; rejected work stays historical. Runtime widget themes,
Games You Follow, volume/mute OSD, Glass Shatter, Crumble, Exploding Tiles, Directional Pixel Accretion, Ink Bloom,
Melt Drip and Slide → Perspective Push are not reopened without a concrete defect or explicit extension request.
Tendril Reveal remains rejected/retired.

Capability terminology remains: *activated/deactivated* is the application-level capability gate; *enabled/disabled*
is feature/instance state inside an activated capability.
