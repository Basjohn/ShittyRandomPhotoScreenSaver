# Qt Quick Production Migration — Technical Decomposition Index

Status: subordinate technical notes for `Current_Plan.md`  
Last updated: 2026-08-24  
Reviewed documentation/source basis: `f049baedb80d6b7e7a74fb03395b06e94b870a1c` (F0 closed; F0.5 docs active)

These documents are not independent plans. Sequence and work admission come only from
`Current_Plan.md`; deferred cleanup/deletion comes from `Future_Cleanup.md`.

Current normal implementation work: **Phase F0.5 — delete legacy shadow-tuning authority, normalize canonical shadow settings, and complete Widgets → General shadow controls before the first retained family port**.

Within Phase E:

- E2 capability activation / SETUP: **CLOSED**
- E2.7 Visualizer CUSTOM failover/reclaim: **CLOSED / audit GREEN**
- E1 presentation-neutral widget runtime ownership: **CLOSED / audit GREEN @ `4466c306`**
- E3 retained ordinary-widget substrate: **CLOSED / audit GREEN @ `1f25a791`**
- **E4 global eight-direction shadow authority: CLOSED / independently GREEN @ `3a562632`**;
- **Phase E: CLOSED**;
- **Phase F: ACTIVE; F0 is closed; F0.5 legacy shadow-tuning retirement + canonical shadow controls are next; then F1 Clock**.

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
| **F** | **active: F0 closed; F0.5 shadow-tuning retirement + controls next; then F1 Clock** |
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
| `10_Widget_Family_Port_Decomposition.md` | **detailed Phase-F family order, reference/retirement policy and per-family implementation contracts** |
| `11_Clock_Analogue_Shadow_Contract.md` | **required F1 Clock analogue ring/marker/numeral/hand shadow reference; also protects that reference during F0.5 sidecar deletion** |

For active Phase-F work, F0.5 is the admitted slice: delete the legacy `shadowtuning.json` authority/unused offset pair, normalize canonical shadow settings, then add the General controls. Read `Docs/Custom_Style_Implementation.md` plus `10_Widget_Family_Port_Decomposition.md`; use `04_Widget_Runtime_Presentation.md` and `09_Widget_Quick_Presentation_Bridge.md` for destination semantics. **Before deleting shadow consumers, also read `11_Clock_Analogue_Shadow_Contract.md` so sidecar cleanup does not erase the family-authored Clock analogue reference.** For F1 Clock after F0.5 is GREEN, read `09_Widget_Quick_Presentation_Bridge.md`, `10_Widget_Family_Port_Decomposition.md` and `11_Clock_Analogue_Shadow_Contract.md` together.

## Current-legacy warning

The old physical `DisplayWidget` / QRhiWidget / `GLCompositorWidget` stack remains until H production
cutover. Ordinary family presenters have a shorter lifetime: keep an unported family's QWidget pixels
only while they are still needed as behavioral/visual reference, then delete them after that family's
independent GREEN + caller proof instead of carrying them to I.

Do not deepen old presentation architecture or create a selectable fallback presenter. Git is sufficient
historical reference after a family closes. Real resilience contracts are not removed by this rule.

## Off-rails rule

If a decomposition suggests work not admitted by `Current_Plan.md`, do not perform it yet.

If exact current source invalidates a decomposition assumption, update the smallest affected current doc
and sequence authority deliberately.

Do not create another migration roadmap. New technical notes must stay subordinate to
`Current_Plan.md`.
