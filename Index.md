# SRPSS Documentation Index

Last updated: 2026-09-08

## Start here

```text
exact current source
-> Current_Plan.md
-> relevant focused current contract/decomposition
-> tests/evidence for the claim
```

Live migration phase/checkpoint status is owned only by `Current_Plan.md`. The
Qt Quick migration is closed; its per-phase decomposition tree
(`Docs/QtQuick_Migration/`) was deleted once the work landed. Do not recreate it —
current owners live in the durable contracts below, and any surviving residue is
tracked in `Current_Plan.md` / `Future_Cleanup.md` / `Docs/TestSuite.md`.

## Current authority

| Need | Read |
| --- | --- |
| current work / sequence / phase gates | `Current_Plan.md` |
| durable product/architecture | `Spec.md` |
| fast current owner map | `Docs/Contracts.md` |
| physical scene/presenter/runtime architecture (host, lifecycle, threading, transitions, visualizer shell) | `Docs/Compositor_Architecture.md` |
| Settings theme / Acrylic / Glass / Foundry architecture | `Docs/Settings_Theme_Architecture.md` |
| runtime Widget Theme precedence / semantic role / Custom transition | `Docs/Custom_Style_Implementation.md` + `Docs/Contracts.md` |
| `dark.qss` retirement execution | `Docs/Settings_Dark_QSS_Retirement.md` |
| CUSTOM / edit / geometry ownership | `Docs/Contracts.md` (Geometry / CUSTOM) + `Docs/Future_Work/Edit_Layout_Live_Commit.md` |
| ordinary widget authoring | `Docs/10_WIDGET_GUIDELINES.md` |
| defaults / SSOT / import / reset | `Docs/Defaults_Guide.md` |
| visualizer authored/reference behavior | `Docs/Visualizer_Reference.md` |
| visualizer presentation invariant | `Docs/Guardrails/Visualizer_Presentation.md` |
| Visualizer change checklist / preflight | `Docs/Visualizer_Change_Checklist.md` |
| Bubble temporal fidelity | `Docs/Guardrails/Bubble_Temporal_Fidelity.md` |
| performance optimization admission / reference envelopes | `Docs/Guardrails/Performance_Optimization_Contract.md` |
| runtime efficiency contract | `Docs/Guardrails/Runtime_Efficiency.md` |
| transitions change checklist | `Docs/Transition_Change_Checklist.md` |
| safety / guardrail router | `Docs/Guardrails.md` |
| test inventory/retirement | `Docs/TestSuite.md` |
| harness/command routing | `Docs/Harness_Index.md` |
| retained widget pixel/resize comparison | `Docs/Ordinary_Widget_Resize_Capture.md` |
| logging / Qt-QML observability | `Docs/Logging_Guide.md` + `Docs/Qt_QML_Observability.md` |
| presentation change preflight | `Docs/Presentation_Change_Preflight.md` |
| historical bug/failed-repair index | `Docs/Historical_Bugs.md` |
| deferred deletion/debt | `Future_Cleanup.md` |
| deferred features | `Future_Work.md` |
| operator-activated Future Work / live checklists | `FWPlan.md` |
| doc lifecycle / maintenance policy | `Docs/Documentation_Maintenance.md` |

Reorientation/handoff files are conversation/operator artifacts, not repository
architecture. Do not add a current reorientation file under `Docs/` unless the
operator explicitly asks for a repository handoff artifact.

## Active planned work (Future_Work)

`Current_Plan.md` owns which portions are implemented/awaiting validation; these
are the focused live-checklist decompositions it links:

- `Docs/Future_Work/Ordinary_Widget_Resize_Normalization.md` — remaining physical
  validation of geometry-only whole-card CUSTOM resize, plus the separate deferred
  non-CUSTOM stacker auto-shrink contract. New-widget guidance lives in the authoring guide.
- `Docs/Future_Work/Visualizer_Replay_Reactivity_Floor.md` — current offline replay
  harness and fixed reactivity floors; diagnostic artifacts and calibration review.
- `Docs/Settings_Dark_QSS_Retirement.md` — retire `themes/dark.qss` so
  `SettingsThemeSpec` is the sole Settings-dialog authority (colour and structure).
- `Docs/Future_Work/SST_9of10_Settings.md` — settings-migration closeout evidence.
- `Docs/Future_Work/Bubble_Aspect_And_Presentation_Decomposition.md` — Bubble
  aspect response / bounded presentation-cost diagnosis.
- `Docs/Future_Work/Visualizer_Edit_Geometry_And_Sphere_Materials.md` — all-mode
  live geometry, line-glow scaling, Bubble freeze/outline, Sphere material work.
