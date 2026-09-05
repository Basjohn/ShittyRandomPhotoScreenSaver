# SRPSS Documentation Index

Last updated: 2026-09-03

## Start here

```text
exact current source
-> Current_Plan.md
-> relevant focused current contract/decomposition
-> tests/evidence for the claim
```

Live migration phase/checkpoint status is intentionally owned only by `Current_Plan.md`.

## Current authority

| Need | Read |
| --- | --- |
| current work / sequence / phase gates | `Current_Plan.md` |
| durable product/architecture | `Spec.md` |
| fast current owner map | `Docs/Contracts.md` |
| Settings theme / Acrylic / Glass architecture | `Docs/Settings_Theme_Architecture.md` |
| runtime Widget Theme / semantic role / linking | `Docs/QtQuick_Migration/Widget_Theme_Implementation_Plan.md` + `Docs/Contracts.md` |
| `dark.qss` retirement execution | `Docs/Settings_Dark_QSS_Retirement.md` |
| physical scene/presenter architecture | `Docs/Compositor_Architecture.md` |
| CUSTOM/edit/input/auxiliary | `Docs/QtQuick_Migration/05_Custom_Layout_Input_Interaction.md` |
| runtime host/lifecycle | `Docs/QtQuick_Migration/01_Runtime_Host_Lifecycle.md` |
| visualizer migration architecture | `Docs/QtQuick_Migration/03_Visualizer.md` |
| visualizer presentation invariant | `Docs/Guardrails/Visualizer_Presentation.md` |
| performance optimization admission / reference envelopes | `Docs/Guardrails/Performance_Optimization_Contract.md` |
| Bubble temporal fidelity | `Docs/Guardrails/Bubble_Temporal_Fidelity.md` |
| visualizer authored/reference behavior | `Docs/Visualizer_Reference.md` |
| Visualizer change checklist / preflight | `Docs/Visualizer_Change_Checklist.md` |
| active Visualizer hitch attribution / optimization | `Docs/QtQuick_Migration/Visualizer_Hitch_Attribution_And_Optimization_Plan_2026-09-03.md` |
| Visualizer mode modularization (V0-V4 landed) + planned V5-V8 Settings rehost | `Docs/QtQuick_Migration/Visualizer_Mode_Modularization_And_Settings_Tab_Decomposition_2026-09-02.md` |
| ordinary widget authoring | `Docs/10_WIDGET_GUIDELINES.md` |
| safety | `Docs/Guardrails.md` |
| test inventory/retirement | `Docs/TestSuite.md` |
| harness/command routing | `Docs/Harness_Index.md` |
| logging / Qt-QML observability | `Docs/Logging_Guide.md` + `Docs/Qt_QML_Observability.md` |
| deferred deletion/debt | `Future_Cleanup.md` |
| deferred features | `Future_Work.md` |
| operator-activated Future Work implementation / live checklists | `FWPlan.md` |
| active Bubble aspect response / bounded presentation-cost diagnosis | `Docs/Future_Work/Bubble_Aspect_And_Presentation_Decomposition.md` |
| active operator-rejected visualizer appearance / Bubble / Sphere repair | `Docs/Future_Work/Visualizer_Visual_Regression_Recovery.md` |
| experimental Sphere ownership, materials and validation | `Docs/Future_Work/Sphere_Visualizer_Decomposition.md` |
| G4 durable scale/extent contract | `Docs/QtQuick_Migration/Remaining_G4_Visualizer_Viewport_Resize_Decomposition.md` |
| G4 post-checkpoint correction playbook | `Docs/QtQuick_Migration/G4_Post_Checkpoint_Audit_Corrections_Decomposition.md` |
| G7/G8 auxiliary/focus implementation route | `Docs/QtQuick_Migration/Remaining_G7_G8_Auxiliary_Focus_Decomposition.md` |
| closed H production-cutover record | `Docs/QtQuick_Migration/Remaining_H_Production_Cutover_Decomposition.md` |
| closed H post-cutover runtime corrections | `Docs/QtQuick_Migration/H_Post_Cutover_Runtime_Reality_Corrections.md` |
| closed H5 Visualizer CUSTOM routing/Spectrum evidence | `Docs/QtQuick_Migration/H5_Visualizer_Routing_And_Spectrum_Decomposition_2026-08-30.md` |
| closed H8 retained visualizer middle-click preset evidence | `Docs/QtQuick_Migration/H8_Visualizer_Middle_Click_Preset_Cycle_Decomposition_2026-08-30.md` |
| Phase H closure / permanent golden guardrails | `Docs/QtQuick_Migration/H_Phase_Closure_2026-09-01.md` |
| closed H visualizer edge audit evidence | `Docs/QtQuick_Migration/H_Pre_Cutover_Visualizer_Edge_Corrections.md` |
| closed True-F technical/retained-consumer evidence | `Docs/QtQuick_Migration/H_True_F_Technical_Closure.md` |
| J final installed/physical acceptance route | `Docs/QtQuick_Migration/Remaining_J_Final_Installed_Acceptance_Decomposition.md` |
| J Parity+ historical visual/interaction floor | `Docs/QtQuick_Migration/J_ParityPlus_Historical_Visual_Interaction_Reference_2026-08-30.md` |
| J runtime-card material supersession / anti-resurrection | `Docs/QtQuick_Migration/J_Runtime_Card_Material_Supersession_2026-09-03.md` + `Docs/Historical_Bugs/Runtime_Card_Backdrop_Materials_Rejected_2026-09-02.md` |
| J black-flash / first-visible-frame surface continuity | `Docs/QtQuick_Migration/J_Black_Flash_Surface_Continuity_Decomposition_2026-08-30.md` |

