# Presentation / Cadence Change Preflight

Last updated: 2026-08-24

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

The old `DisplayWidget`/QRhiWidget/`GLCompositorWidget` physical presenter may remain until H. It is
current-legacy and is deleted at H cutover, not a runtime rollback architecture.

Old transition/visualizer pixel-only implementations may disappear earlier on caller proof.

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
- broad second native/C++ physical-presenter migration.

## Before changing a renderer

Ask:

1. Is the defect renderer cost, scheduling, logical cadence or resource ownership?
2. Is the current Quick primitive measured as the limiting factor?
3. Can the change remain inside the one `QQuickWindow`?
4. Does it preserve authored fidelity?
5. Does it preserve one logical clock and latest-state semantics?
6. Are you accidentally preserving an old pixel owner that is already caller-dead?

Do not resurrect old presentation as an escape hatch.

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
- BTF when Bubble is affected.

Average FPS alone never closes a presentation gate.
