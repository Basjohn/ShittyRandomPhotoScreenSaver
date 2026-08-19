# Runtime Efficiency / Change Safety Guardrails

Last updated: 2026-08-19

Read this for:
- new widget families;
- settings/default changes;
- startup/recreation changes;
- provider/background-work changes;
- performance work;
- “small optimizations” that alter caches, timers, threads, queues, invalidation or runtime replay.

`Current_Plan.md` owns active execution. `Docs/Guardrails.md` and `Spec.md` remain the stable global
contracts. This file owns one focused principle:

> SRPSS stays fast by avoiding useless work and bad ownership, not by reducing authored work.

---

## 1. The 4.7.2 lesson

The 2026-08-19 baseline is an important negative control.

The visualizer modes had previously looked like a mode-performance problem. After shared runtime and
presentation waste was removed, all five modes returned to roughly the intended high logical cadence
and looked good without reducing their authored behavior.

Durable lesson:

- shared GUI/runtime starvation can masquerade as a widget/mode-specific performance problem;
- do not optimize the most visibly affected widget first unless current evidence names widget-owned
  work;
- remove shared duplicate/synchronous work before lowering fidelity, cadence or complexity;
- a “minor optimization” that adds another timer, queue, callback stream or invalidation owner can
  make the entire application worse even when its local benchmark looks better.

The named 4.7.2 baseline is evidence, not a permanent performance ceiling.

---

## 2. No-op must actually be no-op

An identical value, payload, style revision, geometry or activation must not cause technical work
that cannot change the authored result.

When applicable, short-circuit before:
- shadow/frame/card regeneration;
- QPixmap/raster rebuild;
- provider refresh;
- runtime reset;
- GL resource invalidation;
- settings write;
- runtime recreation;
- geometry replay;
- fade/reveal restart;
- worker submission;
- signal fan-out.

A setter that accepts the current value should normally return without invalidating downstream state.

Do not use “reapply everything to be safe” as a lifecycle strategy. Broad replay is acceptable only
when the replay is itself the canonical owner of state being reconstructed.

---

## 3. New widget budget

Every widget participates in a shared GUI/runtime budget even when it is visually independent.

A new widget must not:
- perform blocking provider/file/cache work in its constructor, paint path or ordinary GUI update;
- build expensive stable content on every paint;
- add a high-frequency private timer when event/state-driven invalidation is sufficient;
- add per-event GUI callbacks for data that can coalesce;
- duplicate a service/cache/settings/lifecycle owner already present;
- assume “its own 10 ms” is harmless because the widget is small.

Prefer:
- detached worker-safe preparation;
- one narrow GUI commit;
- cache identity/revision ownership;
- event/state-driven updates;
- stable content reused until its real identity changes.

For service-backed widgets, runtime-owned async work must carry generation/lifetime ownership and
retire promptly enough for the destruction barrier. Running on the IO pool is not sufficient if the
operation can outlive its runtime owner.

A process-scoped service is allowed only when its lifetime is genuinely process-scoped and its
runtime/widget consumers are generation-fenced.

---

## 4. Settings changes are not runtime events by default

Opening or hydrating Settings must not:
- contact providers;
- build live runtime widgets;
- start workers;
- walk large caches;
- invalidate live paint caches;
- cause runtime recreation merely because controls were populated.

Applying an unchanged setting must be a no-op where possible.

A setting change should trigger only the narrow owner that truly depends on it.

Do not broaden a local settings change into:
- full widget-family replay;
- full CUSTOM replay;
- full visualizer activation;
- full runtime recreation;
unless the current contract genuinely requires that boundary.

Cancel is not Save. Preview-only edits should normally be discarded by revealing/restoring the
unchanged live runtime, not by replaying every persisted setting into it.

---

## 5. Startup / recreation visible-work rule

Work required for normal smooth operation should not be deliberately dumped into the first visible
seconds merely because it is labelled “deferred.”

If expensive deterministic startup/recreation work:
- belongs to the current runtime generation;
- is required for ordinary near-term use;
- can be completed safely while presentation is still hidden/fade-zero;

prefer:

```text
prepare current generation
-> establish readiness
-> reveal
```

over:

```text
reveal
-> immediately compile/rebuild/warm everything
-> visible hitch
```

Do not replace readiness with a fixed sleep. The gate is completion of the real owned work.

Optional work that is genuinely unrelated to first-visible smoothness may remain deferred.

---

## 6. Minor optimization admission test

Before landing a performance optimization, answer:

1. **What work disappears?**
2. **Which owner currently performs it?**
3. **What visible result remains identical?**
4. **What new mechanism is introduced?**
5. **Does it add a timer/thread/queue/cache/generation/fallback/state machine?**
6. **If yes, which old mechanism does it replace?**
7. **Can identical input become a no-op?**
8. **Could this shift work into startup, Settings, CUSTOM, another display or another thread?**
9. **Does it preserve p95/p99/max behavior as well as average throughput?**
10. **Does the relevant production-shaped bar fail when the old waste/bug is reintroduced?**

If the change adds machinery but cannot name substantial removed work, it is probably not an
optimization.

---

## 7. Shared GUI availability is a product resource

The GUI thread is shared by:
- input;
- widgets;
- QPixmap and legal GUI commits;
- compositor dispatch;
- QRhi/GL ownership callbacks;
- Settings/Edit;
- lifecycle/recreation;
- visualizer logical timing while that owner remains GUI-timer serviced.

Therefore synchronous GUI work has a system-wide cost.

A 10–20 ms cache rebuild can damage a high-refresh transition or visualizer even if the cache owner
itself updates rarely.

Treat GUI availability like memory:
- finite;
- shared;
- measurable;
- easy to waste accidentally.

---

## 8. Do not blame the canary

A subsystem that exposes timing holes most clearly is not automatically the cause.

Before changing a mode/widget algorithm because it looks choppy or expensive, compare:
- its own compute/render cost;
- source/state cadence;
- GUI dispatch age;
- compositor paint cost;
- concurrent cache/provider/startup/recreation work.

If the subsystem's own work is small while service gaps are large, fix the shared owner first.

This applies to all visualizer modes and ordinary widgets.

---

## 9. Threads / queues

Adding a thread is neither forbidden nor automatically an optimization.

A new thread is appropriate when it creates one cleaner authoritative owner and removes dependence
on an unsuitable shared owner.

Forbidden outcomes:
- duplicate clocks;
- duplicate lifecycle owners;
- worker-to-paint handshakes;
- unbounded queues;
- catch-up replay;
- QWidget/QPixmap/GL mutation on workers.

If a dedicated visualizer logical runtime is ever triggered, it should be one mode-general
authoritative logical owner, not a Bubble-specific side lane.

---

## 10. Baseline discipline

After a major architecture/performance improvement:
- name one installed baseline;
- record durable measurements in the owning phase report/current plan;
- preserve the baseline as rollback/fidelity evidence;
- do not copy volatile numbers into every stable document;
- future improvements may exceed it;
- a new feature/settings change should not silently spend the recovered headroom.

A feature is not “free” merely because the development machine remains above 60 FPS.

---

## 11. Evidence proportionality

Use:

```text
exact source
-> existing evidence
-> production-shaped regression bar
-> bounded correction/replacement
```

Add a new probe only when its result chooses between genuinely different remaining explanations or
designs.

Do not spend hours proving again that an already-named synchronous rebuild, replay or ownership
boundary exists.

A bounded architecture replacement may be safer than a succession of tiny compensating patches when
the owner boundary itself is wrong.
