# SRPSS Documentation Index

Last updated: 2026-09-16

## Start here

```text
exact current source
-> Current_Plan.md
-> Spec.md / Docs/Contracts.md
-> relevant Architecture / Guardrail / Guide / Reference / Future Work document
-> tests + physical evidence for the claim
```

`Current_Plan.md` owns current work admission and sequence. `Spec.md` owns durable product/architecture. `Docs/Historical_Bugs/` is the only intentional historical-document collection; ordinary chronology and retired decompositions belong in source control rather than the live docs tree.

## Directory roles

| Location | Role |
| --- | --- |
| `Docs/Architecture/` | durable architecture and subsystem ownership |
| `Docs/Guardrails/` | binding invariants and preflight contracts |
| `Docs/Guides/` | maintained authoring/change procedures |
| `Docs/Reference/` | current lookup/reference material and harness routing |
| `Docs/Future_Work/` | genuinely pending or operator-activated implementation plans |
| `Docs/Historical_Bugs/` | permanent regression/root-cause/failed-method evidence |

Keep the small routing authorities at `Docs/` root: project overview, current owner map, guardrail router, Historical Bugs router and TestSuite. The `.sst` files are generated/default evidence rather than prose documentation.

## Current authority routing

| Need | Read |
| --- | --- |
| current work / next sequence | `Current_Plan.md` |
| durable product / architecture | `Spec.md` |
| fast current owner map | `Docs/Contracts.md` |
| project overview | `Docs/00_PROJECT_OVERVIEW.md` |
| runtime presentation architecture | `Docs/Architecture/Compositor_Architecture.md` |
| Settings theme / Acrylic / Glass / Theme Foundry | `Docs/Architecture/Settings_Theme_Architecture.md` |
| safety / guardrail router | `Docs/Guardrails.md` |
| performance admission / reopen rules | `Docs/Guardrails/Performance_Optimization_Contract.md` |
| Visualizer presentation invariants | `Docs/Guardrails/Visualizer_Presentation.md` |
| Bubble temporal fidelity | `Docs/Guardrails/Bubble_Temporal_Fidelity.md` |
| ordinary widget authoring | `Docs/Guides/10_WIDGET_GUIDELINES.md` |
| Visualizer change preflight | `Docs/Guides/Visualizer_Change_Checklist.md` |
| Visualizer reactivity authoring | `Docs/Guides/Visualizer_Reactivity_Authoring.md` |
| Visualizer current reference | `Docs/Reference/Visualizer_Reference.md` |
| transitions | `Docs/Guides/Transition_Change_Checklist.md` |
| defaults | `Docs/Guides/Defaults_Guide.md` |
| logging / Qt-QML observability | `Docs/Guides/Logging_Guide.md` + `Docs/Guides/Qt_QML_Observability.md` |
| documentation maintenance | `Docs/Guides/Documentation_Maintenance.md` |
| test inventory / retirement | `Docs/TestSuite.md` |
| harness commands | `Docs/Reference/Harness_Index.md` |
| Friend Pulse current contract | `Docs/Reference/Steam_Friend_Pulse.md` |
| System Stats current contract | `Docs/Reference/System_Stats_Widget.md` |
| Sphere current experimental contract | `Docs/Reference/Sphere_Visualizer.md` |
| historical bug / rejected-method routing | `Docs/Historical_Bugs.md` then `Docs/Historical_Bugs/README.md` |
| cleanup / compatibility / schema-migration debt | `Future_Cleanup.md` |
| broad deferred features | `Future_Work.md` |
| dormant future ordering | `FWPlan.md` |

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

Do not add another inventory/changelog/history layer. Closed decompositions are consolidated into current contracts or Historical Bugs and then deleted from the live docs tree. `Future_Cleanup.md` is the single forward ledger for real compatibility/schema-migration debt as well as caller-dead cleanup. When paths move, update this router and all live cross-references in the same checkpoint.
