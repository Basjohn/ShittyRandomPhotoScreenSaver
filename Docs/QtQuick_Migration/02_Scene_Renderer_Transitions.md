# 02 — Quick Scene Renderer, Images, Transitions and Pacing

Status: Phase-C landed architecture / current transition-authoring authority
Last updated: 2026-08-21

Cross-links:

- sequence and phase admission: `Current_Plan.md`
- transition authoring/checklist: `Docs/Transition_Change_Checklist.md`
- runtime/lifecycle: `Docs/QtQuick_Migration/01_Runtime_Host_Lifecycle.md`
- validation routing: `Docs/Harness_Index.md`
- deferred deletion: `Future_Cleanup.md`

## 1. Selected scene/render architecture

The production destination remains one standalone threaded `QQuickWindow` per selected physical display with custom OpenGL rendered inline in the Quick scene.

```text
QQuickWindow
  -> Quick scene
      -> full-screen background/transition QQuickItem
          -> QSGRenderNode
              -> direct OpenGL
      -> visualizer QQuickItem/QSGRenderNode
      -> retained Quick widgets/overlays
```

`QQuickWidget` is prohibited. `QQuickRhiItem`/offscreen-composite presentation is not the normal SRPSS custom-render path. A second accelerated visualizer/transition window is prohibited.

Qt Quick bootstrap remains explicit before the first Quick scene graph exists:

- threaded render loop;
- OpenGL graphics API;
- current OpenGL 4.1/core requirements unless exact source proves otherwise.

The P0 evidence already selected this architecture. Do not reopen presenter comparison without contradictory implementation evidence.

## 2. Render-thread ownership

A custom render node may own, when needed:

- GL programs;
- VAOs/VBOs/meshes;
- image textures;
- transition-specific buffers;
- depth state/resources;
- later visualizer-specific GPU resources.

GUI/runtime state crossing into render ownership must be immutable/synchronized. The render thread must not read live QWidget/QPixmap, SettingsManager, provider objects, `SpotifyVisualizerWidget`, or arbitrary QObject state.

Create/use/delete context-local GL resources on the legal render owner. Failed deletion remains accounted/loud until ownership is actually released.

## 3. Common GL state fence

Transition rendering must leave the Quick scene graph safe for later nodes.

The common transition host is responsible for preserving/restoring every state touched by an implementation, including at least:

- viewport/scissor;
- program;
- VAO/VBO bindings;
- active texture and texture bindings;
- blend enable/function;
- cull state;
- depth enable/write/function/clear state;
- stencil state;
- any later state introduced by a migrated effect.

A complex implementation may use depth or custom meshes. It may not leak those settings into the next Quick node.

## 4. Immutable image boundary

The existing engine/image pipeline may continue to produce `QPixmap` on its legal side. Presentation converts/captures detached immutable image content before render-thread ownership.

Conceptually:

```text
PresentationImage
    identity/path/cache key
    logical size
    DPR intent
    immutable QImage/RGBA payload
```

Per-display render ownership keeps the current base texture and, during a transition, the source/destination pair required by the active run.

Do not repeatedly convert/upload stable images each frame. Do not perform QWidget grabs/painting from the render thread.

## 5. Transition lifecycle

The landed transition-neutral boundary is:

```text
canonical transition descriptor
        ↓
GUI/runtime-side settings + random resolution
        ↓
TransitionRequest
        ↓
TransitionRun
        ↓
monotonic TransitionSample
        ↓
lazy Quick transition renderer
```

`TransitionRequest`/`TransitionRun` own presentation-neutral lifecycle and immutable values. Completion/cancellation are exactly once and generation/run-id fenced.

The controller does not wait for a "last frame painted" acknowledgement. A missed display opportunity advances to the current monotonic sample; it is not replayed.

Explicit cancellation snaps/finalizes according to the authored destination policy once. Stale render snapshots/completions are rejected by identity/generation.

## 6. Canonical authored timing

