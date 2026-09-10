# Future Work

Last updated: 2026-09-09

Long-horizon feature / new-implementation backlog.

The operator has activated backlog implementation (2026-09-05). `FWPlan.md` owns that selected work's live
checklists and links to detailed decompositions; this document retains feature intent and relative priority.

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
8. keep an explicit landed/remaining status so partial completion is not mistaken for finished architecture.

Do not spend a first implementation pass building speculative infrastructure merely because later features might need it.
Build the requested vertical feature, extract only reuse justified by the real implementation, and record attractive but
unproven abstractions in the decomposition for a later second-consumer decision.

### Experimental isolation + Settings single-authority gate

For a genuinely new experimental Visualizer mode, transition identity, widget family, or other independently removable
feature, **plugin-shaped removability is mandatory until explicit product acceptance**. This is an ownership rule, not a
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
- shared lifecycle/render/runtime owners may expose generic extension seams, but experiment-specific exceptions to their
  contracts require explicit review and a focused regression test;
- removal must be bounded and mechanical: delete the owned implementation + descriptor/registration, delete its owned
  canonical Settings/default/preset block, add one explicit retired-key/mode migration if persisted state can survive in
  user profiles, and delete/update focused tests/docs. Do not retain compatibility sludge indefinitely;
- before acceptance, searching the shared tree for the experiment ID/name should find only justified generic registry,
  canonical Settings/default ownership, retirement/migration, tests/docs and integration seams. Every other hit is suspect;
- minimum lifecycle proof is both (a) disabled/default startup imports/constructs no meaningful experiment runtime/resources
  and (b) enable -> activate -> switch away/retire, including before a first source frame where applicable, releases all
  experiment-owned runtime/GPU resources without another cadence.

**Accepted-owner modifier exception:** an option that literally bolts onto an already accepted owner and has no independent
identity/lifecycle is not forced through experimental isolation. Slide Elastic/Wobble/Flex/Perspective are the canonical
example: they stay options of the one Slide descriptor/implementation and use the canonical `transitions.slide` Settings
owner. Do not manufacture a fake plugin/mode merely for removability. If an alleged modifier grows an independent cadence,
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

### Proven 3D seams, not a Sphere foundation — Block Spins + experimental Voxel Sphere

**Quick Block Spins** and the now-landed experimental **Voxel Sphere** are independent 3D consumers with different product owners:
a finite transition run versus a persistent Visualizer logical/runtime path. They prove that context-local programs/buffers,
real Z/depth, projection, GL-state hygiene and explicit retirement are recurring needs. They do **not** make Sphere itself a
canonical 3D foundation or template. A future 3D experiment should compare both consumers, reuse already-neutral helpers,
and extract only the smallest identical low-level seam that the new consumer actually needs. Do not subclass/copy Sphere
wholesale and then inherit its feature-specific Settings/state/material/deformation assumptions.

The instanced **voxel/block** representation is now the active Sphere experiment: hard block stepping is authored appearance rather than a failed smooth silhouette, while still exercising projection, depth, one static cube mesh + one instance buffer, context ownership and retirement. This checkpoint is not a reusable 3D-engine declaration. Keep the implementation local until another independent consumer (for example Exploding Tiles) proves an identical low-level seam worth extracting.

Prefer shared, dependency-light primitives for the parts the two consumers have actually proven common:

- context-local program / VAO / VBO / static-mesh allocation and release helpers;
- bounded depth clear/scissor ownership inside the consuming Quick surface;
- small aspect-correct perspective / projection helpers where equations truly match;
- GL-state restoration helpers that compose with the existing Quick render fence;
- tiny presentation-neutral normal/lighting math only after identical semantics are demonstrated.

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

## 7.1 Voxel Sphere experiment - Unique Mode

**Status:** direct replacement checkpoint landed; operator eyes-on acceptance decides keep vs retire.

The rejected smooth icosphere implementation is gone. Do not restore or preserve it for comparison, and do not resume its derivative-AA, clipped cast-shadow, tangent-normal reconstruction, liquid/fire side systems, or smooth-material topology. Those mechanisms failed the visual/product bar and are useful only as a historical lesson about what not to generalize.

The current experiment intentionally keeps the existing canonical `sphere` mode/persistence boundary while replacing only the owned representation:

```text
one static cube mesh
    +
one static stepped shell instance buffer
    +
one instanced draw
    +
vertex-shader radial/block deformation from immutable authored state
```

The shell uses integer-lattice stepping so block discontinuities are authored appearance. Cubes rotate as one real 3D object, use the existing logical-frame authored time/energy/transient state, and may pulse/translate radially without any per-frame Python topology rebuild. Voxel colour is now literal Fill/Edge RGBA. The historical Chrome / Obsidian / Magma / Silver / Water pseudo-material branches and Palette Effects key are retired rather than carried forward as hidden renderer authority.

