# Index

Last updated: 2026-08-16

Navigation and ownership map for SRPSS. This file is not a specification.

## Start Here

| Task | Read |
|---|---|
| Any code change | relevant `Docs/Guardrails.md` section |
| Visualizer cadence/presentation/repaint change | `Docs/Guardrails/Visualizer_Presentation.md` **and** `Docs/Visualizer_Change_Checklist.md` |
| Find owning subsystem | `Docs/Contracts.md` |
| Stable product/architecture contract | `Spec.md` |
| Current unfinished work / execution order | `Current_Plan.md` |
| Current Phase 5 delivery evidence | `Docs/phase_reports/P05_PRESENTATION_DELIVERY_ATTRIBUTION.md` |
| Architecture program/status | `Docs/audits/SRPSS_Architecture_Roadmap/README.md` |
| Compact audit priorities | `Docs/audits/SRPSS_Architecture_Roadmap/00_INDEX_AND_LIVE_CHECKLIST.md` |
| Presentation/compositor design | `Docs/audits/SRPSS_Architecture_Roadmap/06_PRESENTATION_AND_COMPOSITOR_DESIGN.md` |
| Threading/UI workload | `Docs/audits/SRPSS_Architecture_Roadmap/08_CPU_THREADING_AND_WORKLOAD_PLAN.md` |
| Memory/GPU/cache | `Docs/audits/SRPSS_Architecture_Roadmap/09_MEMORY_GPU_RESOURCE_AND_CACHE_PLAN.md` |
| Logging/routing/retention | `Docs/Logging_Guide.md` |
| Evidence parsing and recurring probes | `Docs/Harness_Index.md` |
| Tests/release gates | `Docs/TestSuite.md` and roadmap `12_TEST_AND_BENCHMARK_PROTOCOL.md` |
| Failure-owner triage | roadmap `14_FAILURE_TRIAGE_MAP.md` |
| Prior fragile regression | `Docs/Historical_Bugs/README.md` |
| Deferred/temporary cleanup | `Future_Cleanup.md` |

Do not read every document by default.

## Authority Chain

```text
Current_Plan.md
    ↓ execution order
Spec.md / Guardrails.md
    ↓ stable contracts
Docs/phase_reports/
    ↓ accepted detailed evidence
Docs/audits/SRPSS_Architecture_Roadmap/
    ↓ dependencies, priorities, design and validation
Future_Cleanup.md
    ↓ temporary-code removal / deferred cleanup / test debt
```

A phase report does not override `Current_Plan.md` task order. `Future_Cleanup.md` is not
an alternate active plan.

## Core Documents

| File | Purpose |
|---|---|
| `Docs/00_PROJECT_OVERVIEW.md` | project/document orientation |
| `Docs/Guardrails.md` | cross-cutting safety/stop rules |
| `Docs/Guardrails/` | focused per-domain guardrails; currently `Visualizer_Presentation.md` |
| `Docs/Visualizer_Change_Checklist.md` | required sweep for visualizer/runtime-bridge changes |
| `Docs/Contracts.md` | task-to-owner routing |
| `Spec.md` | stable behaviour/architecture contracts |
| `Current_Plan.md` | active unfinished work only |
| `Docs/phase_reports/P05_PRESENTATION_DELIVERY_ATTRIBUTION.md` | accepted current delivery/presentation checkpoint |
| `Docs/audits/SRPSS_Architecture_Roadmap/README.md` | current architecture roadmap |
| `Docs/Compositor_Architecture.md` | broader compositor architecture |
| `Docs/Logging_Guide.md` | logging architecture/routing/retention |
| `Docs/TestSuite.md` | test levels/release gates |
| `Docs/Harness_Index.md` | recurring commands/probes |
| `Docs/Historical_Bugs/README.md` | historical incident index |
| `Future_Cleanup.md` | deferred cleanup and temporary-code/test debt |

## Current Runtime Owners

| Domain | Primary owner/location |
|---|---|
| Runtime sequencing | `engine/screensaver_engine.py` |
| Full runtime teardown | `engine/engine_lifecycle.py::teardown_display_runtime` |
| Retired-generation barrier | `engine/runtime_destruction.py` |
| Display topology | `engine/display_manager.py` |
| Fullscreen presenter | `rendering/display_widget.py` |
| Widget lifecycle | `rendering/widget_manager.py` |
| Thread/task ownership | `core/threading/manager.py` |
| Settings in-memory authority | `core/settings/settings_manager.py` |
| Settings ordered durability | `core/settings/persistence.py`, `core/settings/json_store.py` |
| Resource accounting | `core/resources/manager.py`, `core/performance/resource_metrics.py` |
| Whole-process usage | `core/performance/usage_sampler.py` |
| Image pipeline | `engine/image_pipeline.py` and image/prefetch helpers |
| Main compositor/GL | `rendering/gl_compositor.py`, `rendering/gl_compositor_pkg/`, `rendering/gl_programs/` |
| Delivery-stage observation | `rendering/adaptive_timer.py` plus compositor metrics |
| Visualizer logical runtime | `widgets/spotify_visualizer/`, `widgets/spotify_visualizer_widget.py` |
| Visualizer presentation | `widgets/spotify_bars_gl_overlay.py` plus display-local Qt/GL ownership |
| Heavyweight GPU timing | `rendering/gl_timer_queries.py` plus owning renderer/compositor |
| Media provider/GSMTC | `core/media/provider_registry.py`, `core/media/media_controller.py`, `widgets/media_widget.py` |
| CUSTOM layout | custom-layout manager/contract modules |
| Logging | `core/logging/logger.py`, `core/logging/tags.py` |
| Crash breadcrumbs | `core/logging/crash_capture.py` |
| Evidence analysis | `tools/recovery_evidence_parser.py` and focused tools |

Use `Docs/Contracts.md` before assuming a nearby helper is an authority.

## Current Phase 5 Route

For the delivery/presentation thread:

```text
Current_Plan P0 → P1 → P2 → P3 → P4
        │
        ├── evidence: Docs/phase_reports/P05_PRESENTATION_DELIVERY_ATTRIBUTION.md
        ├── design:   roadmap/06_PRESENTATION_AND_COMPOSITOR_DESIGN.md
        ├── tests:    roadmap/12_TEST_AND_BENCHMARK_PROTOCOL.md
        ├── triage:   roadmap/14_FAILURE_TRIAGE_MAP.md
        └── cleanup:  Future_Cleanup.md
```

## Entry Points

- `main.py` — canonical runtime/performance/evidence authority.
- `main_mc.py` — Media Center route; bounded shared smoke coverage.
- `main_diagnostic.py` — frozen-runtime diagnostic attribution; not ordinary performance target.
- `tools/build_runner.py` — build owner.

## Navigation Rule

Add architectural owners and critical evidence routes only. Raw benchmark logs and
completed implementation narratives belong in phase reports/history, not here.
