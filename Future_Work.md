# Future Work

Last updated: 2026-09-04

Long-horizon feature / new-implementation backlog.

## Authority / activation rule

`Future_Work.md` is **not active sequencing by default**. Normal work continues to be owned by
`Current_Plan.md` and `Future_Cleanup.md` unless the operator deliberately selects a future item.

An agent may implement work from this file only when **either**:

1. the operator explicitly asks for a named `Future_Work.md` item; **or**
2. `Current_Plan.md` contains no remaining important active work and no **READY** cleanup row in
   `Future_Cleanup.md` is scheduled ahead of the feature. `DELETE AFTER HORIZON` / `J EXIT` rows are dormant
   gates and do not block unrelated future work merely by existing.

**Operator override:** an explicit request for a named `Future_Work.md` item overrides the normal sequencing above.
Unfinished `Current_Plan.md` or `Future_Cleanup.md` work is not, by itself, permission to refuse or defer that named
future item. Only a genuine technical prerequisite required to implement the requested item safely may block direct
implementation. Where practical, satisfy that prerequisite as the opening subphase of the requested work instead of
deferring the feature wholesale. Preserve unrelated active work and its rollback boundaries while doing so.

Merely encountering, reading, indexing or cross-linking this file is **not** permission to begin one
of these features.

Normal priority:

```text
Current_Plan.md active work
        ↓
Future_Cleanup.md scheduled READY debt/deletion work
        ↓
Future_Work.md new features / experiments
```

This file exists so good ideas survive without expanding current scope. Technical notes are deliberately
provisional; future implementation must inspect the **current** Qt Quick architecture before coding.

### Decomposition rule for large / architecturally unique work

When a requested implementation is long, sizeable, or architecturally unique, create and commit a detailed
implementation decomposition **before substantial coding** if a current one does not already exist. The decomposition
is a continuation artifact, not ceremony: a later agent must be able to resume safely if the original implementer runs
out of quota or stops mid-slice.

At minimum it must:

1. inventory the current relevant foundation and point to the real source/tests that already own it;
2. pin a pre-implementation rollback/comparison HEAD;
3. define state, cadence, Settings, presentation, GPU/resource and retirement ownership;
4. classify new primitives as **feature-local**, **justified reusable infrastructure**, or **speculative reuse deferred**
   until another concrete consumer proves the abstraction;
5. decompose the work into resumable checkpoints that leave the repository coherent whenever practical;
6. define deterministic/source-level, lifecycle/resource, performance and eyes-on visual acceptance bars separately;
7. keep an explicit landed/remaining status so partial completion is not mistaken for finished architecture.

Do not spend a first implementation pass building speculative infrastructure merely because later features might need it.
Build the requested vertical feature, extract only reuse justified by the real implementation, and record attractive but
unproven abstractions in the decomposition for a later second-consumer decision.

Runtime Widget Themes, their semantic resolver/linking/Custom model and the shared Style Overrides surface
are **landed current architecture**, not future work. Their durable contract belongs in `Spec.md` and the
Settings/Widget Theme architecture documents. Do not use this backlog to reopen that foundation.

Capability terminology must follow the final landed contract even in future designs:

```text
activated / deactivated
    = application-level capability gate

enabled / disabled
    = ordinary feature/instance state inside an activated capability
```

Do not revive old presenter, disabled-family, or dual-authority terminology just because a future idea
was originally written before those migration contracts landed.

All future performance-sensitive features also inherit `Docs/Guardrails/Performance_Optimization_Contract.md`. Feature cost must be measured without weakening current freshness/reactivity or replacing bounded useful caches/resources with latency-heavy churn.

---

# 1. Post-migration visual-effects architecture

Assumed destination:

```text
cheap canonical catalog metadata
        ↓
lazy internal implementation resolution
        ↓
QQuickItem / QSGRenderNode
        ↓
direct OpenGL inside the Qt Quick scene
```

Quick 3D Block Spins has already proved that this path can own real mesh geometry, depth-tested faces,
context-local VAO/VBO state and custom shaders inside the Quick scene. Future work is therefore not
limited to fullscreen 2D fragment effects.

A genuinely new transition should normally be:

