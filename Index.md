# SRPSS Documentation Index

Last updated: 2026-08-29

## Start here

```text
exact current source
-> Current_Plan.md
-> relevant focused current contract/decomposition
-> tests/evidence for the claim
```

Current migration: **Phase F closed. Phase G has a bounded post-checkpoint G4 correction batch first, then G7 closure and
G8 focus/MC closure. One independent audit gates the complete checkpointed G state before H.**

## Current authority

| Need | Read |
| --- | --- |
| current work / sequence / G audit gate | `Current_Plan.md` |
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
| deferred deletion/debt | `Future_Cleanup.md` |
| deferred features | `Future_Work.md` |
| G4 durable scale/extent contract | `Docs/QtQuick_Migration/Remaining_G4_Visualizer_Viewport_Resize_Decomposition.md` |
| G4 post-checkpoint correction playbook | `Docs/QtQuick_Migration/G4_Post_Checkpoint_Audit_Corrections_Decomposition.md` |
| G7/G8 auxiliary/focus implementation route | `Docs/QtQuick_Migration/Remaining_G7_G8_Auxiliary_Focus_Decomposition.md` |
| H production cutover implementation route | `Docs/QtQuick_Migration/Remaining_H_Production_Cutover_Decomposition.md` |
| J final installed/physical acceptance route | `Docs/QtQuick_Migration/Remaining_J_Final_Installed_Acceptance_Decomposition.md` |

Reorientation/handoff files are conversation/operator artifacts, not repository architecture. Do not add a current
reorientation file under `Docs/` unless the operator explicitly asks for a repository handoff artifact.

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

G1–G6 are closed. The core G4 viewport-edge implementation, Bubble logical reflow and all-five-mode capability policy are
landed, but the independent post-checkpoint audit found bounded ownership/spatial corrections which are the immediate
priority. After those are GREEN, continue directly through G7 caller-proof closure and G8 focus/MC closure. Do **not** stop
for independent audit between ordinary GREEN G slices; checkpoint all of G, then stop once for independent audit before H.

H is final production owner/orchestration wiring plus remaining old physical-host deletion. It must bind the existing G
viewport-config ownership correctly; it does not get to reset committed non-baseline extent merely because CUSTOM is
inactive. I is deliberately source-driven residue and has no standing pre-H decomposition. J is final installed/physical
acceptance, including the deferred all-five-mode viewport eyes-on gate; use
`Docs/QtQuick_Migration/Remaining_J_Final_Installed_Acceptance_Decomposition.md`.

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
- while the current audit corrections remain open: `Docs/QtQuick_Migration/G4_Post_Checkpoint_Audit_Corrections_Decomposition.md`

The all-five-mode capability policy is landed. Do not reintroduce a Bubble false gate to avoid correcting viewport
ownership or spatial-domain defects.

## Historical evidence

Closed rationale and old owner maps belong under `Docs/Historical_Plans/`, `Docs/Historical_Bugs/`,
`Docs/phase_reports/`, `Docs/Performance_Evidence/`, or `Docs/audits/`. Historical wording does not define current work
admission or ownership and is not rewritten merely to sound current.
