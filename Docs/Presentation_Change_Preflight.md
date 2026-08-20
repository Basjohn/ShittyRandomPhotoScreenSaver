# Presentation / Cadence Change Preflight

Last updated: 2026-08-20

Read before changing physical presentation, visualizer delivery, cadence, or render-state ownership.

## 1. Accepted architecture epoch

Destination:

```text
one display
    -> one standalone QQuickWindow
    -> threaded Qt Quick scene graph

visualizer logical cadence
    -> one VisualizerLogicalRuntime

visualizer/runtime pixels
    -> layers/items inside the one Quick scene
```

During migration the QRhiWidget presenter may still exist as the reference implementation. Do not
treat it as the destination.

## 2. Rejected mechanisms

| Mechanism | Status |
|---|---|
| producer display-rate divisor | rejected |
| pending-until-paint admission | rejected |
| paint/swap acknowledgement | rejected |
| catch-up replay | rejected |
| source/event decimation | rejected |
| separate visualizer presentation surface | rejected |
| GUI recurring timer as visualizer simulation owner | rejected |
| AnimationManager as visualizer simulation owner | rejected |
| per-mode logical clock | rejected |
| `QQuickWidget` runtime presenter | rejected |
| broad C++ physical-presenter phase two | not planned |

## 3. Logical / physical boundary

```text
audio/events
    -> source owner
    -> VisualizerLogicalRuntime
    -> latest logical/render state
    -> bounded Quick synchronization
    -> Quick render owner
    -> physical presentation
```

Physical presentation may sample latest current state.

It may not redefine logical time or event cadence.

## 4. Quick synchronization

A synchronization bridge may coalesce state and prepare render-thread-safe snapshots.

It may not:

- require one GUI callback per logical tick;
- hold producer admission until paint;
- build an unbounded queue;
- allow stale generation state to cross into a replacement scene.

## 5. Readiness

Ask separately:

```text
is intentional presentation drawable?
is reactive source authoritative?
```

Do not require real source identity for a presentation-owned idle scene.

Do not fabricate source identity.

## 6. Renderer changes

Before changing renderer primitive ask:

1. Is the defect presentation scheduling, renderer cost, or resource ownership?
2. Is the current Quick primitive actually measured as the limiting factor?
3. Can the change stay inside the existing `QQuickWindow`?
4. Does it preserve one-surface-per-display?
5. Does it preserve fidelity and lifecycle semantics?

Do not jump from a local renderer issue to a native-window rewrite.

## 7. Instrumentation proportionality

Add a new probe only when it distinguishes materially different remaining designs.

Do not keep expanding the completed P0 benchmark.

## 8. Required acceptance

For presentation changes use the relevant subset of:

- visual fidelity/goldens;
- logical scheduler health;
- one logical clock;
- source freshness;
- state-to-render age;
- physical p95/p99/max gaps;
- severe-gap counts;
- 60 Hz behaviour;
- high-refresh behaviour;
- no callback/backlog growth;
- no additional accelerated surface;
- BTF when Bubble is affected;
- startup/reveal visual review;
- Settings/recreate/topology lifecycle.

Average FPS alone never closes the gate.
