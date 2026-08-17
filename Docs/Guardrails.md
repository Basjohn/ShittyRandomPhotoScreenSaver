# SRPSS Guardrails

Last updated: 2026-08-11

Durable cross-cutting rules for SRPSS.

This is a gatekeeper, not a specification. Read Sections 1–3 for every task, then only the relevant domain section.

## 1. Priority Order

When goals conflict:

1. visualizer fidelity and reactivity;
2. lifecycle and OpenGL safety;
3. frame pacing and perceived smoothness;
4. correct multi-display behaviour;
5. bounded RAM and VRAM;
6. CPU and task efficiency;
7. average FPS;
8. code elegance.

Higher average FPS does not justify worse motion, visualizer feel, lifecycle safety, image quality, or resource use.

Do not silently reduce visualizer behaviour, source cadence, transition quality, image quality, overlay smoothness, or display support to improve a counter.

## 2. Change Scope and Token Discipline

### Normal work

Read:

- Sections 1–3;
- the one relevant domain section;
- `Docs/Contracts.md` to locate the owner.

Do not read every core document for a local change.

### High-risk work

Before changing compositor/GL, visualizer timing, Settings/Edit lifecycle, worker/timer architecture, transition completion, or RAM/VRAM ownership, record briefly:

1. measured problem;
2. owner of each mutable concern;
3. proposed data/control flow;
4. failure modes and rollback;
5. acceptance metrics.

### Complexity escalation

Adding more than one new long-lived thread, timer, queue, state machine, generation, retry, cache, fallback renderer, GL context, or compatibility layer requires architecture review.

State what existing mechanism is removed or replaced. Complexity may not merely accumulate.

## 3. Immediate Stop Conditions

Stop and reassess when:

- Spectrum becomes flatter, less reliable, more stepped, or less smooth;
- Bubble becomes less reactive, less elastic, less expansive, or less correctly song-sensitive;
- any visualizer becomes visibly less smooth;
- a visualizer continues moving while reacting to stale or irregular source data;
- p99/max frame delivery worsens despite better averages;
- cursor halo or unrelated UI becomes choppy;
- a producer waits for paint completion;
- a `QOpenGLContext` affinity warning appears;
- Settings/Edit needs another cleanup flag, retry, generation, or delay;
- RAM or VRAM grows monotonically;
- live resource use cannot be explained;
- task rate rises without measured benefit;
- a silent fallback is required;
- a fix needs broad dynamic forwarding or widget impersonation;
- tests pass while the known user-visible failure remains;
- proxy counters claim equivalence after the operator reports a visualizer regression;
- one phase starts changing lifecycle, compositor, visualizer behaviour, memory, and threading together.

Do not answer these failures with another flag or retry.

## 4. Repository and Documentation Stability

- Edit existing files in place.
- **Never rename or move an existing file, directory, document, module, or public path unless the user explicitly requests that exact rename or move.**
- Do not create “v2”, “new”, “replacement”, or “proposed” canonical copies.
- Preserve public setting keys, visualizer ids, transition ids, widget ids, and storage paths unless an explicit migration is approved.
- Stable architecture belongs in `Spec.md`.
- Active unfinished work belongs in `Current_Plan.md`.
- Detailed subsystem rules belong in the existing focused document.
- Dated failure history belongs in `Docs/Historical_Bugs.md`.
- Completed work is removed from `Current_Plan.md`.

## 5. Ownership and Architecture

### One mutable concern, one owner

Examples:

- runtime lifecycle: runtime coordinator;
- settings: `SettingsManager`;
- task registry: `ThreadManager`;
- visualizer simulation: visualizer controller/model;
- transition state: transition owner;
- image cache: image pipeline/cache;
- GL lifetime: context/resource owner;
- presentation: display compositor.

Managers coordinate; they do not become co-owners.

### Centralization is not universalization

Do not force:

- every GUI timer through `ThreadManager`;
- visualizer simulation through `AnimationManager`;
- every high-rate computation through one generic persistent scheduler;
- per-frame state through `EventSystem`;
- GL context decisions through `ResourceManager`;
- unrelated responsibilities into a generic manager.

### No shadow frameworks

Do not create a second settings path, task registry, transition registry, descriptor registry, lifecycle authority, renderer, or cleanup owner.

