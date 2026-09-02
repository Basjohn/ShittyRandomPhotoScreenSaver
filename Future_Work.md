# Future Work

Last updated: 2026-09-02

Long-horizon feature / new-implementation backlog.

## Authority / activation rule

`Future_Work.md` is **not active sequencing** and must not interrupt work owned by `Current_Plan.md` or
`Future_Cleanup.md`.

An agent may implement work from this file only when **either**:

1. the operator explicitly asks for a named `Future_Work.md` item; **or**
2. `Current_Plan.md` and `Future_Cleanup.md` contain no remaining important active work.

Merely encountering, reading, indexing or cross-linking this file is **not** permission to begin one
of these features.

Normal priority:

```text
Current_Plan.md active work
        ↓
Future_Cleanup.md required debt/deletion work
        ↓
Future_Work.md new features / experiments
```

This file exists so good ideas survive the migration without expanding migration scope. Technical
notes are deliberately provisional; future implementation must inspect the final landed Qt Quick
architecture before coding.

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

## 7.1 Deformable 3D Sphere / Blob Sphere experiment

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

Visualizer viewport resizing is a current destination requirement. Any future sphere must therefore use aspect-correct
projection so wider/taller viewports reveal or reframe more space without turning the sphere into an ellipse. Whole-size
corner/scroll resize scales it uniformly; edge viewport resize changes framing/aspect.

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
specular light to crawl over the actual changing dents/bulges without CPU normal rebuilds.

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

## 7.2 Extruded Spectrum

Instanced shallow 3D columns: one cuboid mesh, 32–128 instances, per-instance height/color/energy,
restrained lighting/specular and mild perspective/orthographic depth.

## 7.3 Waveform Ribbon

Oscilloscope/Sine-like state as a 3D ribbon with a few hundred vertices, amplitude on Y,
authored phase/history through X/Z twist, neighboring-sample normals and bounded ghost ribbons.

## 7.4 Bubble Depth Field

Shallow Z/depth presentation option without changing Bubble logical motion **or R-69 response amplitude**. Depth/parallax must not become a viewport-dependent damping term. Prefer instanced billboard
sphere impostors with analytic normals/specular, per-bubble Z from authored state, depth ordering and
subtle parallax.

## 7.5 Reactive Particle Field

Bounded 3D instanced point/quad field driven by existing analysis. Prefer hundreds/low-thousands in
one/few draws. Persistent state, if truly required, belongs to proper logical/runtime ownership.

## 7.6 Spectrum Terrain

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

1. **Slide optional motion styles** — Elastic first, then Wobble/Flex/Perspective inside Slide;
2. **Deformable 3D Sphere / Blob Sphere experiment**;
3. **Directional Pixel Accretion**;
4. **Glass Shatter**;
5. **Exploding Tiles**;
6. **Organic Growth / Ink Bloom** prototype;
7. other 3D visualizer experiments after final migration validation;
8. **Frosted / glass ordinary-widget cards** only after the widget migration/cutover architecture is stable.

Glass Shatter, Directional Pixel Accretion and the Deformable 3D Sphere are worth preserving even if
their first prototypes are abandoned. Their intended identities should not collapse into generic
`shatter`, `pixel dissolve`, or `audio sphere` effects.

---

# 10. Ordinary-widget card materials — committed Normal / Glass / Acrylic modes

Late J+ execution/admission checklist: `Docs/QtQuick_Migration/J_ParityPlus_Historical_Visual_Interaction_Reference_2026-08-30.md`, section **10. Committed non-blocking J+ work — ordinary-widget Glass / Acrylic cards**.

**Status: committed J+ work, non-blocking for J close. It remains tracked until implemented/accepted or explicitly superseded. The ordinary translucent card
is the baseline and must remain the default.** This feature is not migration parity and must not turn
every ordinary widget into an effect-bearing card simply because Qt Quick makes that possible.

## 10.1 Baseline that must remain cheap

