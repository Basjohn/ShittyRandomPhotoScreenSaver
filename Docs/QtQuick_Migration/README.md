# Qt Quick Production Migration — Technical Decomposition Index

Status: subordinate technical notes for `Current_Plan.md`  
Last updated: 2026-08-24

These documents are **not independent plans**. Sequence and work admission come only from
`Current_Plan.md`; deferred deletion/accounting comes from `Future_Cleanup.md`.

Current normal implementation phase: **Phase E — widget presentation + capability setup foundation**.

Phase C transition implementation/deterministic hardening and Phase D visualizer implementation/
documentation are structurally closed. Remaining physical/eyes-on evidence is explicit acceptance
debt rather than unfinished implementation.

Within Phase E:

- activation/catalog foundation: landed;
- **E2 `SETUP`/live lazy navigation: implementation CLOSED**;
- **E2.7 Visualizer CUSTOM failover/reclaim: implementation CLOSED / audit GREEN**;
- **E1 presentation-neutral runtime/model/provider ownership: ACTIVE**; Achievement slice 5 and the
  bounded Abandonment/Weather correction are GREEN; Media source/cardinality audit is active;
- E3 retained Quick primitives: waiting for E1;
- E4 global eight-direction shadow authority: waiting for E3;
- Phase F waits for Phase-E closure.

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

For active E1 ordinary-widget ownership, read `04_Widget_Runtime_Presentation.md` and
`08_Widget_Runtime_Ownership_Threading.md` together. `08` defines owner scope/cardinality/threading; it
does not authorize a family not admitted by `Current_Plan.md`.

For Phase E3/F ordinary-widget Quick presentation, `09_Widget_Quick_Presentation_Bridge.md` defines the
state/list/image/action/update boundary subordinate to `04`.

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
| **E — widget presentation + capability setup** | **in progress: E1 ACTIVE** | **current normal implementation work** |
| F — widget families | waiting for E | reference only |
| G — CUSTOM/input/auxiliary pixels | waiting for F | reference only |
| H — settings epoch + production cutover | waiting for A–G implementation | reference only |
| I — legacy presenter deletion | waiting for H | reference only |
| J — tooling/final validation/docs closure | waiting for implementation | reference only |

## Current-legacy presentation warning

References to `DisplayWidget`, QRhiWidget, `GLCompositorWidget`, old QWidget runtime pixels,
`CompositorVisualizerLayer` or `SpotifyBarsGLOverlay` presentation ownership may still describe real
pre-cutover source. They are **CURRENT-LEGACY — WILL BE OBSOLETE** at their F/H/I caller-removal gates
and must never be used as destination authority.

Presentation-neutral logic, authored behavior, providers/models/settings and useful math may survive
when their owner is explicitly rehomed.

## Documents

| File | Purpose / current status |
|---|---|
| `01_Runtime_Host_Lifecycle.md` | landed runtime-host decomposition + H cutover requirements; old `DisplayWidget` seam is current-legacy |
| `02_Scene_Renderer_Transitions.md` | landed Phase-C renderer architecture, current transition-authoring authority, permanent regression/acceptance rules |
| `03_Visualizer.md` | landed Phase-D visualizer architecture/reference; old presentation-host names are migration source only |
| `04_Widget_Runtime_Presentation.md` | **active E1**, then E3/E4 and Phase-F widget model/presentation split |
| `05_Custom_Layout_Input_Interaction.md` | Phase-G CUSTOM Save/Cancel, edit overlays, cross-monitor transfer, interaction/context |
| `06_Build_Tooling_Validation.md` | packaging, tools, tests, compiled/runtime/perf gates |
| `07_Settings_Capability_Activation.md` | **landed E2/E2.7 capability/Settings contract** + E1 dormancy boundary |
| `08_Widget_Runtime_Ownership_Threading.md` | **E1 cross-cutting owner scope/cardinality/threading/async-retirement contract**; service is not thread, not every family needs a service |
| `09_Widget_Quick_Presentation_Bridge.md` | **E3/F ordinary-widget state/list/image/action/update bridge and family-port decomposition** |

## Off-rails rule

If a decomposition suggests work not admitted by the active slice in `Current_Plan.md`, do not perform
it yet.

If exact current source invalidates a technical assumption, update the smallest affected
decomposition and update `Current_Plan.md` only when sequencing/authority actually changes.

Do not create another migration roadmap document.

Do not use a later-phase decomposition to smuggle later-phase work into the active phase.
