# Future Work

Last updated: 2026-09-12

Long-horizon feature / new-implementation backlog.

The operator may promote selected backlog work into `Current_Plan.md`. `FWPlan.md` is the compact router/order for dormant implementation only; detailed active execution lives in `Current_Plan.md` or a focused decomposition.
This document retains dormant feature intent, durable architecture rules and relative priority. It must not become an active experiment/status diary.

## Authority / activation rule

`Future_Work.md` is **not active sequencing by default**. Normal work continues to be owned by
`Current_Plan.md` and `Future_Cleanup.md` unless the operator deliberately selects a future item.

An agent may implement work from this file only when **either**:

1. the operator explicitly asks for a named `Future_Work.md` item; **or**
2. `Current_Plan.md` contains no remaining important active work and no **READY** cleanup row in
   `Future_Cleanup.md` is scheduled ahead of the feature. `DELETE AFTER HORIZON` rows are dormant
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

### Experimental isolation + Settings single-authority gate

For a genuinely new experimental Visualizer mode, transition identity, widget family, or other independently removable
feature, **plugin-shaped removability is mandatory until the operator explicitly authorizes architectural migration/promotion**. Product or visual acceptance alone does not end isolation. This is an ownership rule, not a
second configuration system. Experiments may plug into generic hosts/registries, but they may not become permanent by
scattering feature-specific branches across shared owners.

Mandatory contract:

- one canonical descriptor/registration seam and one clearly owned implementation package/module set;
- heavy runtime/capture/renderer/Settings body resolution stays lazy and dormant with the experiment disabled;
- experiment-specific persisted keys live in one clearly owned canonical namespace/key block;
- **Settings remains single-authority**: persisted keys/defaults still belong to the existing canonical Settings schema /
  `default_settings.py` / SettingsManager path. Do **not** create a dynamic plugin schema, shadow defaults tree, private JSON,
  second SettingsManager, or runtime-owned persistence merely to make an experiment removable;
- descriptor capability metadata may say whether an experiment participates in a generic Settings surface, but it may **never**
  provide persisted values or become a second schema/default authority. **Isolation does not require opting out of shared Settings
  families**: when the ordinary family semantics fit, use the ordinary canonical participation/profile and add no redirect merely
  for removability. If an experiment genuinely omits or aliases a generic persisted family (Rainbow, shared bar appearance,
  technical controls, or a future family), that exception must have focused coverage proving descriptor participation/profile
  routing matches canonical default-key ownership;
- for such an omit/alias, the mandatory **generic-family consumer audit** is: canonical defaults/model/schema ownership;
  normalization + retired-key/preset migration; Settings hydration/save/visibility; technical/config application; runtime
  presentation/default-state + owner construction; and any preset/default tooling that enumerates the family. These consumers must
  use the canonical mode-setting-family key/profile resolver rather than manufacturing `{mode}_...` persisted keys independently;
  only bounded canonical model/schema construction may form those keys directly. Missing one of these consumers is a contract
  failure, not a valid experimental shortcut;
- the shared Settings UI may generically host a descriptor-provided lazy body, but after generic descriptor dispatch it
  should not accumulate `if mode == <experiment>` branches or parallel save/hydration paths;
- lazy Settings-body construction/hydration is **transactional** at the generic host boundary: success commits exactly one
  complete body; failure removes any partially attached body and leaves the host retryable without duplicate controls or
  leaked widget state;
- persisted Settings scaffold identities are schema, not decoration. If an experiment adds/renames/removes a collapsible
  bucket or other persisted UI-state key, update canonical UI-state defaults/migration in the same slice and keep a contract
  test proving every builder-owned persisted identity has canonical ownership;
- an experimental Visualizer mode that participates in presets inherits the existing user-owned catalogue contract from
  `Spec.md`: authored preset counts/numbers may be arbitrary or sparse, runtime compacts them without renaming/deleting
  files, and shipped manifests are never runtime authority over the user's preset catalogue;
- shared lifecycle/render/runtime owners may expose generic extension seams, but experiment-specific exceptions to their
  contracts require explicit review and a focused regression test;
- removal must be bounded and mechanical: delete the owned implementation + descriptor/registration, delete its owned
  canonical Settings/default/preset block, add one explicit retired-key/mode migration if persisted state can survive in
  user profiles, and delete/update focused tests/docs. Do not retain compatibility sludge indefinitely;
- while experimental isolation remains active, searching the shared tree for the experiment ID/name should find only justified generic registry,
  canonical Settings/default ownership, retirement/migration, tests/docs and integration seams. Every other hit is suspect;
