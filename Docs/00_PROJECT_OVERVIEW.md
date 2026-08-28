# Project Overview

Last updated: 2026-08-29

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

Exact sequence and source checkpoint live only in `Current_Plan.md`; this overview deliberately does not carry a commit hash.

- F0–F8 closed;
- G1–G3 closed;
- G4 core independent viewport-extent resize, Bubble logical reflow and all-five-mode capability policy landed; a bounded
  post-checkpoint audit correction batch is priority before G7 resumes;
- G5 cross-display retained transfer closed;
- G6 retained input/semantic family actions closed;
- G7 retained dimming/pixel shift, halo and context menu landed and needs caller-proof closure;
- G8 MC/focus closure follows;
- the complete GREEN G checkpoint receives one independent audit before H;
- H finalizes production Quick orchestration and removes the remaining physical host;
- I is residue; J is final installed/physical acceptance.

## Visualizer geometry

All five current visualizer modes support the destination scale/extent model:

```text
wheel/corners -> uniform scale
left/right    -> viewport width
top/bottom    -> viewport height
```

Bubble is included and its capability policy is no longer an accepted place to hide missing reflow. Current G4 correction
work is narrower: committed-vs-CUSTOM viewport configuration ownership plus a few Bubble nonbaseline spatial edge cases.
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