```text
cheap descriptor/catalog entry
        +
one lazy implementation module
        +
authored shader/mesh/per-run state
        +
focused tests + visual oracle
```

Do not return to a central compositor switch where every new effect modifies the whole orchestra.
A failed visual experiment should be removable by deleting/modifying its isolated descriptor,
implementation and tests.

This remains internal plugin-shaped architecture, not a third-party plugin SDK.

### Shared 3D dormancy rule

Future 3D support follows the same admission/dormancy contract as the feature that consumes it. If every admitted
3D-dependent Visualizer mode / transition implementation is dormant, **meaningful 3D-only overhead must also be dormant**.
Do not compile 3D-only shaders, allocate meshes/VAOs/VBOs, retain effect-specific GPU resources, perform depth-specific
per-frame work, start workers, or create another cadence merely because reusable 3D code exists in the repository.
Heavy implementation modules should continue to resolve lazily at the consuming renderer boundary.

Cheap/import-safe pure math, immutable types, tiny shader/resource contracts and canonical catalog metadata may remain
shared/eager when their runtime/resource cost is effectively nil and centralizing them prevents duplication. Do not contort
the architecture to make zero-cost helpers artificially lazy. The boundary is **meaningful owned work/resources**, not a
ritual requirement that every helper live behind an import gate.

Shared 3D infrastructure should therefore be dependency-light at import, while context-local programs, meshes and other
costly assets belong to the admitted renderer and are released on retirement/context loss. There must never be a hidden
"3D subsystem" ticking or holding heavy resources in the background when all of its real consumers are disabled/dormant.

For a **deactivated** transition: keep cheap metadata available, exclude it from Random/Cycle, do not
import heavy implementation solely for catalog construction, do not compile effect shaders, do not
create effect-specific GL resources, and do not run effect-specific timers/workers.

Future transitions/options consume the final monotonic transition run. They may author internal
deformation/easing/physics deterministically from that sample but do not become another clock.

Permanent post-H safety rules apply to every future visual/transition experiment:

- **R-69 Visualizer reactivity is golden.** Geometry/aspect adaptation may reframe, reflow, project or presentation-smooth, but must not globally compress authored musical response, head/radius amplitude, motion, Ghost/history displacement, transient strength, or source freshness as a viewport becomes wide/tall. State already normalized/projected into renderer-content coordinates is consumed exactly once. If an extreme visual tail is too large, target only that proven tail.
- **R-63 black=0 outranks exact shared-edge cover.** A bounded one-device-pixel overshoot is preferable to resurrecting black/stale flashes. Any future seam/coverage change must derive native device geometry from actual monitor rectangles/DPR and remain valid across different resolutions, coordinates, monitor ordering and mixed 1.0/1.25/1.5/1.75/2.0 DPR rather than hard-coding the operator's current pair.
- Future performance work follows `Docs/Guardrails/Performance_Optimization_Contract.md`: remove measured useless allocation/work and target latency tails/resource growth, not authored cadence, source/snapshot freshness, reaction amplitude, bounded useful caches or black-flash safety.

Performance rules:

- no Python/QObject object per shard/tile/pixel/particle;
- no GL draw call per shard/tile/pixel/particle;
- use instancing for repeated geometry;
- generate fracture/mesh data once per run when practical;
- reuse source/destination textures;
- derive per-piece state from compact deterministic seeds;
- bound blur/refraction/trail samples;
- adapt quality to measured cost/resolution;
- preserve the common Quick GL-state fence.

---

# 2. Slide — optional effects inside the one canonical Slide transition

**Elastic, Wobble, Flex and Perspective are options inside Slide, not separate transitions.**

Do not create separate transition IDs or separate Random/Cycle entries. `Slide` remains one canonical
transition identity.

Base Slide remains cardinal-only, uses one canonical progress sample, has mathematically sealed
source/destination coverage, and exposes no black/unowned microgap.

## 2.1 Elastic option

Subtle arrival overshoot/rebound/settle evaluated analytically from normalized canonical time.

Candidate shape:

```text
canonical progress
    -> sealed Slide coverage
    -> analytic damped spring modifier
    -> modifier exactly zero at completion
```

