# Qt Quick Production Migration — Technical Index

Last updated: 2026-08-29

Sequence/work admission comes only from `Current_Plan.md`.

Live phase/checkpoint status is intentionally not duplicated here; read `Current_Plan.md`.

## Current routing

| File | Purpose |
| --- | --- |
| `05_Custom_Layout_Input_Interaction.md` | CUSTOM/input/auxiliary contracts |
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
| `G4_Post_Checkpoint_Audit_Corrections_Decomposition.md` | G4 ownership/spatial correction closure reference |
| `Remaining_G7_G8_Auxiliary_Focus_Decomposition.md` | G7/G8 auxiliary/focus closure reference |
| `Remaining_H_Production_Cutover_Decomposition.md` | H owner wiring, viewport-config binding, cardinality and old-host deletion |
| `Remaining_J_Final_Installed_Acceptance_Decomposition.md` | J compiled/installed/physical acceptance and closure matrix |

## Migration scaffolding rule

A legacy physical host retained during migration is never a supported fallback and does not need to keep the partially
migrated product functional. Caller-dead old family/CUSTOM/auxiliary/transition/visualizer pixels are not retained for
temporary continuity; the production cutover removes the remaining physical-host edge.

## Visualizer viewport rule

The all-five-mode viewport capability policy and core edge-resize path are landed. Do not reintroduce
`viewport_resize_capable=False` for Bubble as a workaround. Current corrections must preserve independent uniform scale vs
viewport extent, deterministic committed-vs-temporary CUSTOM ownership, Bubble BTF and the exact canonical baseline path.

## Sequence rule

`Current_Plan.md` owns admission, active checkpoint, stop gates and live sequencing. This index must not duplicate those
volatile facts.

## Final-phase decomposition rule

H already has a decomposition because it changes production ownership. J has a decomposition because physical/build acceptance
spans many environments and cannot safely live as a prose footnote. I deliberately does **not** have a standing decomposition:
post-H residue must be derived from the exact caller graph. If I ceases to be residue-only, create a bounded decomposition from
that exact source rather than following a speculative pre-H deletion list.

## Off-rails rule

If a decomposition conflicts with exact source or `Current_Plan.md`, determine whether source is missing a durable
contract before rewriting documentation. Historical evidence never overrides current ownership.
