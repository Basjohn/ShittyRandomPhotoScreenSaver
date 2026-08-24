# Qt Quick Production Migration — Technical Decomposition Index

Status: subordinate technical notes for `Current_Plan.md`  
Last updated: 2026-08-24  
Reviewed source basis: `19460a7a8ffe9e5134363267da3d61fe46cc23d4` + F0 closure reconciliation

These documents are not independent plans. Sequence and work admission come only from
`Current_Plan.md`; deferred cleanup/deletion comes from `Future_Cleanup.md`.

Current normal implementation work: **Phase F0.5 — complete Widgets → General canonical shadow controls before the first retained family port**.

Within Phase E:

- E2 capability activation / SETUP: **CLOSED**
- E2.7 Visualizer CUSTOM failover/reclaim: **CLOSED / audit GREEN**
- E1 presentation-neutral widget runtime ownership: **CLOSED / audit GREEN @ `4466c306`**
- E3 retained ordinary-widget substrate: **CLOSED / audit GREEN @ `1f25a791`**
- **E4 global eight-direction shadow authority: CLOSED / independently GREEN @ `3a562632`**;
- **Phase E: CLOSED**;
- **Phase F: ACTIVE; F0 deletion is source-audited GREEN and this reconciliation removes its stale scraping dependency pins; F0.5 canonical shadow controls are next; then F1 Clock**.

## Required routing

```text
exact current source / pushed diff
        ↓
Current_Plan.md
        ↓
Spec.md + Docs/Compositor_Architecture.md + Docs/Contracts.md
        ↓
Docs/Guardrails.md + relevant focused guardrail
        ↓
ONLY the active QtQuick_Migration decomposition
        ↓
focused tests / current evidence
```

Repository connectors/APIs are read/audit tools for SRPSS. Source/document mutation happens in the
operator's real local worktree. Do not add hosted CI unless explicitly requested.

## Phase status

| Phase | Status |
| --- | --- |
| A | closed |
| B | closed |
| C | implementation closed |
| D | implementation closed |
| E | **closed / independently GREEN through E4** |
| **F** | **active: F0 closed after reconciliation; F0.5 shadow controls next; then F1 Clock** |
| G | waiting for F |
| H | waiting for A–G implementation |
| I | waiting for H |
| J | waiting for implementation |

## Documents

| File | Purpose / current status |
| --- | --- |
| `01_Runtime_Host_Lifecycle.md` | landed host/window/scene lifecycle + cutover reference |
| `02_Scene_Renderer_Transitions.md` | landed transition renderer architecture + permanent authoring/regression rules |
| `03_Visualizer.md` | landed visualizer architecture + later integration reference |
| `04_Widget_Runtime_Presentation.md` | landed Phase-E widget/shadow architecture + **active Phase-F shell/fade/effect-carrier guardrails** |
| `05_Custom_Layout_Input_Interaction.md` | Phase-G CUSTOM/input decomposition, including Clock per-mode geometry variants |
| `06_Build_Tooling_Validation.md` | packaging/runtime/compiled/performance validation |
| `07_Settings_Capability_Activation.md` | landed E2/E2.7 activation/SETUP contract |
| `08_Widget_Runtime_Ownership_Threading.md` | landed E1 owner/cardinality/threading contract |
| `09_Widget_Quick_Presentation_Bridge.md` | model/list/image/action/family component bridge built on landed E3 host |
| `10_Widget_Family_Port_Decomposition.md` | **detailed Phase-F family order and per-family implementation contracts** |

For active Phase-F work, F0.5 is the admitted slice. Read `Docs/Custom_Style_Implementation.md` plus `10_Widget_Family_Port_Decomposition.md`; use `04_Widget_Runtime_Presentation.md` and `09_Widget_Quick_Presentation_Bridge.md` for the destination semantics the Settings values must later feed. For F1 Clock after F0.5 is GREEN, read `09_Widget_Quick_Presentation_Bridge.md` and `10_Widget_Family_Port_Decomposition.md` together.

## Current-legacy warning

`DisplayWidget`, QRhiWidget, `GLCompositorWidget`, QWidget runtime widget pixels and painter shadow
implementations may remain before cutover. They are migration source/reference, not destination
authority.

Do not deepen old presentation architecture.

## Off-rails rule

If a decomposition suggests work not admitted by `Current_Plan.md`, do not perform it yet.

If exact current source invalidates a decomposition assumption, update the smallest affected current doc
and sequence authority deliberately.

Do not create another migration roadmap. New technical notes must stay subordinate to
`Current_Plan.md`.
