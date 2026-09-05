# Future Work implementation plan

Last updated: 2026-09-05

The operator explicitly activated implementation from `Future_Work.md`. This file owns that work's live
sequence; `Current_Plan.md` retains unrelated J/product work and physical/log validation. Inspect exact
current source before each slice. Starting comparison HEAD: `0fd64b3d002834614131b46581e41fe497d5cbc5`.

## Active sequence

- [~] **Priority — Visualizer geometry/glow and Sphere validation:** live edit geometry is nearly correct
  by operator report. Sphere now has vocal deformation, independent size pulse, adjustable base/reactive bump,
  diffuse fire/smoke/ash/lava and translucent Water with rounded blobs. Focused GL/settings checks and actual
  preset captures pass; physical music/appearance acceptance remains open. Close the glow and edit-exit rows
  below before queued Slide/widget-glow refinements. Live decomposition:
  `Docs/Future_Work/Visualizer_Edit_Geometry_And_Sphere_Materials.md`.

- [~] **Visualizer glow regression — Sine/Oscilloscope:** operator reports absent visualizer glows after
  line improvements. Trace actual preset/configuration through the immutable draw state and shader at small,
  normal and large scales; repair the owning seam with a real GL coverage test while preserving line AA/colour.
  Confirmed in both playback and Edit Layout. Latest screenshot/short-run evidence is archived under
  `logs/evidence_chest/fw_missing_line_glow_2026_09_05`; test-only glow alpha is not visual acceptance.
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

- [ ] **Early follow-up — Widget interaction glow hold/fade controls:** only after the active Visualizer
  geometry and Sphere-quality slice is implemented and visually checked, create a technical decomposition
  before implementation. Add a settings-owned intensity control and make hover/click fade-in and fade-out
  three times slower. Retain hover glow while the Cursor Halo is over the widget and click glow while that
  widget remains the last clicked target until a click elsewhere; end each prerequisite through existing
  events, then fade gently. Do not add a timer, poller or new persistence owner: if sustained glow cannot
  remain event-owned, omit that sustained behavior while retaining intensity and slower finite fades.

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
- [~] **FW3 — Deformable Sphere — motion restored; material expansion active:** dormant-by-default 3D mesh, five material presets including Water,
  bump/detail controls, source-fenced immutable capture, lazy Settings and event-only inactive GPU retirement.
  Real Quick captures inspected and relevant automatic gates passed; physical acceptance remains separate.
  Detailed evidence: `Docs/Future_Work/Sphere_Visualizer_Decomposition.md`.
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
