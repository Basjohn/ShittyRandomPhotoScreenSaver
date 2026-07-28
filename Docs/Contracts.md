# Contracts

Last updated: 2026-07-28

Fast routing index for SRPSS contracts.

This is not a second `Spec.md`. Find the owner here, then read only the owning code and focused document.

## How to Use

1. Identify the contract family.
2. Read the canonical owner.
3. Read the focused document only when listed.
4. Read `Spec.md` only if stable architecture or product behaviour changes.
5. Apply the relevant section of `Docs/Guardrails.md`.

## Core Runtime Contracts

| Family | Canonical owner | Focused document | Contract |
|---|---|---|---|
| Runtime start/stop and display recreation | `ScreensaverEngine`, `DisplayManager` | `Docs/Compositor_Architecture.md` for render recovery | One ordered runtime lifecycle |
| Fullscreen display presentation | `DisplayWidget` and display-owned compositor | `Docs/Compositor_Architecture.md` | One surface per display; no global display authority |
| Overlay widget lifecycle | `WidgetManager` | `Docs/10_WIDGET_GUIDELINES.md` | One setup/reveal/cleanup authority |
| Thread and task registry | `core/threading/manager.py` | `Docs/Guardrails.md` | Coarse async work; no frame-clock handshakes |
| Qt/native resource tracking | `core/resources/manager.py` plus explicit GL owner | `Docs/Compositor_Architecture.md` | Tracking does not replace context ownership |
| Shared application events | `core/events/event_system.py` | — | Meaningful cross-module events, not frame transport |
| Worker process orchestration | `core/process/supervisor.py` | — | One correlated process-response seam |
| Shared animation timeline | `core/animation/animator.py` | — | Shared animations only; not visualizer simulation |
| Secure-desktop URL/helper handoff | installer task/ACL contract, `core/windows/reddit_helper_bridge.py`, `core/windows/reddit_helper_runtime.py`, and `helpers/reddit_helper_worker.py` | `Docs/Historical_Bugs.md` R-02; active recovery in `Current_Plan.md` | Atomic bounded spool; interactive-only ephemeral helper; saver teardown never waits |

## Rendering and Performance Contracts

| Family | Canonical owner | Focused document | Contract |
|---|---|---|---|
| Compositor architecture | display-owned compositor | `Docs/Compositor_Architecture.md` | Producers publish; compositor consumes |
| Transition identity | `rendering/transition_registry.py` | `Docs/Transition_Change_Checklist.md` | One registry for ids, aliases, gating, and UI |
| Transition progress/completion | transition controller/compositor-local state | `Docs/Compositor_Architecture.md` | Local elapsed-time progress and local finalization |
| Visualizer simulation | visualizer controller/model | `Docs/Visualizer_Reference.md` | Independent logical cadence and mode behaviour |
| Visualizer changes | visualizer subsystem | `Docs/Visualizer_Change_Checklist.md` | Fidelity contract and complete change sweep |
| Visualizer renderer integration | narrow renderer interface | `Docs/Compositor_Architecture.md` | No widget impersonation or paint acknowledgement |
| CPU image pipeline/cache | image pipeline/cache owner | `Docs/Compositor_Architecture.md` | Immutable worker result and byte-bounded storage |
| GPU resource store | explicit GL/context owner | `Docs/Compositor_Architecture.md` | Byte accounting, generation, leases, deletion |
| Performance instrumentation | existing perf/usage modules | `Docs/Logging_Guide.md`, `Docs/TestSuite.md` | Passive sampled observation, never cadence |
| Performance acceptance | benchmark and runtime gates | `Docs/TestSuite.md` | Tail latency and fidelity outrank average FPS |

## Settings and Persistence Contracts

| Family | Canonical owner | Focused document | Contract |
|---|---|---|---|
| Settings read/write/migration | `core/settings/settings_manager.py` | `Docs/Defaults_Guide.md` | One persistence and normalization path |
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
| Steam family | modules under `core/steam/` and Steam widgets | existing Steam focused docs | Core docs route; domain docs own detailed behaviour |

## Validation Contracts

| Family | Canonical document | Contract |
|---|---|---|
| Test levels and release gates | `Docs/TestSuite.md` | Unit, integration, runtime, soak, and manual review |
| Recurring harness commands | `Docs/Harness_Index.md` | Task-specific commands only |
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
