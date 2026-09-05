# Future Work implementation plan

Last updated: 2026-09-05

The operator explicitly activated implementation from `Future_Work.md`. This file owns that work's live
sequence; `Current_Plan.md` retains unrelated J/product work and physical/log validation. Inspect exact
current source before each slice. Starting comparison HEAD: `0fd64b3d002834614131b46581e41fe497d5cbc5`.

## Active sequence

- [x] **Geometry-only Edit Save continuity:** retained geometry/extent is promoted in place and the operator reports
  Save is flowing extremely well without teardown, stale re-entry, or a visible restart. Keep this as the normal
  same-display path; topology-changing operations remain explicit reconciliation.
- [x] **Visualizer cross-display live Save continuity:** current supplied tree is physically reported good: live
  transfer moves the running Visualizer and Save commits without teardown/reinit. Preserve this as a hard UX contract;
  numbered layout-slot reload remains the explicit hot-swap/reconciliation boundary.
- [~] **Bubble extreme-wide presentation checkpoint — SOURCE IMPLEMENTED / PHYSICAL VALIDATION OPEN:** remove the stale
  coupling that subtracted additional main-outline thickness as the large/extreme viewport ramp rose. Canonical/small
  behaviour and the positive firmness protection remain. Ordinary wide/tall logical domains keep authored population and
  speed; only an extreme-wide eased tail reaches +1 big / +3 small bubbles and +20% stream baseline/cap. The measured
  1174x187 (6.28:1) operator viewport is full-tail. This is presentation-tail compensation only: no head-radius, Ghost,
  reaction amplitude, drift or cadence compression.

- [~] **Priority — Visualizer geometry/glow and Sphere validation:** live Edit Save and cross-display Visualizer Save
  are operator-accepted no-teardown paths; preserve them. Checkpoint 2 now raises Sphere Deformation to 4.5 and Size
  Response to 3.0/+0.90 pulse, adds persisted local-AA and lighting-opposed analytical cast-shadow controls, turns major
  Magma fissures into real radius depressions, and replaces detached side-lane liquid staging with shared body-surface
  anchors plus a body bulge / attached neck / pinch-off / gravity sequence. Geometry slots additionally capture the active
  Visualizer `mode` and continue to use the explicit fenced rebuild on slot **load**. The pre-existing 1px discrete display-hop
  projection drift is source-fixed with a floating geometric centre. PySide6/OpenGL and physical appearance validation remain
  open; exact required tests are mirrored in `Current_Plan.md`. Live decomposition:
  `Docs/Future_Work/Visualizer_Edit_Geometry_And_Sphere_Materials.md`.

- [x] **Visualizer glow regression — Sine/Oscilloscope:** repaired curve-normal halo distance and visible-area
  width. The operator confirms restored glow; the final large-size correction preserves logical-pixel/DPR and
  whole-widget scaling. Fourteen focused tests pass, including opaque-background halo, separate glow-off AA,
  DPR 1.5, whole 2x scaling and huge-world encoding. Before/after captures inspected under
  `logs/evidence_chest/fw_missing_line_glow_2026_09_05`.
- [ ] **Awaiting physical validation — final large-scale glow:** confirm the content-sized halo feels balanced
  during playback and Edit Layout at large/extreme sizes.
- [~] **Edit exit without teardown — assessment:** live geometry is operator-described as almost perfect.
  Inventory the Save/Cancel exit teardown and its current responsibilities; measure/check stale frame, age,
  source fencing and geometry. If safe, preserve the existing visualizer state/resources across ordinary edit
  exit, with tests for Save/Cancel, source freshness and unchanged activation. Real retirement boundaries remain.
  Document the decision and decomposition before implementation; do not remove teardown by assumption.
  Decomposition: `Docs/Future_Work/Edit_Layout_Live_Commit.md`.

  For implementation:
  Give QuickDisplayVisualizerOwner an explicit running-safe operation along the lines of:

commit_live_custom_layout(local_rect, viewport_extent)

It should atomically promote the current working state into:

_committed_layout_rect
_committed_layout_extent
controller.commit_presentation_metrics(current_presentation)

Then Save becomes conceptually:

persist → promote working state to committed → end CUSTOM → continue running.

And that ordering is especially beautiful for viewport-sensitive modes.

Immediately before Save:

effective extent = CUSTOM override

Immediately after promotion but before clearing:

CUSTOM override == newly committed extent

Immediately after clearing:

effective extent = newly committed extent

- [~] **Widget interaction glow controls — SOURCE IMPLEMENTED / PHYSICAL ACCEPTANCE OPEN:**
  `input.widget_glow_intensity` remains the 0-100% opacity owner. New `input.widget_glow_distance` is a persisted 6-48 px
  spread control, default 14 px (old fixed analytical extent was 12 px). The existing baked distance-field QSB is mapped
  through a configurable coordinate scale, broadening both travel and softness without an extra blur/capture/render loop.
  Ordinary widgets and Visualizer receive the value through the same immutable Quick input snapshot. Display -> Interaction
  keeps Hover/Click switches visible but hides Intensity/Distance/Color whenever both triggers are off. Hover/click still
  settle between finite state-edge fades; no Timer, poller, worker, frame loop or new cadence owner.

