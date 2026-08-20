# Runtime Presentation Architecture

Last updated: 2026-08-20

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

During migration that code is a **reference/rollback implementation**, not the destination.

Do not:

- expand the old presenter to avoid migration work;
- create new QRhiWidget-specific architecture;
- treat current class names as permanent product contracts.

Do not delete the reference path until the active migration plan has established the replacement and
passed the required cutover gates.

## 3. One-surface invariant

Each physical display owns one independently presented accelerated runtime surface.

Allowed inside that surface:

- retained base image;
- transition rendering;
- visualizer/card;
- runtime overlays;
- compositor-equivalent custom render items.

Forbidden:

- separate native visualizer window;
- transparent accelerated overlay window;
- per-widget accelerated top-level surface;
- `QQuickWidget` as the runtime presenter.

## 4. Threading model

The destination presenter requires the Qt Quick **threaded** scene-graph render loop on the supported
Windows path.

The GUI thread remains responsible for GUI/event-loop work and may prepare/publish state.

The Quick render thread owns the rendering phase according to the selected Qt Quick primitive.

Do not move visualizer logical simulation onto the render thread merely because a render thread now
exists.

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

The exact bridge may use Qt properties/models, explicit synchronization objects, custom item
`synchronize()` state, or another bounded mechanism chosen by the migration plan.

## 6. Renderer primitives

Do not lock the product to one primitive before the migrated scene requires it.

Possible shapes include:

- ordinary retained Quick items;
- shader/effect items;
- `QQuickRhiItem`;
- `QSGRenderNode`;
- custom render-stage integration.

Prefer the simplest primitive that:

- preserves exact visual fidelity;
- keeps one top-level presentation surface;
- respects thread/resource ownership;
- meets physical cadence requirements.

A local native/C++ renderer may be considered only after profiling proves Python callback/render
cost is material. It must remain inside the accepted Quick window architecture.

## 7. Visualizer

The visualizer remains split:

```text
source/audio
   ↓
VisualizerLogicalRuntime
   ↓
latest logical/render state
   ↓
Quick scene presentation
```

The logical runtime never mutates Quick scene objects or GPU resources.

The presenter never advances authored visualizer simulation.

Card and visualizer pixels share one scene/fade authority where they must appear as one authored
visual object.

## 8. Runtime overlays

Providers/models/settings do not migrate merely because pixels migrate.

Target pattern:

```text
existing Python data/model owner
        ↓
small presentation state
        ↓
Quick runtime item/layer
```

Avoid reimplementing network/provider/business logic in QML.

The one Quick scene should own runtime pixels that visually coexist over the screensaver.

## 9. Readiness / first frame

A runtime window must not be visibly exposed until it can show intentional current-generation
content.

Eventually preserve:

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

Old generation must retire before replacement gains authority.

Quick scene/render resources must be destroyed on the legal owner/thread for the selected primitive.

Do not copy QRhiWidget-specific context assumptions into Quick without verifying the new ownership
contract.

## 11. Transition model

Transition logical/progress semantics remain display-local and monotonic with exactly-once completion.

The migration should preserve existing transition shaders/behaviour where practical.

Do not individually retune transitions to hide physical frame holes.

## 12. Evidence bar

Physical presentation is judged primarily by:

- p95/p99/max physical gaps;
- severe-gap counts;
- continuity;
- load resilience;
- correct per-display refresh behaviour.

Internal render callbacks are not physical-display proof.

The P0 result justifies migration. Future evidence is for implementation/cutover quality, not for
re-litigating Quick versus the old presenter on every step.
