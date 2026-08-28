# Qt Quick Production Migration — Technical Index

Last updated: 2026-08-29

Sequence/work admission comes only from `Current_Plan.md`.

Current state:

```text
Phase F F0–F8 closed
G1–G6 closed
G4 core viewport-extent implementation landed; bounded post-checkpoint audit corrections are priority
G7 retained dimming/pixel-shift, halo and context menu landed; caller-proof closure pending
G8 focus/MC closure pending
one independent audit gates the complete checkpointed G state before H
H production owner/orchestration cutover follows accepted G
I residue only
J final installed/physical validation
```

## Current routing

| File | Purpose |
| --- | --- |
| `05_Custom_Layout_Input_Interaction.md` | current G CUSTOM/input/auxiliary contracts |
| `03_Visualizer.md` | visualizer logical/render/geometry contract |
| `01_Runtime_Host_Lifecycle.md` | Quick runtime/window/lifecycle and H owner cutover |
| `06_Build_Tooling_Validation.md` | focused migration proof vs J installed/physical closure |
| `04_Widget_Runtime_Presentation.md` | retained ordinary-widget architecture/style |
| `09_Widget_Quick_Presentation_Bridge.md` | state/model/action/image family bridge |
| `07_Settings_Capability_Activation.md` | capability activation/dormancy |
| `08_Widget_Runtime_Ownership_Threading.md` | neutral runtime ownership/cardinality |
| `10_Widget_Family_Port_Decomposition.md` | closed F1–F8 reference |
| `11_Clock_Analogue_Shadow_Contract.md` | permanent Clock analogue fidelity |
| `Remaining_G4_Visualizer_Viewport_Resize_Decomposition.md` | durable G4 scale/extent architecture and closure bars |
| `G4_Post_Checkpoint_Audit_Corrections_Decomposition.md` | current bounded G4 ownership/spatial correction playbook |
| `Remaining_G7_G8_Auxiliary_Focus_Decomposition.md` | G7 caller retirement + G8 focus/MC/input closure |
| `Remaining_H_Production_Cutover_Decomposition.md` | H owner wiring, viewport-config binding, cardinality and old-host deletion |
| `Remaining_J_Final_Installed_Acceptance_Decomposition.md` | J compiled/installed/physical acceptance and closure matrix |

## Current scaffolding rule

The remaining legacy physical host is not a supported fallback and does not need to keep the partially migrated product
functional. Caller-dead old family/CUSTOM/auxiliary/transition/visualizer pixels should not be retained for temporary
continuity. H wires the destination production chain and removes whatever physical-host edge remains.

## Visualizer viewport rule

The all-five-mode viewport capability policy and core edge-resize path are landed. Do not reintroduce
`viewport_resize_capable=False` for Bubble as a workaround. Current corrections must preserve independent uniform scale vs
viewport extent, deterministic committed-vs-temporary CUSTOM ownership, Bubble BTF and the exact canonical baseline path.

## G audit rule

Do not stop for an independent audit after each GREEN G slice. Finish the bounded G4 corrections, G7 and G8 with focused
tests/self-audit, checkpoint the complete G state, then stop once for independent audit before H. Real RED/YELLOW blockers
still stop immediately.

## Final-phase decomposition rule

H already has a decomposition because it changes production ownership. J has a decomposition because physical/build acceptance
spans many environments and cannot safely live as a prose footnote. I deliberately does **not** have a standing decomposition:
post-H residue must be derived from the exact caller graph. If I ceases to be residue-only, create a bounded decomposition from
that exact source rather than following a speculative pre-H deletion list.

## Off-rails rule

If a decomposition conflicts with exact source or `Current_Plan.md`, determine whether source is missing a durable
contract before rewriting documentation. Historical evidence never overrides current ownership.
