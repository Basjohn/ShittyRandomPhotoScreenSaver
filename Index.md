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
        ↓
Future_Work.md
```

`Future_Work.md` is a long-horizon new-feature/new-implementation backlog, not active sequencing. An
agent may implement from it only when the operator explicitly selects an item or when
`Current_Plan.md` and `Future_Cleanup.md` contain no remaining important active work.

During the Qt Quick migration, exact source tells you what is **currently implemented** while
`Spec.md` and `Docs/Compositor_Architecture.md` define the **accepted destination architecture**.
Do not mistake the temporary QRhiWidget reference implementation for the long-term target.

## Start here

| Task | Read |
|---|---|
| Active migration work | `Current_Plan.md` |
| Qt Quick migration technical detail | `Docs/QtQuick_Migration/README.md` + only the active slice document |
| Accepted runtime presentation architecture | `Docs/Compositor_Architecture.md` |
| Current/migration ownership map | `Docs/Contracts.md` |
| Cross-cutting safety | `Docs/Guardrails.md` |
| Stable architecture | `Spec.md` |
| Visualizer presentation/cadence | `Docs/Guardrails/Visualizer_Presentation.md` |
| Bubble feel / timing | `Docs/Guardrails/Bubble_Temporal_Fidelity.md` |
| Visualizer subsystem | `Docs/Visualizer_Reference.md`, `Docs/Visualizer_Change_Checklist.md` |
| Transition changes | `Docs/Transition_Change_Checklist.md` |
| Widget/runtime presentation | `Docs/10_WIDGET_GUIDELINES.md` |
| Qt Quick architecture evidence | `Docs/Performance_Evidence/QtQuick-P0-Comparison-2026-08-20.md` |
| Tests | `Docs/TestSuite.md` |
| Recurring harnesses | `Docs/Harness_Index.md` |
| Prior regressions | `Docs/Historical_Bugs/README.md` |
| Cutover deletion / deferred cleanup | `Future_Cleanup.md` |
| Explicitly deferred new features / experiments | `Future_Work.md` (only when its activation rule is satisfied) |

Do not read every document by default.

## Active Qt Quick migration support docs

These are subordinate decompositions, not parallel plans:

- `Docs/QtQuick_Migration/01_Runtime_Host_Lifecycle.md`
- `Docs/QtQuick_Migration/02_Scene_Renderer_Transitions.md`
- `Docs/QtQuick_Migration/03_Visualizer.md`
- `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md`
- `Docs/QtQuick_Migration/05_Custom_Layout_Input_Interaction.md`
- `Docs/QtQuick_Migration/06_Build_Tooling_Validation.md`

`Current_Plan.md` owns their sequence.

## Accepted presentation destination

```text
one physical display
        ↓
one standalone top-level QQuickWindow
        ↓
threaded Qt Quick scene graph
        ↓
base image + transitions + visualizer + runtime overlays
        ↓
OS presentation
```

`QQuickWidget` is not an acceptable substitute.

There is no planned second migration to a native/C++ presenter. Native code is allowed only as a
localized measured renderer optimization inside this architecture.

## Current implementation during migration

Until production cutover, `main` may still contain and run:

- `DisplayWidget`;
- `GLCompositorWidget`;
- QRhiWidget/OpenGL presenter code;
- GUI-side presentation handoffs.

Those files are migration source/reference code, not permission to expand the old architecture.

No production runtime switch/fallback between old and Quick is to be introduced.

## Durable runtime owners

| Domain | Owner/direction |
|---|---|
| Runtime sequencing | `ScreensaverEngine` |
| Display topology | `DisplayManager` |
| Runtime physical window | destination: one `QQuickWindow` per display |
| Runtime scene pixels | destination: retained Quick + Quick render-thread custom nodes |
| Visualizer logical cadence | `VisualizerLogicalRuntime` |
| Visualizer source/audio | BeatEngine/audio worker/backend |
| Settings | existing QWidget/settings owners |
| Providers / service logic | existing Python owners |
| Persistence | existing settings/store owners |
| Widget models/providers | existing/refactored Python owners |
| Runtime widget pixels | destination: inside display Quick scene |
| Thread/task ownership | `ThreadManager` for general async work |
| Resource accounting | `ResourceManager`; never deletion fallback |

## Visualizer direction

```text
audio / analysis
        ↓
VisualizerLogicalRuntime
        ↓
immutable latest state
        ↓
Quick visualizer item synchronization
        ↓
render-thread custom node
        ↓
physical presentation
```

## Migration execution rule

After every landed slice:

```text
focused gate
-> commit
-> push
-> continue
```

Do not stop merely because a slice exposed a fixable bug.

Do not use destructive Git operations to force checkpoint state.

## Historical navigation

Older reports intentionally contain old owner maps.

Do not recover current direction from historical references to:

- QOpenGLWidget;
- QRhiWidget as final presenter;
- separate visualizer overlay;
- GUI visualizer timers;
- paint-coupled admission.

Use historical material only for the mechanism/regression it records.