Do not integrate spring state from frame delta and do not create physical source/destination separation
that exposes background.

## 2.2 Soft Wobble option

Gentle perpendicular organic flex during travel that decays completely at settlement.

Candidate:

```text
warp = perpendicular_direction
       * amplitude(t)
       * sin(spatial_frequency * position + phase(t))
```

A second low-frequency harmonic can reduce synthetic appearance. Use a bounded UV warp or a modest
tessellated mesh. Coverage must remain sealed.

## 2.3 Rubber-Sheet / Flex option

Leading edge moves first while the rest stretches/catches up.

Candidate:

```text
local_t = clamp(global_t + flex_amount * shape(position_along_axis), 0, 1)
```

A modest tessellated mesh is likely appropriate. Final frame collapses exactly to destination.

## 2.4 Perspective Push option

Mild true-3D Slide presentation: source tilts slightly away and/or destination pushes into plane while
moving.

Use shallow card geometry, modest perspective, restrained yaw/pitch/Z and a sealed-coverage strategy.

## 2.5 Combination policy

Some modifiers may compose, e.g. small Wobble during travel plus Elastic settlement. Do not expose
every possible cross-product automatically. All modifiers share the one Slide run/coverage owner.

---

# 3. Glass Shatter

Old image fractures into convincing glass-like shards that break away in a selected direction or from
a **Center Out** impact, revealing destination beneath.

Initial modes:

- Left;
- Right;
- Up;
- Down;
- diagonal TL -> BR;
- diagonal TR -> BL;
- Center Out.

Directional activation should use centroid projection + bounded seeded jitter. Center Out uses radial
distance + jitter. The eye should read one coherent break wave, not random disappearance.

Generate one deterministic fracture mesh once per run. Candidate: seeded normalized sites,
Voronoi/Delaunay-style cells (or bounded irregular substitute), triangulated once and uploaded in
compact buffers with per-shard centroid/activation/launch/rotation/Z/edge metadata.

After activation, shards have analytic XY impulse, real Z travel, arbitrary 3D rotation axis,
angular velocity, optional gravity, and directional/radial launch bias. Avoid frame-by-frame CPU physics.

Glass appearance should prioritize convincing bounded rendering:

- true perspective/depth;
- source texture continuously mapped across original fracture coordinates;
- bright edge/Fresnel response;
- cool/white edge tint;
- specular from transformed normal;
- subtle transmissive/desaturated body;
- optional tiny refraction offset;
- backside darkening/alternate sheen;
- destination full-screen underneath.

Planar shards with real 3D rotation are acceptable initially. Add shallow extrusion only if it
materially improves the look. No ray tracing or unbounded blur/refraction.

Validation: deterministic fracture, directional/Center Out falloff, exact endpoints, destination
always underneath departed shards, actual depth/rotation, bounded resources, clean dormancy/release,
and later eyes-on glass/specular/edge quality.

---

# 4. Exploding Tiles

Structured tiles launch out of the image plane with real 3D rotation/depth while progressively
revealing destination.

Distinct from Block Puzzle Flip (pieces leave the plane), Crumble (regular rather than organic), and
Glass Shatter (solid regular pieces rather than irregular glass).

Strong candidate for instancing: one quad or shallow cuboid mesh; per instance derive grid coordinate,
UV rectangle, activation delay, seeded rotation, launch vector, Z impulse and optional shrink from
`gl_InstanceID`, grid size and seed.

Modes may include Center Out, cardinals, diagonals, and later seeded impact point.

Bounded visual additions: key light, mild specular, shaded side faces, short motion ghost, slight
scale reduction, destination underlay.

---

# 5. Directional Pixel Accretion

Working name: **Directional Pixel Accretion**. Alternatives: Pixel Build, Pixel Drift Build,
Pixel Cascade.

Destination rapidly assembles from many visible micro-tiles. At run start one direction resolves and
**every micro-tile follows that same event direction**.

For a bottom-left event:

```text
one destination micro-tile slides into target
        ↓
another follows from the same direction and lands next/over it
        ↓
thousands rapidly accrete in a coherent directional wave
        ↓
complete destination image
```

Actual translation is essential; this must not become a pixel dissolve/reveal.

