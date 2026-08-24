# Qt Quick Production Migration — Technical Decomposition Index

Status: subordinate technical notes for `Current_Plan.md`  
Last updated: 2026-08-24  
Reviewed source basis: `1f25a791a2af822aff707f1e64ff836d0fc6f070`

These documents are not independent plans. Sequence and work admission come only from
`Current_Plan.md`; deferred cleanup/deletion comes from `Future_Cleanup.md`.

Current normal implementation work: **Phase E4 — global shadow authority + retained shadow
normalization**.

Within Phase E:

- E2 capability activation / SETUP: **CLOSED**
- E2.7 Visualizer CUSTOM failover/reclaim: **CLOSED / audit GREEN**
- E1 presentation-neutral widget runtime ownership: **CLOSED / audit GREEN @ `4466c306`**
- E3 retained ordinary-widget substrate: **CLOSED / audit GREEN @ `1f25a791`**
- **E4 global eight-direction shadow authority: ACTIVE NEXT**
- Phase F waits for E4 + Phase-E closure review.

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
| **E** | **in progress: E4 active; E1/E2/E2.7/E3 closed** |
| F | waiting for Phase-E closure |
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
| `04_Widget_Runtime_Presentation.md` | **active E4 shadow/style authority; landed E1/E3 widget architecture; Phase-F shell contract** |
| `05_Custom_Layout_Input_Interaction.md` | Phase-G CUSTOM/input decomposition, including Clock per-mode geometry variants |
| `06_Build_Tooling_Validation.md` | packaging/runtime/compiled/performance validation |
| `07_Settings_Capability_Activation.md` | landed E2/E2.7 activation/SETUP contract |
| `08_Widget_Runtime_Ownership_Threading.md` | landed E1 owner/cardinality/threading contract |
| `09_Widget_Quick_Presentation_Bridge.md` | model/list/image/action/family component bridge built on landed E3 host |
| `10_Widget_Family_Port_Decomposition.md` | **detailed Phase-F family order and per-family implementation contracts** |

For active E4 work read `04_Widget_Runtime_Presentation.md` plus exact current shadow source/tests.

For the first Phase-F family, after Phase-E closure, read `09_Widget_Quick_Presentation_Bridge.md` and
`10_Widget_Family_Port_Decomposition.md` together.

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
