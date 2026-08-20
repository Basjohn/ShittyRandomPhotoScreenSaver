# Project Overview

Last updated: 2026-08-20

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
