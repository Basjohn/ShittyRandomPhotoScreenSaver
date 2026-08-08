# Index

Last updated: 2026-08-02

Navigation and ownership map for SRPSS.

This file is not a specification and must not accumulate implementation narratives.

## Start Here

| Task | Read |
|---|---|
| Any code change | Relevant section of `Docs/Guardrails.md` |
| Find the owning subsystem | `Docs/Contracts.md` |
| Stable architecture change | `Spec.md` |
| Current recovery work | `Current_Plan.md` |
| Recovery program and live checklist | `Docs/audits/SRPSS_Architecture_Recovery_Roadmap/README.md` |
| Compositor/GL/performance recovery | `Docs/Compositor_Architecture.md` |
| Test selection | `Docs/TestSuite.md` |
| Existing harness command | `Docs/Harness_Index.md` |
| Prior regression in fragile area | `Docs/Historical_Bugs.md` |
| Documentation cleanup | `Docs/Documentation_Maintenance.md` |

Do not read every document by default.

## Core Documents

| File | Purpose |
|---|---|
| `Docs/00_PROJECT_OVERVIEW.md` | Short project and documentation orientation |
| `Docs/Guardrails.md` | Cross-cutting safety rules and stop conditions |
| `Docs/Contracts.md` | Fast task-to-owner routing |
| `Spec.md` | Stable architecture and behaviour contracts |
| `Current_Plan.md` | Active unfinished work only |
| `Docs/audits/SRPSS_Architecture_Recovery_Roadmap/README.md` | Full recovery audit, phase program, ownership targets, and evidence gates |
| `Docs/Compositor_Architecture.md` | Compositor recovery target and validation |
| `Docs/TestSuite.md` | Test levels and release gates |
| `Docs/Harness_Index.md` | Recurring commands/probes |
| `Docs/Historical_Bugs.md` | Dated bug narratives |
| `Docs/Regression_Notes.md` | Small resolved regression notes |
| `Docs/Documentation_Maintenance.md` | Drift and document-size control |
| `Future_Cleanup.md` | Deferred low-priority cleanup |

## Focused Guides

| Area | Document |
|---|---|
| Defaults/settings transport | `Docs/Defaults_Guide.md` |
| Widget development | `Docs/10_WIDGET_GUIDELINES.md` |
| Visualizer architecture/settings | `Docs/Visualizer_Reference.md` |
| Visualizer change sweep | `Docs/Visualizer_Change_Checklist.md` |
| Transition changes | `Docs/Transition_Change_Checklist.md` |
| Logging | `Docs/Logging_Guide.md` |
| Shared UI style | `Docs/Custom_Style_Implementation.md` |
| Historical architecture/Bubble/geometry/Oscilloscope audits | `Docs/audits/OLD/` |
| Steam sources and promotion | existing Steam-focused documents |
| Media-key/focus investigation | `Docs/MEDIAKEYDEBUG.md` |

## Entry Points

| File | Role |
|---|---|
| `main.py` | Normal screensaver runtime and Windows invocation modes |
| `main_mc.py` | Media Center runtime |
| `tools/build_runner.py` | Build Foundry GUI/CLI owner for normal and repo-root-venv release pipelines |

## Runtime Ownership Map

| Domain | Primary owner/location |
|---|---|
| Runtime sequencing | `engine/screensaver_engine.py` |
| Full runtime teardown | `engine/engine_lifecycle.py::teardown_display_runtime` |
| Retired-generation destruction barrier | `engine/runtime_destruction.py` |
| Display topology/lifecycle | `engine/display_manager.py` |
| Fullscreen presenter | `rendering/display_widget.py` |
| Display-local ordered teardown | `rendering/display_cleanup.py::cleanup_runtime` |
| Display setup | existing modules under `rendering/display_*` |
| Widget lifecycle | `rendering/widget_manager.py` |
| Startup overlay reveal / deferred GL warmup | `rendering/fade_coordinator.py`, `rendering/widget_manager.py`, `rendering/gl_compositor_pkg/gl_lifecycle.py` |
| Widget setup | `rendering/widget_setup_all.py` |
| Widget metadata | `rendering/widget_descriptors.py` |
| Thread/task ownership | `core/threading/manager.py` |
| Resource tracking and generation ownership | `core/resources/manager.py`, `core/performance/resource_metrics.py` |
| Whole-process usage sampling | `core/performance/usage_sampler.py` |
| Settings | `core/settings/settings_manager.py` |
| Defaults/profile resolution | modules under `core/settings/` |
| Shared events | `core/events/event_system.py` |
| Worker processes and response disposal | `core/process/supervisor.py` |
| Image shared-memory handoff/accounting | `core/process/shared_memory_transport.py` |
| Shared animation | `core/animation/animator.py` |
| Transition identity | `rendering/transition_registry.py` |
| Compositor | existing compositor modules under `rendering/` |
| Image pipeline | existing image-pipeline and prefetch modules |
| Media artwork worker/UI handoff | `widgets/media_widget.py`, `widgets/media/display_update.py`, `rendering/display_widget.py` |
| External media-command ingress/deduplication | `rendering/media_command_ingress.py`, then `rendering/input_handler.py` / `rendering/display_native_events.py` |
| Display image accounting | `rendering/image_resource_accounting.py` |
| Compositor program ownership | `rendering/gl_programs/program_cache.py` |
| Passive GL resource accounting | `core/resources/manager.py` |
| Compositor texture/PBO budgets | `rendering/gl_programs/texture_manager.py` |
| Visualizer model/runtime | existing modules under `widgets/spotify_visualizer/` |
| Visualizer replay schema/runtime | `widgets/spotify_visualizer/feature_frame.py`, `widgets/spotify_visualizer/replay_runtime.py` |
| Visualizer renderer | existing GL visualizer renderer modules |
| CUSTOM layout | existing custom-layout contract/manager modules |
| Input routing | existing centralized input handler |
| Secure-desktop URL/helper handoff | installer task/ACL contract plus `core/windows/reddit_helper_bridge.py`, `core/windows/reddit_helper_runtime.py`, and `helpers/reddit_helper_worker.py` |
| Logging/performance | modules under `core/performance/`, logging tools |

