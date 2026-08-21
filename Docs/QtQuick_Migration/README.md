# Qt Quick Production Migration — Technical Decomposition Index

Status: subordinate technical notes for `Current_Plan.md`
Last updated: 2026-08-21

These documents are **not independent plans**. Sequence and work admission come only from `Current_Plan.md`; deferred deletion/accounting comes from `Future_Cleanup.md`.

Current active implementation phase: **Phase D — visualizer**.

Phase C transition implementation is structurally complete. Its remaining physical/eyes-on acceptance is tracked explicitly and does not by itself block unrelated Phase-D implementation.

## Required routing before active migration work

Use the repository authority chain rather than treating one decomposition as self-sufficient:

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

For visualizer work, `Docs/Guardrails/Visualizer_Presentation.md` is binding; for Bubble also read `Docs/Guardrails/Bubble_Temporal_Fidelity.md` (BTF).

`Future_Work.md` is not migration work admission. It remains a deferred feature/experiment ledger unless the operator explicitly selects an item or the active plan/cleanup authority says it is eligible.

## Documents

| File | Purpose |
|---|---|
| `01_Runtime_Host_Lifecycle.md` | QQuickWindow/runtime owner, display topology, lifecycle, input seams |
| `02_Scene_Renderer_Transitions.md` | landed QSGRenderNode/OpenGL image/transition architecture, authored transition contracts, pacing, Phase-C sign-off |
| `03_Visualizer.md` | ACTIVE Phase-D runtime split, immutable latest snapshots, five-mode Quick rendering, BTF |
| `04_Widget_Runtime_Presentation.md` | widget manager/model split, retained Quick components, shadows, family migration |
| `05_Custom_Layout_Input_Interaction.md` | CUSTOM Save/Cancel, edit overlays, cross-monitor transfer, interaction/context |
| `06_Build_Tooling_Validation.md` | Nuitka/QML packaging, tools, tests, compiled/runtime/perf gates |

## Off-rails rule

If a decomposition suggests work that is not admitted by the active slice in `Current_Plan.md`, do not perform it yet.

If exact current source invalidates a technical assumption, update the smallest affected decomposition and update `Current_Plan.md` only when sequencing/authority actually changes.

Do not create another migration roadmap document.

Do not use a later-phase decomposition to smuggle later-phase work into the active phase.

## Repository/API checkpoint rule

When edits are made through a connector/API rather than a normal local Git worktree, a created blob/tree is not a checkpoint.

For risky whole-file reconstruction use:

```text
authoritative parent
-> candidate blobs/tree
-> UNATTACHED candidate commit
-> compare parent..candidate
-> spot-fetch reconstructed boundaries/suspicious sections
-> move branch ref only when clean
-> verify pushed commit/diff
```

Abandon malformed candidate commits before they become branch-reachable.
