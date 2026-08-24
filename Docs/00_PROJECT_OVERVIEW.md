# Project Overview

Last updated: 2026-08-24

SRPSS is a Windows screensaver/media runtime with multi-display image presentation, accelerated
transitions, a high-fidelity multi-mode visualizer, configurable runtime overlays and durable settings.

## Current architecture epoch

Accepted destination:

```text
one physical display
-> one standalone threaded QQuickWindow
-> one retained Quick scene
-> inline custom GL for transitions/visualizer
```

Settings/providers/persistence/media/orchestration/logical runtimes remain Python/QWidget where
appropriate.

The old `DisplayWidget` / QRhiWidget / `GLCompositorWidget` physical path is temporary current-legacy
until H cutover. It is not a supported fallback presenter.

## Current migration position

**Phase F is active.**

Current exact reviewed checkpoint:

```text
a586801d2ffe0868710fc23da1a649df1d122d29
F0.5 implemented
independent audit YELLOW — narrow sidecar-derived constant cleanup before F1
```

After F0.5 GREEN: F1 Clock is the first retained ordinary-family port.

`Current_Plan.md` owns exact sequencing.

## Legacy retirement

- ordinary family old pixels: delete after that family GREEN;
- transition/visualizer old pixel-only implementations: delete on caller proof, potentially before H;
- physical old presenter/backend: delete at H;
- I: residue only.

Keep old code as live reference only where it is still genuinely needed to reproduce an unported family.

## Visualizer

`VisualizerLogicalRuntime` remains the one mode-general authored visualizer clock.

Quick changes the presentation consumer, not authored logical cadence.

All current modes use retained card shell + inline GL content; Bubble timing/fidelity remains bound by
`Docs/Guardrails/Bubble_Temporal_Fidelity.md`.

## Read order

```text
exact source
-> Current_Plan.md
-> relevant focused current contract
-> tests/evidence
```

Do not read all historical plans by default.