Temporary comparison paths require an explicit development flag, separate metrics, and removal deadline. They may not activate silently.

### No compatibility mega-layer

Do not use:

- broad `__getattr__`/`__setattr__`;
- giant forwarded-attribute lists;
- widget impersonation;
- whole-widget free-function seams;
- generic managers with unrelated state.

Use explicit interfaces and immutable data.

### Generations represent lifetimes

Use generations for runtime/context recreation, stale request rejection, or activation replacement.

Do not create dirty/requested/acknowledged/presented generations for ordinary frames.

## 6. Presentation and Compositor

- One compositor surface per display is acceptable.
- One surface does not mean one scheduler or one clock.
- Visualizer simulation, transition time, and Qt presentation remain separate.
- Producers publish latest immutable state and return.
- The compositor consumes the latest scene when Qt paints.
- Intermediate render snapshots may coalesce; logical input may not be dropped before simulation.
- A GUI-local pending `update()` flag is allowed.
- That flag is not a producer acknowledgement.

**A general allowance never licenses a mechanism a focused document forbids for a specific
task.** The pending-`update()` allowance above covers ordinary compositor repaint coalescing.
It does **not** authorize pending-until-paint as the admission mechanism for visualizer
presentation, which
`Docs/audits/SRPSS_Architecture_Roadmap/06_PRESENTATION_AND_COMPOSITOR_DESIGN.md`
("Forbidden Admission Mechanisms") explicitly rejects. Before proposing any presentation,
cadence, scheduling or admission mechanism, read that document's forbidden list first and
quote the specific item you believe does not apply. A permissive clause found elsewhere is
not a counter-argument to an explicit prohibition.

Prohibited:

- worker wait for `paintGL()`;
- presentation-generation wait;
- producer pause until paint;
- scheduler release by accepted paint;
- catch-up repaint bursts;
- compositor-owned visualizer cadence;
- distributed terminal-frame transactions.

`paintGL()` may draw, calculate local transition progress, record passive metrics, and request another frame while local animation remains active.

`paintGL()` may not simulate visualizers, decode/convert images, hash whole buffers, wait for workers/fences, run lifecycle, or emit per-frame INFO logs.

Transition completion is local: destination becomes base, old/temporary resources release, transition becomes inactive.

Each display owns its surface, viewport, DPR, scene, update state, and resources/leases. Display 0 is not implicit global authority.

A clearly owned GUI-local `QTimer` is allowed. Retry timers and duplicate cadence authorities are not. Never sleep or pump events on the GUI thread.

## 7. Visualizer Safety

Protected mode behaviour includes:

- attack;
- amplitude;
- decay;
- smoothing;
- overshoot;
- elasticity;
- settling;
- low-energy response;
- spatial distribution;
- continuity under irregular presentation;
- source freshness;
- transient and onset timing;
- mode-specific personality under different song dynamics.

Before and after shared visualizer/audio/timing/render changes:

- run the focused reactivity harness;
- run deterministic replay where available;
- compare Spectrum and Bubble;
- test irregular paint cadence/UI stalls;
- perform manual review;
- do not rewrite expected output merely to pass.

### Scheduler substitution is a behavioural change

Moving an existing visualizer path between the general executor, a persistent lane, a dedicated scheduler, a queue, a recurring worker, or a different callback sequence is a behavioural change even when the equations and final packet values are unchanged.

Such a substitution can change source sampling, worker competition, event consumption, callback ordering, publication timing, teardown ownership, and first-frame authority.

Never migrate both the shared audio source and a mode-owned simulation path in one acceptance slice. Change and validate one causal boundary at a time.

A visualizer scheduler substitution is rejected when either:

- the operator reports a fidelity regression; or
- lifecycle ownership becomes less deterministic.

Zero rejected submissions, cheap means, high throughput, exact final state, and green logical goldens do not overrule those failures.

When a substitution fails, restore the exact previously approved execution semantics from the named commit before attempting tuning or a replacement scheduler.

No further Bubble or Spectrum scheduling, smoothing, cadence, or task-reduction optimization may begin until the user has explicitly approved a named restored build and the stronger baseline required by `Current_Plan.md` has been captured.

### Reactive visualizer task-reduction stop rule

