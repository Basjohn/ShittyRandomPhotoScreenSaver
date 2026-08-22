# Qt Quick Production Migration — Technical Decomposition Index

Status: subordinate technical notes for `Current_Plan.md`  
Last updated: 2026-08-22

These documents are **not independent plans**. Sequence and work admission come only from
`Current_Plan.md`; deferred deletion/accounting comes from `Future_Cleanup.md`.

Current normal implementation phase: **Phase E — widget presentation + capability setup foundation**.

Phase C transition implementation is structurally complete and its deterministic hardening has landed.
Its remaining acceptance debt is explicit and operator-scheduled. Phase D visualizer implementation and
documentation closure are complete; its remaining physical cadence/eyes-on items are likewise explicit
acceptance debt rather than unfinished migration implementation.

## Required routing before active migration work

```text
exact current source / pushed diff
        ↓
Current_Plan.md
        ↓
Spec.md + Docs/Compositor_Architecture.md + Docs/Contracts.md
        ↓
Docs/Guardrails.md + the relevant focused guardrail
        ↓
ONLY the active QtQuick_Migration decomposition
        ↓
focused tests / current evidence
```

`Current_Plan.md` decides what is admitted **now**. A decomposition may retain landed rationale from an
earlier phase without reopening that phase.

For visualizer work, `Docs/Guardrails/Visualizer_Presentation.md` is binding; for Bubble also read
`Docs/Guardrails/Bubble_Temporal_Fidelity.md`.

`Future_Work.md` is not migration work admission. It remains a deferred feature/experiment ledger
unless the operator explicitly selects an item or the active plan/cleanup authority says it is
eligible.

## Repository workflow boundary

SRPSS source/document mutation happens in the real local Git worktree.

Repository connectors/APIs are for read/audit in this project, not normal create/update/delete work.
Do not invent connector blob/tree/branch-ref editing workflows.

SRPSS also does not use hosted repository CI as the normal migration test path. Do not add a hosted
workflow unless the operator explicitly requests one.

When durable docs are changed by a reviewer that cannot safely edit the local worktree, return whole
replacement files in a handoff pack for local diff/commit/push.

## Phase status

| Phase | Status | Normal use of its decomposition now |
|---|---|---|
| A — bootstrap/render-node proof | structurally complete | landed architecture/reference only |
| B — runtime-host decomposition | structurally complete | landed owner/lifecycle reference |
| C — base image + transitions | implementation complete | current transition authoring + regression/acceptance reference |
| D — visualizer | complete | landed visualizer architecture + later G/H integration reference |
| **E — widget presentation + capability setup** | **in progress** | **current normal implementation work** |
| F — widget families | waiting for E | reference only |
| G — CUSTOM/input/auxiliary pixels | waiting for F | reference only |
| H — settings epoch + production cutover | waiting for A–G implementation | reference only |
| I — legacy presenter deletion | waiting for H | reference only |
| J — tooling/final validation/docs closure | waiting for implementation | reference only |

Current Phase-E foundation already includes:

- presentation-neutral widget-family catalog metadata;
- canonical widget-family and transition capability-activation settings;
- transition runtime admission that honors activation;
- runtime widget creation gating by family activation.

The broader E1 `WidgetRuntimeManager` ownership split and the E2 operator-facing `SETUP`/lazy
navigation UI remain separate work until exact current source/`Current_Plan.md` says otherwise.

## Documents

| File | Purpose / current status |
|---|---|
| `01_Runtime_Host_Lifecycle.md` | landed runtime-host owner/lifecycle decomposition and cutover requirements |
| `02_Scene_Renderer_Transitions.md` | landed Phase-C renderer architecture, current transition-authoring authority, permanent regression/acceptance rules |
| `03_Visualizer.md` | landed Phase-D visualizer architecture/reference; not active Phase-D sequencing |
| `04_Widget_Runtime_Presentation.md` | active Phase-E/F widget model/presentation split, retained Quick primitives, shadows and family migration |
| `05_Custom_Layout_Input_Interaction.md` | Phase-G CUSTOM Save/Cancel, edit overlays, cross-monitor transfer, interaction/context |
| `06_Build_Tooling_Validation.md` | packaging, tools, tests, compiled/runtime/perf gates |
| `07_Settings_Capability_Activation.md` | Phase-E activation authority + E2 `SETUP`, live lazy navigation and transition random/manual UX |

## Off-rails rule

If a decomposition suggests work not admitted by the active slice in `Current_Plan.md`, do not perform
it yet.

If exact current source invalidates a technical assumption, update the smallest affected
decomposition and update `Current_Plan.md` only when sequencing/authority actually changes.

Do not create another migration roadmap document.

Do not use a later-phase decomposition to smuggle later-phase work into the active phase.
