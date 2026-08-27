# Project Overview

Last updated: 2026-08-28

SRPSS is a Windows screensaver/media runtime with multi-display image presentation, accelerated transitions, a
high-fidelity multi-mode visualizer, configurable runtime overlays and durable settings.

## Accepted architecture

```text
one selected physical display
-> one QuickDisplayRuntime
-> one standalone threaded QQuickWindow
-> one retained Quick scene
-> inline custom GL for transitions/visualizer
-> retained Quick ordinary widgets / CUSTOM / auxiliary pixels
```

Settings, providers, persistence, media/business orchestration and logical runtimes remain Python/QWidget where
appropriate.

The old `DisplayWidget` / QRhiWidget / `GLCompositorWidget` physical path may still exist in source until H. It is
migration scaffolding, not a supported fallback and not something agents should preserve to keep the partially migrated
application runnable.

## Current migration position

Reviewed source checkpoint: `59f4a3c98235215a9ff89fc09e4cc979d1831e89`.

- F0–F8 closed;
- G1 neutral session/variants/layout slots closed;
- G2 retained edit overlay/family binding closed;
- G3 Save/Cancel/enabled persistence closed;
- G4 retained corner/wheel uniform resize landed, but independent visualizer viewport-edge resize was missed and is now
  the first correction;
- G5 cross-display retained transfer closed;
- G6 retained input/semantic family actions closed;
- G7 retained dimming/pixel shift, halo and context menu landed and is near closure;
- G8 MC/focus closure follows;
- H finalizes production Quick orchestration and removes the remaining physical host;
- I is residue; J is final installed/physical acceptance.

`Current_Plan.md` owns exact sequence.

## Important visualizer geometry correction

All five current visualizer modes must support independent viewport extent as well as uniform whole-size scale:

```text
wheel/corners -> uniform scale
left/right    -> viewport width
top/bottom    -> viewport height
```

Bubble is included. Its current source capability gate is unfinished migration state, not intended product behavior.
Viewport changes reconfigure the spatial domain while preserving BTF; they never stretch finished pixels or redefine
simulation cadence.

## Ordinary widget pattern

```text
neutral runtime/backend
-> coherent accepted state
-> stable presentation model
-> retained family QML
-> OrdinaryWidgetPresentationHost
```

## Migration continuity policy

A fully functioning legacy screensaver between migration slices is not required. Do not rebuild caller-dead QWidget/
compositor presentation merely for temporary continuity. Destination ownership and focused proof come first; full
product acceptance is J.