User-selectable transition easing is retired for the final architecture. Legacy persisted easing may remain loadable during migration but is not a runtime-authoring authority.

The canonical descriptor/effect owns timing:

- Slide uses `SINE_IN_OUT`.
- Shader/physics effects that already stage their own motion normally receive a linear outer timeline.
- 3D Block Spins receives a linear outer timeline and applies its authored cubic spin internally.

Never add easing to conceal seam/cadence defects.

## 7. Static lazy implementation registry

Transition rendering is internally plugin-shaped but statically registered.

Canonical identity remains in `rendering/transition_registry.py`. The Quick implementation registry contains only lightweight module/factory references until an enabled transition is actually resolved.

Disabled transitions may remain discoverable in Settings, but disabled runtime selection must not cause:

- implementation-module import;
- transition shader import/compile;
- GPU allocation;
- transition-specific timers/state/resources.

No central transition `if/elif` dispatcher belongs in `QuickSceneController`, `TransitionRequest`, or `TransitionRun`.

Do not turn this internal modularity into dynamic discovery, manifests, hot loading, dependency resolution, API versioning, or a third-party SDK.

A permanent registry-parity test now makes the Phase-C inventory self-checking: canonical production ids and Quick implementation ids must match exactly and remain unique.

## 8. GUI-side parameter resolution

Parameterized effects resolve Settings spelling, canonical defaults, random choices, clamping, color normalization, and legacy fall-through semantics before request admission.

Canonical Settings defaults are the fallback authority. Do not duplicate stale constructor defaults in the Quick resolver.

The renderers are intentionally strict: required resolved values must be present and valid instead of being silently invented in the renderer.

Per-run seeds/random values are selected once and frozen into the request/run.

## 9. Landed canonical transition inventory

Phase C now has Quick implementations for all 12 canonical production transitions:

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

If the canonical registry changes later, registry parity must fail until the Quick implementation surface changes with it.

No final Quick transition depends on `GLCompositorWidget`.

## 10. Slide preservation contract

Quick Slide supports the four product directions only:

- left;
- right;
- up;
- down.

Source and destination coordinates plus the sole pixel owner come from the same immutable eased sample in one draw. Their union must cover the complete viewport at endpoints, midpoint, arbitrary fractions, and discontinuous progress jumps caused by missed presentation intervals.

Do not independently accumulate or round source/destination positions.

Do not restore diagonal full-frame Slide unless a newly authored effect also solves the exposed-corner coverage problem.

## 11. Block Puzzle Flip preservation contract

Block Puzzle Flip remains shader-authoritative with resolved Settings-owned rows/columns. Its Quick visual contract is 3D strip/slab behavior rather than CPU region/per-block QWidget work.

Preserve cardinal and the saved diagonal direction semantics, exact endpoints, and authored visual character. Do not reintroduce CPU-region presentation ownership.

## 12. 3D Block Spins preservation contract

3D Block Spins is a real 3D effect, not a flat narrowing approximation.

Preserve:

- one thin 36-vertex rectangular-prism slab;
- front/back/side faces and thickness;
- depth-tested face ordering over opaque black void;
- horizontal, vertical, and both diagonal axes;
- opposite direction spin signs;
- destination/back-face UV transforms that keep the arriving image upright;
- cubic internal spin timing;
- dark side core;
- direction-sensitive moving specular band;
- edge-on white rim;
- exact source/destination endpoints;
- context-local mesh/program ownership and teardown.

No flat-quad fallback.

## 13. Blinds preservation contract

Preserve the existing authored Blinds fragment shader rather than a lookalike rewrite.

The Quick implementation keeps:

- linear outer timeline;
- existing effective slat grid;
- Horizontal, Vertical, and Diagonal modes;
- resolved shader-space feather;
- authored centre-out band growth;
- late global destination tail;
- lazy implementation/resource ownership.

`Random` is resolved before renderer admission.

## 14. Diffuse / Ripple / Crumble

These effects reuse the existing canonical shader/math surface through isolated Quick renderers.