Current source already has the expected simple retained-card architecture: `OverlayCard.qml` paints one
ordinary `Rectangle` background with independent alpha, border and cached shadow, while family content
stays above it. Its current default background (`#b3101010`) is already translucent. Treat that as the
source-level baseline even if runtime visual acceptance is temporarily unavailable during migration.

The default material path is therefore:

```text
effective_card_material_mode = normal   # resolved renderer-facing DEFAULT/OFF; current translucent path

ordinary OverlayCard
    -> one alpha/tinted Rectangle fill
    -> ordinary border
    -> existing cached shadow
    -> retained family content
```

Requirements for `normal` / the current translucent path:

- no backdrop capture;
- no offscreen texture/FBO created for card materials;
- no blur pass;
- no `ShaderEffectSource` / `MultiEffect` solely for the card;
- no additional render cadence or timer;
- preserve current whole-widget root-fade semantics;
- cost should remain essentially the ordinary retained `OverlayCard` cost that exists now.

A future Widget Theme (`.srwtheme`) may change the simple card's RGB/alpha/border/shadow and may recommend a
**default** material once the committed material system is physically accepted. The theme recommendation is not the final
runtime material authority: users must be able to keep the selected theme's colours while explicitly choosing another
surface material. Theme application must never create a second material renderer or independent Glass/Acrylic booleans.

## 10.2 Material modes and surface override

Palette/theme selection and card material are two related but **orthogonal** appearance axes. The theme may recommend a
surface, while one explicit user override can replace only that surface without detaching the rest of the Widget Theme.
Keep the three layers named separately so there is no dual authority:

```text
# serialized by the .srwtheme visual bundle
default_card_material_mode = normal | glass | acrylic

# persisted user preference; DEFAULT = theme
card_material_override = theme | normal | glass | acrylic

# one resolved value consumed by retained runtime material owners
effective_card_material_mode = (
    default_card_material_mode
    if card_material_override == theme
    else card_material_override
)
```

The eventual user-facing control in `Settings -> Widgets -> General -> Appearance` should therefore be one
mutually-exclusive **Surface Style** choice:

```text
Theme Default   # DEFAULT; subtitle/secondary text may show the resolved theme recommendation, e.g. "Glass"
Normal          # explicit override; current cheap translucent OverlayCard path
Glass           # explicit scene-local frosted override
Acrylic         # explicit scene-local stronger-material override
```

This deliberately avoids a separate `Override Theme Background` checkbox. `Theme Default` *is* the no-override state, so
there is no second switch to explain and no need to grey out the material choices. It also avoids making a fake `Custom`
Widget Theme solely to unlock existing colour controls.

`normal` remains the product/UI name for the current cheap translucent `OverlayCard` path. Do not expose separate
`Enable Glass` / `Enable Acrylic` toggles: invalid simultaneous states must be impossible by construction. Existing/Dark
Widget Theme recommends `normal`. Until Glass/Acrylic have passed the shared/lazy material admission gates, those explicit
choices remain unavailable even if the future theme schema can name their defaults.

Glass and Acrylic are **Qt Quick scene-local materials**. They are not Windows native backdrop modes and
must not use the Settings HWND implementation (`SetWindowCompositionAttribute`, AccentPolicy state 3/4)
on the screensaver `QQuickWindow` or attempt one native backdrop per widget. The Settings solution is
valuable architecture evidence about separating material ownership, but its HWND primitive is the wrong
mechanism for cards that live inside one Quick scene.

Suggested visual recipes:

```text
Glass
    shared blurred screensaver backdrop
    + weak / highly translucent card tint
    + border
    + existing shadow/content

Acrylic
    same shared blurred screensaver backdrop
    + stronger material tint
    + optional restrained noise/luminosity treatment if it materially helps
    + border
    + existing shadow/content
```

Glass/Acrylic should preferably share the same blurred backdrop representation. Their visible
difference should primarily come from cheap card-local material parameters. Do not create separate
full-display blur pipelines merely because the names differ. If eyes-on work eventually proves distinct
blur strengths are necessary, prefer a small bounded set of shared per-display blur tiers rather than
one arbitrary blur pass per card.

