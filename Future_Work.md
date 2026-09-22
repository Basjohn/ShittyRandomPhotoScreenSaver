# Future Work

Long-horizon feature / new-implementation backlog.

The operator may promote selected backlog work into `Current_Plan.md`. `FWPlan.md` is the compact live router for deferred and explicitly promoted items; detailed active execution lives in `Current_Plan.md` or a focused decomposition.
This document retains dormant feature intent, durable architecture rules and relative priority. It must not become an active experiment/status diary.

## Authority / activation rule

`Future_Work.md` is **not active sequencing by default**. Normal work continues to be owned by
`Current_Plan.md` unless the operator deliberately selects a future item.

An agent may implement work from this file only when **either**:

1. the operator explicitly asks for a named `Future_Work.md` item; **or**
2. `Current_Plan.md` contains no remaining important active work. A horizon-gated persisted-input
   compatibility bridge (`Docs/Architecture/Persisted_Input_Compatibility.md`) is dormant
   user-data protection and does not block unrelated future work merely by existing.

**Operator override:** an explicit request for a named `Future_Work.md` item overrides the normal sequencing above.
Unfinished `Current_Plan.md` work is not, by itself, permission to refuse or defer that named
future item. Only a genuine technical prerequisite required to implement the requested item safely may block direct
implementation. Where practical, satisfy that prerequisite as the opening subphase of the requested work instead of
deferring the feature wholesale. Preserve unrelated active work and its rollback boundaries while doing so.

Merely encountering, reading, indexing or cross-linking this file is **not** permission to begin one
of these features.

Normal priority:

```text
Current_Plan.md active work
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
5. decompose the work into resumable slices that leave the repository coherent whenever practical;
6. define deterministic/source-level, lifecycle/resource, performance and eyes-on visual acceptance bars separately;
7. keep an explicit landed/remaining status so partial completion is not mistaken for finished architecture.

Do not spend a first implementation pass building speculative infrastructure merely because later features might need it.
Build the requested vertical feature, extract only reuse justified by the real implementation, and record attractive but
unproven abstractions in the decomposition for a later second-consumer decision.

### Canonical integration + self-contained implementation gate

A new transition should enter the **existing** transition catalog/registry and Qt Quick render host from its first implementation, initially deactivated by default for development. This is production-shaped integration, **not** a new experimental runtime, private Settings system, parallel preview or separate compositor. Its implementation module/shaders/mesh/per-run resources remain local so it can be disabled immediately and removed by deleting its descriptor, code and owned canonical state. Dormancy, not perpetual quarantine, is the relevant safety boundary. The already accepted Voxel Sphere is an **independent Visualizer mode** with its own protected isolation contract; this transition decision does not promote, merge or retune Sphere.

- [ ] For a **new transition identity**, add one cheap canonical descriptor and lazy implementation to the existing registry/host and use current transition source/state/presentation/Settings authority. Keep per-transition rendering logic/resources local and do not sprinkle special cases through shared owners. Disabled transition: no heavy imports, shaders, buffers, cadence or frame work; enabled->switch away->retire releases all owned GPU/context resources.
- [ ] For a **modifier of an existing effect** (e.g., Slide Perspective Push), extend that effect's single descriptor/implementation and canonical options. Do not make a fake transition identity for removability; if independent resources/owner/cadence emerge, revisit the identity boundary.
- [ ] For a new **Visualizer mode**, use the current canonical mode descriptor, lazy builder/renderer, per-mode settings/preset authority and shared technical-family routing; do not treat a transition's lighter registry model as permission to alter Voxel Sphere/Bubble goldens or the accepted preset system.
- [ ] All persisted values/defaults stay under the existing canonical `default_settings.py` / SettingsManager + appropriate accepted schema namespace. No dynamic plugin schema, private JSON, second SettingsManager or feature-local persistence to make removal easy. Descriptor metadata chooses generic Settings participation, never becomes another default/value authority. If omitting or aliasing a generic family, audit defaults/model/schema, normalization/migration, UI hydrate/save, technical/runtime application and preset/tool enumerators together; preserve user-authored preset catalogues (including sparse indices).
- [ ] Keep Settings body lazy and **transactional**: attach on complete success, remove partial body on failure, retry without duplicate controls or leaked state. New persisted collapsible-bucket keys need canonical UI-state defaults/migration and exact identity tests. Do not add per-experiment `if mode == ...` branches beyond necessary catalog/registration boundaries.
- [ ] Removal proof: deleting implementation + one registry entry + its owned canonical settings/default/preset block and focused tests/docs leaves shared hosts and unrelated options functioning. If user profiles can hold old values, perform one explicit retired-key/mode migration instead of indefinite compatibility sludge. A source search for the effect ID should show only justified registry, settings/migration, owned code and tests/docs references.
- [ ] Run disabled import/resource dormancy, deterministic state and pixel/GL smoke, cleanup/context-loss, both display activation and representative heavy-load perf/freshness tests. A visual experiment can be reverted without preserving it for sunk cost. **Keep genuine module boundaries**, but do not require a second approval ceremony to use the effect through the normal host once tests and operator acceptance are complete.

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

Do not revive old presenter, disabled-family, or dual-authority terminology just because an older idea used it.
Current contracts always outrank the wording that originally described a dormant idea.

All future performance-sensitive features also inherit `Docs/Guardrails/Performance_Optimization_Contract.md`. Feature cost must be measured without weakening current freshness/reactivity or replacing bounded useful caches/resources with latency-heavy churn.

---

# 1. Visual-effects extension architecture

Current extension model:

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

The instanced **voxel/block** representation is the accepted experimental Sphere representation. Hard block stepping is authored appearance rather than a failed smooth silhouette, while still exercising projection, depth, one static cube mesh + one instance buffer, context ownership and retirement. The reusable architectural lesson is the experimental **host/isolation seam** (lazy descriptor wiring, dormancy/retirement, private namespace and shared-family opt-outs), not Sphere internals. Keep Sphere implementation local until the operator explicitly authorizes promotion; a future independent consumer may separately prove small low-level 3D helpers worth extracting.

Prefer shared, dependency-light primitives for the parts the two consumers have actually proven common:

- context-local program / VAO / VBO / static-mesh allocation and release helpers;
- bounded depth clear/scissor ownership inside the consuming Quick surface;
- small aspect-correct perspective / projection helpers where equations truly match;
- GL-state restoration helpers that compose with the existing Quick render fence;
- tiny presentation-neutral normal/lighting math only after identical semantics are demonstrated.

**Instancing now has concrete transition consumers.** Exploding Tiles and Directional Pixel Accretion derive their bounded cells from `gl_InstanceID`; they do not need Sphere's instance-buffer upload machinery. They share only small context-local program/static-mesh/underlay/depth primitives with Glass Shatter. Sphere's distinct shell-instance state remains local. A later consumer must still justify any further extraction from matching source, not hypothetical reuse.

Keep the transition run, source/destination texture ownership, fracture/tile per-run state, Visualizer audio/logical state,
Sphere deformation/materials and every feature's authored shader semantics local. Do **not** grow a generic camera tree,
material hierarchy, physics engine or always-resident "SRPSS 3D engine". Heavy shared resources remain lazy and dormant.

The current transition expansion reuses this substrate. Later page-curl/fold/cloth-like ideas should inspect both existing mesh consumers and the small shared transition helpers before adding resource/depth machinery. Extract only what a concrete implementation proves reusable.

For a **deactivated** transition: keep cheap metadata available, exclude it from Random/Cycle, do not
import heavy implementation solely for catalog construction, do not compile effect shaders, do not
create effect-specific GL resources, and do not run effect-specific timers/workers.

Future transitions/options consume the final monotonic transition run. They may author internal
deformation/easing/physics deterministically from that sample but do not become another clock.

Permanent safety rules apply to every future visual/transition experiment:

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

# 2. Activated transition expansion

Glass Shatter, Exploding Tiles, Directional Pixel Accretion, Slide Perspective Push, Ink Bloom and Melt Drip are implemented through the canonical Quick path. They are no longer dormant implementation ideas. Tendril Reveal was rejected and retired completely; it is not dormant future work. The remaining expansion capabilities start deactivated; operator visual quality and representative heavy-load/mixed-display acceptance remain open.

- Current appearance, controls and resource contracts: `Docs/Reference/Transitions.md`.
- Remaining actionable acceptance: `Current_Plan.md` and `Docs/Future_Work/Transition_Expansion.md`.
- Do not reimplement these effects from old backlog proposals or broaden this activation to the Visualizer ideas below.

---

# 3. Future 3D visualizer experiments

- [ ] Each requested 3D Visualizer has a distinct canonical mode identity and protected settings/preset ownership; the accepted Voxel Sphere remains unchanged unless specifically requested.

These preserve `VisualizerLogicalRuntime` as the authored logical clock. Presentation may not discard
logical steps or turn render refresh into simulation cadence.

**Unique Mode means a real mode boundary.** Each experiment labelled `Unique Mode` gets one canonical descriptor plus its own lazy mode-local logical/runtime/renderer/Settings implementation. It may reuse shared analysis bands, direction vocabulary, shader utilities and proven math, but it must not parasitically run another mode's active runtime, install a second visualizer clock, or create an ad-hoc six-way switch outside the descriptor seam. A Bubble-derived or Spectrum-derived experiment may borrow contracts/equations while remaining independently dormant when disabled.

**Voxel Sphere golden preservation:** the accepted Voxel Sphere is not future work. Its current
reactivity/motion/presets are golden and its architecture remains isolated; do not retune or promote it unless the
operator explicitly requests that work. The current preservation/isolation contract lives in
`Docs/Reference/Sphere_Visualizer.md`.

## 3.1 Extruded Spectrum - Unique Mode

Instanced shallow 3D columns: one cuboid mesh, 32–128 instances, per-instance height/color/energy,
restrained lighting/specular and mild perspective/orthographic depth.

## 3.2 Waveform Ribbon - Unique Mode

Oscilloscope/Sine-like state as a 3D ribbon with a few hundred vertices, amplitude on Y,
authored phase/history through X/Z twist, neighboring-sample normals and bounded ghost ribbons.

## 3.3 Bubble Depth Field - Unique Mode

Shallow Z/depth presentation option without changing Bubble logical motion **or R-69 response amplitude**. Depth/parallax must not become a viewport-dependent damping term. Prefer instanced billboard
sphere impostors with analytic normals/specular, per-bubble Z from authored state, depth ordering and
subtle parallax.

## 3.4 Reactive Particle Field - Unique Mode

Bounded 3D instanced point/quad field driven by existing analysis. Prefer hundreds/low-thousands in
one/few draws. Persistent state, if truly required, belongs to proper logical/runtime ownership.

## 3.5 Spectrum Terrain - Unique Mode

Spectrum/history mapped onto a modest grid mesh: current spectrum across one axis, short retained
history into depth, a few thousand vertices, displacement from compact data/texture, normals/lighting.

---

# 4. Future transition / Visualizer workflow | reusable checklist

- [ ] Record the concrete visual contract and rollback reference; classify the idea as a new transition, an option of an existing transition, or a distinct Visualizer mode before coding.
- [ ] Wire to **canonical** catalog/descriptor/defaults, lazy implementation and the one Qt Quick scene from day one. Use module-local expensive resources, not a parallel experimental engine or a Settings shadow tree.
- [ ] Use deterministic seed/input and add source/owner state, disabled dormancy, GPU resource retirement/context-loss, Settings and removability tests; preserve existing accepted owners and visualizer goldens.
- [ ] Validate production-shaped native Quick rendering, measured GPU/event-loop/frame/freshness cost, visual quality and multi-display behavior where material. Do not accept a shader merely because source or isolated offline preview compiles.
- [ ] On acceptance, enable/offer via the existing canonical Settings/cycle/transition flow as applicable. On rejection, delete the self-contained implementation and its descriptor/owned canonical state with a bounded migration for persisted profiles if required; do not leave dead branches.
- [ ] For Slide Perspective Push and similar existing-effect modifiers, use the single existing Slide owner instead of inventing a new transition identity.

---

# 5. Dormant idea priority — not active sequencing

This ranking contains dormant ideas only. Active/promoted work is deliberately absent; `Current_Plan.md` is the sole active sequencing authority.

1. **Deformable 3D Sphere / Blob Sphere experiment**;
2. other 3D visualizer experiments;
3. **Settings FlowContainer polish [LOW]** where it genuinely improves alignment/space use without changing ownership.

Activated transitions are tracked in the live plan, not this dormant ranking.

Games You Follow and the system volume/mute OSD are implemented. Their durable product contracts live in `Docs/Reference/`; reopen either only for a concrete defect or an explicitly requested extension.

The Deformable 3D Sphere idea is worth preserving even if its first prototype is abandoned. Its identity should not collapse into a generic audio sphere. Current Glass Shatter and Accretion identities are owned by the transition reference.

Runtime frosted/glass ordinary-widget cards remain **rejected/shelved**, not a queued feature. Reconsider only if a future renderer architecture independently justifies the capability; begin from the rejected-experiment record rather than reviving 2026-09-02 debris.

---

# 6. Operator-requested UI polish contracts

## 6.1 Settings FlowContainer polish [LOW]

- [ ] Only promote this UI polish for a demonstrated Settings layout issue; preserve lazy Settings bodies and current owner.

Use FlowContainers in additional Settings sections only where they materially improve alignment and space usage. This is presentation polish, not permission to restructure settings ownership or eagerly construct otherwise lazy bodies.
