# SRPSS Documentation Index

Last updated: 2026-08-25

## Start here

For implementation work:

```text
exact current source
-> Current_Plan.md
-> relevant focused current contract
-> tests/evidence for the claim
```

Current migration state: **Phase F active; F1 Clock and F2 Weather are caller-proven and CLOSED.
F3 Media core is ACTIVE.**

Do not read the whole history tree by default.

## Current authority

| Need | Read |
| --- | --- |
| What may be changed now? | `Current_Plan.md` |
| Durable product/architecture | `Spec.md` |
| Physical presenter architecture | `Docs/Compositor_Architecture.md` |
| Current owner map | `Docs/Contracts.md` |
| General safety | `Docs/Guardrails.md` |
| Test inventory/retirement | `Docs/TestSuite.md` |
| Deferred deletion/debt | `Future_Cleanup.md` |
| Deferred feature work | `Future_Work.md` |

## Active Phase-F routing

| Work | Read |
| --- | --- |
| Phase-F sequence/family contracts | `Docs/QtQuick_Migration/10_Widget_Family_Port_Decomposition.md` |
| retained widget shell/style | `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md` |
| model/state/action/image bridge | `Docs/QtQuick_Migration/09_Widget_Quick_Presentation_Bridge.md` |
| Clock analogue shadow fidelity | `Docs/QtQuick_Migration/11_Clock_Analogue_Shadow_Contract.md` |
| widget authoring | `Docs/10_WIDGET_GUIDELINES.md` |
| Settings/style controls | `Docs/Custom_Style_Implementation.md` |
| CUSTOM/input later | `Docs/QtQuick_Migration/05_Custom_Layout_Input_Interaction.md` |

## Transitions

Quick transition architecture is landed. Read:

- `Docs/QtQuick_Migration/02_Scene_Renderer_Transitions.md`
- `Docs/Transition_Change_Checklist.md`

The old compositor transition implementations are migration debris once caller-proofed. They are not
the visual reference for new transition work.

## Visualizer

Read:

- `Docs/QtQuick_Migration/03_Visualizer.md`
- `Docs/Guardrails/Visualizer_Presentation.md`
- `Docs/Guardrails/Bubble_Temporal_Fidelity.md`
- `Docs/Visualizer_Reference.md`

Preserve logical/authored/runtime state used by Quick. Old compositor-only pixels are not automatically
protected because they are in the visualizer package.

## Steam family

Current Quick-era routing:

- `Docs/SRPSS_Steam_Widget_Family_Implementation_Plan.md` — **Quick-era wrapper/reference index**
- `widgets/steam_card_models.py` and current neutral Steam runtime/preparation source
- Phase-F decomposition for substantive Steam ports F7–F8

The large pre-Quick Steam plan is historical product/UX/data evidence, not current presentation
architecture. Steam Journey/Progress and Friend Pulse are unfinished dev-gated scaffolds and are not
Phase-F migration ports.

## Historical evidence

Closed phase rationale and old owner maps belong under:

- `Docs/Historical_Plans/`
- `Docs/Historical_Bugs/`
- `Docs/phase_reports/`
- `Docs/Performance_Evidence/`
- `Docs/audits/`

Historical wording does not define current work admission or ownership.