## 10.3 Shared/lazy backdrop contract

When at least one Glass/Acrylic card is visible on a display:

```text
base image / current transition for that display
        ↓
ONE lazy shared per-display backdrop source
        ↓
optional deliberate downsample
        ↓
ONE shared bounded blur representation (or bounded shared tiers if proven necessary)
        ↓
card-local display-space crop/sample + rounded mask
        ↓
Glass/Acrylic local material parameters
        ↓
normal cached card shadow + retained family content
```

When the final Glass/Acrylic consumer disappears, the shared backdrop resources should retire and the
display returns to the plain `normal` / current-translucent cost path.

Hard rules:

- never create one full-display `ShaderEffectSource`, capture, FBO or blur chain per widget;
- never capture the already-composited widget layer: the source is the scene **below ordinary widgets**;
- do not capture the Visualizer, other cards, CUSTOM overlays, cursor halo or context menu into the
  backdrop; avoid recursion, feedback and double blur;
- keep all expensive material work GPU/Quick/render-thread native; no Python pixel readback, QWidget
  screenshots, QPixmap bridges or CPU blur;
- one optional render-thread-owned per-display offscreen target is acceptable if that proves to be the
  cheapest production solution. The prohibition is against per-widget/CPU/duplicate capture ownership,
  not against the single shared texture that a real blur material necessarily needs;
- card-local tint, mask, border and any subtle Acrylic noise should remain cheap even with many cards;
- preserve the single production `QQuickWindow` and retained scene; do not add another accelerated
  top-level/window merely for material effects.

## 10.4 Prototype path versus production path

Do not prematurely build a complicated custom texture bridge before proving the look and measuring it.
Recommended order:

### Prototype / visual proof

Use **one per-display `ShaderEffectSource` targeting the background presentation only**, deliberately
reduced in resolution, feeding one shared blur (`MultiEffect` or an equivalent bounded Quick effect).
Cards sample/crop that shared result.

This prototype is acceptable because there is still only one backdrop source/blur owner per display.
Measure it before replacing it simply because a lower-level design sounds faster.

### Production optimization only if measurements justify it

The existing `BackgroundRenderItem` / `BackgroundRenderNode` already owns the real image/transition
pixels and current source/destination textures. If the Quick capture/effect path is measurably too
expensive, prefer moving shared-backdrop production beside that existing render owner rather than
capturing the whole Quick scene repeatedly.

Candidate shape:

```text
BackgroundRenderNode
    draws normal full-resolution background/transition
    + when material consumers exist only:
        produces one reduced per-display material backdrop from the SAME frame state
        performs/feeds one bounded shared blur
        exposes that shared result through the smallest legal Quick/render bridge
```

Do not assume a raw OpenGL texture can simply be handed to arbitrary QML. The concrete bridge
(QSGTexture provider, custom material item, shared render node, `ShaderEffectSource`, or another supported
Qt mechanism) must be chosen against the Qt/PySide version that exists when this feature is implemented.
Prefer the simplest measured solution that obeys the ownership rules above.

## 10.5 Temporal and geometry correctness

A frosted card must show the background that is actually behind that card **on the same presented
frame**.

During transitions:

- backdrop production must use the same `TransitionRun` and the same per-frame transition sample as the
  full-resolution background;
- if backdrop generation is moved into the custom background renderer, sample canonical transition time
  once and use that exact sample for both the display draw and material-backdrop draw;
- do not let the card blur lag a frame behind or independently sample monotonic time, because even a
  small mismatch will read as the card swimming/slipping over the transition.

For geometry:

- crop/sample coordinates must be resolved in final display space, including current CUSTOM placement,
  resize and pixel-shift transform;
- do not use stale stored geometry to choose backdrop UVs;
- rounded masking belongs to the card-local material stage, not the shared full-display backdrop.

Background dimming currently lives below ordinary widgets. A card should therefore visually agree with
the dimmed background beneath it. If the dimming operation remains uniform black/opacity, it can be
reapplied cheaply in the material sample path rather than forcing a second composited scene capture.

