# Index

Last updated: 2026-08-18

Navigation and current ownership map. This file is not a benchmark report.

## Authority Chain

```text
current user instruction + exact current main
        ↓
Current_Plan.md                         active execution order
        ↓
Spec.md + Docs/Guardrails.md + focused current docs
                                        durable architecture/safety contracts
        ↓
Docs/phase_reports/                     checkpoint evidence, scoped to named source/commit
        ↓
Future_Cleanup.md                       deferred cleanup/debt
        ↓
Docs/Historical_Bugs/                   incident evidence/negative controls
```

`Docs/audits/SRPSS_Architecture_Roadmap/` now contains supplemental specialized references only. It
is not an authority layer or second task list.

## Start Here

| Task | Read |
|---|---|
| Active work | `Current_Plan.md` first |
| Find the current owner | `Docs/Contracts.md` |
| Cross-cutting safety | `Docs/Guardrails.md` |
| Stable architecture | `Spec.md` |
| Compositor/QRhi/single-surface work | `Docs/Compositor_Architecture.md` |
| Visualizer presentation/cadence | `Docs/Presentation_Change_Preflight.md`, then `Docs/Guardrails/Visualizer_Presentation.md` |
| Visualizer subsystem | `Docs/Visualizer_Reference.md`, `Docs/Visualizer_Change_Checklist.md` |
| Current delivery evidence | `Docs/phase_reports/P05_PRESENTATION_DELIVERY_ATTRIBUTION.md` while P2/P4 remains active |
| Monitor lifecycle / wake | `Current_Plan.md` P5; optional specialized audit references only after it |
| Tests | `Docs/TestSuite.md` |
| Recurring harnesses | `Docs/Harness_Index.md` |
| Prior regression | `Docs/Historical_Bugs/README.md` |
| Deferred cleanup | `Future_Cleanup.md` |

Do not read every document by default.

## Current Runtime Owners

| Domain | Current owner/location |
|---|---|
| Runtime sequencing | `engine/screensaver_engine.py` |
| Full runtime teardown | `engine/engine_lifecycle.py`, `engine/runtime_destruction.py` |
| Display topology | `engine/display_manager.py` |
| Fullscreen host | `rendering/display_widget.py` |
| Accelerated presentation surface | `rendering/gl_compositor.py`, `rendering/gl_rhi_surface.py` |
| QRhi/OpenGL lifecycle | `rendering/gl_compositor_pkg/gl_lifecycle.py`, `rendering/gl_rhi_surface.py` |
| Physical presentation cadence | display compositor `AdaptiveRenderStrategyManager`; presentation only, never visualizer simulation |
| Image transition scene | `rendering/gl_compositor_pkg/`, transition modules |
| Visualizer logical/runtime state | `widgets/spotify_visualizer_widget.py`, `widgets/spotify_visualizer/`, `widgets/spotify_bars_gl_overlay.py` |
| Visualizer presentation layer | `rendering/gl_compositor_pkg/visualizer_layer.py` inside the display compositor |
| Visualizer card pixels | compositor card-texture path; QWidget remains logical/layout/edit anchor where required |
| Visualizer audio analysis | `widgets/spotify_visualizer/beat_engine.py`, audio worker/backend, analysis helpers |
| Widget lifecycle | `rendering/widget_manager.py` |
| CUSTOM layout | `rendering/custom_layout_manager.py` and descriptor/layout owners |
| Thread/task ownership | `core/threading/manager.py` |
| Resource accounting | `core/resources/manager.py` |
| Settings | `core/settings/settings_manager.py` plus persistence/store owners |
| Logging | `core/logging/logger.py`, `core/logging/tags.py` |
| Evidence analysis | focused tools under `tools/` |

### Important visualizer naming rule

`SpotifyBarsGLOverlay` is retained as a class/path for logical state, geometry and visualizer GL
resources. Its name is historical. It is **not** a separately presented GL overlay anymore.

## Current Presentation Route

```text
visualizer audio/events
      ↓ authored logical cadence
visualizer logical owner / immutable current render state
      ↓
DisplayWidget's single GLCompositorWidget (QRhi/OpenGL)
      ├── base/transition
      ├── cached visualizer card texture
      └── visualizer shader layer
      ↓
Qt physical presentation opportunity
```

There is no ordinary producer acknowledgement from paint.

## Historical Navigation Rule

Older phase reports and incident records intentionally contain old QOpenGLWidget/separate-overlay
owner maps. Use those names only for the checkpoint they describe. Current owner discovery comes
from this index, `Docs/Contracts.md`, current focused docs and exact source.