Target directions should include at least the eight compass directions. Random resolves once per run.

Preferred implementation: one instanced micro-quad draw over fullscreen source underlay.

For an NxM grid:

- derive row/column from `gl_InstanceID`;
- derive deterministic activation variation from row/column/seed;
- derive target position/UV analytically;
- derive local progress from canonical time + activation rank;
- translate from offset along event vector into final target;
- sample destination texture using final tile UV rectangle.

Example only: 2560x1440 at 8x8 visual micro-tiles is about 57,600 instances. The actual adaptive cap
must be measured; 4K should enlarge visual tile size as needed.

Primary activation rank:

```text
rank = projection(target_position, event_direction)
```

Add small bounded seeded variation and optional low-frequency orthogonal noise so the front is coherent
but organic.

To sell the "another slides on top" piling feeling: use tiny analytic Z/depth or deterministic ordering,
slight temporary oversize/height bump, then exact target bounds.

Optional ghost/motion trail: one/two faded echo instances or a second instanced draw for short offset
copies. Avoid full-screen multi-sample motion blur.

Endpoints: exact source at 0; source remains underneath during run; exact fullscreen destination at 1.

---

# 6. Organic-feeling transition ideas

General goal: effects that feel grown, fluid, torn, burned, cellular or materially organic rather than
rectangular UI animations.

## 6.1 Organic Growth / Ink Bloom

Destination grows through several irregular connected fronts like ink, lichen or pigment spreading.

Cheap candidate: small seeded growth centers + distance field + domain-warped FBM/noise + advancing
threshold + thin wet/colored edge. Do not CPU flood-fill each frame.

## 6.2 Tendril / Vein Reveal

Branching lines spread and thicken until destination takes over.

Candidates: flow field + warped ridge noise, several analytic branch seeds, or one deterministic
low-resolution growth mask generated once and animated by threshold.

## 6.3 Melt / Drip

Source softens/runs in a gravity direction while destination is revealed.

Candidate: seeded per-column/region thresholds, bounded UV stretch near melt front, a few analytic
rounded drips, destination underlay, no general fluid simulation.

Avoid raymarching for prestige, unbounded iterative simulation, per-pixel CPU state, and giant blur
chains.

---

# 7. Future 3D visualizer experiments

These preserve `VisualizerLogicalRuntime` as the authored logical clock. Presentation may not discard
logical steps or turn render refresh into simulation cadence.

**Unique Mode means a real mode boundary.** Each experiment labelled `Unique Mode` gets one canonical descriptor plus its own lazy mode-local logical/runtime/renderer/Settings implementation. It may reuse shared analysis bands, direction vocabulary, shader utilities and proven math, but it must not parasitically run another mode's active runtime, install a second visualizer clock, or create an ad-hoc six-way switch outside the descriptor seam. A Bubble-derived or Spectrum-derived experiment may borrow contracts/equations while remaining independently dormant when disabled.

## 7.1 Deformable 3D Sphere / Blob Sphere experiment - Unique Mode

The project once had a lost visualizer remembered as **Blob** that could never be rebuilt correctly.
This is **not** a promise to reconstruct that historical effect from memory.

Instead, experiment with a new real three-dimensional sphere/orb that rotates in 3D and continuously
deforms its physical surface in response to music.

This is the primary planned consumer of the Phase-D **frameless visualizer shell** seam:

```text
shell_policy = FRAMELESS
clip_policy  = VIEWPORT_RECT
```

It should appear as a free-standing 3D object with no rectangular card fill, frame/border or card
shadow. It still renders inside the normal visualizer Quick item/QSGRenderNode, participates in the
same fade/lifecycle/generation ownership, and stays inside its assigned transparent viewport.

### 7.1A Existing foundation — inspect before inventing

The Sphere is deliberately ambitious, but it does **not** start from an empty renderer. Before designing new substrate,
inspect the current architecture below. These are reconnaissance pointers, **not mandated reuse**: reuse current contracts
that fit, extend them minimally where the Sphere proves a need, and do not cargo-cult transition-specific projection/math
or distort an existing helper merely to claim reuse.

