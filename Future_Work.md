# Future Work

Last updated: 2026-08-24

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

Shallow Z/depth presentation option without changing Bubble logical motion. Prefer instanced billboard
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

# 10. Frosted / glass ordinary-widget cards

**Status: far-future optional customization. This is not migration parity and is not admitted merely
because Qt Quick makes it possible.** The ordinary-widget migration should first finish on the simple
retained `OverlayCard` path.

Goal: optionally let the transparent/translucent area of an ordinary widget card blur the screensaver
image/transition behind it so the card reads as real frosted/glass material rather than only a tinted
transparent rectangle.

Conceptual destination:

```text
base image / transition scene for one display
        ↓
one lazy shared per-display backdrop source
        ↓
optional bounded downsample / shared blur representation
        ↓
card-local crop/sample + rounded mask
        ↓
translucent tint + border
        ↓
normal cached card shadow + retained family content
```

The important optimization is **shared per display, not one full-screen capture per widget**.

Rules for a future implementation:
- NEVER DELETE THE OPERATOR BOX FROM THIS DOCUMENT OR ANY OTHER IT IS FOUND IN, ONLY IMPORT IT INTO ACTIVE OR NEAR FUTURE WORK AND CLEAN IT.
- do not create one full-display `ShaderEffectSource`, FBO/capture or equivalent backdrop copy for every
  glass widget;
- when at least one glass card is active, establish the smallest legal shared backdrop source for that
  display and let cards sample bounded regions from it;
- if all active glass cards use the same blur policy/radius, prefer one blurred/downsampled backdrop per
  display and crop/sample it per card rather than repeating the blur pass for each widget;
- if authored cards genuinely require different blur strengths, still share the underlying backdrop
  source and bound any per-card effect work to the card region where practical;
- the backdrop represents the scene **below ordinary widgets** (normally base image/transition pixels),
  not an already-composited capture of the widgets themselves; avoid feedback recursion, double-blur,
  and accidentally blurring later z-layers such as the Visualizer/control overlays;
- no glass-enabled cards means no backdrop capture/layer/effect work: the optional feature should return
  to the ordinary `OverlayCard` cost when disabled;
- keep the path GPU/Quick-native. Do not introduce Python pixel readback, QWidget screenshots, QPixmap
  bridges or a second app-managed FBO/pixmap cache merely to create glass;
- `MultiEffect`, a purpose-built shader/effect, or another final-Qt-Quick mechanism may be used if final
  architecture/performance evidence earns it. This future permission does not reopen ordinary text
  shadow blur or the QWidget one-effect workaround architecture;
- preserve the single production `QQuickWindow`/retained-scene architecture and normal root-fade
  semantics;
- measure full-scene GPU time, offscreen-pass cost, texture memory, batching impact and p95/p99/tails on
  representative multi-display/DPR setups with several simultaneous glass cards;
- bound blur radius/sample count and consider deliberate backdrop downsampling when the visual result is
  acceptable;
- only add polished Settings controls after the visual path is proven worthwhile and cheap enough.

The final implementation should inspect the then-current Qt/PySide capabilities before selecting
`ShaderEffectSource`, `MultiEffect`, custom shader composition or another mechanism. The durable product
contract is the shared/lazy/bounded architecture above, not a particular provisional Qt type.

!OPERATOR BOX!
Ideas put in this box are to be added to work asap but at a lower priotiy than future cleanup or current plan work, unless existing in those as well.
############
1. Give SettingsGUI Display section a Pill style look like widgets/transitions for its sections as they are quite large.
2. Add two options in the Interaction Pill for Display. "Widget Glow on Hover" "Widget Glow On Click" with a shared swatch colour selector. These will cause a small pulse in glow effect when triggered in relation to the cursor halo and pulse out when hover leaves or click leaves. This must not introduce timers or any thread contention/starvation.
3. Check if Settings GUI Theme support has completely landed and if it has its own tab yet. Ideal goal Settings GUI loadable themes and a second pill for Widget Themes. Widget Themes would control the choice of colours for widgets (not their on/off state or geo positions, only visual customization) and if they are using glass cards/opacity/shadows/acrylic or anything else available to them visually. Existing will be default as it already is (Dark). Widget themes will be .srwtheme files.
5. [LOW] Give more SettingsGUI sections Flowcontainers where it would benefit well aligned space usage.
