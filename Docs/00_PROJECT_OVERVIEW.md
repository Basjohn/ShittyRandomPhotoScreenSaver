# Project Overview

Last updated: 2026-08-26

SRPSS is a Windows screensaver/media runtime with multi-display image presentation, accelerated transitions,
a high-fidelity multi-mode visualizer, configurable runtime overlays and durable settings.

## Current architecture epoch

```text
one selected physical display
-> one standalone threaded QQuickWindow
-> one retained Quick scene
-> inline custom GL for transitions/visualizer
-> retained Quick ordinary widgets
```

Settings, providers, persistence, media/business orchestration and logical runtimes remain Python/QWidget
where appropriate.

The old `DisplayWidget` / QRhiWidget / `GLCompositorWidget` physical path remains temporary current-legacy
until H. It is not a supported fallback presenter.

## Current migration position

Exact reviewed checkpoint:

```text
c6af1260b695e35b802e7b70ddcbb2277ef0100a
5.0.0 - Phase F6 Partial
```

- F0/F0.5 closed;
- F1 Clock through F5 Reddit/Reddit2 closed;
- F2–F5 independently re-audited GREEN as an integrated run;
- F6 Gmail active: stable retained model plus partial retained QML/wrapper landed;
- one shared Quick import-dormancy correction is required in F6 before real Gmail owner injection;
- G handles CUSTOM/input;
- H is normal-production Quick physical cutover;
- I is residue; J is final installed/physical closure.

`Current_Plan.md` owns exact sequence.

## Ordinary widget pattern

```text
neutral runtime/backend
-> coherent accepted state
-> stable presentation model
-> retained family QML
-> OrdinaryWidgetPresentationHost
-> OverlayWidget / OverlayCard / ShadowedText
-> display's one QQuickWindow
```

Delete old family pixels after replacement GREEN + caller proof; do not keep them to H merely as fallback.
See `Docs/10_WIDGET_GUIDELINES.md`.

## Visualizer

`VisualizerLogicalRuntime` remains the one mode-general authored visualizer clock. Quick changes the
presentation consumer, not authored logical cadence. Bubble fidelity remains governed by
`Docs/Guardrails/Bubble_Temporal_Fidelity.md`.

## Read order

```text
exact source
-> Current_Plan.md
-> relevant focused current contract
-> tests/evidence
```
