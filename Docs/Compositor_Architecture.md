# Runtime Presentation Architecture

Last updated: 2026-08-21

## 1. Decision

SRPSS's accepted runtime presentation architecture is:

```text
one physical display
        ↓
one standalone top-level QQuickWindow
        ↓
threaded Qt Quick scene graph
        ↓
one composed runtime scene
        ↓
physical presentation
```

The 2026-08-20 P0 experiment materially beat the QWidget/QRhiWidget reference under both light and
heavy external load.

This decision is closed unless new production evidence contradicts it.

## 2. Migration status

The production source may still contain the previous presenter:

```text
DisplayWidget
   └── GLCompositorWidget
          └── OpenGL QRhiWidget path
```

Until Phase H cutover that code may remain the current production/reference implementation. It is
not the destination and is not a permanent fallback architecture.

Do not:

- expand the old presenter to avoid migration work;
- create new QRhiWidget-specific architecture;
- treat current old class names as permanent product contracts;
- add a production runtime switch between old and Quick presenters.

Do not delete the reference path until the active migration plan reaches the cutover/deletion phases.

## 3. One-surface invariant

Each physical display owns one independently presented accelerated runtime surface.

Allowed inside that surface:

- retained base image;
- transition rendering;
- visualizer/card;
- runtime overlays;
- retained Quick widgets;
- inline custom render nodes.

Forbidden:

- separate native visualizer window;
- transparent accelerated overlay window;
- per-widget accelerated top-level surface;
- `QQuickWidget` as the runtime presenter;
- per-effect fallback to an independently presented old surface.

## 4. Threading model

The destination presenter requires the Qt Quick **threaded** scene-graph render loop on the supported
Windows path.

The GUI thread remains responsible for GUI/event-loop work and may prepare/publish synchronized state.

The Quick render thread owns custom rendering according to the selected inline scene-graph primitive.

Do not move visualizer logical simulation onto the render thread merely because a render thread exists.

`VisualizerLogicalRuntime` remains independent and authoritative for authored visualizer time.

## 5. State flow

Conceptual flow:

```text
models / providers / logical runtimes
        ↓
bounded immutable/latest render state
        ↓
Quick scene synchronization boundary
        ↓
render-thread scene consumption
        ↓
physical presentation
```

Properties:

- latest-state semantics;
- no FIFO/catch-up;
- no producer wait for paint/present;
- no paint acknowledgement;
- no callback-per-logical-frame requirement;
- generation fencing;
- stale-state rejection.

The exact bounded GUI→Quick synchronization object may vary by owner, but those semantics may not.

## 6. Selected renderer primitives

The ordinary retained-presentation primitive is normal Qt Quick items/components.

The selected SRPSS custom-OpenGL primitive is:

```text
QQuickItem(ItemHasContents)
    -> updatePaintNode()
    -> QSGRenderNode
    -> direct OpenGL inside the owning QQuickWindow scene
```

This choice was proved during the Qt Quick foundation and is the current custom-render contract for
transitions and the visualizer migration.

Why this is the selected path:

- custom rendering stays inline in the one scene;
- correct stacking with retained Quick content;
- no extra offscreen texture/composite pass solely to reinsert the effect;
- supports existing shaders, meshes, depth, VAOs/VBOs, and context-local resources;
- preserves one physical presentation surface.

`QQuickRhiItem` is not the normal/final SRPSS custom-render path. `QQuickWidget` is prohibited.

If pinned PySide/compiled-product evidence proves the selected `QSGRenderNode` seam fundamentally
unusable, stop and deliberately revise the **single** custom-render primitive. Do not keep multiple
product primitives as compatibility fallbacks.

A localized native/C++ renderer may be considered only if profiling of the migrated implementation
proves a specific Python render callback materially limits the result. It must stay inside the same
QQuickWindow/scene ownership.

## 7. Visualizer

The visualizer remains split:

```text
source/audio
   ↓
VisualizerLogicalRuntime
   ↓
latest immutable logical/render state
   ↓
Quick visualizer item synchronization
   ↓
QSGRenderNode custom GL
```

The logical runtime never mutates Quick scene objects or GPU resources.

The presenter never advances authored visualizer simulation.

Card and visualizer pixels share one scene/fade/geometry authority where they must appear as one
authored visual object.

## 8. Runtime overlays

Providers/models/settings do not migrate merely because pixels migrate.

Target pattern:

```text
existing Python data/model owner
        ↓
small presentation state
        ↓
retained Quick runtime item/layer
```

Avoid reimplementing network/provider/business logic in QML.

The one Quick scene owns runtime pixels that visually coexist over the screensaver.

## 9. Readiness / first frame

A runtime window must not be visibly exposed until it can show intentional current-generation content.

Preserve:

- no white/default flash;
- no black placeholder;
- no stale image/texture pop;
- no visualizer/card flash;
- coordinated multi-display reveal.

Separate:

```text
presentation_ready
reactive_source_ready
```

Do not make real audio/source freshness a universal prerequisite for an intentional idle scene.

## 10. Lifecycle

Topology, Settings/recreate, Edit, and shutdown remain generation-owned.

Old generation retires before replacement gains authority.

Quick scene/render resources are destroyed on the legal render/context owner for the selected
`QSGRenderNode` contract.

Do not copy QRhiWidget-specific context assumptions into Quick.

Generation `0` remains valid.

## 11. Transition model

Transition request/run semantics are display-local, immutable, monotonic, and exactly-once for
completion/cancellation.

Canonical transition implementations resolve lazily and render through the display's inline Quick
custom-render owner. Existing authored shader/math is preserved where valid.

Do not individually retune transitions to hide physical frame holes.

## 12. Evidence bar

Physical presentation is judged primarily by:

- p95/p99/max physical gaps;
- severe-gap counts;
- continuity;
- load resilience;
- correct per-display refresh behaviour.

Internal render callbacks are not physical-display proof.

The P0 result justifies migration. Later evidence is for implementation/cutover quality, not for
re-litigating Quick versus the old presenter on every step.
