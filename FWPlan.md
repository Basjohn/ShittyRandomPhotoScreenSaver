# Future Work implementation plan

Last updated: 2026-09-05

The operator explicitly activated implementation from `Future_Work.md`. This file owns that work's live
sequence; `Current_Plan.md` retains unrelated J/product work and physical/log validation. Inspect exact
current source before each slice. Starting comparison HEAD: `0fd64b3d002834614131b46581e41fe497d5cbc5`.

## Active sequence

- [x] **Geometry-only Edit Save continuity:** retained geometry/extent is promoted in place and the operator reports
  Save is flowing extremely well without teardown, stale re-entry, or a visible restart. Keep this as the normal
  same-display path; topology-changing operations remain explicit reconciliation.
- [~] **Priority — Visualizer cross-display ownership transfer:** the 03:40-03:45 run produced 432 occupied-target QML
  warnings plus one surviving `QuickDisplayVisualizerOwner` at the destruction barrier. Source repair moves the active
  runtime/frame-pacer/bind/retirement edge with the retained scene and permits one crossing per pointer gesture. A small
  theme-palette left/right arrow control is now also present on the Visualizer CUSTOM frame; it routes through the same Python
  owner seam and preserves shape/relative placement without inventing another transfer authority. Await physical proof of both
  drag and button transfer. Do **not** add source/target fades until the operator run shows they improve the experience.
- [x] **Bubble main outlines at extremes:** reduced full main-outline width by another logical pixel at
  large sizes through the existing visible-area transition. Small/canonical and Ghost styling remain intact.
  Three real-GL tests pass, including same-area wide/tall outlines; physical weight acceptance remains open.

- [~] **Priority — Visualizer geometry/glow and Sphere validation:** live edit geometry is nearly correct
  by operator report. Sphere now has vocal deformation, independent size pulse, adjustable base/reactive bump,
  diffuse fire/smoke/ash/lava and translucent Water with rounded blobs. Focused GL/settings checks and actual
  preset captures pass; physical music/appearance acceptance remains open. Close the glow and edit-exit rows
  below before queued Slide/widget-glow refinements. Live decomposition:
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

- [~] **Widget interaction glow hold/fade controls — SOURCE IMPLEMENTED / PHYSICAL ACCEPTANCE OPEN:**
  `input.widget_glow_intensity` is now a settings-owned 0-100% slider projected once into the immutable Quick
  input snapshot. Hover fades in on the existing `HoverHandler` edge, remains settled while hovered, and fades
  gently only when hover state ends. Click is no longer a self-decaying one-shot pulse: one admitted window
  press selects the top retained ordinary card as `widgetGlowClicked`; it remains settled as the last-clicked
  target until another admitted press selects another card or empty space, then fades out. Child semantic actions
  still own their click; the observer adds no foreground MouseArea. Physical follow-up found 100% too weak and missing
  on the Visualizer plus incorrectly framed on shell-less Digital Clock. The follow-up therefore strengthens the same
  event-held primitive, projects it around the retained Visualizer viewport/frame, and lets Digital Clock use intrinsic
  content bounds when its card shell is absent. No Timer, poller, worker, frame loop or new persistence/cadence owner.
  Real Quick strength/geometry still needs operator eyes.

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
  a logical-cadence elastic/breathing spring with a much larger high-setting ceiling and makes Magma fissure bump relief
  explicitly inward. Operator acceptance says the new size motion feels substantially better; Deformation and Vocal
  Response now expose a 3.0 upper range (50% above the prior 2.0 cap) while defaults remain unchanged. `Future_Work.md` now records Block Spins + Sphere as the two-consumer proof for a small dormant 3D
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
