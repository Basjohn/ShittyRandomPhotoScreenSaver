# Contracts

Last updated: 2026-08-18

Fast task-to-owner routing for current `main`. `Current_Plan.md` owns active sequencing.
Historical reports own evidence only.

## Core Runtime

| Family | Current owner | Focused document | Contract |
|---|---|---|---|
| Runtime start/stop/recreate | `ScreensaverEngine`, `DisplayManager` | `Docs/Compositor_Architecture.md` | one ordered runtime lifecycle |
| Monitor topology | engine/display-manager topology owner | `Current_Plan.md` while P5 active | native/Qt events invalidate; one owner settles/snapshots/rebuilds |
| Fullscreen presentation | each `DisplayWidget` + `GLCompositorWidget` | `Docs/Compositor_Architecture.md` | one accelerated QRhi/OpenGL surface per display |
| Widget lifecycle | `WidgetManager` | `Docs/10_WIDGET_GUIDELINES.md` | one setup/reveal/cleanup owner |
| Task registry | `ThreadManager` | `Docs/Guardrails.md` | async work; never paint acknowledgement |
| GL accounting | explicit GL owner + `ResourceManager` | `Docs/Compositor_Architecture.md` | context owner deletes; ResourceManager accounts |

## Rendering / Presentation

| Family | Current owner | Focused document | Contract |
|---|---|---|---|
| QRhi surface | `rendering/gl_rhi_surface.py` | `Docs/Compositor_Architecture.md` | `QRhiWidget.Api.OpenGL`; borrowed Qt context; ExternalContent raw GL |
| Main compositor | `rendering/gl_compositor.py` | `Docs/Compositor_Architecture.md` | base + transition + compositor-owned visual layers |
| Physical frame opportunities | display compositor render strategy | `Docs/Presentation_Change_Preflight.md` | display-refresh presentation only; not simulation |
| Transition state/progress | compositor/transition owners | `Docs/Compositor_Architecture.md` | monotonic local progress; exactly-once completion |
| Visualizer logical cadence | visualizer tick/model | `Docs/Guardrails/Visualizer_Presentation.md` | integrate authored inputs independently of paint |
| Visualizer render state | visualizer logical owner | `Docs/Visualizer_Reference.md` | latest current generation/activation state; no paint ack |
| Visualizer presentation | `rendering/gl_compositor_pkg/visualizer_layer.py` | `Docs/Compositor_Architecture.md` | layer inside the sole display compositor |
| Visualizer GL resources | `SpotifyBarsGLOverlay` resource owner on compositor borrowed context | `Docs/Visualizer_Reference.md` | no independent visualizer surface/context |
| Visualizer card texture | compositor visualizer layer/card texture | `Docs/Compositor_Architecture.md` | QPainter-prepared source pixels uploaded on revision change; steady draw is GL |
| Performance instrumentation | owning renderer + perf modules | `Docs/Logging_Guide.md` | passive/bounded; never admission/cadence |

## Physical Presentation vs Logical Visualizer Cadence

The display compositor may use `AdaptiveRenderStrategyManager` / its adaptive timer as the
**one physical presentation strategy for that display**, provided its liveness covers every
reason the display needs animated presentation (for example active transition and active
visualizer).

This does **not** authorize it to own visualizer source sampling, simulation dt, event
integration or publication.

R-61/R-62 rejected a different architecture: binding a separately presented visualizer surface
to a transition-scoped timer/deferral mechanism. Those incidents do not require resurrecting a
second visualizer presentation clock after the visualizer has moved into the sole display scene.

### Admission rule

A cross-thread `dispatch_pending` guard may prevent duplicate queued Python/Qt callbacks only
until the queued callback actually executes on the GUI thread and calls `QWidget.update()`.

Paint pending/paint completion may be observed for diagnostics but may not block the next
presentation deadline. Qt may coalesce repeated `update()` requests itself.

Forbidden:

- producer waits for paint;
- pending-until-paint admission;
- producer timestamp/display divisor gate;
- paint or swap acknowledgement;
- render-callback self-scheduling loop;
- repaint rescue/retry timer;
- source/event decimation;
- second visualizer presentation clock/surface.

## Visualizer Settings / Activation

| Family | Owner | Contract |
|---|---|---|
| Mode identity | `core/settings/visualizer_mode_registry.py` | stable ids/labels |
| Settings model | `core/settings/models/_spotify_visualizer.py` | one grouped model/serializer |
| Preset resolution | `core/settings/visualizer_presets.py` | one resolved activation payload |
| Runtime activation | visualizer activation/runtime modules | one final activation generation; stale generations never reveal |
| Audio capture/analysis | beat engine/audio worker | source freshness; no backlog/catch-up semantics |
| CUSTOM geometry | shared CUSTOM owner + visualizer geometry anchor | one authoritative rect per runtime/display/DPR |

## GL Lifecycle

- QRhi/OpenGL context exposed by Qt is borrowed and Qt-owned.
- SRPSS never destroys it and never `doneCurrent()`s it as owner.
- GL resources are created/deleted with the correct borrowed context current inside legal QRhi
  lifecycle/render boundaries.
- `releaseResources()`/runtime cleanup share one deletion authority.
- Failed deletion retains ownership and fails closed.
- resize does not masquerade as context destruction.
- true QRhi/context generation replacement retires old-generation resources before reinit.
- global top-level no-vsync request remains intentional; do not add SRPSS-owned `swapBuffers()`.

## Validation / Evidence

| Family | Owner/document | Contract |
|---|---|---|
| Active work | `Current_Plan.md` | unfinished work only |
| Detailed current delivery evidence | P05 phase report | evidence + limits, not task order |
| Stable contracts | `Spec.md`, `Docs/Guardrails.md` | durable architecture/safety |
| Historical incidents | `Docs/Historical_Bugs/` | historical mechanism evidence only |
| Old phase reports | `Docs/phase_reports/` | frozen checkpoint evidence unless explicitly active |

Do not recover current ownership from an old phase report when exact `main` disagrees.