### 7.1A Experimental isolation / Settings authority

- `sphere` remains independently disabled by default and lazily resolves its Settings body, capture, frame runtime and renderer.
- All persisted `sphere_*` values remain in the one canonical Settings/default authority. No plugin-private JSON/default store, second SettingsManager or fallback persistence path is allowed.
- A mode with no technical-control UI may name a canonical technical profile in its descriptor. Sphere explicitly consumes the Spectrum technical profile; shared owners resolve that descriptor contract generically instead of assuming `technical_cache[mode]`.
- Heavy GL resources exist only while Sphere is admitted and retire through the existing event-owned renderer/context lifecycle. No timer, worker or independent cadence is added.
- Removal must remain mechanical: delete the owned mode implementation/builder/capture/runtime/preset/settings block and descriptor entry, then apply one explicit retired-mode/key migration.

### 7.1B Reuse policy

Do not build future 3D work *on Sphere*. Reuse already-neutral infrastructure and extract new shared code only after a second independent consumer proves the same seam. The current voxel implementation may later prove useful ideas for Exploding Tiles or another instanced effect (cube mesh, instance-buffer ownership, projection/depth state), but those remain Sphere-local until that second consumer exists.

Transitions and visualizers may share low-level GPU primitives while keeping separate lifecycle owners: a finite two-image transition must never inherit the persistent Visualizer logical/audio runtime merely because both draw 3D geometry.

### 7.1C Iteration / acceptance gate

The voxel representation has passed the first operator bar: it is not worse than the rejected smooth Sphere and is worth
iterating. Continue bounded voxel-only passes while each pass attacks an observed visual/reaction defect. Do not preserve or
restore the rejected smooth representation, and do not invent a parallel third representation merely from sunk cost.

Current reaction contract after the detached-packet pass established the first genuinely desirable visual floor. **The current local travel/fallout is now a minimum accepted reward: future audio-linkage work may change when/where packets fire, but must not quietly compress the detached-cube displacement back toward the shell.**

1. treat the shell as a **sparse 3D Spectrum**, but never use shared Spectrum bar height as displacement authority: routine near-total `1.0` plateaus make both absolute height and recent-rise unusable for this mode;
2. reuse the existing public support-aware Bubble energy feed for mode-local control. This is reuse of an existing analysis seam, not another worker/cadence/Settings authority;
3. **detached block displacement is the visual reward.** Do not tune the mode as though it were preserving a smooth sphere surface. A strong local event must visibly separate cubes by a substantial fraction of the shell radius;
4. use eight fixed 3D spatial sections with true angular fallout. A musical packet excites one local section; nearby blocks participate progressively less and remote blocks receive zero authority. Static local polarity permits both protrusion and recession;
5. **punch events own detached displacement.** Generic spectral-shape/envelope change is explicitly forbidden from packet authorship. A Sphere-local baseline-relative transient crest, confirmed vocal/kick/snare event, or onset may earn one packet through the shared bounded admission gate. A held/pegged transient converges into the local baseline and cannot keep firing; ordinary unclassified bass level does not detach geometry;
6. all detached packets share the one Sphere-local admission path and a bounded minimum interval. Packet location is music-derived from current spectral balance/brightness plus bounded event classification, never round-robin/time/cursor progression; repeated similar material should reinforce a local region rather than mechanically fill all eight octants;
7. section attack remains immediate/aggressive and release is long/gentle. Source loss/pause is decay-only and may never manufacture a packet from the collapse to zero. `sphere_size_response` instead owns only slow sustained passage-weight growth (~0.5 s attack / ~1 s release, small bounded maximum), never a beat pulse;
8. rotation phase is integrated monotonically in the logical runtime. Canonical **Base Rotation** is the independent continuous floor; **Velocity Reaction** is an additive boost that follows **current articulation** with fast attack and short release. Spectral/envelope movement may articulate rotation and the tracer, but may not detach cubes;
9. while the mapping is experimental, remaining interference-prone legacy motion controls stay disabled/inert, but pseudo-material settings do **not**: `sphere_material`, `sphere_material_color`, and `sphere_material_fx` forward-migrate to the clean `sphere_finish` / `sphere_fill_color` contract and are then removed. Deformation, **Size Response**, Base Rotation, Velocity Reaction, Block Reactivity and Vocal Response remain live;
10. audio owns geometry only. Fill hue/alpha, edge hue/alpha, Toon, Gloss/Specular and Rainbow Ghosting are presentation controls and may not become a second audio-reactive colour/emission system;
11. broad directional lighting is explicitly **screen-X/Y anchored**. Shell Z and rotating cube-face normals have no broad diffuse/specular authority. Cube face readability is a separate model layer whose face identity and bevel UVs come from each cube's **unrotated local face normal**; this accepted fix must not regress;
12. **Toon means visibly hard toon**, not subtle quantization: hard diffuse plateaus, strong authored edge/ink colour, and a hard highlight patch. Normal finish uses the same stable face identity plus per-face sheen controlled explicitly by Gloss and Specular. A shell-space highlight lobe that picks one/few blocks is forbidden because it competes with the Light Tracer;
13. the Sphere scene shadow is a **literal flat 2D** soft quad/disc, offset directly opposite the selected light, and gated by its own canonical Drop Shadow checkbox. Its radius/offset may grow modestly with staged sustained body growth. It has no voxel Z, cube faces, self-overlap, rigid-body rotation or detached-block geometry. The shared presentation layer must not gain a Sphere shadow escape hatch;
14. canonical Sphere presentation includes independent literal **Fill Color** and **Edge Color** (including independent alpha), plus default-off **Rainbow Ghosting**. Historical Chrome/Obsidian/Magma/Silver/Water pseudo-material transforms are retired; `sphere_finish` is Settings-only convenience that writes Gloss/Specular and never reaches the renderer. Ghosting keeps only bounded reactive/moving history, draws after the hero with ordinary alpha blending, and must never redraw the whole shell additively into a white orb;
15. current diagnostics emit `[SPHERE_AUDIO]` with crest components, shape/envelope articulation, typed events/onset, sustained/body/tracer/rotation state, section occupancy and packet-source counts in `vocal/crest/kick/snare/onset` order. There is no generic `change` packet source;
16. Scene Overflow and Incoming Fade remain descriptor/Sphere-owned. The generic clip capability is opt-in and accepted modes retain their existing clip/shadow behavior;
17. **Contingency only, not current behavior:** raw pre-AGC onset + four-corner ingress has now produced the first operator-described “reactive across the board / alive” run. First resolve perceptual jerk with stable ingress population + optional geometry-only fragment interpolation. Only if reactivity still needs another layer after continuity acceptance may replacement/accretion be evaluated: event intensity could raise incoming velocity and increase dominant ingress corners from one toward two/three/four at the absolute peak while existing shell voxels fade out as arrivals replace them. Keep it secondary to fragmentation, event-owned, bounded, and never an ambient particle fountain/private animation clock;
17. operator acceptance now checks punch-linked local fragmentation, staged soft→heavy body growth, intentional tracer snake + gentle local selected-cube rotation, variable active shell rotation, fixed light quadrant + persistent cube detail, checkbox flat shadow with staged growth, independent edge alpha, obvious Toon, visible Gloss/Specular range, visible Rainbow Ghosting, quiet stability, the neutral Reactive Voxel validation preset, and ordinary/CUSTOM geometry.