## 10.6 Widget Theme ownership

The eventual `.srwtheme` contract should primarily **serialize/apply the mature visual settings already exposed in
Settings** instead of inventing a parallel palette system. Existing widget swatches, opacity, border and shadow controls
remain the normal editing surface; a Widget Theme is a named visual bundle over those same authorities. Family-specific
visual values may participate where they are genuinely appearance-only.

Candidate visual ownership includes:

- `default_card_material_mode`: the theme's recommended `normal` / `glass` / `acrylic` surface, **not** the final resolved mode;
- ordinary card tint/opacity and existing card/background swatches;
- semantic text/accent/selection/runtime-overlay colours that are genuinely widget appearance;
- Glass/Acrylic tint/material strength once those scene-local materials are physically proven;
- border colour/opacity/width where already supported;
- shadow visual parameters already exposed by the final widget-style contract;
- other existing appearance-only values that can round-trip without altering runtime behaviour;
- optional bounded material parameters that have actually earned their place through visual/performance testing.

The Widget Theme palette is the **global/default baseline**, not a destructive replacement for existing family-specific card settings. Existing explicit `widgets.<family>.card.*` swatches/opacity/border values keep higher precedence for that family; a family with no explicit authored value inherits the active Widget Theme role. The retained Context Menu has no family override layer and therefore consumes the Widget Theme palette directly. Editing a family-specific swatch is a family customization and does **not** create Widget Theme `Custom`; editing a Widget-Theme-owned baseline swatch does.

The theme palette and the surface override remain independent in the UI. **Do not hide or disable colour swatches merely
because a Widget Theme is selected.** A user choosing a Glass-oriented Widget Theme and then explicitly selecting `Normal`
or `Acrylic` must retain the same theme colours.

Manual editing of any **Widget Theme-owned** appearance value has one deterministic ownership transition:

```text
selected named Widget Theme
        +
manual change to a theme-owned swatch/border/shadow/other visual value
        ↓
snapshot the complete currently resolved Widget Theme appearance into user-owned Custom
        ↓
apply the user's edit to that Custom snapshot
        ↓
Widget Theme selection = Custom
Keep Synced = OFF
```

The switch is intentionally near-silent: no confirmation dialog is required for the edit that creates `Custom`; at most,
show a small passive indication that the Widget Theme is now Custom and sync is off. The shipped/installed `.srwtheme` is
never mutated. The snapshot preserves all currently resolved old theme values and changes only the value the user actually
edited.

`Custom` is a user-owned working snapshot, not a second inheritance/cascade system and **not a physical `.srwtheme`
file**. Persist the Custom snapshot in normal SRPSS Settings data alongside Widget Theme selection/sync state; ordinary
runtime customization must never require write access to the installed ProgramData theme catalogue. Do not preserve a
hidden stack of per-property overrides on top of named themes. Selecting another named Widget Theme may leave the Custom
snapshot available for later return; re-enabling `Keep Synced` while Custom is active may switch selection back to the
Settings theme's linked Widget Theme, but must not destroy the Custom snapshot merely because it is no longer selected.

Creating/exporting a real reusable `.srwtheme` is an explicit authoring/export action, separate from the automatic Custom
working snapshot.

Changing only `card_material_override` does **not** create Custom, dirty/modify the selected theme, or turn Keep Synced off,
because Surface Style is a separate user preference rather than a mutation of the `.srwtheme` bundle.

A Widget Theme should therefore contain a coherent semantic palette plus any proven material-specific tuning needed to
render that palette in each supported material. The selected material determines which tuning is consumed; it must not
replace the theme's semantic colour identity.

Widget Themes do **not** own widget activation, ordinary ON/OFF, provider/account/source state, geometry,
refresh cadence or runtime business logic.

Default/Dark Widget Theme recommends `default_card_material_mode = normal` and reproduces the existing simple card
appearance as closely as practical. Glass/Acrylic remain opt-in and **must not become selectable merely because the file
schema can name them**; the shared/lazy Qt Quick material path needs runtime visual/performance proof first.

