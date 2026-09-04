# Future Work implementation plan

Last updated: 2026-09-05

The operator explicitly activated implementation from `Future_Work.md`. This file owns that work's live
sequence; `Current_Plan.md` retains unrelated J/product work and physical/log validation. Inspect exact
current source before each slice. Starting comparison HEAD: `0fd64b3d002834614131b46581e41fe497d5cbc5`.

## Active sequence

- [x] Read backlog, current navigation/contracts and repository guardrails; preserve the clean starting tree.
- [x] **FW1 — Widget interaction glow:** two Interaction switches, theme-inheriting shared swatch, one retained
  shader/quad and finite event-driven feedback. 64 focused tests passed; real Quick peak capture inspected.
  Detailed ownership and acceptance: `Docs/Future_Work/Widget_Interaction_Glow_Decomposition.md`.
- [x] **FW2 — Slide motion options:** Elastic, Wobble and Flex are implemented in the sealed Slide owner with frozen
  per-run style resolution, exact endpoints and real-GL coverage. Perspective remains a separately designed feature;
  do not counterfeit it with a 2D effect.
  Decomposition: `Docs/Future_Work/Slide_Motion_Options_Decomposition.md`.
- [x] **FW3 — Deformable Sphere:** dormant-by-default 3D mesh, five material presets including Water,
  bump/detail controls, source-fenced immutable capture, lazy Settings and event-only inactive GPU retirement.
  Real Quick captures inspected and relevant automatic gates passed; physical acceptance remains separate.
  Detailed evidence: `Docs/Future_Work/Sphere_Visualizer_Decomposition.md`.
- [x] **Bubble aspect/response investigation and bounded optimization:** after Sphere checkpoint `66be7344`,
  traced/documented height-based radius versus field occupancy, fixed the proven local-highlight aspect defect,
  and removed measured immutable-tuple reconstruction (`139aed21`). Preserved canonical pixels, authored
  response, consume-once events and cadence. Evidence and remaining physical/log checks:
  `Docs/Future_Work/Bubble_Aspect_And_Presentation_Decomposition.md`.
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
- [ ] Keep physical/installed/visual acceptance open where automated evidence cannot close it.

## Awaiting validation

- [ ] After FW1 lands: inspect hover/click appearance, action passthrough, Ctrl/context-menu suppression and
  CUSTOM/mixed-DPR transfer in a real runtime.
- [ ] After FW2 lands: inspect Slide settlement and motion at representative resolution/refresh; black/stale=0
  remains mandatory.
