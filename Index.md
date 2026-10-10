# SRPSS Documentation Index

## Start here

```text
exact current source
-> Current_Plan.md
-> Spec.md / Docs/Contracts.md
-> relevant Architecture / Guardrail / Guide / Reference / Future Work document
-> tests + physical evidence for the claim
```

`Current_Plan.md` owns current work admission and sequence. `Spec.md` owns durable product/architecture. `Docs/Historical_Bugs.md` is the sole historical index; incident narratives live in `Docs/Historical_Bugs/` (older audit snapshots elsewhere are not current authority) (the legacy `Docs/Fossils/` described outdated architecture and is retired; source control keeps it). Ordinary chronology and retired decompositions belong in source control rather than the live docs tree.

## Current product and regression references

- `Current_Plan.md` contains the next actionable checklist; accepted Sphere/Shockwave DSP and R151 cache/Settings work are not implementation queues.
- `Docs/Reference/Steam_Games_You_Follow.md` and `Docs/Reference/System_Volume_OSD.md` describe the current product contracts. `Future_Work.md` routes deferred feature ideas, not completed products.
- `Docs/Historical_Bugs/R-88_QtQuick_Custom_Edit_Paint_Role_Churn_And_False_Test_Oracles.md` records durable Edit paint/role and test-oracle failures; use the live source and targeted tests for any new defect.

Local-repo transition concept mock references currently used by the plan live under `tmp/mocks/` in the checked-out repository (for example `TBlockPuzzle.png`, `TVolu.png`, `TVHS.png`, `TLens.png`, `TMemb.png`, `TGroup.png`). They are visual review artifacts, not separate product authorities, and are intentionally not treated as normal GODZIP handoff payload.

## Directory roles

| Location | Role |
| --- | --- |
| `Docs/Architecture/` | durable architecture and subsystem ownership |
| `Docs/Guardrails/` | binding invariants and preflight contracts |
| `Docs/Guides/` | maintained authoring/change procedures |
| `Docs/Reference/` | current lookup/reference material and harness routing |
| `Docs/Historical_Bugs/` | permanent regression/root-cause/failed-method evidence |

Keep the small routing authorities at `Docs/` root: project overview, current owner map, guardrail router, Historical Bugs router and TestSuite.

`.godzip/CHECKPOINT_HANDOFF.md` and `.godzip/CHECKPOINT_LIVE_CHECKLIST.md` are untracked checkpoint orientation and open acceptance evidence, **not** competing architecture, product, persistence, or test authorities. Reconcile them against the current source, `Current_Plan.md`, `Docs/Contracts.md` and `Docs/TestSuite.md`.

## Current authority routing