Task-count reduction is subordinate to authored reaction timing. Never add a second cadence authority, token bucket, deadline gate, or paint/transition-derived clock between an authored visualizer tick and its simulation. Never batch multiple logical simulation steps when only the terminal snapshot will be published, and never place a live mutable scheduler or event source inside a deferred or batched payload.

Coalescing is permitted only after each logical input has been integrated and the mode's visible publication semantics remain intact. A lower submission count is a failed optimization if it delays first visible attack, hides or decays a discrete edge before publication, reduces loud-passage expansion or elasticity, repeats unchanged state while the ownership lane is free, changes Spectrum smoothing, or increases source age while the visualizer continues moving. Do not revive such a design under a different scheduler name.

Before accepting visualizer cadence or task-frequency work, require a runtime-shaped source-tick-to-first-visible oracle, discrete-edge accounting, irregular-stall and transition coverage, 60 Hz and high-refresh coverage, Bubble and Spectrum comparison, and installed manual review. Final-state equality, packet ordering, average FPS, worker duration, accepted-step totals, and task-cap tests are not sufficient. If the visible complaint reproduces while those tests remain green, the optimization fails and the validation bar must be strengthened.

Visualizer simulation is independent of paint and transition cadence.

The compositor may skip render snapshots, but cannot block simulation, change simulation time, drop input before integration, or flatten behaviour after a stall.

Worker visualizer work requires one owner, bounded input, no stale/new overlap, latest-result publication, generation rejection, no UI wait, and no per-display duplicate simulation.

More worker threads do not prove multi-core scaling. Use measured vectorized/native work or remove duplicate work before lowering fidelity.

Mode arrays, history, envelopes, buffers, and pending work are mode-owned and cleared on activation unless reuse is explicit.

## 8. GL Lifecycle, Settings, and Edit

All GL creation, mutation, and deletion occurs:

- on the owner thread;
- with the expected context current;
- under the correct runtime/context generation.

Assertions identify thread, context/share group, resource, owner, and generation.

Never suppress:

```text
Cannot make QOpenGLContext current in a different thread
```

Settings, Edit, topology recreation, and exit follow full ordered teardown:

1. close old-runtime admission and invalidate its runtime generation;
2. stop producers and GUI timers;
3. disconnect callbacks, animations, and global subscriptions;
4. cancel/drain workers plus queued and delayed GUI work;
5. reject every remaining old-runtime GUI/GL publication;
6. delete child GL resources with valid context;
7. close old Qt roots and queue compositor/surface destruction last;
8. wait for watched root destruction and assert zero old-generation resources, tasks, timers, animations, and subscriptions;
9. only then create a clean generation.

The current production boundary is one engine runtime generation plus exact `DisplayManager` identity. Settings/CUSTOM handlers must call full teardown before constructing dialogs or replacement displays. `DisplayManager.cleanup()` invokes `DisplayWidget.cleanup_runtime()` synchronously; a non-reentrant destruction barrier then confirms that the retired Qt roots and generation-scoped owners are gone. Do not treat `deleteLater()`, hide-only pauses, post-dialog cleanup, or a bounded timer delay as destruction proof, and do not use nested `processEvents()` calls to manufacture that proof. A successfully started RUN session must also disable Qt last-window auto-quit: the deliberate zero-window destruction interval is not an application-exit request, and only explicit terminal routes may end it.

The destruction barrier and presentation barrier are independent. Destroying the old graph only permits replacement construction. The replacement display/compositor/visualizer remains hidden until current runtime generation, visualizer engine generation, and activation identity produce their own authoritative first frame. The existing `FadeCoordinator` remains the sole reveal coordinator; old frames, cached state, construction, GL initialization, repaint requests, and timer ticks do not satisfy readiness.

Context acquisition/deletion failure is a hard incomplete teardown: retain the resource/manager, keep the compositor out of `DESTROYED`, log the owner/context/generation, and fail the reconfiguration. Never clear handles to manufacture a zero count.

Partial GL reinitialization requires a separate approved architecture proposal.

A worker may stop asynchronously, but context destruction cannot proceed while it can touch the retiring runtime.

Do not clear handles while a worker lives, destroy the context first, block the GUI indefinitely, force-drop ownership, or add cleanup retry timers.

Every GL resource has one owner, byte size, context/share generation, and exactly-once deletion path.

