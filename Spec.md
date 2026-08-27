# SRPSS Specification

Last updated: 2026-08-28

Canonical durable architecture and product-behavior contracts. `Current_Plan.md` owns sequence; independent closure
narrative belongs under `Docs/audits/` or historical evidence.

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

Hard: one accelerated runtime surface per selected display; standalone `QQuickWindow`, never `QQuickWidget`; threaded
Quick scene graph; Settings may remain QWidget; business/runtime ownership remains Python; transition+visualizer GL
remains inline in the one Quick scene; no permanent old/software presenter fallback.

## Migration epoch

The legacy `DisplayWidget` / QRhiWidget / `GLCompositorWidget` path may still exist in source until H removes the final
physical-host routing. It is scaffolding, not rollback architecture.

**Pre-H product continuity is not a migration requirement.** The old path must not be preserved, rebuilt or expanded
merely to keep a half-migrated screensaver functional. Caller-dead old pixels/helpers should retire as soon as their
replacement owns the contract. H wires the destination production owner and removes the remaining physical host; I is
residue only; J is full installed/physical acceptance.

## Capability / ordinary instance state

Family activation/deactivation is different from ordinary instance ON/OFF. Capability deactivation preserves detail
settings and suppresses family-exclusive ownership; ordinary `enabled=False` is the casual per-widget off state inside
an activated family.

CUSTOM X and layout-slot replay may change ordinary ON/OFF only. They never activate a deactivated capability/family.

## Import dormancy

Common Quick scene/host imports must not eagerly import inactive family business/runtime/backend trees. Family
implementation resolves at actual family caller/activation. Static presentation-only registry metadata is fine.
Common Quick import must not bootstrap provider/controller/runtime/backend singletons.

## Ordinary widgets

```text
provider/backend/runtime/cadence/actions
-> stable presentation model/state
-> retained Quick pixels
```

Current proven patterns are deliberately heterogeneous:

- Clock: shared `GlobalClockTicker` + stable models; no invented service;
- Weather: neutral manager-owned runtime service + retained model;
- Media: runtime-generation shared owner with display leases, separate narrow volume/mute owners and a process-engine
  artwork provider;
- Reddit/Reddit2: separate configured member runtime services/models using shared family policy;
- Gmail: runtime-generation shared Gmail owner/backend with per-display lease;
- Achievement Pulse: neutral Steam runtime/preparation/cache/selection ownership;
- Abandonment Issues: neutral Steam runtime/data/cache/rotation ownership.

Do not create services/managers merely for naming symmetry.

## State / actions

Producers integrate work then publish coherent accepted current state. Presentation consumes bounded latest state with
generation/request fencing. No producer wait for paint, paint acknowledgement, FIFO render backlog, catch-up replay or
display-rate division of authored cadence.

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

Canonical direction is NW/N/NE/W/E/SW/S/SE, default SE, resolved in Python. No Text Blur, Intense mode,
`widgets.shadows.offset`, `shadowtuning.json`, or replacement hidden tuning. Ordinary card = cached retained
`RectangularShadow`; ordinary text = duplicate glyph + signed offset; whole-widget fade = one retained root opacity.
Clock analogue hard shadows are permanent family-authored exceptions under doc 11.

## Geometry / CUSTOM

Outer geometry is Python/session-owned. Variant key supports `(widget_id, display_identity, geometry_variant)`.
Clock digital/analogue are the first required example.

Edit-mode X changes working session only: duplicate removal or singleton ordinary-enabled OFF. Never family capability
deactivation. Save/Enter commits; Cancel restores pre-edit geometry/instances/enabled state.

Layout slots save/load ordinary visible-layout state, including ordinary ON/OFF, but never capability activation or
provider/account/source settings.

## Visualizer geometry

`VisualizerLogicalRuntime` remains sole mode-general authored visualizer clock. Quick presentation does not own
simulation cadence.

All five current modes share a default/baseline 1.5 aspect and support two distinct CUSTOM operations:

```text
uniform_visual_scale
    wheel/corner -> whole visualizer scales uniformly; viewport extent unchanged

viewport_extent
    left/right edge -> width only
    top/bottom edge -> height only
```

Viewport extent is world/layout playroom, not final-pixel X/Y stretch. All five current modes—Spectrum,
Oscilloscope, Sine, Bubble and DevCurve—must reflow/adapt to wide/tall extents. Bubble's viewport bounds are spatial
configuration to its logical side; changing them must preserve round geometry, motion/collision semantics and BTF and
must not create another clock.

A temporary source capability flag that disables Bubble viewport resizing is migration debt, not destination product
behavior.

## Transitions

Transitions resolve canonical settings/admission into immutable request/run state and lazy Quick rendering. Old
`GLCompositor*Transition` pixels are not destination authority after caller proof.

## Lifecycle

Old generation loses admission before replacement gains authority; generation 0 is valid. GPU resources are
created/used/destroyed by legal render/context owner. No `glFinish()`, `DwmFlush()`, GUI sleeps or nested event pumping
as cadence repair. Shared `QQmlEngine` is component/cache owner, not hidden runtime-generation owner.

## H production authority

H makes the existing Quick destination the sole production owner:

```text
selected display
-> one QuickDisplayRuntime
-> one display-owned WidgetRuntimeManager
-> canonical capability/ordinary-instance resolution
-> existing neutral runtime/service leases
-> stable family presentation models
-> QuickSceneController
-> retained family items
```

Do not run old/new production runtime managers in parallel. Preserve semantic cardinality. H deletes the remaining old
physical presenter/backend in the same audited owner-cutover boundary; it does not need to preserve a fully working
legacy application or provide a product switch back.

## Validation epochs

- G: focused implementation/runtime-shaped proof;
- H: destination production ownership + lifecycle/caller proof and physical-host deletion;
- I: residue only;
- J: compiled/installed and physical 1/2/N-display/DPR/topology/eyes-on/performance closure.

## Documentation roles

- `Current_Plan.md`: current checkpoint/work/next/debt;
- `Spec.md`: durable product/architecture;
- focused docs/guardrails: durable subsystem contracts;
- `Docs/audits/`: independent audit findings/closure evidence;
- `Docs/TestSuite.md`: live test inventory/status ledger;
- `Future_Cleanup.md`: deferred deletion/debt;
- `Future_Work.md`: deferred features;
- historical records: history only.