- minimum lifecycle proof is both (a) disabled/default startup imports/constructs no meaningful experiment runtime/resources
  and (b) enable -> activate -> switch away/retire, including before a first source frame where applicable, releases all
  experiment-owned runtime/GPU resources without another cadence.

**Accepted-owner modifier exception:** an option that literally bolts onto an already accepted owner and has no independent
identity/lifecycle is not forced through experimental isolation. The landed Slide Elastic/Wobble/Flex options are canonical
examples: they stay options of the one Slide descriptor/implementation and use the canonical `transitions.slide` Settings
owner. The same ownership rule would apply to future Perspective Push only if it remains a modifier without independent cadence/resources. Do not manufacture a fake plugin/mode merely for removability. If an alleged modifier grows an independent cadence,
resource lifetime, source owner, catalog identity, or substantial feature-specific shared branches, stop and reassess whether
it has become a real standalone implementation boundary.

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

### Proven 3D seams, not a Sphere foundation — Block Spins + accepted-experimental Voxel Sphere

**Quick Block Spins** and the accepted-experimental **Voxel Sphere** are independent 3D consumers with different product owners:
a finite transition run versus a persistent Visualizer logical/runtime path. They prove that context-local programs/buffers,
real Z/depth, projection, GL-state hygiene and explicit retirement are recurring needs. They do **not** make Sphere itself a
canonical 3D foundation or template. A future 3D experiment should compare both consumers, reuse already-neutral helpers,
and extract only the smallest identical low-level seam that the new consumer actually needs. Do not subclass/copy Sphere
wholesale and then inherit its feature-specific Settings/state/material/deformation assumptions.

The instanced **voxel/block** representation is the accepted experimental Sphere representation. Hard block stepping is authored appearance rather than a failed smooth silhouette, while still exercising projection, depth, one static cube mesh + one instance buffer, context ownership and retirement. The reusable architectural lesson is the experimental **host/isolation seam** (lazy descriptor wiring, dormancy/retirement, private namespace and shared-family opt-outs), not Sphere internals. Keep Sphere implementation local until the operator explicitly authorizes migration; a future independent consumer may separately prove small low-level 3D helpers worth extracting.

Prefer shared, dependency-light primitives for the parts the two consumers have actually proven common:

- context-local program / VAO / VBO / static-mesh allocation and release helpers;
- bounded depth clear/scissor ownership inside the consuming Quick surface;
- small aspect-correct perspective / projection helpers where equations truly match;
- GL-state restoration helpers that compose with the existing Quick render fence;
- tiny presentation-neutral normal/lighting math only after identical semantics are demonstrated.

**Instancing is a second-consumer extraction candidate, not current infrastructure work.** When the next real instanced
consumer (for example Extruded Spectrum, Exploding Tiles or Reactive Particle Field) is implemented, compare its static
mesh + instance-buffer layout/upload/lifetime machinery with Voxel Sphere. Extract only the smallest identical helper if
the concrete implementations genuinely match; do not pre-build a generic instancing engine from Sphere alone.

Keep the transition run, source/destination texture ownership, fracture/tile per-run state, Visualizer audio/logical state,
Sphere deformation/materials and every feature's authored shader semantics local. Do **not** grow a generic camera tree,
material hierarchy, physics engine or always-resident "SRPSS 3D engine". Heavy shared resources remain lazy and dormant.

Future **Glass Shatter**, **Exploding Tiles**, Slide **Perspective Push**, the optional tiny-Z pile in **Directional Pixel
Accretion**, and later page-curl/fold/cloth-like ideas should inspect this substrate first instead of inventing another 3D
resource/depth foundation. Extract only what their concrete implementation proves reusable.

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

# 2. Slide — remaining Perspective Push option

Linear / Elastic / Wobble / Flex are landed current architecture and are intentionally absent from future work.
The only surviving Slide idea here is **Perspective Push**: a restrained true-3D presentation option inside the one
canonical Slide transition, not a separate transition identity.

Source may tilt slightly away and/or destination may push into plane while moving. Use shallow card geometry, modest
perspective, restrained yaw/pitch/Z and a sealed-coverage strategy. It shares Slide's one canonical progress/coverage
owner and must collapse exactly to the destination at completion.

Do not add a second clock, transition ID, Random/Cycle entry or independent lifecycle. If implemented, first inspect the
current landed Slide implementation and the proven Quick 3D resource/depth seams rather than reviving the old proposal.

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

