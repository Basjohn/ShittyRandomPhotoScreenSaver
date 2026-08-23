# 02 — Quick Scene Renderer, Images, Transitions and Pacing

Status: **Phase-C landed architecture / current transition-authoring authority**  
Last updated: 2026-08-23

Cross-links:

- sequence/work admission: `Current_Plan.md`
- transition authoring/checklist: `Docs/Transition_Change_Checklist.md`
- capability activation / landed E2: `Docs/QtQuick_Migration/07_Settings_Capability_Activation.md`
- runtime/lifecycle: `Docs/QtQuick_Migration/01_Runtime_Host_Lifecycle.md`
- validation routing: `Docs/Harness_Index.md`
- deferred deletion: `Future_Cleanup.md`

Phase C implementation and deterministic test hardening are landed. The transition architecture below
is current authoring/regression authority; it is not a request to repeat Phase C. Operator-scheduled
physical/eyes-on evidence remains separate acceptance work where `Current_Plan.md` records it.

## 1. Selected scene/render architecture

The production destination remains one standalone threaded `QQuickWindow` per selected physical
display with custom OpenGL rendered inline in the Quick scene.

```text
QQuickWindow
  -> Quick scene
      -> full-screen background/transition QQuickItem
          -> QSGRenderNode
              -> direct OpenGL
      -> visualizer QQuickItem/QSGRenderNode
      -> retained Quick widgets/overlays
```

`QQuickWidget` is prohibited. `QQuickRhiItem`/offscreen-composite presentation is not the normal SRPSS
custom-render path. A second accelerated transition/visualizer window is prohibited.

Qt Quick bootstrap remains explicit before the first scene graph exists:

- threaded render loop;
- OpenGL graphics API;
- current pinned OpenGL format requirements unless exact source proves a deliberate change.

The P0 evidence selected this architecture. Do not reopen presenter comparison without contradictory
implementation evidence.

## 2. Render-thread ownership

A custom transition render node may own, when needed:

- GL programs;
- VAOs/VBOs/meshes;
- image textures;
- transition-specific buffers;
- depth state/resources;
- other context-local effect resources.

GUI/runtime state crossing into render ownership is immutable/synchronized. The render thread does not
read live QWidget/QPixmap, SettingsManager, provider objects or arbitrary mutable QObject state.

Create/use/delete context-local GL resources on the legal render owner. Failed deletion remains
accounted/loud until ownership is actually released.

## 3. Common GL state fence

Transition rendering must leave the Quick scene graph safe for later nodes.

The common host preserves/restores every state touched by an implementation, including as applicable:

- viewport/scissor;
- program;
- VAO/VBO bindings;
- active texture and texture bindings;
- blend enable/function;
- cull state;
- depth enable/write/function/clear state;
- stencil state;
- later state introduced by a migrated effect.

The permanent regression includes restoration on the normal path **and when renderer execution raises**.

A complex implementation may use depth or custom meshes; it may not leak that state into the next
Quick node.

## 4. Immutable image boundary

The existing engine/image pipeline may continue to produce `QPixmap` on its legal side. Presentation
converts/captures detached immutable image content before render-thread ownership.

Conceptually:

```text
PresentationImage
    identity/path/cache key
    logical size
    DPR intent
    immutable QImage/RGBA payload
```

Per-display render ownership keeps the current base texture and, during a transition, the source/
destination pair required by the active run.

Do not repeatedly convert/upload stable images each frame. Do not perform QWidget grabs/painting from
the render thread.

## 5. Transition lifecycle

The landed transition-neutral boundary is:

```text
canonical transition descriptor
        ↓
application activation admission
        ↓
GUI/runtime-side settings + random/manual resolution
        ↓
TransitionRequest
        ↓
TransitionRun
        ↓
monotonic TransitionSample
        ↓
lazy Quick transition renderer
```

`TransitionRequest`/`TransitionRun` own presentation-neutral lifecycle and immutable values.
Completion/cancellation are exactly once and generation/run-id fenced.

The controller does not wait for a “last frame painted” acknowledgement. A missed display opportunity
advances to the current monotonic sample; it is not replayed.

Explicit cancellation snaps/finalizes according to authored destination policy once. Stale render
snapshots/completions are rejected by identity/generation.

## 6. Application-level activation — LANDED E2 contract

Transition activation is a landed coarse runtime authority:

```text
transitions.activation.<canonical setting name>
```

It is distinct from manual selection and saved Random-pool membership.

A deactivated transition is excluded from effective manual/cycle/random resolution and must not gain a
renderer merely because its code is installed.

Saved pool preference may remain while inactive. Effective runtime Random candidates are:

```text
activated ∩ saved pool membership ∩ runnable/hardware
```

