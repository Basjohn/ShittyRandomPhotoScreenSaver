# Project Overview

Last updated: 2026-08-22

## What SRPSS is

SRPSS is a Windows screensaver/media runtime with multi-display image presentation, accelerated
transitions, a high-fidelity multi-mode visualizer, configurable runtime overlays, durable settings,
and Normal/Media Center variants.

## Architecture epoch

The physical-presentation experiment is complete.

Standalone threaded `QQuickWindow` materially improved presentation cadence and load resilience over
the QWidget/QRhiWidget reference path. Qt Quick is therefore the accepted destination for runtime
presentation.

This is not a whole-application QML rewrite.

Keep Python/QWidget ownership for:

- Settings/configuration UI;
- persistence;
- providers;
- media/GSMTC integration;
- orchestration;
- logical runtimes;
- data models.

Move the runtime **pixel scene/presentation owner** to one standalone `QQuickWindow` per display.

## Current implementation vs accepted target

During migration, current `main` may still run through `DisplayWidget`/`GLCompositorWidget`/
QRhiWidget.

That is the current implementation and rollback/reference path.

It is not the long-term architecture target.

Do not spend migration time broadening or micro-optimizing that presenter unless the active plan
requires a bounded compatibility fix.

## Visualizer cadence

`VisualizerLogicalRuntime` remains the one mode-general authored visualizer clock.

Logical state is produced independently of GUI/physical presentation and published with latest-state
semantics.

The migration changes the presentation consumer, not the authored logical clock.

For Bubble feel/timing, read:

`Docs/Guardrails/Bubble_Temporal_Fidelity.md`

## Visualizer presentation direction

The Quick visualizer is not architecturally synonymous with a card.

All five current production modes remain carded and use the rounded inner card as their content clip:

```text
CARD + CARD_INTERIOR
```

The architecture also permits an explicitly authored future mode to be frameless while remaining in
the same display `QQuickWindow` and the same visualizer render/lifecycle path:

```text
FRAMELESS + VIEWPORT_RECT
```

Current-mode geometry uses one canonical baseline viewport aspect. Mode switches and visualizer
presets do not resize that baseline.

The old per-mode visualizer card-height/growth controls are pre-Quick presentation customization and
are deliberately retired from the destination architecture.

CUSTOM keeps whole-size scaling distinct from viewport playroom:

```text
scroll / corner resize
    -> uniform whole-visualizer scale
    -> baseline aspect preserved

left/right edge resize
    -> viewport width only

top/bottom edge resize
    -> viewport height only
```

The edge-only viewport behavior is a later Phase-G QoL seam. It changes the available mode world/layout
rather than stretching rendered pixels and is not a migration blocker for a mode that cannot safely
support it.

For the detailed contract, read:

- `Docs/Contracts.md`
- `Docs/QtQuick_Migration/03_Visualizer.md`
- `Docs/Guardrails/Visualizer_Presentation.md`
- `Docs/Visualizer_Reference.md`

## Core engineering priorities

1. visualizer fidelity/reactivity;
2. lifecycle/resource safety;
3. physical frame pacing/perceived smoothness;
4. multi-display correctness;
5. bounded resources;
6. CPU/task efficiency;
7. average FPS;
8. elegance.

## C++ status

A separate native/C++ presenter is not an active or expected migration phase.

The Quick benchmark already achieved the architectural gain while retaining Python/PySide and
representative existing rendering work.

Native code may be introduced only for a specifically measured renderer hot path, inside the accepted
Quick presentation architecture.

## Read order

For active work:

1. user instruction + exact current `main`;
2. `Current_Plan.md`;
3. `Spec.md`;
4. `Docs/Compositor_Architecture.md`;
5. `Docs/Contracts.md`;
6. relevant guardrail/reference;
7. current evidence if measurements matter.

Do not read the whole history tree by default.
