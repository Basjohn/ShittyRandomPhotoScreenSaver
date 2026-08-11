# Index

Last updated: 2026-08-11

Navigation and ownership map for SRPSS. This file is not a specification.

## Start Here

| Task | Read |
|---|---|
| Any code change | relevant `Docs/Guardrails.md` section |
| Find owning subsystem | `Docs/Contracts.md` |
| Stable product/architecture contract | `Spec.md` |
| Current unfinished work | `Current_Plan.md` |
| Architecture program/status | `Docs/audits/SRPSS_Architecture_Roadmap/README.md` |
| Compositor/presentation/GL | `Docs/Compositor_Architecture.md` |
| Threading/UI workload | `Docs/audits/SRPSS_Architecture_Roadmap/08_CPU_THREADING_AND_WORKLOAD_PLAN.md` |
| Memory/GPU/cache | `Docs/audits/SRPSS_Architecture_Roadmap/09_MEMORY_GPU_RESOURCE_AND_CACHE_PLAN.md` |
| Logging | `Docs/Logging_Guide.md` |
| Tests/harnesses | `Docs/TestSuite.md`, `Docs/Harness_Index.md` |
| Prior fragile regression | `Docs/Historical_Bugs/README.md` |
| Deferred cleanup | `Future_Cleanup.md` |

Do not read every document by default.

## Core Documents

| File | Purpose |
|---|---|
| `Docs/00_PROJECT_OVERVIEW.md` | project/document orientation |
| `Docs/Guardrails.md` | cross-cutting safety/stop rules |
| `Docs/Contracts.md` | task-to-owner routing |
| `Spec.md` | stable behaviour/architecture contracts |
| `Current_Plan.md` | active unfinished work only |
| `Docs/audits/SRPSS_Architecture_Roadmap/README.md` | current architecture roadmap and phase program |
| `Docs/Compositor_Architecture.md` | current presentation/compositor target |
| `Docs/Logging_Guide.md` | logging architecture/routing contract |
| `Docs/TestSuite.md` | test levels/release gates |
| `Docs/Harness_Index.md` | recurring commands/probes |
| `Docs/Historical_Bugs/README.md` | historical incident index |
| `Docs/Historical_Bugs.md` | compact historical navigation/status |
| `Future_Cleanup.md` | deferred low-priority cleanup only |

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
| Compositor/GL programs | `rendering/gl_compositor.py`, `rendering/gl_compositor_pkg/`, `rendering/gl_programs/` |
| Media provider/GSMTC/progress presentation | `core/media/provider_registry.py`, `core/media/media_controller.py`, `widgets/media_widget.py`, `widgets/media/display_update.py`, `widgets/media/painting.py` |
| Reddit provider/preparation/Qt commit | `core/reddit_post_provider.py`, `core/reddit_preparation.py`, `widgets/reddit_widget.py` |
| Weather provider/preparation/Qt commit | `weather/open_meteo_provider.py`, `core/weather_preparation.py`, `widgets/weather_widget.py` |
| Visualizer model/runtime | `widgets/spotify_visualizer/` and `widgets/spotify_visualizer_widget.py` |
| Visualizer presentation | `widgets/spotify_bars_gl_overlay.py` plus display-local Qt/GL ownership |
| CUSTOM layout | custom-layout manager/contract modules |
| Logging | `core/logging/logger.py` and focused logging helpers |

Use `Docs/Contracts.md` before assuming a nearby helper is an authority.

## Architecture Evidence References

```text
working branch:      main
approved visual ref: ff93461685476bd0657aa88312fc2e35e9037880
current evidence:    logs/evidence_chest/08_09_ca830d7_14_59/
roadmap:             Docs/audits/SRPSS_Architecture_Roadmap/
phase reports:       Docs/phase_reports/
historical lessons: Docs/audits/SRPSS_Architecture_Roadmap/10_HISTORICAL_CANDIDATE_LESSONS.md
```

Historical baseline/candidate commits are opened only for a named forensic question or
negative control. They are not current implementation seams.

## Entry Points

- `main.py` — canonical runtime/performance/evidence authority.
- `main_mc.py` — Media Center route; bounded shared smoke coverage only.
- `main_diagnostic.py` — opt-in frozen-runtime diagnostic attribution product; not an ordinary performance target.
- `tools/build_runner.py` — build owner.

## Test Infrastructure

- `tests/conftest.py` — shared isolation/fixtures.
- `tests/run_chunked.py` — bounded subprocess full-suite execution.
- `tools/visualizer_replay.py` — protected visualizer replay/negative controls.
- phase/resource/thread benchmarks and evidence parser — use via `Docs/Harness_Index.md`.

## Navigation Rule

Add only architectural owners/critical entry points. Detailed implementation narratives,
benchmark numbers and completed work belong in focused docs/reports/history.