E2 `SETUP`/pill UI and live navigation are implementation-closed and use the same canonical activation
store. They do not introduce a second authority.

The formerly ambiguous invalid states now have explicit persisted normalization:

```text
zero activated transitions
    -> activate Crossfade in canonical state
    -> persist repair

Random on + empty effective saved pool
    -> random_always=False
    -> persist deterministic activated manual selection
    -> preserve saved pool preferences
```

This is state repair, not permission to execute a deactivated Crossfade.

Final admission is also closed: stale pre-resolved `transitions.random_choice` is revalidated at the
factory boundary; `_pick_random_transition` fails closed rather than returning blanket Crossfade; and
engine/factory/C-key empty-candidate paths never run a deactivated transition. `random_always` is the
single live Random authority; legacy `type="Random"` is migration input only.

Do not write “before E2 exposes it” or “E2 adds this later” around this contract. It is landed and must
be preserved.

## 7. Canonical authored timing

User-selectable global transition easing is retired from the final architecture. Legacy persisted
easing may remain loadable during migration but is not runtime authoring authority.

The canonical descriptor/effect owns timing:

- Slide uses `SINE_IN_OUT`;
- shader/physics effects that already stage their own motion normally receive a linear outer timeline;
- 3D Block Spins receives a linear outer timeline and applies its authored cubic spin internally.

Never add easing to conceal seam/cadence defects.

## 8. Static lazy implementation registry

Transition rendering is internally plugin-shaped but statically registered.

Canonical identity remains in `rendering/transition_registry.py`. The Quick implementation registry
contains only lightweight module/factory references until an **activated** transition is actually
resolved.

A deactivated transition must not gain solely from catalog/settings construction:

- implementation-module import;
- shader import/compile;
- GPU allocation;
- transition-specific timer/state/resource ownership.

No central transition `if/elif` dispatcher belongs in `QuickSceneController`, `TransitionRequest` or
`TransitionRun`.

Do not turn this internal modularity into dynamic discovery, manifests, hot loading, dependency
resolution, API versioning or a third-party SDK.

Permanent registry parity proves canonical production ids and Quick implementation ids match exactly
and remain unique.

## 9. GUI-side parameter resolution

Parameterized effects resolve Settings spelling, canonical defaults, random choices, clamping, color
normalization and supported legacy fall-through semantics before request admission.

Canonical Settings defaults are fallback authority. Do not duplicate stale constructor defaults in the
Quick renderer.

Renderers are strict: required resolved values must be present and valid rather than silently invented
at render time.

Per-run seeds/random choices are selected once and frozen into the request/run.

## 10. Canonical transition inventory

All 12 canonical production transitions have Quick implementations:

1. Crossfade
2. Slide
3. Wipe
4. Warp Dissolve
5. Block Puzzle Flip
6. 3D Block Spins
7. Blinds
8. Diffuse
9. Ripple / Raindrops
10. Crumble
11. Particle
12. Burn

If the canonical registry changes, registry parity must fail until the Quick implementation surface is
updated deliberately.

No final Quick transition depends on `GLCompositorWidget`.

## 11. Slide preservation contract

Quick Slide supports the four product directions:

- left;
- right;
- up;
- down.

Source and destination coordinates plus sole pixel ownership come from one immutable eased sample in
one draw. Their union covers the complete viewport at endpoints, midpoint, arbitrary fractions and
discontinuous progress jumps caused by missed presentation intervals.

Do not independently accumulate or round source/destination positions.

Do not restore diagonal full-frame Slide unless a newly authored effect also solves exposed-corner
coverage.

## 12. Block Puzzle Flip preservation contract

Block Puzzle Flip remains shader-authoritative with resolved Settings-owned rows/columns.

Preserve its 3D strip/slab visual character, cardinal and saved diagonal semantics, exact endpoints and
authored behavior. Do not reintroduce CPU region/per-block QWidget presentation ownership.

## 13. 3D Block Spins preservation contract

3D Block Spins is a real 3D effect, not a flat narrowing approximation.

Preserve:

- one thin 36-vertex rectangular-prism slab;
- front/back/side faces and thickness;
- depth-tested face ordering over opaque black void;
- horizontal, vertical and both diagonal axes;
- opposite-direction spin signs;
- destination/back-face UV transforms that keep arriving image upright;
- cubic internal spin timing;
- dark side core;
- direction-sensitive moving specular band;
- edge-on white rim;
- exact source/destination endpoints;
- context-local mesh/program ownership and teardown.

No flat-quad fallback.

## 14. Blinds preservation contract

Preserve the authored Blinds fragment shader rather than a lookalike rewrite.

Keep:

