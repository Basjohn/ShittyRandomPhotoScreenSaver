# SRPSS Documentation Index

Last updated: 2026-08-30

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
| `dark.qss` retirement execution | `Docs/Settings_Dark_QSS_Retirement.md` |
| physical scene/presenter architecture | `Docs/Compositor_Architecture.md` |
| CUSTOM/edit/input/auxiliary | `Docs/QtQuick_Migration/05_Custom_Layout_Input_Interaction.md` |
| runtime host/lifecycle/H | `Docs/QtQuick_Migration/01_Runtime_Host_Lifecycle.md` |
| visualizer migration architecture | `Docs/QtQuick_Migration/03_Visualizer.md` |
| visualizer presentation invariant | `Docs/Guardrails/Visualizer_Presentation.md` |
| Bubble temporal fidelity | `Docs/Guardrails/Bubble_Temporal_Fidelity.md` |
| visualizer authored/reference behavior | `Docs/Visualizer_Reference.md` |
| ordinary widget authoring | `Docs/10_WIDGET_GUIDELINES.md` |
| safety | `Docs/Guardrails.md` |
| test inventory/retirement | `Docs/TestSuite.md` |
| harness/command routing | `Docs/Harness_Index.md` |
| logging / Qt-QML observability | `Docs/Logging_Guide.md` + `Docs/Qt_QML_Observability.md` |
| deferred deletion/debt | `Future_Cleanup.md` |
| deferred features | `Future_Work.md` |
| G4 durable scale/extent contract | `Docs/QtQuick_Migration/Remaining_G4_Visualizer_Viewport_Resize_Decomposition.md` |
| G4 post-checkpoint correction playbook | `Docs/QtQuick_Migration/G4_Post_Checkpoint_Audit_Corrections_Decomposition.md` |
| G7/G8 auxiliary/focus implementation route | `Docs/QtQuick_Migration/Remaining_G7_G8_Auxiliary_Focus_Decomposition.md` |
| H production cutover implementation route | `Docs/QtQuick_Migration/Remaining_H_Production_Cutover_Decomposition.md` |
| H8 retained visualizer middle-click preset hotswap | `Docs/QtQuick_Migration/H8_Visualizer_Middle_Click_Preset_Cycle_Decomposition_2026-08-30.md` |
| closed H visualizer edge audit evidence | `Docs/QtQuick_Migration/H_Pre_Cutover_Visualizer_Edge_Corrections.md` |
| closed True-F technical/retained-consumer evidence | `Docs/QtQuick_Migration/H_True_F_Technical_Closure.md` |
| J final installed/physical acceptance route | `Docs/QtQuick_Migration/Remaining_J_Final_Installed_Acceptance_Decomposition.md` |
| J Parity+ historical visual/interaction floor | `Docs/QtQuick_Migration/J_ParityPlus_Historical_Visual_Interaction_Reference_2026-08-30.md` |
| J black-flash / first-visible-frame surface continuity | `Docs/QtQuick_Migration/J_Black_Flash_Surface_Continuity_Decomposition_2026-08-30.md` |

Reorientation/handoff files are conversation/operator artifacts, not repository architecture. Do not add a current
reorientation file under `Docs/` unless the operator explicitly asks for a repository handoff artifact.

## Runtime observability

Qt Quick acceptance has two first-class log planes: `screensaver.log` and always-on `screensaver_qml.log`. The latter is direct Qt/QML message-handler evidence and must exist even on a zero-message clean run. Read `Docs/Qt_QML_Observability.md` before changing capture lifetime, sidecar semantics or considering an OS-level stderr redirect. Permanent health coverage includes both a fake-handler contract test and a real `QQmlEngine` warning probe (`tests/test_qt_message_capture_qml_runtime.py`).

Physical H/J Quick gates are not fully evidenced by the Python log alone.

## Settings themes

`Docs/Settings_Theme_Architecture.md` is the permanent Settings-theme contract. It owns schema-v5 theme semantics,
layered-QWidget native backdrop mapping, Acrylic/Glass division of responsibility, Theme Foundry authoring rules and the
boundary around future `dark.qss` retirement. `Docs/Settings_Dark_QSS_Retirement.md` is the focused execution authority
for removing that legacy stylesheet with zero intended visual/behavior change once `Future_Cleanup.md` admits the work.
Historical Glass investigation is R-61; temporary theme planning notes are not current authority.

## Closed ordinary-family migration

Phase F F1–F8 is closed. The decomposition remains a reference, not current work admission:
`Docs/QtQuick_Migration/10_Widget_Family_Port_Decomposition.md`.

Steam Journey/Progress and Friend Pulse remain future-product scaffolds; Achievement Pulse and Abandonment Issues are
the two substantive migrated Steam families.

## G / H / I / J

`Current_Plan.md` owns which phase/slice is active and which gates have closed. This index deliberately does not duplicate
that volatile status.

Durable roles:

- G owns retained CUSTOM/input/auxiliary/focus destination contracts and deterministic closure;
- H owns final production Quick owner/orchestration cutover plus caller-proven old physical-host deletion;
- I is source-driven residue only and has no standing speculative deletion plan;
- J owns compiled/installed/physical acceptance, including real displays, mixed refresh/DPR, off/wake, MC/screensaver input,
  eyes-on parity, performance tails and packaging.

## Transitions

Quick transition architecture is landed. Read `Docs/QtQuick_Migration/02_Scene_Renderer_Transitions.md` and
`Docs/Transition_Change_Checklist.md`. Old compositor transition pixels are migration debris after caller proof, not
new-work visual authority.

## Visualizer

For geometry/CUSTOM work read these together:

- `Docs/QtQuick_Migration/03_Visualizer.md`
- `Docs/Guardrails/Visualizer_Presentation.md`
- `Docs/Guardrails/Bubble_Temporal_Fidelity.md`
- `Docs/Visualizer_Reference.md`
- `Docs/QtQuick_Migration/Remaining_G4_Visualizer_Viewport_Resize_Decomposition.md`
- `Docs/QtQuick_Migration/G4_Post_Checkpoint_Audit_Corrections_Decomposition.md` for the bounded G4 correction record

For historical H visualizer-edge reasoning only, use the closed
`H_Pre_Cutover_Visualizer_Edge_Corrections.md` + `H_True_F_Technical_Closure.md` pair. They are evidence, not active work
admission. `Remaining_H_Production_Cutover_Decomposition.md` is the durable closed cutover record; current I admission lives
only in `Current_Plan.md`.

The all-five-mode capability policy is landed. Do not reintroduce a Bubble false gate to avoid correcting viewport
ownership or spatial-domain defects.

## Historical evidence

Closed rationale and old owner maps belong under `Docs/Historical_Plans/`, `Docs/Historical_Bugs/`,
`Docs/phase_reports/`, `Docs/Performance_Evidence/`, or `Docs/audits/`. Historical wording does not define current work
admission or ownership and is not rewritten merely to sound current.