A Qt share group makes a numeric GL handle accessible across contexts; it does not create deletion ownership. Never copy one globally cached program, texture, buffer, or other numeric handle into multiple local owner records. Share numeric handles only through an explicit lease/generation registry; otherwise allocate and delete them per compositor. Reusing a stateless shader helper is not resource sharing.

`ResourceManager` is passive GL accounting, not a fallback GL owner. It may retain handle identity, bytes, owner, and generation, but it must never retain or invoke a `glDelete*` callback. The context-bound owner deletes first and releases the accounting record only after success.

Settings/Edit handlers invoke the engine stop boundary once. `engine.stop(exit_app=False)` is the sole full-teardown authority; handlers must not add a second direct `teardown_display_runtime()` call.

Do not rely on garbage collection, `deleteLater()` alone, or driver cleanup. `QObject.destroyed` may participate in an explicit bounded destruction barrier, but never replaces synchronous owner-context GL/resource cleanup. Periodic/production `gc.collect()`, working-set or allocator trimming, process/worker recycling, cache enlargement, retired-tree reuse, and warm-standby runtimes are forbidden substitutes for releasing owners.

Warmup is optional optimization; correctness never depends on it.

## 9. CPU, Threading, Logging, RAM, and VRAM

### CPU and threading

Reduce work before adding threads.

Before adding a worker:

- identify the hotspot;
- measure queue/callback cost and GIL behaviour;
- remove duplicate work;
- batch tiny jobs;
- stop hidden/static work;
- coalesce latest non-critical state.

Do not use a general COMPUTE task per presentation frame, worker-to-paint handshake, busy-spin timing, or one UI callback per diagnostic event. Where an explicitly operator-approved reactive path uses a bounded compute lane, task reduction must preserve every lane-free authored step and every discrete input edge; do not add a second token clock or publish only an already-decayed terminal batch state.

Measure GUI timer lateness, callback duration, paint duration, scene age, signal backlog, synchronous I/O, and logging overhead.

### Logging

Diagnostics are CLI-gated, sampled, fixed-memory, aggregated, non-overlapping, and lazily formatted.

Valid explicit `srpss_log_families` metadata is the routing authority and may contain
multiple families. Visible tags remain human/parser text; name/tag heuristics are a
compatibility fallback for unmigrated and third-party records. Every WARNING+ remains
main-visible regardless of family sidecars.

No per-frame INFO logs or per-frame state dumps.

Diagnostic evidence exists to make later optimization accurate. Do not delete or
weaken a perf-only attribution path merely to improve its own measured run. Measure
its cost first and preserve equivalent owner fields if the cost is material.

Conversely, diagnostic bookkeeping may never create one GUI callback per event,
change task admission, become presentation control flow, or remain active in an
ordinary run merely because it was originally added for profiling. Remove that
delivery overhead while retaining passive snapshots and bounded summaries.

### Memory and resources

Byte-account:

- encoded/decoded/scaled images;
- `QImage`/`QPixmap`;
- upload buffers;
- textures;
- FBOs/PBOs/renderbuffers;
- retained frames;
- transition and visualizer resources.

Record identity, owner, bytes, format, generation, leases, and deletion reason.

Image cycling, transitions, and Settings/Edit cycles must reach a stable plateau.

For the current dual-1440p target:

- investigate application-owned GL allocations above roughly 500 MiB;
- investigate RSS above roughly 900 MiB;
- explicitly explain multi-gigabyte private commit.

These are investigation gates, not budgets to consume.

CPU/GPU caches require exact logical-byte and count limits, pinning, deterministic eviction, stale-prefetch cancellation, pressure behaviour, and metrics. Count-only limits never substitute for byte budgets, and persisted legacy values must be clamped before owner construction.

Shared textures require verified share group, exact identity, explicit leases, generation safety, and exactly-once deletion. No GL calls under registry locks.

Workers may prepare immutable thread-safe image data. They may not create GUI-affine `QPixmap` or call GL. Pending decode/scale work is bounded by concurrency, queue count, and future decoded bytes.

Avoid repeated full-buffer copies, hot-path whole-buffer hashing, visible-paint conversion, and UI fence waits. Share immutable image backing only for exact source, transform, dimensions, mode, and DPR identity.

Transition completion/cancellation clears every transition state family and releases active texture pins. PBO pools and texture caches have independent byte caps and owner-context deletion; do not raise either cap to hide unexplained growth.

