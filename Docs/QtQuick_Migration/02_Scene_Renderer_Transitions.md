# 02 — Quick Scene Renderer, Images, Transitions and Pacing

Status: technical decomposition only
Last updated: 2026-08-20

Cross-links:

- sequence: `Current_Plan.md`
- cleanup: `Future_Cleanup.md`
- transition checklist: `Docs/Transition_Change_Checklist.md`

## 1. Why not QQuickRhiItem as the default SRPSS custom renderer

`QQuickRhiItem` is the Quick counterpart of QRhiWidget: render to an offscreen color texture, then
composite that texture into the scene.

SRPSS is migrating specifically to avoid unnecessary presentation layers.

Preferred first production proof:

```text
QQuickItem(ItemHasContents)
    -> QSGRenderNode
    -> inline OpenGL commands
```

This keeps custom content in the main Quick scene render ordering without an extra item-sized
offscreen render target.

The choice is not irrevocable until the first primitive proof passes pinned PySide 6.9.1 + compiled
smoke. If it is fundamentally blocked, revise the single chosen primitive before porting the product.
Do not keep two runtime renderers.

## 2. Proposed renderer structure

```text
rendering/quick/
    render/
        background_item.py
        background_node.py
        visualizer_item.py
        visualizer_node.py
        gl_resources.py
        image_textures.py
        transition_renderer.py
        transition_state.py
```

### Full-screen background node

Draws:

- stable base image;
- active old/new transition;
- transition-specific overlays/particles.

### Visualizer node

A separate scene-graph item/node at the visualizer card geometry/z position.

It is still inside the same `QQuickWindow`.

This lets ordinary retained Quick widgets participate naturally above/below it without a second
window or offscreen QWidget surface.

## 3. Render-thread ownership

Render node owns:

- GL programs;
- VAO/VBO;
- textures;
- per-transition GPU buffers;
- visualizer GPU resources used by that node.

GUI/runtime state must be synchronized into immutable render-node state.

The render thread must not read live:

- `QPixmap`;
- QWidget;
- `QQuickItem` properties outside the permitted sync/updatePaintNode phase;
- `SpotifyVisualizerWidget`;
- provider objects;
- SettingsManager.

## 4. OpenGL state

Inside `QSGRenderNode::render()`:

- use the scene graph's active OpenGL context;
- do not call `beginExternalCommands()`/`endExternalCommands()` from inside the render node unless
  Qt documentation for the exact binding requires it; render nodes are already the integration seam;
- accurately declare changed render states;
- restore/leave GL state according to QSGRenderNode contract;
- do not assume the old QRhiWidget FBO/context shape.

Audit state touched by existing renderer:

- viewport;
- scissor;
- blend enable/function;
- stencil;
- depth;
- program;
- VAO/VBO;
- active texture/bindings;
- clear state.

No state leak into later Quick nodes.

## 5. Image boundary

Current engine/image pipeline may continue to produce `QPixmap`.

The presentation boundary must convert/capture immutable image content on the GUI-safe side.

Preferred model:

```text
PresentationImage
    id / path / cache identity
    logical QSize
    DPR intent
    QImage or immutable RGBA bytes
```

Render node uploads only when image identity changes.

Do not:

- call QWidget screen-grab/paint from render thread;
- repeatedly convert QPixmap every frame;
- upload stable image textures every frame.

Keep old/new image textures alive for exactly the active transition + resulting base ownership.

## 6. Texture ownership

Per display render node/context generation owns its textures.

No cross-window numeric GL-handle sharing unless a later explicit proven shared-context contract
requires it.

Account:

- current base texture;
- transition destination texture;
- transition scratch/particle buffers;
- visualizer resources.

On scene invalidation, delete on the legal render/context owner.

Failed deletion is loud and ownership remains accounted until actually released.

## 7. Transition control refactor

Current `gl_compositor_*_transition.py` classes are presentation-coupled:

