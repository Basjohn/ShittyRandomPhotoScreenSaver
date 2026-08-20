# SRPSS Index

Last updated: 2026-08-20

Navigation and architecture-epoch routing.

## Authority chain

```text
current user instruction + exact current main
        ↓
Current_Plan.md
        ↓
Spec.md + Docs/Guardrails.md + focused current docs
        ↓
current evidence
        ↓
phase reports / Historical_Bugs
        ↓
Future_Cleanup.md
```

During the Qt Quick migration, exact source tells you what is **currently implemented** while
`Spec.md` and `Docs/Compositor_Architecture.md` define the **accepted destination architecture**.
Do not mistake the temporary QRhiWidget reference implementation for the long-term target.

## Start here

| Task | Read |
|---|---|
| Active migration work | `Current_Plan.md` |
| Accepted runtime presentation architecture | `Docs/Compositor_Architecture.md` |
| Current/migration ownership map | `Docs/Contracts.md` |
| Cross-cutting safety | `Docs/Guardrails.md` |
| Stable architecture | `Spec.md` |
| Visualizer presentation/cadence | `Docs/Presentation_Change_Preflight.md`, `Docs/Guardrails/Visualizer_Presentation.md` |
| Bubble feel / timing | `Docs/Guardrails/Bubble_Temporal_Fidelity.md` |
| Visualizer subsystem | `Docs/Visualizer_Reference.md`, `Docs/Visualizer_Change_Checklist.md` |
| Qt Quick architecture evidence | `Docs/Performance_Evidence/QtQuick-P0-Comparison-2026-08-20.md` |
| Tests | `Docs/TestSuite.md` |
| Recurring harnesses | `Docs/Harness_Index.md` |
| Prior regressions | `Docs/Historical_Bugs/README.md` |
| Deferred cleanup | `Future_Cleanup.md` |

Do not read every document by default.

## Accepted presentation destination

```text
one physical display
        ↓
one standalone top-level QQuickWindow
        ↓
threaded Qt Quick scene graph
        ↓
base image + transition + visualizer + runtime overlays
        ↓
OS presentation
```

`QQuickWidget` is not an acceptable substitute.

There is no planned second migration to a native/C++ presenter. Native code is allowed only as a
localized measured renderer optimization inside this architecture.

## Current implementation during migration

Until cutover, `main` may still contain:

- `DisplayWidget`;
- `GLCompositorWidget`;
- QRhiWidget/OpenGL presenter code;
- GUI-side presentation handoffs.

Those files are the migration source/reference and may remain live until their replacement passes
parity gates. They are not permission to expand the old architecture.

## Durable runtime owners

| Domain | Owner/direction |
|---|---|
| Runtime sequencing | `ScreensaverEngine` |
| Display topology | `DisplayManager` |
| Runtime physical window | destination: one `QQuickWindow` per display |
| Runtime scene pixels | destination: Quick scene/render-thread presentation |
| Visualizer logical cadence | `VisualizerLogicalRuntime` |
| Visualizer source/audio | BeatEngine/audio worker/backend |
| Visualizer logical publication | latest-state, generation-fenced |
| Settings | existing QWidget/settings owners |
| Providers / service logic | existing Python owners |
| Persistence | existing settings/store owners |
| Widget models/providers | existing Python owners unless separately justified |
| Runtime widget pixels | destination: inside the display's Quick scene |
| Thread/task ownership | `ThreadManager` for general async work |
| Resource accounting | `ResourceManager`; never deletion fallback |

## Visualizer route

Accepted direction:

```text
audio / analysis
        ↓
VisualizerLogicalRuntime
        ↓
latest immutable/plain-data state
        ↓
Quick presentation bridge
        ↓
display QQuickWindow scene/render owner
        ↓
physical presentation
```

There is:

- one visualizer logical clock;
- one physical accelerated runtime surface per display;
- no paint acknowledgement;
- no independent visualizer surface.

## Evidence rule

The Qt Quick P0 comparison closed the architecture-choice experiment in favour of Quick.

Do not restart:

- QRhiWidget micro-optimization as an alternative architecture programme;
- C++ physical-presenter research as an assumed phase two;
- more P0 benchmark variants merely to reconfirm the decision.

New evidence may still guide migration implementation details and local renderer optimizations.

## Historical navigation

Older reports intentionally contain old owner maps.

Do not recover current direction from historical references to:

- QOpenGLWidget;
- QRhiWidget as final presenter;
- separate visualizer overlay;
- GUI visualizer timers;
- paint-coupled admission.

Use historical material only for the mechanism/regression it records.
