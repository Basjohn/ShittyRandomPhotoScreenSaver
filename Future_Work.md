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

# 1A. Widget semantic theme-role expansion + shared fade polish

**The Slice-8 semantic foundation plus the named Widget Theme/catalogue/bidirectional-link wave are landed and physically exercised; remaining work is bounded semantic/readability review, not foundational admission.** Continue literal adoption only where it improves the mature shared vocabulary; do not reopen accepted family geometry or create swatches merely because a literal exists. Light/dark-text themes require composition-aware contrast on both the Settings HWND and runtime Widget surfaces.

## 1A.1 Semantic role inheritance instead of swatch proliferation

Extend the existing `WidgetThemeSpec.colors` semantic-role map rather than giving every decorative literal an always-visible Settings swatch. Target roles include branded-header Fill/Border/Text, separators and decorative outlines, secondary panels, gradients, Media transport surface/border/separators, mute surface/border/icon, app-volume Fill/Track/Outline and equivalent Steam secondary surfaces.

Preferred resolution shape:

```text
explicit per-widget override (only when intentionally set)
        ↓ otherwise
widget/family semantic theme role (when theme supplies it)
        ↓ otherwise
shared semantic parent role (text / border / panel / accent / muted)
        ↓ otherwise
preserved current visual default
```

The default/inherit path must reproduce the currently accepted visuals byte-for-pixel-equivalent where practical; adding a role is not permission to recolor shipped defaults. Settings should expose advanced overrides progressively/collapsed or behind an `Inherit` state rather than flooding the normal Widget UI. Do not create a second Media/Steam-local palette system.

**Landed foundation:** `ui/widget_visual_roles.py` owns exactly this cascade; schema-v3 themes admit sparse optional roles; `local.*` terminals never serialize. Consumers include all shared branded headers, Media transport/mute/volume/progress, Gmail action/separators, Reddit/Weather/Clock separators, Steam info/tooltip/artwork/gradients/metrics and the retained Context Menu palette. Named Widget Theme selection/linking and the 58-theme mirror pack are now wired at the construction authority. Remaining work is physical theme review plus incremental adoption of any genuinely meaningful decorative literals, not another resolver or blanket swatch expansion.

## 1A.2 Shared artwork and metadata fade polish

`rendering/quick/qml/ArtworkFadeImage.qml` remains the shared event-driven primitive used by Media, Achievement Pulse and Abandonment Issues artwork. Slice 8 establishes a gentler shared `200 ms` fade-out / `340 ms` fade-in baseline; family lifecycle choreography may explicitly shorten a fade only when the parent is already fully hidden. Preserve no polling, no provider freshness delay and bounded texture/effect cost. A true two-texture artwork crossfade remains optional future polish only if measured visual gain justifies the extra texture residency.

Media Title/Artist/Album now use `MediaMetadataColumn.qml`: model/provider truth updates immediately, the outgoing rendered strings are retained only for one bounded `240/340 ms` old->new opacity crossfade, and the current HorizontalFit/visibility contract is duplicated in both small text columns. No timer/cadence/provider owner was added. Validate rapid track skipping and optional Album state physically before calling this closed.

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
8. **Runtime frosted/glass ordinary-widget cards are rejected/shelved.** Reconsider only if a future renderer architecture independently justifies the capability; do not revive the 2026-09-02 card-only experiments.

Glass Shatter, Directional Pixel Accretion and the Deformable 3D Sphere are worth preserving even if
their first prototypes are abandoned. Their intended identities should not collapse into generic
`shatter`, `pixel dissolve`, or `audio sphere` effects.

---

# 10. Runtime Widget Themes — colour-only semantic bundles

Status: implemented/retained. Runtime Widget Themes are intentionally narrower than Settings themes: they own semantic colours and explicit Settings<->Widget stable link identity, not backdrop/material rendering. The 2026-09-02 Quick Glass/Acrylic card experiments were rejected after physically breaking wallpaper/transition presentation and are preserved only in `Docs/QtQuick_Migration/Rejected_Card_Material_Experiments_2026-09-02.md`.

Durable contract:

```text
Widget Theme = stable identity + linked Settings-theme id + semantic RGBA roles
Custom       = persisted colour snapshot created by editing a theme-owned role
Keep Synced  = bidirectional stable-ID theme identity link
Style Overrides = Card Surface + Card Border + Card Border Width
runtime card = ordinary retained RGBA OverlayCard path
```

- Widget Themes never own activation, ordinary ON/OFF, provider/account/source state, geometry, refresh cadence, compositor state or native Settings-window backdrop mode.
- Card Surface/Card Border edits snapshot the full resolved named palette into `Custom` and switch the Widget side Independent; explicit family card overrides remain higher precedence.
- Card Border Width is a global geometry/style value outside `.srwtheme`.
- Context Menu consumes Widget Theme semantics directly because it has no family override layer.
- Specialized optional roles inherit through `ui/widget_visual_roles.py`; do not serialize `local.*` presentation context or invent family-local cascades.
- The curated pack contains 58 Settings themes + 58 deterministic Widget mirrors. Widget mirrors are schema-v3 colour-only files and materialize mature Media/Volume/Seek/Backlog roles through `tools/generate_widget_theme_mirrors.py`.
- Settings theme names/files may contain `[Glass]`/`[Acrylic]` because those describe the Settings HWND. Widget mirror names/files omit those runtime-irrelevant tags while `linked_settings_theme_id` keeps the exact Settings file identity.
- Theme Foundry `Save Widget Counterpart…` must use the same deterministic converter as pack generation and strict-reload its output.
- Installed/frozen storage remains `%ProgramData%\SRPSS\themes\widgets`; source/dev remains `<repo-root>/themes/widgets`. `Custom` remains Settings persistence, never a generated file.
- The retained screensaver Context Menu follows the selected Widget Theme, not the QWidget Settings theme directly. When linking is ON the paired identities naturally coordinate palettes; when Independent it follows the independently selected Widget Theme.

Do not add a Surface Style control, `default_card_material_mode`, `card_material_override`, runtime material enum, material Loader/capture/mask tree, or background-layer cadence callback back into this architecture. A future backdrop-card proposal requires a fresh product/renderer justification and must start from the rejected-experiment record rather than reviving hidden debris.

!OPERATOR BOX!
Ideas put in this box are to be added to work asap but at a lower priotiy than future cleanup or current plan work, unless existing in those as well.
############
1. Add two options in the Interaction Pill for Display. "Widget Glow on Hover" "Widget Glow On Click" with a shared swatch colour selector. These will cause a small pulse in glow effect when triggered in relation to the cursor halo and pulse out when hover leaves or click leaves. This must not introduce timers or any thread contention/starvation.
2. Finish/accept the colour-only Widget Themes vertical slice. Preserve the shared semantic resolver, 58 mirrored `.srwtheme` catalogue, explicit bidirectional stable-ID link metadata, Linked/Independent control and Custom snapshot behavior. Widget Theme card roles are global/default baselines and explicit `widgets.<family>.card.*` values remain higher-precedence family overrides; Context Menu consumes Widget Theme semantics directly. Continue semantic migration only where physical review exposes a meaningful uncovered visual; do not serialize `local.*`, blanket-theme debug/editor/shadow primitives, or revive runtime card-material state.
3. [LOW] Give more SettingsGUI sections Flowcontainers where it would benefit well aligned space usage.
