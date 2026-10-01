# SRPSS Documentation Index

## Start here

```text
exact current source
-> Current_Plan.md
-> Spec.md / Docs/Contracts.md
-> relevant Architecture / Guardrail / Guide / Reference / Future Work document
-> tests + physical evidence for the claim
```

`Current_Plan.md` owns current work admission and sequence. `Spec.md` owns durable product/architecture. `Docs/Historical_Bugs/` is the maintained historical authority; there is no other history folder (the legacy `Docs/Fossils/` described outdated architecture and is retired; source control keeps it). Ordinary chronology and retired decompositions belong in source control rather than the live docs tree.

## Current product and regression references

- `Current_Plan.md` contains only active work; closed Games You Follow and OSD work is not an implementation queue.
- `Docs/Reference/Steam_Games_You_Follow.md` and `Docs/Reference/System_Volume_OSD.md` describe the current product contracts. `Future_Work.md` routes deferred feature ideas, not completed products.
- `Docs/Historical_Bugs/R-88_QtQuick_Custom_Edit_Paint_Role_Churn_And_False_Test_Oracles.md` records durable Edit paint/role and test-oracle failures; use the live source and targeted tests for any new defect.

## Directory roles

| Location | Role |
| --- | --- |
| `Docs/Architecture/` | durable architecture and subsystem ownership |
| `Docs/Guardrails/` | binding invariants and preflight contracts |
| `Docs/Guides/` | maintained authoring/change procedures |
| `Docs/Reference/` | current lookup/reference material and harness routing |
| `Docs/Future_Work/` | a focused decomposition for promoted, architecturally large work, created only when needed (currently `3D_Scene_Foundation.md`; implemented plans are historicalised) |
| `Docs/Historical_Bugs/` | permanent regression/root-cause/failed-method evidence |

Keep the small routing authorities at `Docs/` root: project overview, current owner map, guardrail router, Historical Bugs router and TestSuite.

`.godzip/CHECKPOINT_HANDOFF.md` and `.godzip/CHECKPOINT_LIVE_CHECKLIST.md` are untracked checkpoint orientation and open acceptance evidence, **not** competing architecture, product, persistence, or test authorities. Reconcile them against the current source, `Current_Plan.md`, `Docs/Contracts.md` and `Docs/TestSuite.md`.

## Current authority routing

