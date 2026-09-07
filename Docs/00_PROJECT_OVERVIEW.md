# Project Overview

Last updated: 2026-09-07

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

The old `DisplayWidget` / QRhiWidget / `GLCompositorWidget` physical path was removed by H after caller proof. It is not rollback architecture, a supported fallback, or something agents should reconstruct to satisfy stale tests.

## Current migration position

Exact sequence and source checkpoint live only in `Current_Plan.md`; this overview deliberately does not carry a commit hash.

- F/G/H and caller-proven Phase-I cleanup are closed; Quick is the sole production presentation authority.
- Visualizer CUSTOM/lifecycle closeout and Bubble reference parity are closed evidence.
- remaining migration-close work is product-readiness/build/install/physical acceptance and any specifically admitted current regression; exact status/sequence lives only in `Current_Plan.md`.
- surviving cleanup/deletion debt belongs in `Future_Cleanup.md`; deferred product work belongs in `FWPlan.md` / focused Future Work references. Closed migration slices are not re-opened merely because their decompositions remain on disk.

## Visualizer geometry

Visualizer mode identity now has two useful sets: five established carded technical modes (Spectrum, Oscilloscope, Sine, Bubble, DevCurve) plus the separately registered experimental Sphere. All registered modes use the destination scale/extent ownership model; Sphere is FRAMELESS + VIEWPORT_RECT and dormant by default.

```text
wheel/corners -> uniform scale
left/right    -> viewport width
top/bottom    -> viewport height
```

Bubble is included and its capability policy is no longer an accepted place to hide a reflow defect. Committed runtime viewport truth is distinct from the temporary CUSTOM working override. Viewport changes reconfigure the spatial domain while preserving BTF; they never stretch finished pixels or redefine simulation cadence.

**R-69 is golden:** wide/tall adaptation may not globally compress Bubble renderer-facing head radius, already-normalized Ghost/history displacement, or another mode's authored musical response/freshness. If an extreme full-expansion visual tail is too large, fix only that proven tail. Audio analysis remains one persistent newest-source serial lane with retained DSP state; performance work may not lower authored cadence or increase visible staleness.

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