Use `Docs/Contracts.md` before assuming a nearby helper is an authority.

## Settings and Persistence

Canonical areas:

- `core/settings/settings_manager.py`
- `core/settings/defaults.py`
- `core/settings/default_settings.py`
- profile override and snapshot modules
- `core/settings/storage_paths.py`
- visualizer registry/model/preset modules

Focused details belong in `Docs/Defaults_Guide.md` and `Docs/Visualizer_Reference.md`.

## Widgets

Canonical areas:

- `rendering/widget_descriptors.py`
- `rendering/widget_setup_all.py`
- `rendering/widget_manager.py`
- widget-local modules under `widgets/`
- settings builders under `ui/tabs/`

Use `Docs/10_WIDGET_GUIDELINES.md`.

## Rendering Recovery References

```text
branch:          main
baseline:        00edb57a3076b845cb8ee4b6cb7f36ea83411f0c
donor branch:    donor-7376bb9 (reference-only/read-only)
donor:           7376bb9bb380253f3bd14079e65d7bdbca062fad
evidence:        logs/evidence_chest/
audit roadmap:   Docs/audits/SRPSS_Architecture_Recovery_Roadmap/
Phase 1 report:  Docs/phase_reports/P01_MEASUREMENT_FOUNDATION.md
Phase 2 report:  Docs/phase_reports/P02_VISUALIZER_FIDELITY_LOCK.md
Phase 3 report:  Docs/phase_reports/P03_GL_LIFECYCLE_AND_RECONFIGURATION.md
Phase 4 report:  Docs/phase_reports/P04_MEMORY_VRAM_CONTAINMENT.md
Phase 4 map:     Docs/phase_reports/P04_RESOURCE_LIFETIME_MAP.md
Phase 5 report:  Docs/phase_reports/P05_CPU_TASK_REDUCTION.md
```

Read `Docs/Compositor_Architecture.md`.

## Test Infrastructure

| File | Purpose |
|---|---|
| `tests/conftest.py` | Shared test isolation/fixtures |
| `tests/run_chunked.py` | Bounded subprocess suite execution |
| `Docs/TestSuite.md` | Test selection and gates |
| `Docs/Harness_Index.md` | Focused recurring commands |
| `tools/visualizer_replay.py` | Deterministic visualizer replay, protected golden verification, and review artifacts |
| `tools/phase3_lifecycle_harness.py` | Deterministic 50/50/50 full-teardown, generation, callback, and resource plateau gate |
| `tools/phase4_resource_harness.py` | Deterministic 45-cycle CPU-image/display/texture/PBO budget, terminal-retention/reuse, and allocator plateau gate |
| `tools/phase4_image_worker_shm_harness.py` | Real spawned-ImageWorker 50×4K shared-memory/RSS plateau and orphan gate |
| `tools/phase5_thread_manager_benchmark.py` | General COMPUTE executor accounting/callback overhead projection |
| `tools/phase5_frame_owner_benchmark.py` | Perf-only passive frame-owner snapshot cost projection |
| `tools/recovery_evidence_parser.py` | Parse current plain evidence subfolders or legacy ZIP comparisons |

## Navigation Rule

Add a module here only when it is an architectural owner or a critical entry point.

Do not add:

- every implementation file;
- detailed test descriptions;
- benchmark results;
- completed work;
- long provider-specific contracts.

Those belong in focused documents or code.
