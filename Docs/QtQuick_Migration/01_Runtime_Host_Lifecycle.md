# 01 — Runtime Host and Lifecycle Decomposition

Status: technical decomposition only; sequence owned by `Current_Plan.md`
Last updated: 2026-08-20

Cross-links:

- active sequence: `Current_Plan.md`
- deletion ledger: `Future_Cleanup.md`
- durable target: `Docs/Compositor_Architecture.md`

## 1. Current problem seam

`rendering/display_widget.py::DisplayWidget` currently combines too many concerns:

- top-level fullscreen QWidget;
- QScreen/DPR identity;
- input/native Windows events;
- image presentation;
- transition ownership;
- compositor ownership;
- widget construction;
- visualizer plumbing;
- CUSTOM layout;
- dimming;
- cursor halo;
- context menu;
- lifecycle/resource teardown.

That shape must **not** be recreated as one giant `QuickDisplayWindow`.

`engine/display_manager.py` also types its active display set directly as `DisplayWidget` and probes
private QWidget/compositor members during startup.

## 2. Destination owner split

Proposed package:

```text
rendering/quick/
    bootstrap.py
    runtime.py
    window.py
    scene_controller.py
    state.py
    frame_pacer.py
    input_controller.py
    qml/
        DisplayScene.qml
        components/
```

### `QuickDisplayWindow(QQuickWindow)`

Own only window/QWindow responsibilities:

- QScreen placement;
- window flags;
- visibility;
- focus;
- key/mouse/native events;
- surface/window lifecycle signals;
- content root.

It does not own providers, widget business logic, transition algorithms, or visualizer simulation.

### `QuickDisplayRuntime(QObject)`

One per physical display.

Own:

- screen index / screen identity;
- runtime generation;
- exact `QuickDisplayWindow`;
- `QuickSceneController`;
- display-local frame pacer;
- runtime input controller;
- widget runtime manager;
- CUSTOM session reference;
- display-level signals expected by `DisplayManager`.

This is the type that replaces `DisplayWidget` in `DisplayManager`.

Do not inherit QWidget.

Do not emulate arbitrary QWidget methods.

### `QuickSceneController`

Owns presentation-facing scene state:

- base image;
- transition run;
- visualizer presentation model;
- Quick widget items;
- dimming;
- pixel-shift root;
- edit overlays;
- reveal/fade state.

It is the only owner allowed to create/destroy runtime Quick scene items for that display.

### shared QML engine

A process-level `QQmlEngine` or equivalent shared component factory may be used to avoid recompiling
components for every display, but runtime QML contexts/items must be generation/display scoped.

A shared QML engine must not hold references to retired display runtime models.

Prefer:

```text
one app-level component/cache owner
+
one per-display QQmlContext / root item lifetime
```

over one QML engine per widget.

## 3. Bootstrap

The successful P0 conditions must be configured deterministically.

Before the first Quick scene graph/window:

```text
QSG_RENDER_LOOP=threaded
QQuickWindow graphics API = OpenGL
global QSurfaceFormat = current required OpenGL format
```

Do not rely on environment defaults.

`main.py` currently imports Qt at module import time and configures `QSurfaceFormat` before
`QApplication`. Keep that ordering safe.

If `QSG_RENDER_LOOP` is set through environment, set it before `QApplication` and before any Quick
window/engine creation. Prefer setting it at the earliest deterministic startup point.

Do not make the production render loop configurable through a casual user setting.

## 4. DisplayManager migration

Keep `DisplayManager` responsibilities:

- screen enumeration;
- monitor allow-list;
- topology reconciliation;
- current-image routing;
- coordinated readiness/reveal;
- outward engine signals.

Refactor concrete display assumptions.

Change:

```python
self.displays: list[DisplayWidget]
```

to the actual new runtime type.

Do not insert:

```python
class DisplayWidgetCompatibilityFacade:
    ...
```

Expected `QuickDisplayRuntime` surface should be small and explicit, e.g.:

```text
show_on_screen()
hide()
close_runtime()/cleanup()
set_image(...)
clear()
set_display_mode(...)
set_dimming(...)
quiesce_for_runtime_pause()
describe_runtime_state()
screen_index
runtime_generation

signals:
exit_requested
image_displayed
startup_reveal_completed
transition_completed
previous_requested
next_requested
cycle_transition_requested
settings_requested
custom_layout_reload_requested
dimming_changed
```

