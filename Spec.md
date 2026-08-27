# SRPSS Specification

Last updated: 2026-08-26

Canonical durable architecture and product-behavior contracts. `Current_Plan.md` owns sequence; independent
closure narrative belongs under `Docs/audits/` or historical evidence.

## Product priorities

1. visualizer fidelity/reactivity;
2. lifecycle/resource safety;
3. frame pacing/perceived continuity;
4. multi-display correctness;
5. bounded resources;
6. CPU/task efficiency;
7. average FPS;
8. elegance.

Do not improve counters by reducing authored cadence, visual quality, overlay behavior or topology support.

## Accepted runtime presentation

```text
Python / QWidget application shell
-> Settings / persistence / providers / media / orchestration
-> logical runtimes + models
-> bounded presentation state
-> one standalone threaded QQuickWindow per selected physical display
-> one retained Quick scene + inline QSGRenderNode custom GL
```

Hard: one accelerated runtime surface per selected display; standalone `QQuickWindow`, never `QQuickWidget`;
threaded Quick scene graph; Settings may remain QWidget; business/runtime ownership remains Python;
transition+visualizer GL remains inline in the one Quick scene; no permanent old/software presenter fallback.

## Migration epoch / retirement

Old `DisplayWidget` / QRhiWidget / `GLCompositorWidget` is current-legacy until H, not rollback architecture.

```text
ordinary family QWidget pixels -> family GREEN + caller proof in F
old CUSTOM/edit pixels          -> G replacement GREEN
old transition/visualizer pixels-> caller-proof early; H maximum if physical-host bound
old physical presenter/backend  -> H cutover + deletion
residual debris                 -> I only
```

## Capability / instance state

Family activation/deactivation is different from ordinary instance enabled/disabled. Capability
deactivation preserves detail settings and suppresses family-exclusive ownership; ordinary `enabled=False`
is the casual per-widget off state inside an activated family.

## Import dormancy

Common Quick scene/host imports must not eagerly import inactive family business/runtime/backend trees.
Family implementation resolves at actual family caller/activation. Static presentation-only registry
metadata is fine. Common Quick import must not bootstrap provider/controller/runtime/backend singletons.

## Ordinary widgets

```text
provider/backend/runtime/cadence/actions
-> stable presentation model/state
-> retained Quick pixels
```

Current proven patterns are deliberately heterogeneous:

- Clock: shared `GlobalClockTicker` + stable models; no invented service;
- Weather: neutral manager-owned runtime service + retained model;
- Media: runtime-generation shared owner with display leases, separate narrow volume/mute owners and a
  process-engine artwork provider;
- Reddit/Reddit2: separate configured member runtime services/models using shared family policy;
- Gmail: runtime-generation shared Gmail owner/backend with per-display lease; retained model/QML complete and
  old QWidget presentation retired.
- Achievement Pulse: existing neutral Steam runtime/preparation/cache/selection ownership; retained model/QML
  complete and old QWidget presentation retired.
- Abandonment Issues: existing neutral Steam runtime/data/cache/rotation ownership; retained model/QML complete
  and old QWidget presentation retired.

Do not create services/managers merely for naming symmetry.

## State / actions

Producers integrate work then publish coherent accepted current state. Presentation consumes bounded latest
state with generation/request fencing. No producer wait for paint, paint acknowledgement, FIFO render backlog,
catch-up replay or display-rate division of authored cadence.

```text
QML semantic action
-> Python action owner
-> business side effect
-> accepted current state
-> presentation
```

QML does not persist settings or directly invoke providers/backends.

## Dynamic images

Use stable identity and bounded presentation image ownership. Proven Media shape:

```text
runtime-owned decoded QImage + stable artwork key
-> process-engine image provider
-> retained Image source identity
```

No QPixmap worker transport, base64 churn, tempfile-per-update or unchanged-image reupload.

## Shadows / fade

Canonical direction is NW/N/NE/W/E/SW/S/SE, default SE, resolved in Python.
No Text Blur, Intense mode, `widgets.shadows.offset`, `shadowtuning.json`, or replacement hidden tuning.
Ordinary card = cached retained `RectangularShadow`; ordinary text = duplicate glyph + signed offset;
whole-widget fade = one retained root opacity. Clock analogue hard shadows are permanent family-authored
exceptions under doc 11.

## Geometry / CUSTOM

Outer geometry is Python/session-owned. Variant key supports `(widget_id, display_identity, geometry_variant)`.
Clock digital/analogue are first required example.

Edit-mode X changes working session only: duplicate removal or singleton ordinary-enabled OFF. Never family
capability deactivation. Save/Enter commits; Cancel restores pre-edit geometry/instances/enabled state.

## Visualizer / transitions

`VisualizerLogicalRuntime` remains sole mode-general authored visualizer clock. Quick presentation does not
own simulation cadence.

Transitions resolve canonical settings/admission into immutable request/run state and lazy Quick rendering.
Old `GLCompositor*Transition` pixels are not destination authority after caller proof.

## Lifecycle

Old generation loses admission before replacement gains authority; generation 0 is valid. GPU resources are
created/used/destroyed by legal render/context owner. No `glFinish()`, `DwmFlush()`, GUI sleeps or nested
event pumping as cadence repair. Shared `QQmlEngine` is component/cache owner, not hidden runtime-generation
owner.

## H production cutover

Before normal startup switches to Quick, prove:

```text
selected display
-> one QuickDisplayRuntime
-> one display-owned WidgetRuntimeManager
-> canonical capability/instance resolution
-> existing neutral runtime/service leases
-> stable family presentation models
-> QuickSceneController
-> retained family items
```

Do not run old/new production runtime managers in parallel. Preserve semantic cardinality. H deletes the old
physical presenter/backend in the same audited cutover boundary; no product switch back.

## Documentation roles

- `Current_Plan.md`: current checkpoint/work/next/debt;
- `Spec.md`: durable product/architecture;
- focused docs/guardrails: durable subsystem contracts;
- `Docs/audits/`: independent audit findings/closure evidence;
- `Docs/TestSuite.md`: live test inventory/status ledger;
- `Future_Cleanup.md`: deferred deletion/debt;
- `Future_Work.md`: deferred features;
- historical records: history only.