### Settings Theme <-> Widget Theme mirroring / Keep Synced

Every mature Settings GUI theme should have a mirrored Widget Theme intended to produce the same visual language on
runtime cards/overlays. The Themes tab should expose **Keep Synced**, default **ON**. With sync ON, choosing a Settings
Theme selects its linked/mirrored Widget Theme (and choosing the linked Widget Theme keeps the pair coherent); the user
sees one coordinated palette without maintaining two selections. Turning sync OFF explicitly permits arbitrary
combinations of Settings GUI theme + Widget Theme.

`Keep Synced` synchronizes **theme identity**, not the explicit surface override. Therefore:

```text
Keep Synced ON + Surface Style = Theme Default
    -> Settings theme selects mirrored Widget Theme
    -> Widget Theme colours + its recommended material both follow the pair

Keep Synced ON + Surface Style = Normal/Glass/Acrylic
    -> Settings theme still selects mirrored Widget Theme and its colours
    -> explicit surface override survives theme changes and wins only for material

Keep Synced OFF
    -> Settings Theme and Widget Theme may be paired arbitrarily
    -> the same Theme Default/explicit surface rule still applies
```

This is the important UX escape hatch for a user who likes a Glass GUI/theme palette but dislikes Glass widget cards: keep
the linked Widget Theme and select `Normal` or `Acrylic` under Surface Style. No theme duplication is required.

Theme IDs/link metadata should be explicit rather than matched by display-name heuristics. Pack-generation tooling may use
matching names/stems as a convenience when producing corresponding `.srtheme` / `.srwtheme` packs, but it should write the
resolved stable link metadata rather than making runtime pairing depend on names forever. Manual Widget Theme-owned edits
follow the Custom-snapshot/auto-unsync rule above; Surface Style does not. Sync must never create two writers fighting over
the same widget setting.

The retained screensaver **Context Menu belongs to Widget Theme semantics**, because it is a runtime display-scene overlay
rendered beside widgets. It must not read the QWidget Settings theme directly. When Keep Synced is ON, the mirrored Widget
Theme naturally makes the Context Menu palette match the Settings GUI; when OFF, the Context Menu follows the independently
selected Widget Theme. Its material consumes the same **effective** runtime surface resolution described above, so an
explicit `Normal`/`Glass`/`Acrylic` override changes the Context Menu material while preserving the selected Widget Theme's
colours. Do not create a second Context-Menu-only surface override unless a later explicit product requirement proves one is
needed. Candidate Context Menu roles include surface/background, border, separator, normal/disabled text, hover/selected
row, toggle/choice indicator, submenu arrow, and the canonical global Card shadow. Glass/Acrylic Context Menu pixels must
reuse the same lazy scene-local Qt Quick material/backdrop authority as widget cards; never invoke the Settings HWND
Acrylic/Glass AccentPolicy path for runtime menu pixels.

## 10.7 Theme file storage / discovery

Settings and Widget Themes share one resolved theme root, with Widget Themes deliberately isolated in a child folder:

```text
installed/frozen:
%ProgramData%\SRPSS\themes\
    *.srtheme
    widgets\
        *.srwtheme

source/dev:
<repo-root>\themes\
    *.srtheme
    widgets\
        *.srwtheme
```

This preserves the existing Settings-theme convention while preventing mirrored `.srtheme` + `.srwtheme` packs from
turning one directory into a hundred-file dump.

Storage/discovery rules:

- filesystem location is startup/build authority, not theme-catalog semantic authority;
- explicit test/tool directory injection remains valid;
- installed/frozen builds use the stable ProgramData root used by other SRPSS curated assets;
- repository/bundled trees are source/dev or bootstrap/copy sources, not a second simultaneously merged production
  catalogue;
