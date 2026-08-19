# Runtime Efficiency / Change Safety Guardrails

Last updated: 2026-08-19

Read this for new widgets, settings/default changes, startup/recreation, provider/background work,
performance work, and “small optimizations” that alter caches/timers/threads/queues/invalidation.

Core principle:

> SRPSS stays fast by avoiding useless work and bad ownership, not by reducing authored work.

## 1. Current architecture baseline

Two important owner migrations are already landed:

1. one compositor presentation surface per display;
2. one dedicated `VisualizerLogicalRuntime` for visualizer logical cadence.

Do not describe the visualizer logical worker as a future possibility.

Do not move logical cadence back to the GUI timer simply because other GUI delivery problems remain.

## 2. No-op means no-op

Identical value/payload/style/geometry/activation should not trigger work that cannot change the
authored result.

Short-circuit before:

- shadow/card raster regeneration;
- QPixmap/cache rebuild;
- provider refresh;
- runtime reset;
- GL invalidation;
- settings write;
- geometry replay;
- fade/reveal restart;
- worker submission;
- signal fan-out.

“Reapply everything to be safe” is not a lifecycle strategy.

## 3. Shared GUI availability

The GUI thread is shared by:

- input;
- widgets;
- QPixmap/legal image promotion;
- compositor dispatch;
- QRhi/GL owner callbacks;
- Settings/Edit;
- lifecycle/recreation;
- visualizer GUI reveal/presentation commit;
- MediaWidget feedback and other widget animation.

It **no longer directly owns visualizer logical cadence**.

Therefore distinguish:

- GUI starvation damaging physical presentation;
- Python/process contention delaying the logical worker;
- source-analysis staleness.

A 10–20 ms synchronous GUI operation can still damage high-refresh physical delivery even when the
logical worker continues at ~90 Hz.

## 4. New widget / feedback budget

A new widget or animation must not:

- block on provider/file/cache work in GUI paths;
- rebuild stable content every paint;
- add a high-frequency private timer when state-driven invalidation works;
- add per-event GUI callbacks for coalescible data;
- duplicate an existing service/cache/settings/lifecycle owner;
- repaint a large stable parent because a small child decoration changed.

Prefer:

- detached worker-safe preparation;
- one narrow GUI commit;
- cache/revision identity;
- dirty-region or small-layer animation;
- event/state-driven updates.

### Media feedback lesson

The current Pause/Play investigation exposed a durable anti-pattern:

> a small control-feedback animation must not require dozens of full MediaWidget card repaints.

Preserve authored feedback appearance while using the smallest practical paint/presentation owner.

Merely lowering feedback FPS while retaining full-card repaint ownership is not the preferred
optimization.

## 5. Settings are not runtime events by default

Opening/hydrating Settings must not:

- contact providers;
- start workers;
- construct live runtime graphs;
- invalidate live paint caches;
- recreate runtime merely because controls were populated.

Cancel is not Save.

A setting change should trigger only the narrow owner that depends on it.

## 6. Startup / recreation

If deterministic work:

- belongs to the current generation;
- is required for ordinary first-visible use;
- can be completed safely while hidden/fade-zero;

prefer:

```text
prepare
-> readiness
-> reveal
```

over dumping the same work into the first visible seconds.

Readiness is completion-driven, not a fixed sleep.

## 7. Threads / queues

Adding a thread is justified when it creates a cleaner authoritative owner and replaces dependence
on an unsuitable shared owner.

The dedicated visualizer logical thread is the current example.

Forbidden outcomes:

- duplicate clocks;
- duplicate lifecycle owners;
- worker-to-paint handshake;
- unbounded queues;
- catch-up replay;
- QWidget/QPixmap/GL mutation on workers.

Do not infer “one successful worker migration” means every subsystem should move to a worker.

## 8. Visualizer logical runtime safety

Current contract:

- one mode-general logical runtime;
- roughly authored high logical cadence;
- no GUI timer as simulation owner;
- latest-state mailbox;
- no FIFO/catch-up;
- generation-owned start/stop/join;
- valid generation 0 preserved;
- scheduler wait must not regress to the measured coarse-timer ~64 Hz class.

A future optimization may change implementation only if it preserves these observable semantics.

## 9. Do not blame the canary

Before changing a mode/widget because it looks choppy or expensive, compare:

- its own compute/render cost;
- source age;
- logical cadence;
- GUI dispatch age;
- compositor paint cost;
- shared widget/cache/provider/recreation work.

Bubble can expose shared timing problems while being cheap itself.

The 165 Hz non-visualizer display is an especially useful shared-presentation canary.

## 10. Minor optimization admission

Before landing an optimization, answer:

1. what work disappears?
2. which owner performs it now?
3. what visible result stays identical?
4. what new mechanism is introduced?
5. what old mechanism does it replace?
6. could it shift work into startup/Settings/CUSTOM/another display/thread?
7. does p95/p99/max improve or remain healthy?
8. does the production-shaped gate fail when the old waste is reintroduced?

If machinery is added but meaningful work cannot be named as removed, it is probably not an
optimization.

## 11. Baseline discipline

Named baselines are rollback/evidence controls, not permanent ceilings.

Do not copy volatile numbers into every stable doc.

When newer installed evidence contradicts an older performance narrative, update current routing and
keep the old report frozen as checkpoint evidence.

## 12. Evidence proportionality

Use:

```text
exact source
-> existing evidence
-> production-shaped regression bar
-> bounded correction
```

Add a probe only when it distinguishes materially different remaining choices.

Do not spend another investigation round proving a current-source owner already visible in code.