- linear outer timeline;
- authored slat grid;
- Horizontal, Vertical and Diagonal modes;
- resolved shader-space feather;
- centre-out band growth;
- late global destination tail;
- lazy implementation/resource ownership.

`Random` is resolved before renderer admission.

## 15. Diffuse / Ripple / Crumble

These effects reuse canonical shader/math through isolated Quick renderers.

### Diffuse

Preserve block-size/grid semantics and authored shape modes: Rectangle, Membrane, Lines, Diamonds,
Amorph, Random.

### Ripple / Raindrops

Preserve ripple-count bounds, per-run seed, existing raindrop shader behavior and exact endpoints.

### Crumble

Preserve piece count, crack complexity, per-run seed, mosaic uniform contract where present and
canonical weighting modes. Current Settings/factory label quirks are migration evidence; do not
silently reinterpret them during renderer work.

`u_mosaic_mode` is not a visual-behavior contract while the canonical fragment shader does not consume
it. Test optional upload only until authored shader behavior deliberately changes.

## 16. Particle preservation contract

Preserve the canonical particle shader and:

- Directional, Swirl and Converge modes;
- eight directional vectors;
- Random Direction / Random Placement shader semantics;
- particle radius and overlap;
- trail length/strength;
- swirl strength/turns/order;
- 3D shading;
- texture mapping;
- wobble;
- gloss size;
- light direction;
- per-run seed;
- physical-framebuffer `u_resolution` semantics.

Settings label/index oddities are not permission to retune the effect.

## 17. Burn preservation contract

Burn uses the actual authored rich shader/math.

Preserve:

- exact source/destination endpoints;
- four cardinal + two diagonal directions;
- ignition phase before front movement;
- four-octave noise/domain-warped FBM;
- jagged paper-like front displacement;
- heat distortion;
- warm glow bleed;
- white-hot/thermite core;
- char width and cooling progression;
- crackle/detail/smouldering pulse;
- glow intensity/color;
- sparks/embers;
- smoke wisps;
- falling ash;
- smoke/ash toggles/density;
- per-run seed;
- effect time derived from immutable run clock;
- delayed near-completion destination tail fade.

Do not reduce Burn to a noisy wipe.

## 18. Presentation frame pacer

One presentation pacer exists per display/window.

Inputs include active transition demand and visible custom-GL visualizer demand.

Properties:

- target follows owning display refresh;
- single-shot/monotonic deadline behavior;
- missed opportunities skipped;
- `QQuickWindow.update()` requested only while dynamic custom rendering needs frames;
- no `afterRendering -> update()` self-loop;
- no FIFO/catch-up;
- no paint acknowledgement;
- no feedback into visualizer logical cadence.

Static retained widgets do not keep the custom-GL pacer alive merely because they exist.

## 19. Quick-native ordinary animations

Use retained Quick properties/animations for ordinary opacity/geometry/hover behavior where
appropriate.

Do not introduce a Python callback per physical frame for simple UI animation. Quick animation never
becomes visualizer simulation authority.

## 20. Landed deterministic test hardening

The following are **landed permanent regression obligations**, not Phase-C TODOs:

- effect-discriminative real-GL oracles for Diffuse/Ripple/Crumble/Particle/Burn;
- deterministic parameter sensitivity for Ripple counts, Crumble weighting, Particle modes/directions
  and Burn smoke/ash toggles;
- direct request -> uniform wiring tests for parameter-rich renderers;
- common GL-state fence and exception-path restoration;
- sparse-default coverage including Blinds/Ripple;
- controller cancellation/generation-fence false-pass correction;
- Crumble `mosaic_mode` tests limited to actual authored shader behavior;
- registry parity as canonical inventory rather than a duplicate hard-coded id list.

Do not “add” these again. Preserve/extend them only when a changed contract requires new coverage.

## 21. Physical/eyes-on evidence

Implementation/source closure and physical acceptance remain separate evidence classes.

Current Plan records the exact Phase-C sign-off state, including the completed deterministic and
real-GL sweeps. Preserve the runnable harnesses in `Docs/Harness_Index.md` as regression tools.

Future acceptance work may include:

- visual parity where subjective authored effect character matters;
- refresh/mixed-refresh continuity;
- physical delivery/PresentMon only when it answers a new question.

A later failure reopens the smallest demonstrated defect. It does not reopen the selected presenter
architecture by default.

## 22. Phase-C closure

Phase C implementation is complete. Later phases may use this document as current transition-authoring
and regression authority.

Production cutover remains Phase H. Old compositor-only presentation code is
**CURRENT-LEGACY — WILL BE OBSOLETE at Phase I** after caller proof; no new Quick transition may call
back into it or keep it as a fallback.