1. **Static mesh allocation/lifetime** — start with
   `rendering/quick/transitions/implementations/block_spins.py` and the OpenGL-free authored mesh/shader contract in
   `rendering/gl_programs/blockspin_program.py`. Block Spins already proves static vertex data, VAO/VBO ownership and
   explicit release inside the Quick scene.
2. **Perspective / aspect-correct projection** — start with the current Visualizer presentation/geometry/render-frame
   contract and `FRAMELESS + VIEWPORT_RECT`. Block Spins is a useful shallow-3D transform precedent, but the Sphere should
   add only the minimal true-perspective/aspect-correct projection actually required rather than copying transition math.
3. **Model/view/projection transforms** — inspect the current Quick matrix handoff in
   `rendering/quick/visualizer/render_contract.py` and the transformed 3D geometry in
   `rendering/gl_programs/blockspin_program.py`; introduce a reusable MVP helper only if the Sphere makes that boundary real.
4. **Depth-state handling** — inspect `rendering/quick/visualizer/render_host.py`,
   `rendering/quick/visualizer/clip_host.py`, and `rendering/quick/transitions/implementations/block_spins.py`. The common
   Qt Quick GL-state fence already owns preservation/restoration of depth/cull/depth-write state.
5. **Shader program/resource ownership** — follow the lazy Visualizer implementation contract in
   `rendering/quick/visualizer/implementation_registry.py`, the render host, existing Visualizer implementation modules,
   and `rendering/quick/render/gl_resources.py`. Shader programs/resources remain context-local renderer ownership.
6. **Proper resource retirement/recreation** — reuse the renderer `release_resources()` contract and current lazy
   implementation/context lifecycle. Retirement/context loss must leave no Sphere mesh/program resource behind.
7. **Vertex-shader deformation** — new Sphere-local authored work initially. Reuse shader/program conventions, not a new
   simulation owner; never upload rebuilt sphere topology every frame.
8. **Deformed normals** — new Sphere-local shader work initially. Keep tangent-offset/normal reconstruction local unless a
   later concrete deforming-mesh consumer proves a reusable primitive.
9. **Directional lighting** — `rendering/gl_programs/blockspin_program.py` is a current normal/light/specular precedent.
   Resolve the project's existing direction vocabulary into Sphere configuration rather than creating a live dependency on
   Widget shadow state.
10. **Fresnel/specular/material parameters** — Block Spins supplies only precedent for bounded lit 3D shader treatment.
    Sphere material semantics remain Sphere-local initially; shared lighting helpers are justified only when they are truly
    presentation-neutral.
11. **Viewport resize behavior** — inspect `VisualizerModePresentationPolicy`, `VisualizerShellPolicy.FRAMELESS`,
    `VisualizerClipPolicy.VIEWPORT_RECT`, `tests/test_qtquick_visualizer_geometry.py`, and
    `tools/qtquick_visualizer_clip_smoke.py`. Preserve the existing whole-scale vs viewport-extent contract.
12. **Deterministic authored-time animation rather than render-frame physics** — preserve `VisualizerLogicalRuntime` and
    the isolated mode-owned logical/frame runtime as the clock/state authority. The Sphere renderer consumes authored
    state/time; render refresh never advances simulation.

### 7.1B First-consumer reusable-infrastructure policy

Treat the Sphere as the first **demanding consumer** of reusable SRPSS 3D rendering primitives, not as permission to build
an SRPSS general-purpose 3D engine before the object exists.

Likely reusable candidates, **if the Sphere implementation actually justifies them**, include:

- static mesh/buffer ownership and context-local release helpers;
- aspect-correct perspective and small model/view/projection math helpers;
- safe depth/cull/depth-write state handling that composes with the existing Quick fence;
- common shader/program/resource lifetime helpers;
- a bounded presentation-neutral lighting-direction resolver;
- tiny lit-mesh shader/math utilities only where they do not encode Sphere semantics.

Keep Sphere-specific deformation fields, spherical-harmonic/lobe/noise choices, audio-to-deformation mapping,
deformed-sphere normal strategy, material identities (**Chrome / Obsidian / Magma / Silver**) and authored behavior local to
the mode unless a later second concrete consumer proves an abstraction worthwhile.