- Widget Theme discovery is `resolved_theme_root / "widgets"`;
- installed/frozen theme files are curated/read-mostly runtime assets; normal user customization does not write there;
- the automatic `Custom` Widget Theme snapshot lives in Settings persistence, not `themes/widgets/Custom.srwtheme`;
- portable theme IDs/link metadata never contain absolute install paths;
- a missing external directory must degrade to the appropriate compiled/default-safe theme behavior, not a hidden second
  mutable theme root.

The live `ui/settings_theme_paths.py` placeholder is known temporary wiring. When Widget Themes land, replace/centralize
that stub with the durable shared theme-root resolver rather than cloning another Widget-only path stub.

## 10.8 Performance / acceptance gates

Measure with representative simultaneous cards and real transitions on 1/2/N displays and relevant DPRs:

- full-scene GPU time;
- extra offscreen/capture/blur pass cost;
- texture memory;
- batching impact;
- p95/p99/tail frame cost;
- transition temporal coherence inside and outside cards;
- cost when one card uses a material versus many cards;
- proof that zero Glass/Acrylic consumers returns to the plain Normal/current-translucent cost path.

Bound blur radius/sample count and use deliberate downsampling when the visual result survives it. Only
add polished Settings controls after the material path is visually worthwhile and cheap enough.

The durable contract is therefore:

```text
Widget Theme = semantic visual bundle + recommended/default material
Surface Style = Theme Default | Normal | Glass | Acrylic
Theme Default = follow selected Widget Theme recommendation
explicit Surface Style = override material only; keep Widget Theme colours
one effective runtime material enum = the only renderer-facing material authority
DEFAULT/Dark recommendation = Normal = current cheap translucent OverlayCard
Glass/Acrylic = committed user-selectable modes using lazy shared per-display backdrop + bounded scene-local material
NO per-widget capture pipelines
NO native HWND backdrop mechanism for Quick cards
```

The exact Qt effect/texture type is provisional; the ownership, default behavior, laziness, temporal
coherence and bounded-cost rules are not.

!OPERATOR BOX!
Ideas put in this box are to be added to work asap but at a lower priotiy than future cleanup or current plan work, unless existing in those as well.
############
1. Add two options in the Interaction Pill for Display. "Widget Glow on Hover" "Widget Glow On Click" with a shared swatch colour selector. These will cause a small pulse in glow effect when triggered in relation to the cursor halo and pulse out when hover leaves or click leaves. This must not introduce timers or any thread contention/starvation.
2. Finish the already-reserved Widget Themes pill in the landed Themes tab. Reuse the mature existing widget visual vocabulary rather than inventing parallel presentation controls, but preserve precedence: Widget Theme card roles are global/default baselines and explicit `widgets.<family>.card.*` values remain higher-precedence family overrides; Context Menu consumes the Widget Theme palette directly. Widget Themes use `.srwtheme` files and never own widget activation/ordinary ON/OFF, provider/account/source state, geometry, refresh cadence or runtime business logic. Add `Keep Synced` default ON: each Settings GUI theme has an explicitly linked mirrored Widget Theme; sync OFF permits independent pairings. Manual edits to any Widget Theme-owned visual value silently snapshot the full currently resolved named theme into user-owned `Custom`, apply the edit there, switch Widget Theme to `Custom`, and turn Keep Synced OFF; never mutate the source `.srwtheme` or build hidden per-property inheritance overrides. Keep **surface material orthogonal to theme identity**: `.srwtheme` stores `default_card_material_mode`, while `Settings -> Widgets -> General -> Appearance -> Surface Style` exposes `Theme Default / Normal / Glass / Acrylic` and persists a separate override. `Theme Default` follows the selected Widget Theme; an explicit mode overrides only material while retaining theme colours and does **not** create Custom or unsync. Runtime Context Menu follows the same Widget Theme palette + effective material resolution. The existing/Dark Widget Theme recommends Normal/current cheap translucent cards. The committed Glass/Acrylic modes remain blocked on the shared/lazy Qt Quick material contract in section 10 and require runtime visual/performance proof before becoming selectable.
3. [LOW] Give more SettingsGUI sections Flowcontainers where it would benefit well aligned space usage.
