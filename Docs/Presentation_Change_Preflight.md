# Presentation / Cadence Change Preflight

Last updated: 2026-08-28

Read before changing physical presentation, visualizer delivery, cadence or render-state ownership.

## Accepted architecture

```text
one display
-> one standalone threaded QQuickWindow
-> one retained scene

VisualizerLogicalRuntime
-> sole authored visualizer cadence
-> latest bounded state
-> Quick presentation
```

Legacy `DisplayWidget`/QRhiWidget/`GLCompositorWidget` source may survive until H only where still physically wired. It
is not rollback architecture and **does not need to remain a functioning product during migration**. Do not rebuild old
pixels for continuity.

## Rejected

- producer display-rate divisor;
- pending-until-paint admission;
- paint/swap acknowledgement;
- catch-up replay;
- source/event decimation;
- separate visualizer presentation surface;
- GUI recurring timer as visualizer simulation owner;
- per-mode visualizer logical clocks;
- `QQuickWidget` runtime presenter;
- old compositor/software presenter fallback;
- broad second native/C++ physical-presenter migration;
- anisotropic stretching in place of visualizer viewport reflow.

## Visualizer geometry preflight

Do not collapse these operations:

```text
wheel / corner handles -> uniform_visual_scale
left/right edge        -> viewport width
 top/bottom edge       -> viewport height
```

All five current modes, including Bubble, must support the viewport operation. Bubble viewport changes are spatial
configuration and remain subordinate to BTF; they are not grounds for algorithm/cadence retuning.

## Before changing a renderer

Ask:

1. Is the defect renderer cost, scheduling, logical cadence, geometry or resource ownership?
2. Is the current Quick primitive measured as the limiting factor?
3. Can the change remain inside the one `QQuickWindow`?
4. Does it preserve authored fidelity?
5. Does it preserve one logical clock and latest-state semantics?
6. Are you accidentally preserving an old pixel owner that is caller-dead?
7. If source contradicts a durable destination contract, is this actually missing implementation rather than a doc to delete?

## Acceptance

Use the relevant subset:

- deterministic/source contract tests;
- visual fidelity/goldens;
- authored scheduler health;
- source freshness/state age;
- physical p95/p99/max gaps;
- 60 Hz + high-refresh behavior;
- multi-display/DPR;
- startup/reveal;
- Settings/recreate/topology;
- CUSTOM Save/Cancel and scale/viewport round-trip;
- BTF whenever Bubble is affected.

Average FPS alone never closes a presentation gate.