| Need | Read |
| --- | --- |
| current work / next sequence | `Current_Plan.md` |
| durable product / architecture | `Spec.md` |
| fast current owner map | `Docs/Contracts.md` |
| project overview | `Docs/00_PROJECT_OVERVIEW.md` |
| runtime presentation architecture | `Docs/Architecture/Compositor_Architecture.md` |
| Qt/OpenGL production floor | `Spec.md` → Accepted runtime presentation; `rendering/quick/bootstrap.py` |
| Settings theme / Acrylic / Glass / Theme Foundry | `Docs/Architecture/Settings_Theme_Architecture.md` |
| safety / guardrail router | `Docs/Guardrails.md` |
| performance admission / reopen rules | `Docs/Guardrails/Performance_Optimization_Contract.md` |
| wallpaper cache, speculative source batches and image-worker ownership | `Docs/Contracts.md` → Wallpaper image cache and prefetch |
| image filters, Lanczos cost, quality migration and measurements | `Docs/Reference/Image_Quality.md` |
| Build Runner cancellation and supported products | `Spec.md` → Build control and products |
| immutable Qt resources, editable assets and automatic regeneration | `Spec.md` → Settings themes / native backdrop; `Docs/Guides/10_WIDGET_GUIDELINES.md` → asset ownership |
| Visualizer presentation invariants | `Docs/Guardrails/Visualizer_Presentation.md` |
| Bubble temporal fidelity | `Docs/Guardrails/Bubble_Temporal_Fidelity.md` |
| ordinary widget authoring | `Docs/Guides/10_WIDGET_GUIDELINES.md` |
| ordinary CUSTOM geometry, Edit-only keyboard controls and reset | `Docs/Guides/Custom_Child_Geometry.md` and `Docs/Guides/Custom_Child_Placement_And_Headers.md` |
| stable display identity, saved CUSTOM replay and Clock face overrides | `Spec.md` → Geometry / CUSTOM; `Docs/Architecture/Persisted_Input_Compatibility.md` |
| current source/Qt/physical proof for CUSTOM changes | `Docs/TestSuite.md` → Shared paint/Edit parity acceptance; `Current_Plan.md` for newly opened gates |
| Visualizer change preflight | `Docs/Guides/Visualizer_Change_Checklist.md` |
| Visualizer reactivity authoring | `Docs/Guides/Visualizer_Reactivity_Authoring.md` |
| Visualizer current reference | `Docs/Reference/Visualizer_Reference.md` |
| transitions and material surfaces (open physical acceptance at the end of the reference) | `Docs/Reference/Transitions.md` and `Docs/Guides/Transition_Change_Checklist.md` |
| 3D scene foundation plan (slices, risks, performance hazards) | `Docs/Future_Work/3D_Scene_Foundation.md` |
| shared 3D resource ownership, DSA, immutable storage and state restoration | `Docs/Reference/Scene3D_Resources.md` |
| runtime audit 2026-09-22 outcomes and rejected ideas (closed) | `Docs/Historical_Bugs/R-100_Runtime_Audit_2026-09-22_Outcomes_And_Rejections.md` |
| current FEEDS architecture, invariants and open physical acceptance | `Docs/Reference/Feeds.md` |
| defaults | `Docs/Guides/Defaults_Guide.md` |
| Guided Setup / Quick Start / Settings Arrange | `Docs/Reference/Guided_Setup.md` (open physical acceptance at its end) |
| logging / Qt-QML observability | `Docs/Guides/Logging_Guide.md` + `Docs/Guides/Qt_QML_Observability.md` |
| documentation maintenance | `Docs/Guides/Documentation_Maintenance.md` |
| test inventory / retirement | `Docs/TestSuite.md` |
| harness commands | `Docs/Reference/Harness_Index.md` |
| Friend Pulse current contract | `Docs/Reference/Steam_Friend_Pulse.md` |
| System Stats current contract | `Docs/Reference/System_Stats_Widget.md` |
| Sphere current experimental contract | `Docs/Reference/Sphere_Visualizer.md` |
| historical bug / rejected-method routing | `Docs/Historical_Bugs.md` then `Docs/Historical_Bugs/README.md` |
| compatibility / schema-migration bridges | `Docs/Architecture/Persisted_Input_Compatibility.md` |
| deferred features, 3D transition/Visualizer ideas and their admission rules | `Future_Work.md` |
| Games You Follow product/source/CUSTOM | `Docs/Reference/Steam_Games_You_Follow.md` |
| system master-volume OSD | `Docs/Reference/System_Volume_OSD.md` |

## Performance/freshness baseline

CHK26 / repository commit `a0bf70932c` is the current operator-accepted GOLDEN performance/freshness baseline. CHK23 is the immediately prior GOLDEN rollback/bisect landmark and CHK15 / `0abc479c52` is the older pre-retained-background baseline.

The generic headroom campaign is closed. CHK27-CHK29 retained useful `--frame-trace` observability and proved that the largest remaining scheduler-shaped residuals are Qt frame/render-phase ownership or small distributed Bubble/driver costs rather than another obvious local hotspot. Reopen performance work only from a concrete reproduced symptom. The complete chronology and false trails live in `Docs/Historical_Bugs/R-87_QtQuick_HighRefresh_Freshness_And_Scheduler_Regression.md`.

## Visualizer read order

For a new mode or meaningful reactivity change, read:

1. `Docs/Guides/Visualizer_Reactivity_Authoring.md`;
2. `Docs/Guides/Visualizer_Change_Checklist.md`;
3. `Docs/Guardrails/Visualizer_Presentation.md`;
4. `Docs/Guardrails/Bubble_Temporal_Fidelity.md` when Bubble/shared timing could be affected;
5. `Docs/Reference/Visualizer_Reference.md`;
6. relevant Historical Bug negative controls.

Any production change that touches Bubble reaction/timing requires active-music physical acceptance; idle-only evidence is not sufficient.

## Documentation hygiene

Do not add another inventory/changelog/history layer. Closed decompositions are consolidated into current contracts or Historical Bugs and then deleted from the live docs tree. Persisted-input compatibility bridges are documented as architecture in `Docs/Architecture/Persisted_Input_Compatibility.md` (user-data protection, horizon-gated — not a backlog); caller-dead residue is deleted outright, not tracked in a register. When paths move, update this router and all live cross-references in the same change.
