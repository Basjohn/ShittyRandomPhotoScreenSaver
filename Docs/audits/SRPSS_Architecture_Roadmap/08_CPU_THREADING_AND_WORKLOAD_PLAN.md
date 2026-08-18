# 08 — CPU, Threading, and Workload Architecture

Last reconciled: 2026-08-18  
Status: **stable architecture/reference only; `Current_Plan.md` owns execution**

This document describes workload ownership under the current QRhi/single-surface architecture. It
does not define phase order.

---

## 1. Goal

Make SRPSS cheap by removing waste while preserving:
- authored visualizer reaction/fidelity;
- transition fidelity;
- source freshness;
- multi-display support;
- strict lifecycle/resource ownership.

Do not improve efficiency by reducing cadence, refresh opportunity, source/event rate or quality.

---

## 2. Core model

Prefer:

```text
Prepare -> Commit -> Present
```

Prepare:
- network/file IO;
- parsing/filtering/sorting;
- QImage/plain-data work;
- finite worker-safe simulation/calculation;
- immutable result assembly.

Commit:
- generation/staleness validation;
- minimal QWidget/QPixmap/GL mutation on legal owner;
- cache/revision publication.

Present:
- compositor consumes current prepared state;
- no hidden simulation clock;
- no disk/network/model construction.

Persistence is a separate ordered process-scoped service where durability/order require it.

---

## 3. GUI thread

Keep only work that actually requires GUI/context ownership:
- QObject/QWidget lifetime;
- geometry/visibility/input;
- QPixmap mutation/promotion;
- QRhi/GL create/delete/render;
- narrow current-generation commits;
- compositor presentation scheduling callback.

Remove or avoid:
- synchronous network/file IO;
- repeated JSON/serialization;
- duplicate static/cache raster construction;
- unchanged shadow/card regeneration;
- broad pure-data preparation;
- per-frame diagnostic/log formatting;
- useless physical repaints of unchanged immutable state.

---

## 4. Visualizer logical runtime

The visualizer logical authority is independent from compositor paint.

Protect:
- one authoritative logical cadence;
- all authored dt/events/transients;
- smoothing;
- mode-specific history/state;
- one-in-flight/latest-fresh analysis;
- generation fencing.

Current GUI-QTimer service is a known architectural pressure point only if ordinary logical gaps
survive current GUI-waste removal.

If promoted, the preferred larger design is:

```text
Qt-free logical visualizer runtime
    -> dedicated logical cadence owner
    -> immutable latest render state
    -> GUI/compositor consumer
```

Do not move the existing QWidget-touching `_on_tick()` wholesale onto a worker.

The extraction must first separate logical state mutation from QWidget/QPixmap/GL/presentation
mutation.

---

## 5. Bubble compute

The rejected persistent Bubble scheduler is a negative control, not a dormant optimization.

Current approved semantics:
- one lane-free authored step;
- one in flight;
- no FIFO/backlog;
- no catch-up;
- exact event/dt semantics;
- stale generation result rejected.

Current `BubbleComputeLane` is intentionally a facade over the ordinary COMPUTE executor.

If task/Future churn later proves meaningful, a replacement mechanism may be designed, but it must
start from those accepted semantics and pass full trajectory/event goldens.

Do not reactivate the rejected persistent scheduler.

---

## 6. IO ownership and lifecycle

“Runs on IO” does not mean “safe to outlive the runtime.”

Runtime-owned provider work must:
- carry runtime generation/owner identity;
- become stale immediately on retirement;
- stop/cancel/cooperate promptly enough for the destruction barrier;
- never apply stale results.

Long blocking operations that truly need to survive display/runtime replacement may move to a
genuine process-scoped data service, but only if:
- service lifetime is really process-scoped;
- widget consumers are replaceable/generation-fenced;
- the service does not retain QWidget/runtime owners.

Do not weaken destruction barriers for slow IO.

---

## 7. Presentation workload

One display compositor owns physical presentation.

Allowed:
- display-rate deadlines;
- transition-active every-deadline eligibility;
- visualizer-only unchanged-scene suppression by scene revision;
- Qt coalescing after `QWidget.update()` is requested.

Forbidden:
- paint acknowledgement;
- pending-until-paint;
- producer paint scheduling;
- second visualizer timer;
- visualizer logical state evolving in paint;
- display-rate cap on logical source/simulation.

---

## 8. Caches and raster work

Every cache needs:
- stable identity/revision;
- explicit invalidation boundaries;
- bounded bytes/count where relevant;
- one owner;
- no stale-generation mutation.

Do not regenerate an identical frame shadow/card/static widget image because the caller happened to
paint again.

Worker-safe raster preparation may use QImage/plain data; QPixmap remains GUI-owned.

---

## 9. Process-scoped services

Appropriate examples:
- serialized settings writer;
- bounded logging writer;
- potentially provider data services whose lifetime genuinely exceeds display runtimes.

A process-scoped service must not hold stale QWidget/runtime ownership.

Process scope is not a loophole around lifecycle accounting.

---

## 10. Evidence proportionality

Do not instrument by reflex.

A probe is justified when:
- multiple plausible owners remain;
- the result will choose a concrete architecture/action;
- the decision threshold is known in advance.

When exact source plus existing evidence already identifies the bad boundary, prefer a bounded
refactor/replacement plus production-shaped tests.

The project explicitly allows replacing a structurally bad subsystem when that removes timers,
queues, state machines or ownership ambiguity and preserves the locked behaviour.

---

## 11. Efficiency acceptance

Track:
- logical/source age and cadence;
- GUI request/dispatch age;
- paint/render duration;
- CPU/GPU usage;
- task/queue depth;
- memory/GL resource plateau.

Interpretation:
- high FPS with low utilization is fine;
- a discrete GPU merely being awake is not a defect;
- high sustained utilization caused by unnecessary work is;
- reducing cadence/quality to lower utilization is not accepted.

Use same-machine before/after evidence as the available proxy for lower-end hardware.