Deferred only after musical causality is accepted:

- **true textured/reflective blocks** are technically viable through per-face UVs and/or a future environment/scene-texture reflection seam. Do not add that authority merely to imitate the retired pseudo-material names before the reaction contract is accepted.
- **block dissolve/retirement/replacement** is also viable as event-owned per-instance lifecycle state: an aged/displaced cube can fade out while a replacement fades in from distance. It must use the existing logical cadence and remain event/state driven, never add a private timer or free-running movement source.

Retire the mode only if the voxel concept stops earning further iteration; if retired, strip the remaining owned keys through
one explicit retirement migration. Automated gates before any checkpoint remain: disabled mode imports/owns no heavy
implementation resources; enable -> activate -> switch-away retires renderer resources through the existing event path;
canonical Settings/default snapshot stays singular; no experiment-specific branch spreads into shared owners.

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
11. only after it is worth keeping, polish Settings/defaults/docs and explicitly review promotion from experimental isolation;
12. commit + push bounded work.

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

## 10.1 Widget glow on hover / click — landed, physical tuning open

Display -> Interaction now owns **Widget Glow on Hover**, **Widget Glow on Click**, the shared theme-inheriting
colour swatch, and a 0-100% **Glow Intensity** slider. The retained primitive is state-edge driven rather than a
self-decaying pulse: hover fades in and stays settled until the existing hover edge ends; click selects the last
clicked ordinary card and stays settled until a later admitted press selects another card or empty space. State
changes alone trigger finite fade-in/fade-out animations. No recurring timer, poller, worker, independent frame
loop or per-widget controller exists. Future work here is eyes-on timing/subtlety only unless a concrete defect is
found; do not reopen ownership or invent sustained animation cadence.

## 10.2 Settings FlowContainer polish [LOW]

Use FlowContainers in additional Settings sections only where they materially improve alignment and space
usage. This is presentation polish, not permission to restructure settings ownership or eagerly construct
otherwise lazy bodies.

## 10.3 Optional artwork crossfade [LOW]

The current shared artwork/metadata fades are landed and belong to current physical validation, not future
architecture work. A true outgoing+incoming two-texture artwork crossfade is a separate optional experiment
only if eyes-on validation proves the current fade insufficient. Measure texture residency and transition
cost before keeping it.
