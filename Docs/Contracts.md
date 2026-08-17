# Contracts

Last updated: 2026-08-15

Fast routing index for SRPSS contracts.

This is not a second `Spec.md`. Find the owner here, then read only the owning code and
focused document.

## How to Use

1. Identify the contract family.
2. Read the canonical owner.
3. Read the focused document only when listed.
4. **Read that focused document's prohibition/forbidden list before proposing a mechanism.**
   A general allowance in `Docs/Guardrails.md` or `Spec.md` does not override a specific
   prohibition in the focused document. If you believe a forbidden item does not apply, quote
   it and say why, in the same record that proposes the mechanism.
5. Read `Spec.md` only if stable architecture or product behaviour changes.
6. Apply the relevant section of `Docs/Guardrails.md`.

## Core Runtime Contracts

| Family | Canonical owner | Focused document | Contract |
|---|---|---|---|
| Runtime start/stop and display recreation | `ScreensaverEngine`, `DisplayManager` | `Docs/Compositor_Architecture.md` | One ordered runtime lifecycle |
| Fullscreen display presentation | `DisplayWidget` and display-owned compositor | `Docs/Compositor_Architecture.md` | One surface per display; no global display authority |
| Overlay widget lifecycle | `WidgetManager` | `Docs/10_WIDGET_GUIDELINES.md` | One setup/reveal/cleanup authority |
| Thread and task registry | `core/threading/manager.py` | `Docs/Guardrails.md` | Coarse async work; no frame-clock handshakes |
| Qt/native resource tracking | `core/resources/manager.py` plus explicit GL owner | `Docs/Compositor_Architecture.md` | Tracking does not replace context ownership |
| Shared application events | `core/events/event_system.py` | — | Meaningful cross-module events, not frame transport |
| External media-command ingress | `rendering/media_command_ingress.py` feeding centralized Qt/native input routes | `Docs/10_WIDGET_GUIDELINES.md` | One process-wide claim; OS pass-through preserved; one local feedback/refresh/wake path |
| Worker process orchestration | `core/process/supervisor.py` | `Docs/phase_reports/P04_MEMORY_VRAM_CONTAINMENT.md` | One correlated process-response seam; payload-aware late/cancel/shutdown disposal |
| Image shared-memory transport | `core/process/shared_memory_transport.py` plus `core/process/workers/image_worker.py` | `Docs/phase_reports/P04_RESOURCE_LIFETIME_MAP.md` | One bounded attachment handoff; parent consumes/unlinks; exact live-byte accounting |
| Shared animation timeline | `core/animation/animator.py` | — | Shared animations only; not visualizer simulation |
| Secure-desktop URL/helper handoff | installer task/ACL contract, `core/windows/reddit_helper_bridge.py`, `core/windows/reddit_helper_runtime.py`, `helpers/reddit_helper_worker.py` | `Docs/Historical_Bugs.md` R-02 | Atomic bounded spool; interactive-only ephemeral helper; saver teardown never waits |
| Logging ingress/routing/persistence | `core/logging/logger.py`, `core/logging/tags.py` | `Docs/Logging_Guide.md` | One bounded writer; persistent sinks before optional console; every WARNING+ main-visible |
| Fatal/native diagnostic breadcrumbs | `core/logging/crash_capture.py` | `Docs/Logging_Guide.md` | Direct bounded crash evidence independent of the normal queue |
| Build/release orchestration | `tools/build_runner.py`, `tools/build_layout.ps1`, mode-specific workers under `scripts/` | `Docs/Harness_Index.md` Build Foundry section | One runner; sequential workers; isolated release products; Diagnostic is opt-in |

## Rendering and Performance Contracts

| Family | Canonical owner | Focused document | Contract |
|---|---|---|---|
| Compositor architecture | display-owned compositor | `Docs/Compositor_Architecture.md` | Producers publish; compositor consumes |
| Transition identity | `rendering/transition_registry.py` | `Docs/Transition_Change_Checklist.md` | One registry for ids, aliases, gating, and UI |
| Transition progress/completion | transition controller/compositor-local state | `Docs/Compositor_Architecture.md` | Local elapsed-time progress and local finalization |
| Startup overlay reveal and optional GL warmup | `rendering/fade_coordinator.py`, `rendering/widget_manager.py`, `rendering/gl_compositor_pkg/gl_lifecycle.py` | `Docs/Compositor_Architecture.md` | Critical named holds; real fade completion; one deferred item per idle slice |
| Visualizer simulation | visualizer controller/model | `Docs/Visualizer_Reference.md` | Independent logical cadence and mode behaviour |
| Visualizer changes | visualizer subsystem | `Docs/Visualizer_Change_Checklist.md` | Fidelity contract and complete change sweep |
| Visualizer cadence/presentation/repaint | visualizer tick owner plus display presentation | `Docs/Presentation_Change_Preflight.md` | One cadence authority; one repaint request per accepted payload (R-27); presentation source must be live whenever the visualizer is |
| Visualizer renderer integration | narrow renderer interface | `Docs/Compositor_Architecture.md` | No widget impersonation or paint acknowledgement |
| Passive GL timing attribution | context-owning renderer plus `rendering/gl_timer_queries.py` | `Docs/Harness_Index.md` | Fixed non-blocking query ring; explicit support/sample state; exact owner-context deletion; never cadence |
| CPU image pipeline/cache | image pipeline/cache owner plus transfer-scoped ImageWorker shared memory | `Docs/Compositor_Architecture.md` | Immutable worker result, one Qt-owned copy, byte-bounded storage, no retained transport mapping |
| GPU resource store | explicit GL/context owner | `Docs/Compositor_Architecture.md` | Byte accounting, generation, leases, deletion |
| Performance instrumentation | existing perf/usage modules | `Docs/Logging_Guide.md`, `Docs/TestSuite.md` | Passive sampled observation, never cadence |
| Performance acceptance | benchmark and runtime gates | `Docs/TestSuite.md` | Tail latency and fidelity outrank average FPS |

