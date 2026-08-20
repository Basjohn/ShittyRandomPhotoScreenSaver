# Contracts

Last updated: 2026-08-20

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
| Runtime start/stop/recreate | `ScreensaverEngine` / display lifecycle owners | `Docs/Compositor_Architecture.md` |
| Monitor topology | `DisplayManager` / topology owner | `Docs/Compositor_Architecture.md` |
| Runtime physical surface | destination: one standalone `QQuickWindow` per display | `Docs/Compositor_Architecture.md` |
| Runtime scene pixels | destination: Quick scene/render owner | `Docs/Compositor_Architecture.md` |
| Settings/config UI | existing QWidget/settings owners | `Spec.md` |
| Widget data/provider lifecycle | existing Python owners | `Docs/10_WIDGET_GUIDELINES.md` |
| Runtime widget pixels | destination: display Quick scene | `Docs/10_WIDGET_GUIDELINES.md` |
| General async work | `ThreadManager` | `Docs/Guardrails/Runtime_Efficiency.md` |
| Resource accounting | `ResourceManager`; never deletion fallback | `Docs/Guardrails.md` |

## Visualizer ownership

| Family | Owner | Contract |
|---|---|---|
| Audio capture / analysis | BeatEngine + audio worker/backend | bounded current source |
| Logical cadence | `VisualizerLogicalRuntime` | one authored mode-general clock |
| Logical integration | worker-callable tick pipeline | no GUI/Quick/GL mutation |
| Logical publication | latest-state mailbox/state bridge | latest wins; generation fenced |
| Presentation bridge | migration-owned bounded GUI/Quick synchronization | no paint acknowledgement |
| Visualizer pixels | destination: Quick scene/render item(s) | inside sole display window |
| Bubble temporal fidelity | shared chain + Bubble authored state | BTF binding |

The historical `SpotifyBarsGLOverlay` may remain as temporary state/resource code during migration.
Its class name is not a contract and it must not become a separately presented surface.

## Physical presentation

Destination contract:

```text
QQuickWindow per display
        ↓
threaded scene-graph render loop
        ↓
one composed runtime scene
```

Forbidden:

- `QQuickWidget` presenter;
- second accelerated visualizer window;
- paint/present acknowledgement;
- producer/display divisor gating;
- FIFO/catch-up;
- self-driven independent repaint loops used as architecture;
- source/event decimation.

## Native code

There is no scheduled native/C++ presenter migration.

Native code may be used only for a measured local renderer problem and must preserve the one
`QQuickWindow` presentation topology.

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
| Visualizer presentation | `Docs/Guardrails/Visualizer_Presentation.md` |
| Bubble | `Docs/Guardrails/Bubble_Temporal_Fidelity.md` |
| Qt Quick architecture evidence | `Docs/Performance_Evidence/QtQuick-P0-Comparison-2026-08-20.md` |
| Testing | `Docs/TestSuite.md` |
| Harnesses | `Docs/Harness_Index.md` |

Historical reports are evidence only, never current owner maps.