Background samplers read detached GUI-captured image metadata. They never inspect live `QPixmap`/widget/compositor objects from a worker thread.

## 10. Settings, Widgets, and Layout

- Defaults and normalization remain single-source.
- Settings mutation is synchronously authoritative in memory and preserves cross-manager cache invalidation and notification semantics.
- One process-scoped ordered settings writer owns routine serialization/temp-write/fsync/atomic replacement across profiles; do not create per-manager, per-dialog, or runtime-generation writers.
- Routine save/sync requests persistence. Only an explicit bounded flush acknowledges durability; failed writes remain dirty/retryable, and Settings completion, reload, and process shutdown preserve their flush boundaries.
- Widget metadata remains descriptor-owned.
- Transition identity remains registry-owned.
- Visualizer identity/settings remain registry/model-owned.
- Shared service-widget lifecycle contains mechanics only; provider behaviour remains local.
- CUSTOM layout is descriptor-capability-driven, display-bounded, and DPR-aware.
- Live content refresh cannot become a second geometry owner.
- Drag/resize feel is part of correctness.
- Focus policies are not recursively changed across live widget trees.
- Active graphics effects are not replaced mid-animation.
- Settings/Edit work obeys Section 8.

Detailed rules stay in existing focused documents.

## 11. Testing and Evidence

Test the real failure shape.

Startup, first-visible state, visualizer feel, frame delivery, lifecycle, multi-display ownership, and memory growth require runtime-shaped coverage.

Visual/timing work requires:

- automation;
- runtime logs;
- p95/p99/max;
- manual review.

Logical goldens protect equations and state after accepted input. They do not, by themselves, authorize scheduler, callback-order, cadence, smoothing, or task-frequency changes. Detailed visualizer baseline creation and stronger-golden requirements live in `Current_Plan.md`.

Performance reports include scenario, environment, average FPS, p50/p90/p95/p99/max, gap counts, CPU, task rate, RSS/private commit, tracked GL bytes, driver VRAM, visualizer result, and lifecycle result.

Runtime evidence:

```text
logs/evidence_chest/<plain_run_subfolder>/
```

Plain evidence subfolders are the current capture pattern and may be moved or deleted by the user. Legacy ZIPs remain readable historical inputs; do not create new ZIPs solely for evidence analysis.

Historical baseline/candidate branches and commits are forensic references or negative controls only. They are not implementation authority or merge targets.

Every new production helper must have a production caller verified by repository search.

## 12. Architecture Prohibitions

Do not preserve or reintroduce:

- adaptive timer/presentation worker;
- worker-to-`paintGL()` acknowledgement;
- dirty/requested/acknowledged frame generations;
- compositor-owned visualizer cadence;
- distributed terminal transactions;
- partial Settings/Edit GL reinitialization;
- visualizer compatibility mega-layer;
- broad dynamic forwarding;
- full-buffer SHA-256 hot-path identity;
- silent child-surface or `QPainter` fallback;
- general worker tasks used as GUI timers;
- unapproved visualizer persistent-lane or scheduler substitutions;
- garbage-collection-owned GL lifetime;
- unbounded or count-only image/GPU caches;
- unbounded prefetch queues or unbounded future decoded bytes;
- worker-created `QPixmap` or worker-side live Qt display inspection;
- transition pins retained after terminal presentation.

Historical candidate ideas may be reconsidered only after isolated review and benchmark:

- resource accounting;
- bounded texture reuse/leases;
- immutable worker/render handoff;
- GL affinity assertions;
- passive diagnostics;
- stale-result generation rejection.

## 13. High-Risk Pre-Commit Gate

- [ ] One problem and hypothesis
- [ ] Owners/thread affinity documented
- [ ] No producer waits for paint
- [ ] No hidden fallback
- [ ] No unexplained timer/thread/queue/generation/retry
- [ ] Visualizer fidelity protected
- [ ] Named operator-approved visualizer baseline exists before visualizer optimization
- [ ] p95/p99/max measured
- [ ] RAM/VRAM plateau tested
- [ ] Settings/Edit exercised
- [ ] Multi-display path exercised
- [ ] Helpers have production callers
- [ ] Logs remain sampled
- [ ] Rollback commit known
- [ ] `Current_Plan.md` updated when applicable