- [x] Read backlog, current navigation/contracts and repository guardrails; preserve the clean starting tree.
- [x] **FW1 — Widget interaction glow:** two Interaction switches, theme-inheriting shared swatch, one retained
  shader/quad and finite event-driven feedback. 64 focused tests passed; real Quick peak capture inspected.
  Detailed ownership and acceptance: `Docs/Future_Work/Widget_Interaction_Glow_Decomposition.md`.
- [x] **FW2 — Slide motion options and timing correction:** Elastic, Wobble and Flex are implemented in the sealed Slide owner with frozen
  per-run style resolution, exact endpoints and real-GL coverage. Perspective remains a separately designed feature;
  do not counterfeit it with a 2D effect.
  Elastic's tenfold late velocity discontinuity is replaced by continuous quintic travel/rebound; Wobble/Flex
  settle with zero warp velocity. 106 focused transition tests pass; physical timing acceptance remains open.
  Decomposition: `Docs/Future_Work/Slide_Motion_Options_Decomposition.md`.
- [~] **FW3 — Deformable Sphere — motion/material follow-up active:** dormant-by-default 3D mesh, five material presets including Water,
  bump/detail controls, source-fenced immutable capture, lazy Settings and event-only inactive GPU retirement.
  Real Quick captures inspected and relevant automatic gates passed; physical acceptance remains separate.
  Detailed evidence: `Docs/Future_Work/Sphere_Visualizer_Decomposition.md`. Current follow-up moves whole-body growth into
  a logical-cadence elastic/breathing spring with a much larger high-setting ceiling. Operator acceptance says the motion
  feels substantially better. Current Checkpoint 2 extends Deformation again from 3.0 to 4.5, extends Size Response from
  2.0 to 3.0/+0.90 pulse, preserves the already-expanded Vocal Response 3.0 ceiling, gives Magma real macro-fissure geometry,
  and makes Water/Magma liquid visibly originate from their rotating/deforming body surface before detachment. Defaults remain
  unchanged. `Future_Work.md` now records Block Spins + Sphere as the two-consumer proof for a small dormant 3D
  renderer substrate; transition/Visualizer lifecycle owners remain separate.
- [~] **Bubble aspect/response — awaiting physical validation:** equal-area response replaces the rejected
  height-only coupling; outlines are one pixel thinner with derivative coverage. Live edit preview uses the
  same working geometry as the edit frame. Immutable-tuple reuse remains landed without cadence changes.
  Confirm same-area wide/tall response and rendered contacts. Evidence:
  `Docs/Future_Work/Visualizer_Visual_Regression_Recovery.md`.
- [ ] **Awaiting Validation / Logs — Bubble:** match the operator's resize operation and same-preset
  canonical/wide/narrow feel; obtain a 60 Hz `--perf --viz` baseline without `--usage` before further
  presentation-tail tuning. Per-head GL response is preserved; the original live complaint is not declared closed.
- [ ] **FW4 — Directional Pixel Accretion:** create a decomposition, then implement a deterministic instanced
  directional translation experiment with source underlay and exact endpoints.
- [ ] **FW5 — Glass Shatter / Exploding Tiles:** separate decompositions and isolated lazy implementations after
  earlier checkpoints; prove depth, deterministic launch and resource retirement.
- [ ] **FW6 — Ink Bloom:** bounded isolated shader experiment after the higher-priority features.
- [ ] **Later conditional items:** other 3D modes require final J validation; FlowContainer changes require a
  concrete layout improvement; two-texture artwork crossfade requires evidence the existing fade is insufficient.

## Checkpoint discipline

- [ ] For each landed slice: compile changed Python, run focused falsifying tests, inspect diff, update this live
  checklist and durable navigation/contracts, then narrow commit + push.
- [x] Ran all 115 maintained destination targets; fixed new-feature failures and documented nine unrelated
  red targets in `Future_Cleanup.md`. Focused reruns close changed contracts; the whole profile is not green.
- [x] Later 117-target run completed (105 passed / 12 failed): nine known unrelated targets plus the active
  CUSTOM change, a midpoint-capture fixture race and one non-reproduced native S-hotkey fault. Resolve changed
  contracts with focused reruns; keep the native fault Awaiting Logs. The whole profile is still not green.
- [ ] Keep physical/installed/visual acceptance open where automated evidence cannot close it.

## Awaiting validation

- [ ] After FW1 lands: inspect hover/click appearance, action passthrough, Ctrl/context-menu suppression and
  CUSTOM/mixed-DPR transfer in a real runtime.
- [ ] After FW2 lands: inspect Slide settlement and motion at representative resolution/refresh; black/stale=0
  remains mandatory.