Do **not** pre-build a general scene graph, camera framework, material-class hierarchy, 3D object system or generic physics
engine. When reuse looks plausible but is not yet justified, record the candidate in the Sphere decomposition rather than
abstracting speculatively.

The shared-3D dormancy rule above applies recursively: if Sphere and every other future consumer of an extracted 3D helper
are dormant, any meaningful-cost helper-owned resources/work must also be absent. Cheap pure math/types may stay shared.

Before implementation, if no current detailed Sphere implementation decomposition exists, create and commit one first per
the decomposition rule above. It must include this foundation inventory, the rollback boundary, ownership/lifetime map,
reusable-vs-local decisions, resumable checkpoints and separate deterministic/performance/eyes-on acceptance bars.

Visualizer viewport resizing is a current destination requirement. Any future sphere must therefore use aspect-correct
projection so wider/taller viewports reveal or reframe more space without turning the sphere into an ellipse. Whole-size
corner/scroll resize scales it uniformly; edge viewport resize changes framing/aspect.

The sphere must expose bounded material/lighting options rather than baking one look into the mode. At minimum, preserve design space for **Chrome**, **Obsidian**, **Magma** (including bounded emissive/flow treatment) and **Silver**, plus gloss/specular controls. Material choice is presentation configuration only: it must not add another cadence, per-frame Python material rebuild, or independent resource owner.

Cheap shape:

```text
one static sphere mesh
    +
one vertex-shader deformation pass
    +
one lit fragment shader
    +
one/few draw calls
```

Prefer an evenly distributed icosphere or similar modest static mesh. No per-vertex Python objects and
no per-frame CPU topology rebuild.

Each vertex begins at unit-sphere position `p`; the vertex shader computes:

```text
position' = p * (base_radius + displacement(p, audio_state, authored_time))
```

Possible audio/deformation layers:

- bass -> broad bulges/global breathing;
- low-mid -> several large lobes;
- mids -> smaller moving surface forms;
- highs -> restrained fine ripples;
- very low-amplitude procedural noise -> organic continuity.

Avoid an "audio hedgehog" where every bin becomes one spike.

Potential fields: low-order spherical harmonics, directional lobe functions, 3D noise,
domain-warped noise, driven by compact existing analysis bands.

Rotation derives from authored time/state, never degrees-per-rendered-frame. Possibilities: slow base
rotation, transient acceleration/twist, bounded drifting axis, preset-controlled amount.

Lighting is essential. For a proper version derive deformed normals in the vertex shader by evaluating
the deformation field at two small tangent offsets and crossing displaced tangents. This allows
specular light to crawl over the actual changing dents/bulges without CPU normal rebuilds. Reuse the project's existing eight-way direction vocabulary/resolver for key-light direction, and it may default from the current global shadow direction when the mode/preset is resolved. Do **not** create a live per-frame dependency on Widget shadow state: the resolved Visualizer configuration/preset owns the light direction for the active mode.

Candidate fragment stack:

- restrained directional/key light;
- body color/gradient;
- specular;
- Fresnel/rim;
- optional subtle audio-driven emission;
- correct depth.

Later experiments may try gel/translucent/glass materials, but not before basic geometry is compelling.

Goal: an organic deforming body, not an oscilloscope wrapped around a ball.

Performance target: one sphere draw and no per-frame CPU vertex upload. Quality knobs are subdivision
level, number of field layers, deformed-normal cost and fragment-lighting complexity.

Validation: actual Z/depth geometry, deterministic deformation, independent band response, arbitrary
3D rotation, normals/specular consistent with deformation, no render-frame-driven logical simulation,
clean resource release/dormancy, and subjective confirmation it reads as a deforming 3D body.

## 7.2 Extruded Spectrum - Unique Mode

Instanced shallow 3D columns: one cuboid mesh, 32–128 instances, per-instance height/color/energy,
restrained lighting/specular and mild perspective/orthographic depth.

## 7.3 Waveform Ribbon - Unique Mode

Oscilloscope/Sine-like state as a 3D ribbon with a few hundred vertices, amplitude on Y,
authored phase/history through X/Z twist, neighboring-sample normals and bounded ghost ribbons.

## 7.4 Bubble Depth Field - Unique Mode

