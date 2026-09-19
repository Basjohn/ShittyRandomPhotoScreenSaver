# Runtime Efficiency / Change Safety Guardrails

Core principle:

> SRPSS stays fast by removing useless work and bad ownership, not by reducing authored work.

Canonical performance admission/acceptance checklist and reference envelopes: `Docs/Guardrails/Performance_Optimization_Contract.md`.

## 1. Architecture baseline

Accepted runtime:

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

Under the current architecture, distinguish:

- GUI-thread work;
- Quick render-thread work;
- Python/GIL contention;
- logical-runtime scheduling;
- provider/source latency;
- OS compositor/presentation pressure.

Do not infer that moving presentation to a render thread makes GUI or Python contention irrelevant.

Do not infer that any remaining heavy-load hole proves a C++ presenter is required.


## 3A. Visualizer performance safety

R-71 is the accepted performance boundary: one persistent serial `visualizer.audio_analysis` lane, one in-flight + newest pending source, retained detached DSP state across ordinary frames, and explicit rebuild/fencing at real config/activation/reset epochs. No generic per-frame Future/task fallback.

R-69 is the performance admission veto. A change is **not** an optimization if it improves GC/FPS/skip counters by weakening visible musical response, shrinking Bubble head/radius deltas with viewport extent, suppressing Ghost/history displacement, lowering authored cadence, increasing source/snapshot age, or coalescing away protected transient edges. Apply the same rule to all Visualizer modes.

Performance work is symptom-driven against the accepted golden. GC attribution is useful only when a reproduced hitch implicates collection pauses: correlate wall-clock inter-tick gaps with GC callback duration/yield instead of inferring cost from collection count. Do not retune GC thresholds, forced-collection timing or Visualizer cadence without a current mechanism-specific failure. `Docs/Guardrails/Performance_Optimization_Contract.md` owns the admission and acceptance criteria.

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

### Speculative image derivative isolation

The dedicated speculative image worker is an approved isolation boundary, not a second presentation owner. Preserve all of these together:

- foreground requested-image work stays on the foreground image path; speculative work must never head-of-line block it;
- derivative backlog/byte budgets and latest-useful/generation ownership stay parent-owned and bounded; admit at most one speculative application request to the child at a time;
- generation invalidation must abandon/tombstone the correlation so late or shared-memory results cannot publish stale cache truth;
- worker unavailable/failing means speculative warmup is skipped. **Do not silently fall back to the main-process compute pool**;
- the worker may return detached image data/cache candidates only. It must not mutate Qt/Quick/GPU presentation state;
- lower OS scheduling priority is best-effort isolation, never permission to reduce foreground cadence/reactivity or useful cache semantics.
- speculative completion is owned by `ProcessSupervisor`, not by a generic ThreadManager executor slot: one persistent daemon listener may block on a worker response queue, but **never** one waiter/thread/timer per request;
- while that listener is active it is the **single response-queue reader** for the worker. It must route heartbeat/control messages, deliver registered correlations, and buffer unmatched replies for existing synchronous waiters rather than racing `await_response()`/health drains;
- abandonment and routing share one tombstone authority. Recheck tombstones after dequeue/before callback so a generation clear racing delivery still reclaims inline/shared-memory payloads and cannot publish stale cache truth;
- worker stop/restart/shutdown must cancel registered callbacks so parent single-flight/cache ownership cannot remain wedged after child death; callbacks may complete detached cache candidates only and must never mutate Qt Quick/GPU state.

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

It is not an architectural escape hatch from the accepted Quick ownership model.

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
