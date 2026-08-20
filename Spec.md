# SRPSS Specification

Last updated: 2026-08-20

Canonical durable architecture and product-behaviour contracts for SRPSS.

`Current_Plan.md` owns active sequencing. Evidence reports own volatile measurements. Exact current
source remains implementation truth while a migration is in progress, but the accepted architecture
decision below is the design target and must not be reopened without new contradictory evidence.

## 1. Product priorities

1. visualizer fidelity/reactivity;
2. lifecycle and resource safety;
3. frame pacing / perceived continuity;
4. correct multi-display behaviour;
5. bounded resources;
6. CPU/task efficiency;
7. average FPS;
8. elegance.

Never improve counters by lowering authored visualizer cadence, transition quality, image quality,
overlay behaviour, or supported display topology.

## 2. Accepted presentation architecture

The accepted destination architecture is:

```text
Python / QWidget application shell
        |
        +-- Settings / persistence / providers / media / orchestration
        |
        +-- logical runtimes and models
                 |
                 v
        immutable/latest render state
                 |
        one standalone QQuickWindow per physical display
        with Qt Quick threaded scene-graph rendering
                 |
                 v
        OS physical presentation
```

This is a **runtime presentation migration**, not a wholesale QML rewrite.

Durable rules:

- one independently presented accelerated top-level runtime surface per physical display;
- the runtime presentation owner is standalone `QQuickWindow`, not `QQuickWidget`;
- the Qt Quick threaded scene-graph render loop is required on the supported Windows path;
- Settings/configuration UI may remain QWidget-based;
- providers, persistence, GSMTC/media integration, logical runtimes, orchestration, and data models
  remain Python unless a separate measured reason justifies changing them;
- runtime overlay **presentation** moves into the one Quick scene where required;
- overlay/provider/model logic does not automatically migrate to QML;
- no second independently presented accelerated visualizer/overlay surface.

### Migration-epoch rule

Until cutover is complete, current `main` may still contain the QRhiWidget reference presenter.
That makes it the current implementation, not the accepted long-term design.

Do not deepen the QRhiWidget path merely because it still exists during migration.

Do not remove the old presenter until the replacement has passed the required fidelity, lifecycle,
startup, multi-display, and resource gates.

## 3. Native/C++ boundary

A native/C++ physical-presenter migration is **not planned**.

The Qt Quick P0 experiment materially improved presentation cadence while still using Python/PySide
and existing representative OpenGL work. Therefore the evidence does not justify treating Python or
the GIL as a fundamental reason to replace the accepted Quick presenter.

Native code remains permissible only as a **localized measured implementation optimization** inside
the accepted Quick architecture, for example a specific render node or renderer whose Python cost is
proven material.

Do not plan:

```text
QRhiWidget -> Qt Quick -> second native-window/C++ presenter migration
```

If native code is ever earned, preserve the one-`QQuickWindow`-per-display presentation topology.

## 4. Runtime topology and ownership

- `ScreensaverEngine` owns high-level runtime sequencing.
- `DisplayManager` owns active-display/topology decisions.
- every physical display owns one runtime presentation window;
- display 0 is never implicit global geometry/DPR/presentation authority;
- `WidgetManager` and related model/provider owners may continue to own non-pixel widget lifecycle
  during migration;
- Settings/Edit/topology recreation use ordered generations/lifetimes;
- visualizer audio analysis, logical simulation, render-state publication, and physical presentation
  remain separate concerns.

## 5. Visualizer logical contract

`VisualizerLogicalRuntime` remains the sole mode-general authored visualizer clock.

It:

- runs independently of Qt GUI event-loop timing;
- owns monotonic authored deadlines/dt;
- integrates all five modes;
- consumes source snapshots;
- publishes latest plain-data logical state;
- does not mutate QWidget/QPixmap/QPainter/Quick scene objects/GL resources;
- stops and joins with its runtime generation;
- skips genuinely missed deadlines rather than replaying backlog.

Do not restore:

- GUI recurring timer as simulation owner;
- `AnimationManager` as simulation owner;
- per-mode logical clocks;
- FIFO/catch-up replay;
- paint/present acknowledgement;
- source/event decimation.

For Bubble timing and feel, `Docs/Guardrails/Bubble_Temporal_Fidelity.md` remains binding.

## 6. Logical-to-presentation contract

Producers integrate authored work first, then publish current state.

The presentation side samples the freshest valid state for the current runtime generation.

Allowed:

```text
logical state N published
logical state N+1 supersedes N before presentation consumes
presenter consumes N+1
```

Forbidden:

- producer waits for paint/present;
- paint completion releases producer admission;
- one queued callback per logical tick as a required contract;
- FIFO render queues;
- catch-up bursts;
- display-rate division of authored logical cadence.