Reorientation/handoff files are conversation/operator artifacts, not repository architecture. Do not add a current
reorientation file under `Docs/` unless the operator explicitly asks for a repository handoff artifact.

## Runtime observability

Qt Quick acceptance has two first-class log planes: `screensaver.log` and always-on `screensaver_qml.log`. The latter is direct Qt/QML message-handler evidence and must exist even on a zero-message clean run. Read `Docs/Qt_QML_Observability.md` before changing capture lifetime, sidecar semantics or considering an OS-level stderr redirect. Permanent health coverage includes both a fake-handler contract test and a real `QQmlEngine` warning probe (`tests/test_qt_message_capture_qml_runtime.py`).

Physical/J Quick gates are not fully evidenced by the Python log alone.

## Settings themes

`Docs/Settings_Theme_Architecture.md` is the permanent Settings-theme contract. It owns schema-v5 theme semantics,
layered-QWidget native backdrop mapping, Acrylic/Glass division of responsibility, Theme Foundry authoring rules and the
boundary around future `dark.qss` retirement. `Docs/Settings_Dark_QSS_Retirement.md` is the focused execution authority
for removing that legacy stylesheet with zero intended visual/behavior change once `Future_Cleanup.md` admits the work.
Historical Glass investigation is R-61; temporary theme planning notes are not current authority.

## Runtime Widget Themes

`Docs/QtQuick_Migration/Widget_Theme_Implementation_Plan.md` owns the colour-only `.srwtheme`/linking execution plan; `Docs/Contracts.md` and `Docs/Custom_Style_Implementation.md` own the durable precedence/Custom semantics. Schema-v2 specialized widget visuals use `ui/widget_visual_roles.py` as the one sparse semantic inheritance resolver; do not create family-local theme cascades or serialize `local.*` presentation context. `Current_Plan.md` owns which portions are implemented/awaiting validation.

## Closed ordinary-family migration

Phase F F1–F8 is closed. The decomposition remains a reference, not current work admission:
`Docs/QtQuick_Migration/10_Widget_Family_Port_Decomposition.md`.

Steam Journey/Progress and Friend Pulse remain future-product scaffolds; Achievement Pulse and Abandonment Issues are
the two substantive migrated Steam families.

## G / H / I / J

`Current_Plan.md` owns current sequencing. This index deliberately does not mirror completed slice checklists.

Durable roles:

