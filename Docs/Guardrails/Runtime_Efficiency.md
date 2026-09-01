# Runtime Efficiency / Change Safety Guardrails

Last updated: 2026-09-01

Core principle:

> SRPSS stays fast by removing useless work and bad ownership, not by reducing authored work.

Canonical performance admission/acceptance checklist and reference envelopes: `Docs/Guardrails/Performance_Optimization_Contract.md`.

## 1. Architecture baseline

Accepted destination:

- one standalone threaded `QQuickWindow` per physical display;
- one `VisualizerLogicalRuntime` for authored visualizer cadence;
- Python/QWidget Settings and service/model logic retained where appropriate.

The old QRhiWidget/GLCompositor physical presenter is deleted and must not be restored as an optimization fallback or test convenience.

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


## 3A. Visualizer performance safety after H

R-71 is the accepted performance boundary: one persistent serial `visualizer.audio_analysis` lane, one in-flight + newest pending source, retained detached DSP state across ordinary frames, and explicit rebuild/fencing at real config/activation/reset epochs. No generic per-frame Future/task fallback.

R-69 is the performance admission veto. A change is **not** an optimization if it improves GC/FPS/skip counters by weakening visible musical response, shrinking Bubble head/radius deltas with viewport extent, suppressing Ghost/history displacement, lowering authored cadence, increasing source/snapshot age, or coalescing away protected transient edges. Apply the same rule to all Visualizer modes.

Rare deep GC pauses remain late-J evidence debt. `Docs/Guardrails/Performance_Optimization_Contract.md` owns the target order: rare active latency tails and exact allocation/lifetime mechanisms first; raw GC count, average FPS, CPU/GPU and resource counts are secondary. Change GC thresholds/lifetime policy only from a measured mechanism; do not tune collection counters in isolation.

The 2026-09-01 modest-load reference also showed why: perceived quality was excellent with ~89.9 Hz logical Visualizer publication and ~20 ms median snapshot age while the worst gen-2 pause fell to ~67.7 ms. Protect that freshness/latency shape rather than optimizing one counter.

A paired later log comparison strengthens the mechanism: every sampled Gen2 event aligned with a Bubble wall-clock gap of similar duration, including ~41–47 ms Gen2 scans that collected zero objects in the lighter run, while Bubble's own compute/cadence counters stayed healthy. Treat wall-clock inter-tick time + GC callback duration/yield as the attribution seam; internal per-tick work timing alone cannot see a process-wide stop-the-world pause. Non-GC stalls remain a separate J attribution track.

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