```text
BaseTransition
-> parent DisplayWidget
-> find _gl_compositor
-> call compositor start_*
-> AnimationManager/compositor completion
```

Do not make Quick pretend to expose `_gl_compositor`.

Destination:

```text
TransitionRequest
    canonical transition id
    duration
    easing
    direction/parameters
    old/new PresentationImage identities

        ↓

TransitionRun
    immutable start identity
    monotonic start time
    monotonic end time
    transition-specific immutable parameters

        ↓

QuickTransitionRenderer
```

The controller owns lifecycle/time.

The render node samples current monotonic time and computes render progress.

## 8. Transition completion

Transition completion must be exactly once and not admission-coupled to paint.

Preferred:

- controller knows monotonic end deadline;
- one bounded GUI-side completion deadline finalizes base image/state;
- render node samples state while run is active;
- stale completion is generation/run-id fenced.

Do not require "last frame painted" acknowledgement to release the next image rotation.

Interruption:

- explicit cancel policy snaps to the authored destination state exactly once;
- stale render snapshots are rejected by run id/generation.

## 9. Existing shader reuse

Do not rewrite working GLSL for architectural aesthetics.

Extract the rendering helpers from `GLCompositorWidget` coupling.

Likely reusable:

- `rendering/gl_programs/*`;
- transition shaders;
- transition state dataclasses;
- `GLTransitionRenderer` math after its compositor callbacks are removed;
- visualizer shader sources/render upload helpers.

Refactor them toward explicit inputs:

```text
program/resource owner
viewport
old/new textures
progress
transition state
```

rather than callbacks into the old compositor object.

## 10. Active transition inventory gate

At execution time, query the canonical transition registry.

The plan currently expects at least:

- Crossfade
- Slide
- Wipe
- Warp
- BlockFlip
- BlockSpin
- Blinds
- Diffuse
- Raindrops
- Crumble
- Particle
- Burn

Port the canonical active set, not a stale hard-coded list.

No migration fallback to old compositor for "the difficult transition."

## 11. Presentation frame pacer

Create a production class, e.g.:

```text
QuickFramePacer
QuickFrameDemand
```

Inputs:

- display target refresh;
- active transition reason;
- visible custom-GL visualizer reason;
- any other custom render-node reason that genuinely requires continuous frames.

Properties:

- one precise single-shot timer/pacer per window;
- next deadline derived monotonically;
- skip missed opportunities;
- call `QQuickWindow.update()` only for due opportunities;
- no render-completion self-requeue;
- no FIFO;
- no physical-to-logical cadence feedback.

Static retained widgets do not keep this pacer running merely because they exist.

## 12. Quick-native animations

For fades/ordinary retained UI animation, prefer Quick scene properties/animations.

Do not use a Python callback every rendered frame to animate:

- opacity;
- simple geometry;
- hover feedback.

Do not let a Quick animation become visualizer logical-time authority.

## 13. Transition parity tests

Per active transition:

- start image;
- midpoint;
- end image;
- direction variants;
- easing;
- DPR 1 and non-1 where practical;
- non-zero display origin where geometry can matter;
- cancel/interruption;
- exactly-once completion.

Use image/pixel or deterministic renderer-state tests when possible.

Manual installed review remains required for motion feel.

## 14. Performance acceptance

Check:

- 60 Hz;
- high refresh;
- mixed refresh;
- light;
- external heavy load;
- p95/p99/max physical gaps;
- severe gap counts;
- render-thread cost;
- texture upload frequency;
- GUI callback count.

Do not optimize individual transition shaders because Slide reveals shared cadence issues.

## 15. Commit cadence

Recommended pushed checkpoints:

1. render-node foundation;
2. image texture owner;
3. transition run controller;
4. Crossfade + Slide;
5. simple transition batch;
6. complex transition batch;
7. all-registry transition parity;
8. presentation pacing/perf closure.
