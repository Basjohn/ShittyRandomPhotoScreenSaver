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
- [ ] **FW2 — Slide motion options:** inspect the current sealed Slide owner; commit its decomposition before
  implementation. Implement Elastic first, then Wobble/Flex where sealed coverage and exact endpoints can be proved.
  Assess true Perspective separately; do not counterfeit it with a 2D effect.
  Decomposition: `Docs/Future_Work/Slide_Motion_Options_Decomposition.md`. Elastic/Wobble/Flex implemented;
  final visual/pixel verification and checkpoint pending.
- [ ] **FW3 — Deformable Sphere:** inspect current mode descriptor/runtime/renderer/Settings closure; create the
  required detailed foundation inventory and decomposition before substantial coding. Keep the experiment dormant
  by default and preserve existing modes' authored response.
  Required decomposition committed: `Docs/Future_Work/Sphere_Visualizer_Decomposition.md`.
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
- [ ] Run the maintained destination profile at a meaningful integration checkpoint; classify unrelated failures
  in `Current_Plan.md` / `Future_Cleanup.md` without reviving obsolete owners.
- [ ] Keep physical/installed/visual acceptance open where automated evidence cannot close it.

## Awaiting validation

- [ ] After FW1 lands: inspect hover/click appearance, action passthrough, Ctrl/context-menu suppression and
  CUSTOM/mixed-DPR transfer in a real runtime.
- [ ] After FW2 lands: inspect Slide settlement and motion at representative resolution/refresh; black/stale=0
  remains mandatory.