### Diffuse

Preserve block-size/grid semantics and authored shape modes: Rectangle, Membrane, Lines, Diamonds, Amorph, Random.

### Ripple / Raindrops

Preserve ripple-count bounds, per-run ripple seed, existing raindrop shader behavior, and exact endpoints.

### Crumble

Preserve piece count, crack complexity, per-run seed, mosaic flag contract, and canonical numeric weighting modes. Current legacy Settings/factory fall-through quirks are migration evidence; do not silently reinterpret labels during renderer migration. H0 may deliberately reset/repair presentation settings later.

## 15. Particle preservation contract

Particle reuses the authored canonical particle shader.

Preserve:

- Directional, Swirl, and Converge modes;
- all eight directional vectors;
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
- physical-framebuffer `u_resolution` semantics used by the old compositor.

Settings label/index oddities are not permission to retune the effect during migration.

## 16. Burn preservation contract

Burn is an authored-rich effect and must use the actual canonical Burn shader/math.

Preserve:

- exact source/destination endpoints;
- four cardinal plus two diagonal directions;
- 5% ignition phase before front movement;
- four-octave noise and domain-warped FBM;
- jagged paper-like front displacement;
- heat distortion;
- warm glow bleed;
- white-hot/thermite core;
- char width;
- hot ember -> cooling ember -> dark char -> destination progression;
- char crackle/detail;
- smouldering pulse;
- glow intensity/color;
- sparks/embers;
- smoke wisps;
- falling ash;
- smoke/ash enablement and density;
- per-run seed;
- animated effect time derived from the immutable run clock;
- delayed near-completion destination tail fade.

Do not reduce Burn to a noisy wipe.

## 17. Presentation frame pacer

One presentation pacer exists per display/window.

Inputs include active transition demand and later visible custom-GL visualizer demand.

Properties:

- target follows the owning display refresh;
- single-shot/monotonic deadline behavior;
- missed opportunities are skipped;
- `QQuickWindow.update()` only when continuous custom rendering needs a frame;
- no `afterRendering -> update()` loop;
- no FIFO/catch-up;
- no paint acknowledgement;
- no feedback into visualizer logical cadence.

Static retained widgets do not keep the custom GL pacer alive merely because they exist.

## 18. Quick-native ordinary animations

Use retained Quick properties/animations for ordinary opacity/geometry/hover behavior where appropriate.

Do not introduce a Python callback for every physical frame of simple UI animation. Quick animation never becomes visualizer simulation authority.

## 19. Evidence and deferred Phase-C sign-off

Implementation/source closure and physical acceptance are separate evidence classes.

Permanent deterministic gates should cover:

- registry parity and lazy dormancy;
- request/settings resolution;
- strict parameter admission;
- exact shader/math reuse where required;
- endpoints/midpoints/directions/modes;
- interruption/exactly-once completion;
- generation fencing;
- resource release;
- GL-state restoration.

Focused real-GL wrappers exist for the remaining parameterized effects and Blinds. `tools/qtquick_phase_c_effect_smoke.py` includes Diffuse shapes, Ripple counts, Crumble weighting modes, Particle modes/directions, and Burn directions/toggle cases.

Physical/eyes-on acceptance remains deferred and must not be inferred from deterministic/source-contract tests alone:

- one-window real OpenGL smoke;
- two physical display smoke where requested;
- normal/high-refresh continuity;
- old-vs-Quick eyes-on authored-effect comparison;
- physical cadence/PresentMon only when it answers a new question.

A failure in deferred evidence reopens the smallest demonstrated defect. It does not reopen the selected presenter architecture by default.

## 20. Phase-C closure status

Phase-C implementation is structurally complete and Phase D may proceed.

Remaining Phase-C work is acceptance/sign-off only unless new evidence demonstrates an implementation defect.

Production cutover remains Phase H; old compositor-only presentation code remains until Phase I deletion. Shared authored shader/math assets may survive when the Quick renderer is their real consumer.