- `Docs/Future_Work/Sphere_Visualizer_Decomposition.md` — experimental Sphere
  ownership/materials/validation.
- `Docs/Future_Work/Visualizer_Visual_Regression_Recovery.md` — recovered
  visualizer appearance and remaining Bubble validation.
- `Docs/Future_Work/Widget_Interaction_Glow_Decomposition.md` — interaction glow.
- `Docs/Future_Work/Slide_Motion_Options_Decomposition.md` — slide motion options.
- `Docs/Future_Work/Edit_Layout_Live_Commit.md` — promote retained geometry before
  ending CUSTOM; avoid geometry-only Save teardown.

## Runtime observability

Qt Quick acceptance has two first-class log planes: `screensaver.log` and always-on
`screensaver_qml.log`. The latter is direct Qt/QML message-handler evidence and
must exist even on a zero-message clean run. Read `Docs/Qt_QML_Observability.md`
before changing capture lifetime, sidecar semantics or considering an OS-level
stderr redirect. Permanent health coverage includes both a fake-handler contract
test and a real `QQmlEngine` warning probe
(`tests/test_qt_message_capture_qml_runtime.py`). Physical Quick gates are not
fully evidenced by the Python log alone.

## Settings themes

`Docs/Settings_Theme_Architecture.md` is the permanent Settings-theme contract: it
owns schema-v5 theme semantics, layered-QWidget native backdrop mapping,
Acrylic/Glass division of responsibility and Theme Foundry authoring rules.
`Docs/Settings_Dark_QSS_Retirement.md` is the focused execution authority for
removing the legacy `themes/dark.qss` stylesheet with zero intended
visual/behavior change once `Future_Cleanup.md` admits the work. Historical Glass
investigation is R-61.

## Runtime Widget Themes

`Docs/Custom_Style_Implementation.md` and `Docs/Contracts.md` own the durable
colour-only `.srwtheme` precedence / Custom semantics. Schema-v2 specialized widget
visuals use `ui/widget_visual_roles.py` as the one sparse semantic inheritance
resolver; do not create family-local theme cascades or serialize `local.*`
presentation context. `Current_Plan.md` owns which portions are implemented.

## Widgets

`Docs/10_WIDGET_GUIDELINES.md` owns ordinary-family authoring patterns. Ordinary
family pixels were retired during the migration after destination + caller proof.
Steam family: Achievement Pulse and Abandonment Issues are the two substantive
migrated families (disabled-by-default cards); Steam Journey/Progress and Friend
Pulse remain future-product scaffolds gated by `Docs/Steam_Data_Feasibility.md`
(reference index: `Docs/SRPSS_Steam_Widget_Family_Implementation_Plan.md`).

## Visualizer

For geometry/CUSTOM/presentation work read together:

- `Docs/Compositor_Architecture.md` (§7 Visualizer shell/clipping/geometry);
- `Docs/Guardrails/Visualizer_Presentation.md`;
- `Docs/Guardrails/Performance_Optimization_Contract.md` for any
  performance-motivated Visualizer/runtime change;
- `Docs/Guardrails/Bubble_Temporal_Fidelity.md`;
- `Docs/Visualizer_Reference.md`;
- `Docs/Visualizer_Change_Checklist.md` before shipping a change.

The all-five-mode capability policy is landed. Do not reintroduce a Bubble false
gate to avoid correcting viewport ownership or spatial-domain defects. Bubble's
durable reflow contract is routed through `Spec.md`,
`Docs/Visualizer_Reference.md`, `Docs/Guardrails/Bubble_Temporal_Fidelity.md` and
R-69: expanded-world positions/trails remain distinct from the equal-area pixel
radius response; never restore a viewport-dependent global head/Ghost compressor to
make extreme geometry look smaller.

## Transitions

Quick transition architecture is landed. Read `Docs/Compositor_Architecture.md`
(§11 Transition model) and `Docs/Transition_Change_Checklist.md`. Old compositor
transition pixels are migration debris after caller proof, not new-work visual
authority.

## Historical evidence

Closed rationale, failed-repair lessons and old owner maps live under
`Docs/Historical_Bugs/` (index: `Docs/Historical_Bugs.md`), `Docs/Fossils/` and
`Docs/audits/`. Historical wording does not define current work admission or
ownership and is not rewritten merely to sound current.

- `Docs/Historical_Bugs/R-73_Quick_Card_Shadow_Extra_Offset_Translation_And_Visualizer_Omission.md`
  — frame Extra Offset is directional growth; Visualizer joins global card-shadow ownership.
- `Docs/Historical_Bugs/Runtime_Card_Backdrop_Materials_Rejected_2026-09-02.md`
  — runtime Glass/Acrylic card backdrops are explicitly rejected; Settings-window
  native materials remain separate.
