# Contracts

Last updated: 2026-08-21

Fast task-to-owner routing during the Qt Quick presentation migration.

`Current_Plan.md` owns sequencing. `Spec.md` and focused architecture docs own durable destination
contracts. Exact source owns what is currently implemented.

## Architecture-epoch rule

The old QRhiWidget presenter may remain live during migration.

When current source and destination architecture differ:

- source answers "what runs today?";
- `Docs/Compositor_Architecture.md` answers "what are we migrating toward?";
- `Current_Plan.md` answers "what may be changed in this slice?".

Do not turn temporary old ownership into a new permanent contract.

## Core runtime

| Family | Durable owner/direction | Focused document |
|---|---|---|
| Runtime start/stop/recreate | `ScreensaverEngine` / display lifecycle owners | `Docs/QtQuick_Migration/01_Runtime_Host_Lifecycle.md` |
| Monitor topology | `DisplayManager` / topology owner | `Docs/QtQuick_Migration/01_Runtime_Host_Lifecycle.md` |
| Runtime physical surface | one standalone `QQuickWindow` per display | `Docs/Compositor_Architecture.md` |
| Ordinary runtime scene pixels | retained Quick items/components | `Docs/Compositor_Architecture.md` |
| Custom GL scene pixels | inline `QQuickItem -> QSGRenderNode -> OpenGL` | `Docs/Compositor_Architecture.md` |
| Settings/config UI | existing QWidget/settings owners | `Spec.md` |
| Widget data/provider lifecycle | existing/refactored Python owners | `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md` |
| Runtime widget pixels | destination: display retained Quick scene | `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md` |
| General async work | `ThreadManager` | `Docs/Guardrails/Runtime_Efficiency.md` |
| Resource accounting | `ResourceManager`; never deletion fallback | `Docs/Guardrails.md` |

`QQuickRhiItem` is not the normal SRPSS custom-render path. `QQuickWidget` is not an acceptable runtime presenter.

## Transition ownership

| Family | Owner | Contract |
|---|---|---|
| Canonical id/settings identity | `rendering/transition_registry.py` | stable descriptor/catalog authority |
| GUI/runtime parameter resolution | Quick transition request resolver | canonical defaults/random choices resolved before render ownership |
| Transition lifecycle/time | `TransitionRequest` / `TransitionRun` | immutable, monotonic, exactly-once completion/cancel |
| Transition implementation | lazy static Quick implementation registry | disabled implementations/resources remain dormant |
| Transition pixels/resources | display transition `QSGRenderNode` host + implementation | no old-compositor fallback or state leak |

See `Docs/Transition_Change_Checklist.md` and `Docs/QtQuick_Migration/02_Scene_Renderer_Transitions.md`.

## Visualizer ownership

| Family | Owner | Contract |
|---|---|---|
| Audio capture / analysis | BeatEngine + audio worker/backend | bounded current source |
| Logical cadence | `VisualizerLogicalRuntime` | sole authored mode-general clock |
| Logical integration | worker-callable tick pipeline | no GUI/Quick/GL mutation |
| Logical publication | latest-state mailbox/snapshot bridge | latest wins; generation fenced |
| Presentation bridge | migration-owned bounded GUI/Quick synchronization | immutable; no paint acknowledgement |
| Visualizer pixels | display Quick visualizer item + `QSGRenderNode` | inside sole display window |
| Bubble temporal fidelity | shared chain + Bubble authored state | BTF binding |

The historical `SpotifyBarsGLOverlay` may remain as temporary state/resource/reference code during
migration. Its class name is not a contract and it must not become a separately presented surface.

## Physical presentation

Destination contract:

```text
QQuickWindow per display
        ↓
threaded scene-graph render loop
        ↓
retained Quick items + inline QSGRenderNode custom GL
        ↓
one composed runtime scene
```

Forbidden:

- `QQuickWidget` presenter;
- second accelerated visualizer window;
- per-effect old-compositor fallback;
- paint/present acknowledgement;
- producer/display divisor gating;
- FIFO/catch-up;
- self-driven independent repaint loops used as architecture;
- source/event decimation.

## Native code

There is no scheduled native/C++ presenter migration.

Native code may be used only for a measured local renderer problem and must preserve the one
`QQuickWindow` presentation topology and the same logical/state contracts.

## Readiness

At minimum distinguish:

```text
presentation_ready
reactive_source_ready
```

A presentation-owned idle scene may reveal while real reactive source is unavailable.

## Generation identity

- `0` is valid;
- missing/`None` may be invalid;
- stale retired state cannot reveal or publish;
- new runtime authority begins only after old-generation retirement.

## Validation routing

| Family | Document |
|---|---|
| Active work | `Current_Plan.md` |
| Stable architecture | `Spec.md` |
| Presentation architecture | `Docs/Compositor_Architecture.md` |
| Cross-cutting safety | `Docs/Guardrails.md` |
| Transitions | `Docs/Transition_Change_Checklist.md` |
| Visualizer presentation | `Docs/Guardrails/Visualizer_Presentation.md` |
| Bubble | `Docs/Guardrails/Bubble_Temporal_Fidelity.md` |
| Qt Quick architecture evidence | `Docs/Performance_Evidence/QtQuick-P0-Comparison-2026-08-20.md` |
| Testing | `Docs/TestSuite.md` |
| Harnesses | `Docs/Harness_Index.md` |

Historical reports are evidence only, never current owner maps.
