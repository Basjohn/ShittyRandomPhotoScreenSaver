# Index

Last updated: 2026-08-20

Navigation and **current ownership map**. This file is not a benchmark report.

## Authority chain

```text
current user instruction + exact current main
        ↓
Current_Plan.md                         active unfinished execution
        ↓
Spec.md + Docs/Guardrails.md + focused current docs
                                        durable architecture/safety contracts
        ↓
current evidence checkpoint             installed/runtime evidence, scoped to named source
        ↓
Docs/phase_reports/                     older checkpoint evidence
        ↓
Future_Cleanup.md                       deferred cleanup/debt
        ↓
Docs/Historical_Bugs/                   incident evidence / negative controls
```

Specialized documents under `Docs/audits/SRPSS_Architecture_Roadmap/` are optional reference only.
They are never a second task list or owner map.

## Start here

| Task | Read |
|---|---|
| Active work | `Current_Plan.md` first |
| Current owner / architecture seam | `Docs/Contracts.md` |
| Cross-cutting safety | `Docs/Guardrails.md` |
| Stable architecture | `Spec.md` |
| Compositor / QRhi / single-surface work | `Docs/Compositor_Architecture.md` |
| Visualizer presentation/cadence | `Docs/Presentation_Change_Preflight.md`, then `Docs/Guardrails/Visualizer_Presentation.md` |
| Bubble feel / BTF / Bubble stutter-reactivity | `Docs/Guardrails/Bubble_Temporal_Fidelity.md` (**BTF**) |
| Visualizer subsystem | `Docs/Visualizer_Reference.md`, `Docs/Visualizer_Change_Checklist.md` |
| Current P2 installed evidence | `Docs/P2_Installed_Acceptance_Findings_2026-08-19.md` |
| Current P2 gates | `Docs/P2_Behavioral_Gates.md` |
| Active physical-presentation benchmark | `tools/presentation_benchmark_core.py`, `tools/worker_push_presentation_benchmark.py`, `tools/qtquick_p0_presentation_benchmark.py`; current comparison: `Docs/Performance_Evidence/QtQuick-P0-Comparison-2026-08-20.md` |
| Monitor lifecycle / wake | `Current_Plan.md` P5 boundary; current topology docs only |
| Tests | `Docs/TestSuite.md` |
| Recurring harnesses | `Docs/Harness_Index.md` |
| Prior regression | `Docs/Historical_Bugs/README.md` |
| Deferred cleanup | `Future_Cleanup.md` |

Do not read every document by default.

## Current runtime owners

| Domain | Current owner/location |
|---|---|
| Runtime sequencing | `engine/screensaver_engine.py` |
| Full runtime teardown | `engine/engine_lifecycle.py`, `engine/runtime_destruction.py` |
| Display topology | `engine/display_manager.py` |
| Fullscreen host | `rendering/display_widget.py` |
| Accelerated presentation surface | `rendering/gl_compositor.py`, `rendering/gl_rhi_surface.py` |
| QRhi/OpenGL lifecycle | `rendering/gl_compositor_pkg/gl_lifecycle.py`, `rendering/gl_rhi_surface.py` |
| Physical presentation cadence | each display compositor's render strategy; presentation only |
| Visualizer logical cadence | `widgets/spotify_visualizer/logical_runtime.py::VisualizerLogicalRuntime` |
| Visualizer logical integration / mailbox handoff | `widgets/spotify_visualizer/tick_pipeline.py`, `tick_helpers.py` |
| Visualizer GUI reveal/presentation commit | GUI half of `tick_pipeline.py`, mode/startup/fade owners |
| Visualizer render resources/state host | `widgets/spotify_bars_gl_overlay.py` — historical name, not a surface |
| Visualizer physical pixels | `rendering/gl_compositor_pkg/visualizer_layer.py` inside the display compositor |
| Visualizer card pixels | compositor card-texture path; QWidget remains layout/edit anchor where required |
| Visualizer audio analysis | `widgets/spotify_visualizer/beat_engine.py`, audio worker/backend, analysis helpers |
| Widget lifecycle | `rendering/widget_manager.py` |
| CUSTOM layout | `rendering/custom_layout_manager.py` and descriptor/layout owners |
| Thread/task ownership | `core/threading/manager.py` |
| Resource accounting | `core/resources/manager.py` |
| Settings | `core/settings/settings_manager.py` plus persistence/store owners |
| Logging | `core/logging/logger.py`, `core/logging/tags.py` |

## Current visualizer route

```text
audio / analysis producer
        ↓
current source snapshot + generation/activation identity
        ↓
VisualizerLogicalRuntime
        ↓
single-slot latest logical publication
        ↓ GUI-thread presentation handoff
display GLCompositorWidget
        ├── base / transition
        ├── cached visualizer card
        └── visualizer shader layer
        ↓
Qt / OS physical presentation
```

There is:

- one logical visualizer clock;
- one physical presentation owner per display;
- no ordinary producer acknowledgement from paint;
- no independently presented visualizer surface.

## Readiness rule

`presentation_ready` and `reactive_source_ready` are distinct.

Paused Spectrum can reveal a presentation-owned idle scene without fabricating real source identity.
Reactive Spectrum playback still requires fresh current-generation/current-activation source state.

## Historical navigation rule

Older phase reports and incident records intentionally contain old QOpenGLWidget, GUI-timer,
separate-overlay and pre-worker owner maps. Use those names only for the checkpoint they describe.

Current owner discovery comes from this index, `Docs/Contracts.md`, focused current docs and exact
source.
