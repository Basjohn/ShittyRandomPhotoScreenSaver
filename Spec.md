# SRPSS Specification

Last updated: 2026-08-24

Canonical durable architecture and product-behavior contracts.

`Current_Plan.md` owns sequencing. Historical closure rationale belongs in historical/phase evidence, not
in the active plan.

## Product priorities

1. visualizer fidelity/reactivity;
2. lifecycle/resource safety;
3. frame pacing / perceived continuity;
4. multi-display correctness;
5. bounded resources;
6. CPU/task efficiency;
7. average FPS;
8. elegance.

Do not improve counters by reducing authored visualizer cadence, transition quality, image quality,
overlay behavior or supported display topology.

## Accepted runtime presentation architecture

```text
Python / QWidget application shell
    -> Settings / persistence / providers / media / orchestration
    -> logical runtimes + models
    -> bounded presentation state
    -> one standalone threaded QQuickWindow per selected physical display
    -> retained Quick scene + inline QSGRenderNode custom GL
    -> physical presentation
```

This is a runtime-presentation migration, not a whole-application QML rewrite.

Hard:

- one independently presented accelerated runtime surface per display;
- runtime presenter = standalone `QQuickWindow`, not `QQuickWidget`;
- threaded Quick scene graph on the supported Windows path;
- Settings may remain QWidget;
- provider/persistence/media/orchestration/logical runtimes remain Python-owned;
- transition + visualizer custom GL remain inline in the same Quick scene;
- no second accelerated visualizer/widget/effect window;
- no permanent old-presenter fallback.

## Migration-epoch rule

The old `DisplayWidget` / QRhiWidget / `GLCompositorWidget` physical path may remain until H because it
still hosts the pre-cutover application. It is current-legacy, not a rollback architecture.

Deletion timing is owner-specific:

```text
ordinary family QWidget pixels -> after that family is independently GREEN in F
old CUSTOM/edit pixels          -> after G replacement is GREEN
old transition-only pixels      -> as soon as caller-proofed; H maximum if tied to physical host
old visualizer-only pixels      -> as soon as caller-proofed; H maximum if tied to physical host
old physical presenter/backend  -> H cutover + deletion
residual debris                 -> I only
```

Do not preserve a completed old pixel owner merely to keep the half-migrated product usable.

## Logical-to-presentation rule

Producers integrate authored work first, then publish current state.

Presentation consumes bounded latest current state with generation fencing.

No:

- producer wait for paint/present;
- paint acknowledgement;
- FIFO render backlog;
- catch-up replay;
- display-rate division of authored logical cadence.

## Visualizer

`VisualizerLogicalRuntime` remains the sole mode-general authored visualizer clock.

Quick presentation does not own simulation cadence.

All five current modes use:

```text
CARD + CARD_INTERIOR
```

Architecture permits a deliberately authored future:

```text
FRAMELESS + VIEWPORT_RECT
```

inside the same Quick window/visualizer ownership.

Quick visualizer geometry distinguishes:

```text
baseline viewport/aspect
uniform_visual_scale
viewport_extent
```

Retired pre-Quick per-mode growth/card-height controls are not destination behavior.

Bubble temporal fidelity remains bound by `Docs/Guardrails/Bubble_Temporal_Fidelity.md`.

## Transitions

Canonical transition identity/settings remain presentation-neutral.

Destination:

```text
canonical descriptor
-> activation/admission + resolved request
-> TransitionRequest / TransitionRun
-> lazy Quick transition implementation
-> display QSGRenderNode
```

All canonical transition pixels are Quick-owned. Old `GLCompositor*Transition` implementations are not
destination or reference authority once caller-proofed.

Preserve deterministic transition recovery and authored transition identity/math used by Quick.

## Ordinary widgets

Separate:

```text
provider/model/settings/actions/cadence
from
runtime pixel presentation
```

Destination ordinary pixels are retained Quick content under the display's shared ordinary-widget host.

QML does not own providers, persistence or refresh cadence.

For each family, keep old QWidget pixels only until the retained family is proven, then delete the old
pixel presenter.

## Shadows

Canonical global direction:

```text
NW N NE W E SW S SE
```

Default `SE`.

Direction owns orientation. Python resolves signed offsets before QML.

User shadow settings:

```text
Card: enabled, frame_opacity, blur_radius, frame_extra_offset
Text: text_enabled, text_opacity, text_extra_offset
Header enable remains a gate
All: direction
```

No Text Blur. No Intense mode. No `widgets.shadows.offset`.

No `shadowtuning.json` or replacement hidden tuning authority.

A family-authored reference exists only when the family independently owns a visual relationship; values
sourced solely from the retired global sidecar do not become family-authored by being copied into a
family module.

Clock analogue hard-shadow geometry is an explicit family-authored exception/reference.

## Geometry/CUSTOM

Outer geometry remains Python/session-owned.

Family QML lays out inside assigned geometry.

Geometry keys must support a variant dimension where required:

```text
(widget_id, display_identity, variant)
```

Clock digital/analogue are the known required case.

## Lifecycle

Old generation loses publication/admission before replacement gains authority.

Generation `0` is valid.

GPU resources are created/used/destroyed by their legal render/context owner.

No `glFinish()`, `DwmFlush()`, GUI sleeps or nested event pumping as cadence repairs.

## Validation

Tests are necessary but not sufficient for:

- visualizer feel;
- transition visual character;
- continuity;
- startup/reveal;
- multi-display behavior;
- lifecycle;
- resource behavior.

Use focused automation plus runtime-shaped Windows/physical/eyes-on evidence where the claim requires it.

## Documentation roles

- `Current_Plan.md`: current checkpoint, active work, next/future sequence, current debt.
- `Spec.md`: durable product/architecture.
- focused docs/guardrails: durable subsystem contracts.
- `Docs/TestSuite.md`: live test inventory/status ledger.
- `Future_Cleanup.md`: deferred deletion/debt.
- `Future_Work.md`: deferred features/experiments.
- `Docs/Historical_Plans/`, phase reports, historical bugs/evidence: history only.
