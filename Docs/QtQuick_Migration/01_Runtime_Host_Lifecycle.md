# 01 — Runtime Host and Lifecycle Contract

Status: **landed Quick host foundation; production orchestration/cutover remains Phase H**  
Last updated: 2026-08-26

`Current_Plan.md` owns sequence.

## Current source reality

Before H normal production remains:

```text
DisplayManager -> DisplayWidget -> old physical presenter/compositor
```

Destination Quick host is real and used by runtime-shaped tests/harnesses:

```text
QuickDisplayRuntime -> QuickDisplayWindow -> QuickSceneController -> retained scene
```

Quick existing does not mean normal production has cut over.

## Destination owner split

`QuickDisplayWindow(QQuickWindow)` owns QScreen placement, window flags/visibility/focus, key/mouse/native
events and surface/window lifetime. No provider/business/transition algorithm/visualizer simulation.

`QuickDisplayRuntime` is one per selected display and destination owner for screen identity, runtime
generation, exact Quick window, scene controller, display frame pacer, input controller, one display
`WidgetRuntimeManager` after H orchestration, and CUSTOM session after G. It replaces `DisplayWidget` at H;
do not build a QWidget compatibility facade.

`QuickSceneController` owns presentation-facing scene state: base image, transition run, visualizer
presentation, ordinary retained items, dimming/pixel shift/edit overlays and reveal/fade. It is sole creator/
destructor of runtime Quick scene items for that display.

One process `QQmlEngine` may own components/cache. Per-display contexts/items remain display/generation
scoped; shared engine must not retain retired models or become hidden runtime-generation owner.

## Import boundary

Importing common Quick host/scene must not eagerly import inactive family business/runtime/backend trees.
Family implementation resolves at actual family activation/caller boundary.

## Bootstrap

Before first Quick scene/window, configure threaded Quick render loop, OpenGL graphics API and required
surface format deterministically where Qt requires. Do not expose production render loop as casual user
setting.

## DisplayManager boundary

DisplayManager keeps screen enumeration/allow-list, topology reconciliation, current-image routing,
coordinated readiness/reveal and outward engine signals. Replace QWidget/private-compositor probing with a
small explicit `QuickDisplayRuntime` product API, not arbitrary QWidget emulation.

## H production family orchestration — REQUIRED

Current Quick runtime does not yet own normal-production widget orchestration. H connects exactly once:

```text
selected display
-> QuickDisplayRuntime
-> one display-owned WidgetRuntimeManager
-> canonical capability + ordinary enabled/instance resolution
-> existing neutral service lease(s)
-> stable family presentation model(s)
-> QuickSceneController ordinaryWidgetHost
-> retained family QML item(s)
```

Never run legacy and Quick production `WidgetRuntimeManager` ownership in parallel. Preserve real service
cardinality. Settings/topology recreation rebinds current accepted state without duplicating providers/
controllers. Activation remains distinct from ordinary enabled. Stale old-generation callbacks cannot target
replacement items. Every retained production family is caller-proofed through this chain before old physical
host deletion.

## Engine lifecycle

```text
close old admission
-> invalidate/advance generation
-> quiesce generation-owned work
-> stop display pacers / join logical runtimes where required
-> close Quick presentation admission
-> retire render resources on legal render/context owner
-> close window/root scene
-> destruction barrier
-> construct replacement
-> prepare intentional first content
-> reveal
```

Generation 0 is valid. Do not destroy custom GL resources from GUI thread merely because window closes.

## QML lifetime

Per-display context/root lifetime is generation scoped; runtime Python models are not process-global QML
singletons; stale model signals cannot target replacement roots; no QML Connections survives runtime context;
presentation retirement callbacks run before item detachment/deletion where required.

## Readiness / reveal

Prefer explicit readiness facts: window created, scene graph initialized, background renderer ready,
intentional base frame ready, required runtime overlays ready, reveal started/completed. First visible frame
is intentional: no fixed sleep, white/default flash, black placeholder or stale texture accepted as ready.

## Topology

One runtime per selected QScreen, bound before show, using that screen's local geometry/refresh/DPR. Topology
replacement retires old generation completely; do not move live render resources between windows. Rebuild
presentation from current accepted model/runtime state.

## H deletion boundary

After production chain proven, delete `DisplayWidget`, QRhiWidget/`GLCompositorWidget`, old compositor
scheduling/presentation glue, unsupported software/backend-demotion fallback, old physical-host transition/
visualizer debris and temporary anchors no longer needed. No production switch back.

## Cutover gates

Before H GREEN: 1/2/N displays, generation 0->1, repeated create/destroy, Settings recreate, topology change,
display off/wake, render-thread teardown, no stale QML/model callbacks, no duplicate family owners, no extra
accelerated windows and clean installed exit.
