# Runtime Efficiency / Change Safety Guardrails

Last updated: 2026-08-20

Core principle:

> SRPSS stays fast by removing useless work and bad ownership, not by reducing authored work.

## 1. Architecture baseline

Accepted destination:

- one standalone threaded `QQuickWindow` per physical display;
- one `VisualizerLogicalRuntime` for authored visualizer cadence;
- Python/QWidget Settings and service/model logic retained where appropriate.

The old QRhiWidget presenter may remain during migration but is not a new optimization target.

## 2. No-op means no-op

Identical state should not trigger work that cannot change visible output.

Short-circuit before:

- stable cache rebuild;
- provider refresh;
- settings write;
- geometry replay;
- fade restart;
- worker submission;
- signal fan-out;
- Quick scene property churn;
- GPU resource regeneration.

## 3. Shared execution resources

After migration, distinguish:

- GUI-thread work;
- Quick render-thread work;
- Python/GIL contention;
- logical-runtime scheduling;
- provider/source latency;
- OS compositor/presentation pressure.

Do not infer that moving presentation to a render thread makes GUI or Python contention irrelevant.

Do not infer that any remaining heavy-load hole proves a C++ presenter is required.

## 4. Runtime overlays

Provider/model work and pixel presentation are separate.

Prefer:

```text
provider/model update
-> compact immutable presentation state
-> Quick item/layer update
```

Avoid doing network/cache/provider work in render synchronization or render callbacks.

## 5. Threads / queues

Adding a thread is justified only by cleaner ownership and measured benefit.

Forbidden:

- duplicate clocks;
- duplicate lifecycle owners;
- worker-to-paint handshake;
- unbounded queues;
- catch-up replay;
- GUI/Quick/GPU mutation from logical workers.

## 6. Startup / recreation

Prepare deterministic current-generation work while hidden where legal.

Reveal on readiness, not fixed sleeps.

Do not move expensive initialization into the first visible seconds to make startup counters look
better.

## 7. Minor optimization admission

Before landing an optimization answer:

1. what work disappears?
2. which owner performs the remaining work?
3. what visible result stays identical?
4. what mechanism is removed?
5. what mechanism is added?
6. does physical p95/p99/max improve or remain healthy?
7. does lifecycle remain correct?

If machinery increases and named work does not disappear, it is probably not an optimization.

## 8. Native code

Native code requires evidence of a specific local bottleneck.

It is not an architectural escape hatch from doing the Quick migration correctly.

Any native renderer remains subordinate to the one-Quick-window-per-display topology.

## 9. Evidence proportionality

Use:

```text
exact source
-> existing evidence
-> focused runtime-shaped gate
-> bounded correction
```

Do not create another investigation programme for an already-selected architecture.
