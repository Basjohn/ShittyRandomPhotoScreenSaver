# Qt Quick Production Migration — Technical Index

Last updated: 2026-08-28

Sequence/work admission comes only from `Current_Plan.md`.

Current state:

```text
Phase F F0–F8 closed
G1–G6 closed
G7 retained dimming/pixel-shift, halo and context menu landed; closure pending
G4 correction required first: visualizer independent viewport-edge resize for all five modes
G8 pending
H production owner/orchestration cutover follows G
I residue only
J final installed/physical validation
```

## Current routing

| File | Purpose |
| --- | --- |
| `05_Custom_Layout_Input_Interaction.md` | current G contracts, including required viewport-resize correction and G7/G8 |
| `03_Visualizer.md` | visualizer logical/render/geometry contract |
| `01_Runtime_Host_Lifecycle.md` | Quick runtime/window/lifecycle and H owner cutover |
| `06_Build_Tooling_Validation.md` | focused migration proof vs J installed/physical closure |
| `04_Widget_Runtime_Presentation.md` | retained ordinary-widget architecture/style |
| `09_Widget_Quick_Presentation_Bridge.md` | state/model/action/image family bridge |
| `07_Settings_Capability_Activation.md` | capability activation/dormancy |
| `08_Widget_Runtime_Ownership_Threading.md` | neutral runtime ownership/cardinality |
| `10_Widget_Family_Port_Decomposition.md` | closed F1–F8 reference |
| `11_Clock_Analogue_Shadow_Contract.md` | permanent Clock analogue fidelity |
| `Remaining_G4_Visualizer_Viewport_Resize_Decomposition.md` | prescriptive implementation route for the missed G4 scale/extent split |
| `Remaining_G7_G8_Auxiliary_Focus_Decomposition.md` | prescriptive G7 caller retirement + G8 focus/MC/input closure |
| `Remaining_H_Production_Cutover_Decomposition.md` | prescriptive H owner wiring, cardinality and old-host deletion |

## Current scaffolding rule

The remaining legacy physical host is not a supported fallback and does not need to keep the partially migrated product
functional. Caller-dead old family/CUSTOM/auxiliary/transition/visualizer pixels should not be retained for temporary
continuity. H wires the destination production chain and removes whatever physical-host edge remains.

## Visualizer correction rule

Do not interpret a temporary `viewport_resize_capable=False` flag as destination intent. All five current modes,
including Bubble, must support independent viewport extent in CUSTOM in addition to uniform whole-size scale.

## Off-rails rule

If a decomposition conflicts with exact source or `Current_Plan.md`, determine whether source is missing a durable
contract before rewriting documentation. Historical evidence never overrides current ownership.
