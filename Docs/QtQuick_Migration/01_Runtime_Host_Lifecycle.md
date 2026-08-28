# 01 — Runtime Host and Lifecycle Contract

Status: **Quick host foundation landed; Phase H final production owner wiring remains**  
Last updated: 2026-08-29

`Current_Plan.md` owns sequence.

## Current source routing

Engine startup still routes through the legacy physical host before H:

```text
DisplayManager -> DisplayWidget -> old physical presenter/compositor
```

The destination host is already real and runtime-shaped:

```text
QuickDisplayRuntime -> QuickDisplayWindow -> QuickSceneController -> retained scene
```

This does **not** mean the old path must remain product-functional while migration is incomplete. Do not create
compatibility facades or restore retired pixels just to maintain intermediate continuity.

## Destination owner split

`QuickDisplayWindow(QQuickWindow)` owns QScreen placement, window flags/visibility/focus, key/mouse/native events and
surface/window lifetime. It owns no provider/business/transition algorithm/visualizer simulation.

`QuickDisplayRuntime` is one per selected display and owns screen identity, runtime generation, exact Quick window,
scene controller, display frame pacer, input controller, retained auxiliary/controller state, one display
`WidgetRuntimeManager` after H orchestration, and the destination CUSTOM session/scene integration.

`QuickSceneController` owns presentation-facing scene state: base image, transition run, visualizer presentation,
ordinary retained items, CUSTOM overlay, dimming/pixel shift/halo/context presentation and reveal/fade. It is sole
creator/destructor of runtime Quick scene items for that display.

One process `QQmlEngine` may own components/cache. Per-display contexts/items remain display/generation scoped; shared
engine must not retain retired models or become hidden runtime-generation owner.

## Import boundary

Importing common Quick host/scene must not eagerly import inactive family business/runtime/backend trees. Family
implementation resolves at actual family activation/caller boundary.

## Bootstrap

Before first Quick scene/window, configure threaded Quick render loop, OpenGL graphics API and required surface format
deterministically where Qt requires. Do not expose production render loop as a casual user setting.

## DisplayManager boundary

DisplayManager keeps screen enumeration/allow-list, topology reconciliation, current-image routing, coordinated
readiness/reveal and outward engine signals. H replaces QWidget/private-compositor probing with a small explicit
`QuickDisplayRuntime` product API, not arbitrary QWidget emulation.

## H production family orchestration

Implementation sequence and deletion/cardinality traps are decomposed in
`Remaining_H_Production_Cutover_Decomposition.md`.

H begins only after the complete checkpointed G state passes its independent audit. H then connects exactly once:

```text
selected display
-> QuickDisplayRuntime
-> one display-owned WidgetRuntimeManager
-> canonical capability + ordinary enabled/instance resolution
-> existing neutral service lease(s)
-> stable family presentation model(s)
-> QuickSceneController ordinaryWidgetHost / visualizer / G owners
-> retained family QML item(s)
```

The visualizer viewport-config seam is part of this binding. Ordinary committed extent remains authoritative outside
CUSTOM; a live CUSTOM working extent is only a temporary override. H must not rely on "CUSTOM inactive -> None -> canonical"
as a substitute for the committed configuration owner.

Never run legacy and Quick production `WidgetRuntimeManager` ownership in parallel. Preserve real service cardinality.
Settings/topology recreation rebinds current accepted state without duplicating providers/controllers. Activation
remains distinct from ordinary enabled. Stale old-generation callbacks cannot target replacement items.

H is not an exercise in maintaining a seamless live handoff from a complete old product. The half-migrated old path may
already be nonfunctional. H proves destination owner/lifecycle correctness, makes Quick authoritative and removes the
remaining physical-host source.

## Lifecycle

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

Generation 0 is valid. Do not destroy custom GL resources from GUI thread merely because a window closes.

## QML lifetime

Per-display context/root lifetime is generation scoped; runtime Python models are not process-global QML singletons;
stale model signals cannot target replacement roots; no QML Connections survives runtime context; presentation
retirement callbacks run before item detachment/deletion where required.

## Readiness / topology

Prefer explicit readiness facts: window created, scene graph initialized, background renderer ready, intentional base
frame ready, required runtime overlays ready, reveal started/completed. No fixed sleep, white/default flash, black
placeholder or stale texture is accepted as ready.

One runtime per selected QScreen, bound before show, uses that screen's local geometry/refresh/DPR. Topology replacement
retires old generation completely; do not move live render resources between windows. Rebuild presentation from current
accepted model/runtime state.

## H deletion boundary

After destination production ownership is proven, delete the remaining `DisplayWidget`, QRhiWidget/
`GLCompositorWidget`, old compositor scheduling/presentation glue, unsupported software/backend-demotion fallback,
old physical-host transition/visualizer debris, temporary anchors and obsolete presentation compatibility. No product
switch back.

## H vs J proof

H requires focused/runtime-shaped proof sufficient to establish sole destination ownership, lifecycle safety,
cardinality and caller-dead old-host deletion.

J owns the comprehensive compiled/installed physical matrix: real 1/2/N displays, mixed refresh/DPR, topology/off-wake,
full widget/Visualizer eyes-on parity (including the deferred all-five-mode baseline/wide/tall viewport gate), physical
continuity/tail metrics and clean installed exit.