## Settings and Persistence Contracts

| Family | Canonical owner | Focused document | Contract |
|---|---|---|---|
| Settings read/write/migration | `core/settings/settings_manager.py` | `Docs/Defaults_Guide.md` | One persistence and normalization path |
| Ordered settings durability | `core/settings/persistence.py`, `core/settings/json_store.py` | `Docs/Defaults_Guide.md` | Process-scoped revisioned writer with explicit flush boundaries |
| Canonical defaults | defaults modules under `core/settings/` | `Docs/Defaults_Guide.md` | Normal base plus explicit profile differences |
| Visualizer settings model | `core/settings/models/_spotify_visualizer.py` | `Docs/Visualizer_Reference.md` | One grouped model and serializer |
| Visualizer mode identity | `core/settings/visualizer_mode_registry.py` | `Docs/Visualizer_Reference.md` | Stable ids and labels |
| Visualizer preset activation | `core/settings/visualizer_presets.py` and activation seam | `Docs/Visualizer_Reference.md` | One resolved activation payload |
| Storage paths | `core/settings/storage_paths.py` | `Docs/Defaults_Guide.md` | No ad hoc machine paths |
| Credentials | provider-specific credential modules | provider focused docs | Credentials never become ordinary settings/export data |

## Widgets and Layout Contracts

| Family | Canonical owner | Focused document | Contract |
|---|---|---|---|
| Widget metadata | `rendering/widget_descriptors.py` | `Docs/10_WIDGET_GUIDELINES.md` | One descriptor source |
| Widget setup | `rendering/widget_setup_all.py` | `Docs/10_WIDGET_GUIDELINES.md` | One setup authority |
| Widget positioning | existing position/stacking owners | `Docs/10_WIDGET_GUIDELINES.md` | One authored positioning path |
| CUSTOM layout storage and apply | existing CUSTOM layout contract/manager | `Docs/10_WIDGET_GUIDELINES.md` | Display-bounded, descriptor-capability-driven |
| Service-widget shared lifecycle | existing service runtime helper | `Docs/10_WIDGET_GUIDELINES.md` | Shared mechanics only; provider behaviour local |
| Shared overlay painted-frame cache | `widgets/base_overlay_widget.py` | `Docs/10_WIDGET_GUIDELINES.md`, `Docs/audits/SRPSS_Architecture_Roadmap/08_CPU_THREADING_AND_WORKLOAD_PLAN.md` | GUI-owned exact size/DPR/style/revision preparation at state commits; paint validates and blits only |
| Reddit fetch/preparation/commit | `core/reddit_post_provider.py`, `core/reddit_preparation.py`, `widgets/reddit_widget.py` | roadmap CPU/workload plan | Provider/network and detached cache preparation on shared IO; Qt-visible commit on GUI |
| Weather fetch/preparation/commit | `weather/open_meteo_provider.py`, `core/weather_preparation.py`, `widgets/weather_widget.py` | roadmap CPU/workload plan | Startup/provider I/O and atomic persistence on shared IO; immutable result publication; Qt-visible commit on GUI |
| Gmail cache/backend preparation/commit | `core/gmail/gmail_preparation.py`, `core/gmail/gmail_bootstrap.py`, `core/gmail/gmail_backend.py`, `core/gmail/gmail_oauth.py`, `widgets/gmail_widget.py` | roadmap CPU/workload plan | Shared-IO preparation; GUI-affine authority; request/revision-gated visible commit |
| Media artwork/progress preparation and presentation | `widgets/media_widget.py`, `widgets/media/display_update.py`, `widgets/media/painting.py`, `rendering/display_widget.py` | `Docs/10_WIDGET_GUIDELINES.md`, `Spec.md` | Worker QImage decode; GUI QPixmap handoff; transition deferral; progress consumes existing GSMTC snapshot |
| Media provider identity, GSMTC selection and app-volume routing | `core/media/provider_registry.py`, `core/media/media_controller.py`, `core/media/spotify_volume.py`, media widgets | `Spec.md` | Exact source ids; one background session snapshot; unsupported ids inert; exact-browser fallback |
| Steam family | modules under `core/steam/` and Steam widgets | existing Steam focused docs | Core docs route; domain docs own detailed behaviour |

## Validation Contracts

| Family | Canonical document/owner | Contract |
|---|---|---|
| Test levels and release gates | `Docs/TestSuite.md` | Unit, integration, runtime, soak, and manual review |
| Recurring harness commands | `Docs/Harness_Index.md` | Task-specific commands only |
| Evidence parser | `tools/recovery_evidence_parser.py` | Read-only; rotations/time range preserved; human main-log presentation normalized without changing canonical sidecar semantics |
| Historical regression lessons | `Docs/Historical_Bugs.md` | Dated evidence, not current architecture |
| Active work | `Current_Plan.md` | Unfinished checklist only |
| Documentation drift | `Docs/Documentation_Maintenance.md` | One truth per document role |

## Contract Change Rule

A contract change must update:

1. the canonical owner;
2. the focused document;
3. `Spec.md` only if stable architecture changes;
4. `Index.md` only if ownership/navigation changes;
5. tests/harness references;
6. `Current_Plan.md` only while work remains active.

Do not duplicate the full rule across all documents.
