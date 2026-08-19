# Contracts

Last updated: 2026-08-19

Fast task-to-owner routing for current `main`. `Current_Plan.md` owns active sequencing.
Historical reports own evidence only.

## Core runtime

| Family | Current owner | Focused document | Contract |
|---|---|---|---|
| Runtime start/stop/recreate | `ScreensaverEngine`, `DisplayManager` | `Docs/Compositor_Architecture.md` | one ordered runtime lifecycle |
| Monitor topology | engine/display-manager topology owner | `Current_Plan.md` while P5 active | native/Qt events invalidate; one owner settles/snapshots/rebuilds |
| Fullscreen presentation | each `DisplayWidget` + `GLCompositorWidget` | `Docs/Compositor_Architecture.md` | one accelerated QRhi/OpenGL surface per display |
| Widget lifecycle | `WidgetManager` | `Docs/10_WIDGET_GUIDELINES.md` | one setup/reveal/cleanup owner |
| General async task registry | `ThreadManager` | `Docs/Guardrails.md` | async work; not a visualizer logical or physical display clock |
| GL accounting | explicit GL owner + `ResourceManager` | `Docs/Compositor_Architecture.md` | context owner deletes; ResourceManager accounts |

## Visualizer ownership

| Family | Current owner | Focused document | Contract |
|---|---|---|---|
| Audio capture / analysis | BeatEngine + audio worker/backend | `Docs/Visualizer_Reference.md` | bounded latest-fresh source; capture lifetime separate from visual playback state |
| Logical cadence | `VisualizerLogicalRuntime` | `Docs/P2_Visualizer_Recovery_Contract.md` | one mode-general authored logical clock; no GUI-timer simulation ownership |
| Logical integration | worker-callable `tick_pipeline.logical_tick()` path | `Docs/Guardrails/Visualizer_Presentation.md` | no QWidget/QPixmap/GL mutation; every authored input integrates before presentation coalescing |
| Logical publication | one-slot latest-state mailbox | `Docs/P2_Visualizer_Recovery_Contract.md` | latest wins; no FIFO/catch-up/backpressure |
| GUI reveal / present commit | GUI `present_tick` / reveal/fade/layout owners | `Docs/Guardrails/Visualizer_Presentation.md` | consumes current-generation plain-data intent and performs GUI/GL-facing work |
| Bubble temporal fidelity | shared visualizer chain + Bubble authored state | `Docs/Guardrails/Bubble_Temporal_Fidelity.md` | **BTF**: approved Bubble shape plus healthy source/logical/publication/presentation timing |
| Visualizer render state / GL resources | `SpotifyBarsGLOverlay` historical host | `Docs/Visualizer_Reference.md` | resource/state host only; no independent presentation surface |
| Visualizer physical presentation | compositor visualizer layer | `Docs/Compositor_Architecture.md` | layer inside the sole display compositor |
| Visualizer card texture | compositor visualizer layer/card texture | `Docs/Compositor_Architecture.md` | source pixels update by revision; steady draw is retained GL |

## Physical presentation

| Family | Current owner | Contract |
|---|---|---|
| QRhi surface | `rendering/gl_rhi_surface.py` | `QRhiWidget.Api.OpenGL`; borrowed Qt context; external-content raw GL |
| Main compositor | `rendering/gl_compositor.py` | base + transition + compositor-owned visual layers |
| Physical frame opportunities | display compositor render strategy | display-refresh presentation only; not visualizer simulation |
| Transition state/progress | compositor/transition owners | monotonic local progress; exactly-once completion |
| Performance instrumentation | owning renderer/perf modules | passive/bounded; never admission/cadence |

The display's physical presentation strategy may remain live for multiple reasons such as a
transition, visualizer or other compositor-owned animation. It samples the freshest valid scene.

It may **not**:

- become the visualizer logical clock;
- wait for producer acknowledgement;
- release logical deadlines from paint;
- create a second visualizer presentation loop.

## Readiness contract

Do not overload source freshness into presentation permission.

At minimum distinguish:

```text
presentation_ready
reactive_source_ready
```

Renderer/card/geometry/current-runtime readiness may permit a presentation-owned idle scene while
reactive source authority remains false.

Paused Spectrum is the canonical example.

No source generation/activation may be fabricated merely to satisfy presentation code.

## Generation / activation identity

Generations and activations are ownership fences.

- integer `0` is valid identity when the owner starts at zero;
- `None` / missing may map to an invalid sentinel;
- never use truthiness conversion that turns valid zero into `-1`;
- retired generation/activation state cannot reveal or publish into a replacement owner.

## Admission rule

A cross-thread dispatch-pending guard may prevent duplicate queued GUI callbacks only until the
queued callback actually executes and requests the relevant GUI update/presentation work.

Paint completion may be observed for diagnostics but may not block the next presentation deadline.

Forbidden:

- producer waits for paint;
- pending-until-paint admission;
- producer timestamp/display divisor gate;
- paint or swap acknowledgement;
- render-callback self-scheduling loop;
- repaint rescue/retry timer;
- source/event decimation;
- second visualizer presentation clock/surface;
- second visualizer logical clock.

## GL lifecycle

- Qt owns QRhi and the borrowed OpenGL context.
- SRPSS never destroys/doneCurrent()s the borrowed context as owner.
- GL create/delete occurs on the GUI/context owner.
- one numeric GL handle has one deletion owner.
- failed deletion retains ownership and fails closed.
- resize is not context destruction.
- true QRhi/context generation replacement retires old resources before reinit.
- no SRPSS-owned `swapBuffers()`.

## Validation / evidence

| Family | Owner/document |
|---|---|
| Active work | `Current_Plan.md` |
| Current P2 installed evidence | `Docs/P2_Installed_Acceptance_Findings_2026-08-19.md` |
| Current P2 behavioral gates | `Docs/P2_Behavioral_Gates.md` |
| Stable contracts | `Spec.md`, `Docs/Guardrails.md`, focused guardrails |
| Older phase reports | frozen checkpoint evidence |
| Historical incidents | mechanism/regression evidence only |

Do not recover current ownership from an old phase report when exact `main` disagrees.