- G owns retained CUSTOM/input/auxiliary/focus destination contracts;
- H is closed: final production Quick owner/orchestration cutover and heavy-load acceptance live in the H closure record;
- residual I-style source/test/tool truth cleanup is now a bounded non-blocking obligation tracked by `Current_Plan.md`, `Future_Cleanup.md` and `Docs/TestSuite.md`, not a reason to repopulate the live plan with old migration sub-slices;
- J owns remaining physical/installed/frozen acceptance and the mandatory post-migration GC/general optimization tranche.

## Transitions

Quick transition architecture is landed. Read `Docs/QtQuick_Migration/02_Scene_Renderer_Transitions.md` and
`Docs/Transition_Change_Checklist.md`. Old compositor transition pixels are migration debris after caller proof, not
new-work visual authority.

## Visualizer

For geometry/CUSTOM work read these together:

- `Docs/QtQuick_Migration/03_Visualizer.md`
- `Docs/Guardrails/Visualizer_Presentation.md`
- `Docs/Guardrails/Performance_Optimization_Contract.md` for any performance-motivated Visualizer/runtime change
- `Docs/Guardrails/Bubble_Temporal_Fidelity.md`
- `Docs/Visualizer_Reference.md`
- `Docs/QtQuick_Migration/Visualizer_Hitch_Attribution_And_Optimization_Plan_2026-09-03.md` for the active P0 hitch evidence/order and Bubble+tall-Spectrum acceptance oracles
- `Docs/QtQuick_Migration/Visualizer_Mode_Modularization_And_Settings_Tab_Decomposition_2026-09-02.md` for the planned per-mode activation/dormancy + dedicated Visualizers tab work
- `Docs/QtQuick_Migration/Remaining_G4_Visualizer_Viewport_Resize_Decomposition.md`
- `Docs/QtQuick_Migration/G4_Post_Checkpoint_Audit_Corrections_Decomposition.md` for the bounded G4 correction record
- `Docs/QtQuick_Migration/H5_Visualizer_Routing_And_Spectrum_Decomposition_2026-08-30.md` for closed H CUSTOM route evidence

For historical H visualizer-edge reasoning only, use the closed
`H_Pre_Cutover_Visualizer_Edge_Corrections.md` + `H_True_F_Technical_Closure.md` pair. They are evidence, not active work
admission. `Remaining_H_Production_Cutover_Decomposition.md` is the durable closed cutover record; Phase I is closed and surviving residue/deletion work lives only in `Current_Plan.md` / `Future_Cleanup.md` / `Docs/TestSuite.md`.

The all-five-mode capability policy is landed. Do not reintroduce a Bubble false gate to avoid correcting viewport
ownership or spatial-domain defects.

Bubble's durable reflow contract is routed through `Spec.md`, `Docs/Visualizer_Reference.md`, `Docs/Guardrails/Bubble_Temporal_Fidelity.md` and R-69: expanded-world positions/trails remain distinct from the historical card-height-normalized render radius, whose collision/spawn mapping is explicitly converted back into world units. Never restore a viewport-dependent global head/Ghost compressor to make extreme geometry look smaller.

## Historical evidence

Closed rationale and old owner maps belong under `Docs/Historical_Plans/`, `Docs/Historical_Bugs/`,
`Docs/phase_reports/`, `Docs/Performance_Evidence/`, or `Docs/audits/`. Historical wording does not define current work
admission or ownership and is not rewritten merely to sound current.

- `Docs/Tooling_Audit_2026-09-01.md` — stable route to the **2026-09-03 re-audited** current operator-tool keep/temporary/J-exit authority; R-72 production/tool boundary.

- `Docs/Historical_Bugs/R-73_Quick_Card_Shadow_Extra_Offset_Translation_And_Visualizer_Omission.md` — frame Extra Offset is directional growth, and Visualizer joins global card-shadow ownership.
- `Docs/Historical_Bugs/Runtime_Card_Backdrop_Materials_Rejected_2026-09-02.md` — runtime Glass/Acrylic card backdrops are explicitly rejected; Settings-window native materials remain separate.

- `Docs/Future_Work/Visualizer_Edit_Geometry_And_Sphere_Materials.md` — active all-mode Edit Layout geometry and Sphere material expansion.