These are product/runtime operations, not QWidget compatibility methods.

As callers are changed, prefer public methods over probing:

```text
_runtime_generation
_gl_compositor
_render_surface
```

Add explicit readiness/state APIs instead.

## 5. ScreensaverEngine boundary

Do not rewrite `ScreensaverEngine`.

Required changes should be limited to:

- concrete display runtime type assumptions;
- startup readiness wiring;
- image-state types if the presentation boundary changes QPixmap/QImage ownership;
- lifecycle teardown APIs.

Keep:

- source/image queue;
- rotations;
- settings lifecycle;
- generation ownership;
- process/thread managers;
- stale-callback fencing.

## 6. Engine lifecycle

`engine/engine_lifecycle.py` already has a strong sequence:

```text
advance generation
-> disconnect monitor owner
-> quiesce displays
-> cancel generation callbacks
-> cleanup manager
-> retire roots
-> destruction barrier
```

Preserve this architecture.

Replace GL/QWidget-specific words/steps with Quick equivalents.

New required retirement ordering:

```text
generation invalidated
-> logical/widget/provider generation work quiesced
-> display frame pacers stopped
-> visualizer logical runtime joined
-> Quick presentation state admission closed
-> Quick scene render resources invalidated/deleted on render thread
-> window/root scene closed
-> QObject/QML roots queued
-> destruction barrier crossed
-> replacement runtime constructed
```

Do not destroy OpenGL scene resources from the GUI thread just because the window is closing.

Use `sceneGraphInvalidated` / render-node destruction contract for render resources.

## 7. QML object lifetime

Rules:

- per-display root context is parented to the runtime/window owner;
- runtime Python models are not registered as process-global singleton QML objects;
- stale model signals cannot target a replacement root;
- generation identity is explicit in state publications;
- `0` remains a valid generation;
- no QML `Connections` object survives its runtime context;
- do not let one shared QML engine become a hidden runtime-generation owner.

## 8. Readiness / reveal

Replace old compositor-private probes with explicit facts:

```text
window_created
scene_graph_initialized
background_renderer_ready
intentional_base_frame_ready
required runtime overlays ready
reveal_started
reveal_completed
```

Visualizer also has its own presentation/reactive readiness contract.

The first visible frame must be intentional.

No fixed sleep.

No black/default flash accepted as "window ready."

## 9. Monitor topology

Keep current settled-topology reconcile behaviour.

For each selected QScreen:

- create one `QuickDisplayRuntime`;
- bind exact QScreen before show;
- use local geometry, refresh, DPR;
- do not use display 0 as global authority.

On topology replacement:

- retire old generation completely;
- do not move live render resources between windows;
- build replacement scene from current engine/model state.

## 10. Media Center / flags

Audit current `DisplayWidget` flags and Windows behaviour.

Reproduce required product semantics using QWindow/QQuickWindow flags, not QWidget compatibility.

Gate:

- off taskbar/Alt+Tab where required;
- correct topmost behaviour;
- focus and interaction mode;
- cursor;
- cross-display focus;
- context-menu interaction;
- no shadow corruption after focus changes.

Do not carry deprecated class-global `DisplayWidget` input ownership into the new runtime.

## 11. Refactor opportunities admitted here

Allowed:

- split current display/input/lifecycle responsibilities;
- remove class-global display instance state in favour of `MultiMonitorCoordinator`/explicit owners;
- give DisplayManager a small runtime protocol/API;
- replace private-member probes with explicit readiness APIs.

Not admitted:

- source/provider rewrite;
- Settings UI rewrite;
- image queue rewrite;
- generic EventSystem redesign.

## 12. Gates

Before production cutover:

- 1, 2, and N selected displays;
- generation `0 -> 1`;
- repeated create/destroy;
- Settings recreate;
- topology change;
- display off/wake;
- exact render-thread teardown;
- no stale QML/model callbacks;
- no extra top-level accelerated windows;
- clean installed exit.

Every landed owner extraction is committed and pushed before continuing.
