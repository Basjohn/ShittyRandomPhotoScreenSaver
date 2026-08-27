# Qt Quick Production Migration — Technical Index

Last updated: 2026-08-27

Sequence/work admission comes only from `Current_Plan.md`.

Current state:

```text
Phase F closed
Phase G CUSTOM/input active
F0.5 closed
F1 Clock closed
F2 Weather closed
F3 Media core closed
F4 Media controls closed
F5 Reddit closed
F6 Gmail closed
F7 Achievement Pulse closed
F8 Abandonment Issues closed
```

Closed A–E history is intentionally not repeated here.

## Active routing

| File | Purpose |
| --- | --- |
| `04_Widget_Runtime_Presentation.md` | retained ordinary-widget architecture/style |
| `09_Widget_Quick_Presentation_Bridge.md` | state/model/action/image family bridge |
| `10_Widget_Family_Port_Decomposition.md` | F1–F8 order/contracts |
| `11_Clock_Analogue_Shadow_Contract.md` | mandatory F1 analogue shadow fidelity |
| `05_Custom_Layout_Input_Interaction.md` | Phase-G CUSTOM/input |
| `06_Build_Tooling_Validation.md` | final/installed/build validation |

Landed references used only when relevant:

| File | Purpose |
| --- | --- |
| `01_Runtime_Host_Lifecycle.md` | Quick runtime/window/lifecycle |
| `02_Scene_Renderer_Transitions.md` | current Quick transition architecture |
| `03_Visualizer.md` | current Quick visualizer architecture |
| `07_Settings_Capability_Activation.md` | capability activation |
| `08_Widget_Runtime_Ownership_Threading.md` | neutral runtime ownership |

Historical Phase-E closure:
`Docs/Historical_Plans/QtQuick_Migration_Phase_E_Closure_2026-08-24.md`.

## Current legacy rule

Ordinary old family pixels survive only until their retained replacement is independently GREEN.

Old transition/visualizer pixel-only implementations may retire earlier on caller proof because their
Quick replacements are already landed.

The old physical DisplayWidget/QRhi/GLCompositor presenter retires at H cutover.

Do not create selectable fallback presentation.

## Off-rails rule

If a decomposition conflicts with exact source or `Current_Plan.md`, stop following the stale portion
and reconcile the smallest current-authority doc. Historical evidence never overrides current ownership.