**Voxel Sphere golden preservation:** the accepted Voxel Sphere is not future work. Its current
reactivity/motion/presets are golden and its architecture remains isolated; do not retune or promote it unless the
operator explicitly requests that work. Detailed preservation/migration evidence remains in
`Docs/Future_Work/Sphere_Visualizer_Decomposition.md`.

## 7.1 Extruded Spectrum - Unique Mode

Instanced shallow 3D columns: one cuboid mesh, 32–128 instances, per-instance height/color/energy,
restrained lighting/specular and mild perspective/orthographic depth.

## 7.2 Waveform Ribbon - Unique Mode

Oscilloscope/Sine-like state as a 3D ribbon with a few hundred vertices, amplitude on Y,
authored phase/history through X/Z twist, neighboring-sample normals and bounded ghost ribbons.

## 7.3 Bubble Depth Field - Unique Mode

Shallow Z/depth presentation option without changing Bubble logical motion **or R-69 response amplitude**. Depth/parallax must not become a viewport-dependent damping term. Prefer instanced billboard
sphere impostors with analytic normals/specular, per-bubble Z from authored state, depth ordering and
subtle parallax.

## 7.4 Reactive Particle Field - Unique Mode

Bounded 3D instanced point/quad field driven by existing analysis. Prefer hundreds/low-thousands in
one/few draws. Persistent state, if truly required, belongs to proper logical/runtime ownership.

## 7.5 Spectrum Terrain - Unique Mode

Spectrum/history mapped onto a modest grid mesh: current spectrum across one axis, short retained
history into depth, a few thousand vertices, displacement from compact data/texture, normals/lighting.

---

# 8. Future experiment workflow

For a genuinely new transition/visualizer implementation:

1. record visual contract here or in a focused note and apply the **Experimental isolation + Settings single-authority gate** above;
2. add cheap descriptor metadata with the capability **deactivated/dev-gated by default** during development;
3. implement one isolated lazy renderer/runtime package using generic host seams rather than experiment-specific shared branches;
4. declare any persisted options in one owned block of the canonical Settings/default authority; keep the Settings body lazy;
5. use deterministic input/seed;
6. add endpoint/lifecycle/state/dormancy/removal-boundary tests;
7. add production-shaped Quick GL smoke/capture oracle where useful;
8. inspect visually;
9. measure frame/GPU cost at representative resolution/refresh;
10. if it looks poor, modify or delete the isolated implementation without preserving it for sunk cost;
11. after it is worth keeping, polish its isolated Settings/defaults/docs; **keep isolation** unless the operator separately and explicitly requests promotion/migration;
12. commit + push bounded work.

For a future option inside an existing transition such as Slide Perspective Push, extend the single existing
implementation/descriptor rather than manufacturing a new transition identity.

---

# 9. Dormant idea priority — not active sequencing

This ranking contains dormant ideas only. Active/promoted work is deliberately absent; `Current_Plan.md` is the sole active sequencing authority.

1. **Directional Pixel Accretion**;
2. **Glass Shatter**;
3. **Exploding Tiles**;
4. **Slide Perspective Push** — remaining optional Slide modifier;
5. **Deformable 3D Sphere / Blob Sphere experiment**;
6. **Organic Growth / Ink Bloom** prototype;
7. other 3D visualizer experiments;
8. **Settings FlowContainer polish [LOW]** where it genuinely improves alignment/space use;
9. **Optional true two-texture artwork crossfade [LOW]** only if the current event-driven fade still has a demonstrated visual discontinuity worth the extra texture residency.

Glass Shatter, Directional Pixel Accretion and the Deformable 3D Sphere are worth preserving even if their first prototypes are abandoned. Their intended identities should not collapse into generic `shatter`, `pixel dissolve`, or `audio sphere` effects.

Runtime frosted/glass ordinary-widget cards remain **rejected/shelved**, not a queued feature. Reconsider only if a future renderer architecture independently justifies the capability; begin from the rejected-experiment record rather than reviving 2026-09-02 debris.

---

# 10. Operator-requested UI polish contracts

## 10.1 Settings FlowContainer polish [LOW]

Use FlowContainers in additional Settings sections only where they materially improve alignment and space usage. This is presentation polish, not permission to restructure settings ownership or eagerly construct otherwise lazy bodies.

## 10.2 Optional artwork crossfade [LOW]

The shared artwork/metadata fades are landed current architecture and are not future work. A true outgoing+incoming two-texture artwork crossfade is a separate optional experiment only if eyes-on validation proves the current fade insufficient. Measure texture residency and transition cost before keeping it.