Shallow Z/depth presentation option without changing Bubble logical motion **or R-69 response amplitude**. Depth/parallax must not become a viewport-dependent damping term. Prefer instanced billboard
sphere impostors with analytic normals/specular, per-bubble Z from authored state, depth ordering and
subtle parallax.

## 7.5 Reactive Particle Field - Unique Mode

Bounded 3D instanced point/quad field driven by existing analysis. Prefer hundreds/low-thousands in
one/few draws. Persistent state, if truly required, belongs to proper logical/runtime ownership.

## 7.6 Spectrum Terrain - Unique Mode

Spectrum/history mapped onto a modest grid mesh: current spectrum across one axis, short retained
history into depth, a few thousand vertices, displacement from compact data/texture, normals/lighting.

---

# 8. Future experiment workflow

For a genuinely new transition/visualizer implementation:

1. record visual contract here or in a focused note;
2. add cheap descriptor metadata with the capability **deactivated/dev-gated by default** during
   development;
3. implement one isolated lazy renderer;
4. use deterministic input/seed;
5. add endpoint/lifecycle/state tests;
6. add production-shaped Quick GL smoke/capture oracle where useful;
7. inspect visually;
8. measure frame/GPU cost at representative resolution/refresh;
9. if it looks poor, modify or delete the isolated implementation without preserving it for sunk cost;
10. only after it is worth keeping, add polished Settings/defaults/docs;
11. commit + push bounded work.

For an option inside an existing transition such as Slide Elastic/Wobble/Flex/Perspective, extend the
single existing implementation/descriptor rather than manufacturing a new transition identity.

---

# 9. Current idea priority — not active sequencing

This is priority **inside Future Work only**. Unless the operator explicitly selects a named item under the
**Operator override** above, `Current_Plan.md` and any scheduled **READY** cleanup still outrank it; dormant
compatibility-horizon/J-exit rows do not.

1. **Widget hover/click glow** — operator-requested bounded interaction polish; shared swatch, event-driven
   hover/click pulse, no polling/timers/thread owner;
2. **Slide optional motion styles** — Elastic first, then Wobble/Flex/Perspective inside Slide;
3. **Deformable 3D Sphere / Blob Sphere experiment**;
4. **Directional Pixel Accretion**;
5. **Glass Shatter**;
6. **Exploding Tiles**;
7. **Organic Growth / Ink Bloom** prototype;
8. other 3D visualizer experiments after final J validation;
9. **Settings FlowContainer polish [LOW]** where it genuinely improves alignment/space use;
10. **Optional true two-texture artwork crossfade [LOW]** only if the current event-driven fade still has a
    demonstrated visual discontinuity worth the extra texture residency.

Glass Shatter, Directional Pixel Accretion and the Deformable 3D Sphere are worth preserving even if their
first prototypes are abandoned. Their intended identities should not collapse into generic `shatter`,
`pixel dissolve`, or `audio sphere` effects.

Runtime frosted/glass ordinary-widget cards remain **rejected/shelved**, not a queued feature. Reconsider
only if a future renderer architecture independently justifies the capability; begin from the rejected-
experiment record rather than reviving 2026-09-02 debris.

---

# 10. Operator-requested UI polish contracts

## 10.1 Widget glow on hover / click

Add two Interaction controls: **Widget Glow on Hover** and **Widget Glow on Click**, with one shared glow
colour swatch. The visual should pulse in relation to cursor interaction and decay when hover/click state
ends. Implementation must be event/state driven: no recurring timer, poller, worker, or thread-contention
owner. Prefer one shared retained visual primitive rather than per-widget implementations.

## 10.2 Settings FlowContainer polish [LOW]

Use FlowContainers in additional Settings sections only where they materially improve alignment and space
usage. This is presentation polish, not permission to restructure settings ownership or eagerly construct
otherwise lazy bodies.

## 10.3 Optional artwork crossfade [LOW]

The current shared artwork/metadata fades are landed and belong to current physical validation, not future
architecture work. A true outgoing+incoming two-texture artwork crossfade is a separate optional experiment
only if eyes-on validation proves the current fade insufficient. Measure texture residency and transition
cost before keeping it.