| Need | Read |
| --- | --- |
| current work / next sequence | `Current_Plan.md` |
| R151 Steam cache publication and Settings UTC: **106 focused Windows tests accepted**, full rerun not requested | `Docs/Historical_Bugs/R-151_Steam_Cache_Windows_Publication_Race_And_Python314_Timestamps.md` |
| R149 Python 3.14 full-test failures, Steam cache WinError 32, NumPy BLAS introspection and 35-minute runtime review | `Docs/Contracts.md` |
| R134–R145 dual-display collapse, reboot-dependent recovery and pre/post performance/cache/handles investigation | `Docs/Historical_Bugs/R-134_to_R-145_Dual_Display_Reboot_Recovery.md` |
| Python 3.14 active MSVC/frozen-product gate (operator runs builds and returns logs) | `Current_Plan.md` §0; `Docs/Guides/Python314_Cutover.md` |
| durable product / architecture | `Spec.md` |
| fast current owner map | `Docs/Contracts.md` |
| project overview | `Docs/00_PROJECT_OVERVIEW.md` |
| runtime presentation architecture | `Docs/Architecture/Compositor_Architecture.md` |
| Qt/OpenGL production floor | `Spec.md` → Accepted runtime presentation; `rendering/quick/bootstrap.py` |
| Settings theme / Acrylic / Glass / Theme Foundry | `Docs/Architecture/Settings_Theme_Architecture.md` |
| runtime Widget Theme / style override ownership | `Docs/Guides/Custom_Style_Implementation.md` |
| safety / guardrail router | `Docs/Guardrails.md` |
| performance admission / reopen rules | `Docs/Guardrails/Performance_Optimization_Contract.md` |
| wallpaper cache, speculative source batches and image-worker ownership | `Docs/Contracts.md` → Wallpaper image cache and prefetch |
| accepted Standard/MC Ban Image and matching-run frozen-build evidence | `Docs/Guides/Python314_Cutover.md`; `Docs/Guides/Python314_Cutover.md` |
| persisted Ban Image identity, zero-ban cost and explicit Clear | `Spec.md` → Persistent Ban Image admission; `Docs/Contracts.md` → Actions / images |
| image filters, Lanczos cost, quality migration and measurements | `Docs/Reference/Image_Quality.md` |
| Build Runner cancellation and supported products | `Spec.md` → Build control and products |
| operator-only build execution / canonical Python 3.14 workers | `Current_Plan.md` §0; `Docs/Guides/Python314_Cutover.md` |
| immutable Qt resources, editable assets and automatic regeneration | `Spec.md` → Settings themes / native backdrop; `Docs/Guides/10_WIDGET_GUIDELINES.md` → asset ownership |
| presentation/cadence renderer preflight | `Docs/Guardrails/Presentation_Change_Preflight.md` |
| Visualizer presentation invariants | `Docs/Guardrails/Visualizer_Presentation.md` |
| Bubble temporal fidelity | `Docs/Guardrails/Bubble_Temporal_Fidelity.md` |
| Bubble drawn-radius release and remaining judder evidence | `Current_Plan.md` §5; `Docs/Historical_Bugs/R-105_Bubble_Remaining_Small_Radius_Judder.md`; `Docs/Reference/Harness_Index.md` |
| ordinary widget authoring | `Docs/Guides/10_WIDGET_GUIDELINES.md` |
| ordinary CUSTOM geometry, Edit-only keyboard controls and reset | `Docs/Guides/Custom_Child_Geometry.md` and `Docs/Guides/Custom_Child_Placement_And_Headers.md` |
| R154 display-owner retirement callback; historical diagnostic preset collision, superseded by R155 unified runtime root | `Docs/Historical_Bugs/R-154_Quick_Display_Terminal_Callback_And_Sphere_Slot_Collision.md` |
| R156 missing Diagnostic frame-trace evidence; native Windows CLI admission and writer-failure receipts | `Docs/Guides/Qt_QML_Observability.md`; `Current_Plan.md` §1A |
| R155 cross-display Media shortcuts and compiled Diagnostic shared preset authority | `Docs/Guardrails/Visualizer_Presentation.md`; `Spec.md` → Media transport / Visualizer preset catalogue |
| stable display identity, saved CUSTOM replay and Clock face overrides | `Spec.md` → Geometry / CUSTOM; `Docs/Architecture/Persisted_Input_Compatibility.md` |
| current source/Qt/physical proof for CUSTOM changes | `Docs/TestSuite.md` → Shared paint/Edit parity acceptance; `Current_Plan.md` for newly opened gates |
| Visualizer planar/freeform CUSTOM geometry split and hot-swap contract | `Docs/Contracts.md`; `Spec.md` → Visualizer geometry; `Docs/Guides/Visualizer_Change_Checklist.md` §7A |
| Visualizer change preflight | `Docs/Guides/Visualizer_Change_Checklist.md` |
| Visualizer reactivity authoring | `Docs/Guides/Visualizer_Reactivity_Authoring.md` |
| Visualizer current reference | `Docs/Reference/Visualizer_Reference.md` |
| transitions and material surfaces (reference-owned acceptance conditions); active transition expansion order and local mock references | `Docs/Reference/Transitions.md`, `Docs/Guides/Transition_Change_Checklist.md` and `Current_Plan.md` §2 |
| active 3D scene foundation plan / live slices | `Current_Plan.md` |
| Usu character authoring source and static review renders | local checkout `assets/usu/README.md` (excluded from normal Godzip); media source guidance in `Current_Plan.md` §3 |
| shared 3D resource ownership, DSA, immutable storage and state restoration | `Docs/Reference/Scene3D_Resources.md` |
| runtime audit 2026-09-22 outcomes and rejected ideas (closed) | `Docs/Guardrails/Performance_Optimization_Contract.md` |
| current FEEDS architecture, invariants and open physical acceptance | `Docs/Reference/Feeds.md` |
| defaults | `Docs/Guides/Defaults_Guide.md` |
| Guided Setup / Quick Start / Settings Arrange | `Docs/Reference/Guided_Setup.md` (open physical acceptance at its end) |
| logging / Qt-QML observability | `Docs/Guides/Logging_Guide.md` + `Docs/Guides/Qt_QML_Observability.md` |
| documentation maintenance | `Docs/Guides/Documentation_Maintenance.md` |
| test inventory / acceptance authority | `Docs/TestSuite.md` |
| durable test authoring / mutable-authority hygiene | `Docs/Guides/Test_Durability.md` |
| harness commands | `Docs/Reference/Harness_Index.md` |
| bounded self-terminating RUN / repeated startup-teardown acceptance | `Docs/Reference/Harness_Index.md` → Bounded self-terminating RUN sessions (`main_mc.py`, `tools/run_matrix.py`, `--exit-after`) |
| Steam source/auth/privacy contract | `Docs/Reference/Steam_Source_Contracts.md` |
| Friend Pulse current contract | `Docs/Reference/Steam_Friend_Pulse.md` |
| System Stats current contract | `Docs/Reference/System_Stats_Widget.md` |
| Sphere standard-mode contract, analysis-only DSP and accepted Shockwave-shaped horizon | `Docs/Reference/Sphere_Visualizer.md`; `Docs/Historical_Bugs/R-150_Sphere_Analysis_Only_Shockwave_Shaper_Audit.md` |
| historical bug / rejected-method routing | `Docs/Historical_Bugs.md` (sole index) |
| compatibility / schema-migration bridges | `Docs/Architecture/Persisted_Input_Compatibility.md` |
| deferred features / long-horizon graphics and Visualizer ideas | `Future_Work.md` |
| Usu Moonscape vertical: behaviour, reactivity, required 3D architecture (S19–S27), asset gates | `Docs/Future_Work/Usu_Moonscape.md` |
| Usu Blender work: previewing Usu, rig/clip fixes, missing clips, bake/export preparation | `Docs/Future_Work/Usu_Blender_Work.md` |
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

Do not add another inventory/changelog/history layer. Closed decompositions are consolidated into current contracts or Historical Bugs and then deleted from the live docs tree. Extensible catalogs are registry-owned: live docs and harnesses say "every registered mode" / "canonical transition registry" rather than freezing today's membership count into prose. Persisted-input compatibility bridges are documented as architecture in `Docs/Architecture/Persisted_Input_Compatibility.md` (user-data protection, horizon-gated — not a backlog); caller-dead residue is deleted outright, not tracked in a register. When paths move, update this router and all live cross-references in the same change.
