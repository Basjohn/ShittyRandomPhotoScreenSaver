# Future Work

The single live router for **deferred** features and architectural horizons. `Current_Plan.md` owns active work. The
OpenGL 4.6 / modern scene3d / Voxel Sphere / high-fidelity effects program is already promoted, so those items no
longer live here as dormant backlog; their active sequence and technical decomposition are both in `Current_Plan.md`.

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

**Experimental is a product-admission state, not permission to build a second renderer.** Sphere is the legacy exception
because it predates the shared Scene3D program. Any new experimental mode created after that foundation exists must join
the canonical mode registry, logical snapshot contract, shared Scene3D/compute/resource/material/quality substrate,
retirement and dormancy machinery from its first implementation. Its reaction model, private settings namespace and
user-facing admission may remain isolated/default-off while it matures. Promotion to stable should therefore be a
status/default-admission/acceptance change, not a later low-level renderer migration that repeats the work.

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

Voxel Sphere promotion is active: share the GPU substrate, not the Sphere behavioural model.

### 2.5 Shared 3D Settings control plane — deferred product surface

Once S17/S18 have enough optional 3D facilities to justify a coherent user surface, add a dedicated **3D Settings**
section rather than scattering capability switches across transitions and Visualizer pages. The UI vocabulary is:

- one quick global profile: **Auto / High / Balanced / Performance / KAK**;
- every optional expensive facility has an explicit disable path and, where meaningful, an explicit enable/quality
  override rather than being silently forced by the profile;
- `KAK` is the hard minimum-viable ceiling: keep the base geometry/effect needed for the consumer to remain itself,
  disable optional expensive 3D features, and resolve essential densities/sample counts to their lowest bounded values;
- leaving `KAK` restores the user's stored overrides rather than destroying them;
- `Auto` resolves once at configuration/admission from hardware/display/effect context. It is **not** a dynamic per-frame
  quality governor; no FPS chasing, polling or mid-effect quality oscillation;
- transitions and continuously-running Visualizers may share the same UI profile names while resolving through separate
  internal budget tables, because a one-shot transition and a 24/7 Visualizer do not have the same sustainable cost;
- all resolution happens before renderer admission. Renderers receive resolved capability/quality state and never read
  Settings per frame. A disabled feature allocates zero owned targets/buffers/volumes/history.

Sphere's S19 migration and every post-foundation experimental mode should use this capability metadata instead of
private one-off quality switches where a shared 3D facility is genuinely being controlled. Mode-specific artistic
parameters remain mode-owned.

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
- **Fluid lens transition** — refractive displaced surface with caustic-style highlights; requires the active
  refraction/material-buffer work to prove quality without excessive full-screen cost. Output remains SDR-only.
- **Reactive Liquid / Audio Melt Pool Visualizer — distant goal.** Revisit the failed old liquid experiment only after
  compute, refraction, material and shared 3D quality work are mature. **Do not start from SDFs.** A credible first
  architecture is a bounded 2D/2.5D height+velocity field (shallow-water/stable-fluid style) or a bounded deformable
  surface/particle sheet: audio events inject impulses/vorticity, compute advances on Visualizer logical cadence, and
  rendering derives normals, viscosity-like deformation, Fresnel/refraction, wet highlights and restrained caustic
  treatment. The existing Melt transition is useful visual-language evidence that SRPSS can render convincing viscous
  smear/liquid highlights, even though Melt deforms a source texture; a liquid Visualizer may instead use palette colour,
  photo/environment IBL or a deliberately abstract material. Avoid full 3D SPH/fluid simulation unless a later measured
  need justifies the cost. Disabled/dormant means no simulation field allocation or dispatch. This sits **behind** the
  current S14-S20 3D program and is not an admission to implement it early.
- **Holographic depth slices** — photo/spectrum sampled into layered depth planes with scanline/light-volume treatment;
  useful only if it reads as real depth rather than a stack of cards.
- **Procedural storm scene** — lightning, rain streaks, smoke/fog and reflected light integrated into one Visualizer;
  admission waits until each primitive is independently cheap and lifecycle-safe.

## 5. Other deferred product work

- **Non-3D maintenance queue migrated from the old Current Plan** — keep these deferred unless a supplied log/physical
  defect makes one immediately relevant: ImageWorker lean spawn entry (R-99), `--usage` sampler diagnostic cost, Gmail
  refresh handle slope, Widgets-tab stale position estimates, overfull authored-display planner cost, Weather child-edit
  loading height, surface-preference SSOT cleanup, flicker diagnostic CLI migration, narrowing the broad Qt-test slot-miss
  suppression, global Python installation hygiene, Spectrum extreme-viewport smoothness and installed GODZIP Foundry
  Windows diff acceptance.
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