The exact bridge from Python state into Quick scene/render state is implementation-owned by the
migration plan, but it must remain bounded, latest-state-oriented, generation-fenced, and free of
paint acknowledgement.

## 7. Quick scene / renderer contract

The one Quick window may contain:

- retained base image;
- active transition;
- visualizer/card;
- runtime overlay presentation;
- other explicitly scene-owned layers.

The exact primitive may differ by content:

- ordinary retained Quick items where appropriate;
- custom scene-graph rendering;
- `QSGRenderNode`;
- `QQuickRhiItem`;
- other measured Qt Quick-compatible custom rendering.

Choose the primitive by correctness, fidelity, and measured cost. Do not choose a native rewrite by
aesthetics.

No `QQuickWidget` architecture proof or production presenter.

No transparent accelerated child/top-level window used to avoid integrating pixels into the one
runtime scene.

## 8. Readiness and reveal

At minimum distinguish:

```text
presentation_ready
reactive_source_ready
```

Presentation readiness covers the current runtime window/scene/resources/geometry needed to show an
intentional frame.

Reactive-source readiness covers current authoritative source identity/data.

A presentation-owned idle scene may reveal without fabricating reactive source identity.

Paused Spectrum is the canonical case.

Startup/recreation must eventually preserve:

- no white/default window flash;
- no black placeholder frame;
- no stale texture/content pop;
- no visualizer/card flash;
- coordinated multi-display reveal;
- intentional first visible content.

## 9. Generation / lifecycle contract

Settings, Edit, topology replacement, and exit retire old generation before replacement can publish.

Required shape:

1. close old-generation admission;
2. stop/cancel generation-owned producers and delayed work;
3. join `VisualizerLogicalRuntime`;
4. reject/clear stale state;
5. retire render resources on their legal owner/thread;
6. destroy retired runtime presentation roots and cross the destruction barrier;
7. construct/register replacement;
8. prepare intentional first content;
9. reveal current-generation content only.

Generation `0` is valid identity. Do not use truthiness conversions that turn valid zero into an
invalid sentinel.

## 10. GPU/resource ownership

Qt owns the runtime window and Qt Quick scene-graph graphics infrastructure.

SRPSS-owned GPU resources must have:

- one explicit owner;
- legal creation/use/destruction on the required render/context owner;
- generation-scoped lifetime;
- failed deletion retaining ownership/failing closed;
- accounting released only after actual ownership is released.

Do not carry QRhiWidget-specific borrowed-context rules forward as universal Quick rules. Re-establish
the exact legal resource boundary for the chosen Quick rendering primitive.

No `glFinish()`, `DwmFlush()`, GUI sleeps, nested event pumping, or fence polling as cadence repairs.

## 11. Widgets and runtime overlays

Widget provider/model/settings logic is not required to migrate merely because runtime pixels do.

During the migration, separate:

```text
widget data/model/provider authority
from
runtime pixel/presentation authority
```

The accepted destination is that runtime pixels which coexist over the screensaver scene are
composed inside the one Quick window.

Settings controls may remain QWidget.

CUSTOM/Edit control UI may remain QWidget where appropriate, but it must not create a competing
accelerated runtime presentation surface or a second live pixel authority.

## 12. Performance contract

Physical presentation quality is judged by:

- visible continuity;
- physical p95/p99/max gaps;
- severe-gap frequency;
- load resilience;
- run-to-run variance;
- correct refresh behaviour per display.

Average FPS is secondary.

Internal Qt render/submission callbacks are not proof that frames reached physical display.
OS/display-boundary evidence such as PresentMon is used when physical-delivery attribution matters.

The accepted Qt Quick architecture decision is grounded in the 2026-08-20 P0 comparison. Do not
reopen the architecture choice because one later local optimization opportunity exists.

## 13. Validation

Tests are necessary but insufficient for:

- visualizer feel;
- presentation continuity;
- startup/reveal;
- multi-display behaviour;
- lifecycle;
- resource behaviour.

Migration gates must include focused automation plus runtime-shaped Windows validation and manual
visual review where perception is part of the requirement.

A gate must be structurally capable of failing on the defect it claims to guard.

## 14. Documentation authority

- `Current_Plan.md`: unfinished migration execution only;
- this file + Guardrails/focused docs: durable contracts;
- `Index.md` / `Docs/Contracts.md`: current routing and migration owner map;
- current evidence reports: measurements and checkpoint evidence;
- phase reports / Historical_Bugs: historical evidence only;
- `Future_Cleanup.md`: deferred debt only.

Old evidence may describe QOpenGLWidget, QRhiWidget, separate overlays, or GUI-timer cadence.
Those are historical mechanisms, not current design targets.
