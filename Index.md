# SRPSS Index

Last updated: 2026-08-22

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

`Current_Plan.md` owns current sequence/work admission and may retain clearly marked completed-phase
closure/rationale for migration continuity. Completed sections do not reopen themselves as work.

`Future_Work.md` is a long-horizon new-feature/new-implementation backlog, not active sequencing. An
agent may implement from it only when the operator explicitly selects an item or when
`Current_Plan.md` and `Future_Cleanup.md` contain no remaining important active work.

During the Qt Quick migration, exact source tells you what is **currently implemented** while
`Spec.md` and `Docs/Compositor_Architecture.md` define the accepted destination architecture.

## Current migration status

Current normal implementation work is **Phase E — widget presentation + capability setup foundation**.

- Phase C transition implementation/deterministic hardening: landed; remaining acceptance is explicit.
- Phase D visualizer implementation/documentation closure: complete; remaining physical/eyes-on items
  are explicit acceptance debt.
- Phase-E activation foundation: family catalog + canonical activation settings + transition runtime
  admission + widget family creation admission have landed.
- Broader E1 runtime ownership, E2 `SETUP`/live lazy navigation, E3 Quick primitives and E4 global
  shadow direction remain governed by exact `Current_Plan.md`/source state.

## Start here

| Task | Read |
|---|---|
| Active migration work | `Current_Plan.md` |
| Qt Quick migration technical detail | `Docs/QtQuick_Migration/README.md` + only the active/focused decomposition |
| Accepted runtime presentation architecture | `Docs/Compositor_Architecture.md` |
| Current/migration ownership map | `Docs/Contracts.md` |
| Cross-cutting safety | `Docs/Guardrails.md` |
| Stable architecture | `Spec.md` |
| Capability activation / E2 SETUP | `Docs/QtQuick_Migration/07_Settings_Capability_Activation.md` |
| Widget/runtime presentation | `Docs/10_WIDGET_GUIDELINES.md`, `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md` |
| Transition authoring/runtime | `Docs/Transition_Change_Checklist.md`, `Docs/QtQuick_Migration/02_Scene_Renderer_Transitions.md` |
| Visualizer presentation/cadence | `Docs/Guardrails/Visualizer_Presentation.md` |
| Bubble feel / timing | `Docs/Guardrails/Bubble_Temporal_Fidelity.md` |
| Visualizer subsystem | `Docs/Visualizer_Reference.md`, `Docs/Visualizer_Change_Checklist.md`, `Docs/QtQuick_Migration/03_Visualizer.md` |
| CUSTOM/input/interaction | `Docs/QtQuick_Migration/05_Custom_Layout_Input_Interaction.md` |
| Defaults/settings schema | `Docs/Defaults_Guide.md` |
| Qt Quick architecture evidence | `Docs/Performance_Evidence/QtQuick-P0-Comparison-2026-08-20.md` |
| Tests | `Docs/TestSuite.md` |
| Recurring harnesses | `Docs/Harness_Index.md` |
| Documentation roles/hygiene | `Docs/Documentation_Maintenance.md` |
| Prior regressions | `Docs/Historical_Bugs/README.md` |
| Cutover deletion / deferred cleanup | `Future_Cleanup.md` |
| Explicitly deferred new features / experiments | `Future_Work.md` (only when activation rule is satisfied) |

Do not read every document by default.

## Qt Quick migration support docs

These are subordinate technical decompositions/references, not parallel plans:

- `Docs/QtQuick_Migration/01_Runtime_Host_Lifecycle.md`
- `Docs/QtQuick_Migration/02_Scene_Renderer_Transitions.md`
- `Docs/QtQuick_Migration/03_Visualizer.md`
- `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md`
- `Docs/QtQuick_Migration/05_Custom_Layout_Input_Interaction.md`
- `Docs/QtQuick_Migration/06_Build_Tooling_Validation.md`
- `Docs/QtQuick_Migration/07_Settings_Capability_Activation.md`

Some decompositions describe landed earlier-phase architecture because they remain the best focused
reference. `Current_Plan.md` alone decides whether work is admitted now.

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

`QQuickWidget` is not acceptable.

There is no planned second migration to a native/C++ presenter. Native code is allowed only as a
localized measured renderer optimization inside this architecture.

## Current implementation during migration

Until production cutover, `main` may still contain/run:

- `DisplayWidget`;
- `GLCompositorWidget`;
- QRhiWidget/OpenGL presenter code;
- GUI-side presentation handoffs;
- QWidget runtime widget presentation.

Those files are current/reference migration source, not permission to expand old architecture.

No production runtime switch/fallback between old and Quick is to be introduced.

## Durable runtime owners/direction

| Domain | Owner/direction |
|---|---|
| Runtime sequencing | `ScreensaverEngine` |
| Display topology | `DisplayManager` |
| Runtime physical window | destination: one `QQuickWindow` per display |
| Runtime scene pixels | destination: retained Quick + Quick render-thread custom nodes |
| Visualizer logical cadence | `VisualizerLogicalRuntime` |
| Visualizer source/audio | BeatEngine/audio worker/backend |
| Settings/config UI | existing QWidget/settings owners |
| Capability activation | canonical settings + presentation-neutral family/transition catalog/query authority |
| Providers / service logic | existing/refactored Python owners |
| Persistence | existing settings/store owners |
| Widget models/providers | current owners migrating toward presentation-neutral `WidgetRuntimeManager` |
| Runtime widget pixels | destination: display Quick scene |
| Thread/task ownership | `ThreadManager` for general async work |
| Resource accounting | `ResourceManager`; accounting only, never deletion owner |

## Capability activation direction

```text
cheap catalog metadata
        ↓
application-level activated?
        ↓ yes
implementation/runtime owner may resolve
        ↓
ordinary enabled / manual / pool state
```

Use `activated/deactivated` for the application-level gate and `enabled/disabled` for ordinary widget
instance state. Transition pool membership/manual selection are separate again.

The visualizer is not a widget-family activation capability.

## Visualizer direction

```text
audio / analysis
        ↓
VisualizerLogicalRuntime
        ↓
mode-owned logical frame runtime
        ↓
immutable latest state
        ↓
Quick visualizer synchronization
        ↓
render-thread custom node
        ↓
physical presentation
```

## Migration execution rule

Local mutation:

```text
focused gate
-> inspect diff/status
-> commit
-> push
```

High-risk/audit-required slice adds:

```text
-> independent audit of actual pushed source before continuation
```

Repository connectors are read/audit only for normal SRPSS workflow. Hosted CI is not added unless the
operator explicitly requests it.

Do not use destructive Git operations to force checkpoint state.

## Historical navigation

Older reports intentionally contain old owner maps.

Do not recover current direction from historical references to:

- QOpenGLWidget;
- QRhiWidget as final presenter;
- separate visualizer overlay;
- GUI visualizer timers;
- paint-coupled admission;
- old widget factories as final pixel authority.

Use historical material only for the mechanism/regression/evidence it records.
