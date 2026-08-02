# 04 — Target Architecture and Ownership

Last reconciled: 2026-08-02

## Core rule

Every mutable concern has one explicit owner.

Sharing immutable data is allowed. Sharing authority, deletion responsibility, cadence, or lifecycle admission is not.

## Current architectural boundary

This document describes the target ownership model. `Current_Plan.md` decides which parts are active now.

The current project deliberately keeps:

- full runtime teardown and reconstruction for Settings and committed CUSTOM Edit;
- graph-based CUSTOM placement/replay;
- generation and exact-manager rejection;
- owner-context GL deletion;
- authoritative-first-frame reveal;
- ordinary general COMPUTE executor semantics for shared visualizer analysis and Bubble.

No target architecture may remove those protections merely to simplify code or lower a resource graph.

# Runtime domains

## 1. Process/application coordinator

Owns:

- application start/stop;
- runtime-generation allocation;
- high-level Settings/Edit/topology sequencing;
- acceptance and deduplication of immutable reload intents;
- admission of full teardown and replacement construction;
- fail-closed response when destruction does not complete.

Does not own:

- temporary Edit shells or save-state collections;
- GL handles;
- visualizer equations/cadence;
- cache eviction details;
- transition time;
- Qt modal-object internals.

The coordinator may retain process-lifetime state. A queued lifecycle continuation may retain the coordinator plus primitive/immutable identity only; it may not retain a retiring manager, display, shell, widget, pixmap, callback, or bound method.

## 2. Runtime-destruction barrier

Owns observation of the retiring generation:

- watched QObjects;
- weak-observed Python roots;
- generation-owned tasks/timers/subscriptions/resources;
- completion/timeout decision;
- one continuation after zero ownership.

Does not own:

- forcing release through GC;
- hiding owners;
- extending timeout to conceal retention;
- constructing the replacement before completion;
- deciding how a retiring owner cleans itself.

The barrier proves retirement; it is not a garbage collector.

## 3. Temporary CUSTOM Edit session

Each display-local `CustomLayoutManager` owns temporary editing state:

- edit shells and grid overlays;
- geometry snapshots/guides;
- pointer interaction;
- manager-bound shell callbacks/signals;
- session save/reset/slot state;
- participation in the class-level active-session/key-filter contract.

On committed save/reset/slot action it must:

1. persist the complete graph-based layout;
2. explicitly retire temporary shells, callbacks, filters, overlays, and class-level participation;
3. return from all manager/action/key-filter frames;
4. request later engine-owned full recreation through immutable intent.

It does not own engine teardown or replacement construction.

Cancel may restore deferred image state into the unchanged runtime. A committed full reload discards old-runtime deferred image state.

## 4. Settings modal session

Owns:

- one Settings dialog and its animation/timer graph;
- user mutation/validation result;
- modal lifetime.

Destruction observation is registered before `exec()` can trigger `WA_DeleteOnClose`.

A Python wrapper is not QObject liveness. Post-modal code validates the underlying C++ object before any method call and never double-closes/deletes an already destroyed dialog.

## 5. Display manager/runtime

Owns:

- current display set and identity;
- display-local runtime objects;
- signal relay to the process coordinator;
- ordered display cleanup;
- membership checks for delayed/current-generation callbacks.

Does not own:

- global application lifetime;
- hidden replacement admission;
- visualizer simulation;
- cross-display deletion ownership.

Exact manager identity is required in addition to runtime generation.

## 6. Image pipeline

Owns:

- source selection;
- decode/prefetch intent;
- crop/scale transform identity;
- bounded CPU image cache;
- bounded raw/scaled pending queues and future bytes;
- immutable upload/display-ready results;
- generation rejection and raw-source derivative lifetime.

Does not own:

- GL texture handles;
- QWidget/QPixmap construction on workers;
- compositor state;
- transition completion;
- lifecycle admission.

Multi-selection removal uses stable identity or explicitly descending unique numeric indices. Priority order is never assumed to equal deletion order.

## 7. CPU image/cache ownership

Every retained image representation has:

- canonical source/transform/DPR/quality identity;
- owner and generation;
- exact logical bytes;
- dimensions/format;
- current usefulness/pin state;
- deterministic eviction/clear path.

Avoid retaining raw decode, multiple scaled variants, QPixmap, upload bytes, and display copies without measured benefit.

## 8. GPU resource owner/store

Current per-compositor owners and any future store own:

- texture/FBO/PBO/program/buffer metadata;
- exact bytes where knowable;
- one deletion identity;
- leases/references;
- context/share-group/runtime generation;
- eviction eligibility;
- owner-thread deletion scheduling.

Does not own:

- image sequencing;
- transition logic;
- visualizer simulation;
- Settings/Edit;
- GL calls under registry locks.

Share-group accessibility is not shared deletion ownership.

A future process-level resource store is optional and must be justified by Phase 5 measurements; it is not automatically required by this target model.

## 9. Visualizer shared source/controller

Owns:

- audio capture/input normalization;
- shared analysis state;
- timestamped logical features/events;
- engine generation and source identity;
- approved ordinary general-executor submission/publication semantics;
- supported-mode activation and visibility authority.

Does not own:

- compositor paint scheduling;
- image transitions;
- GL context lifetime;
- Settings reconstruction;
- a persistent analysis lane.

Aggregate visualizer load is treated as shared/runtime ownership until evidence isolates a mode-specific owner.

## 10. Mode-owned visualizer logic

Each supported mode owns only its specific logical state/equations.

Bubble owns Bubble physics and authored-step state. Spectrum owns Spectrum bars/presentation state. Neither is a default target for application-wide CPU or memory work.

Mode-specific cadence, batching, smoothing, or physics changes require direct owner evidence and explicit user approval.

## 11. Visualizer presentation state

Owns immutable/current render state for one activation/generation.

There is one authoritative presentation cadence. Presentation state:

- updates on the established visualizer tick/publication path;
- resets at mode/activation/generation/teardown boundaries;
- is not advanced from `paintGL()`;
- does not self-request a second repaint loop;
- does not become a feedback controller for producers.

## 12. Transition controller

Owns:

- source and destination resource references;
- monotonic start time;
- duration/easing;
- local exactly-once completion;
- terminal resource release.

Does not own:

- worker scheduling;
- image decode;
- visualizer cadence;
- paint acknowledgement;
- pipeline terminal transactions.

## 13. Display compositor

Owns:

- its display surface/context usage on the GUI thread;
- compositor programs/buffers and one deletion identity;
- current immutable scene snapshot;
- explicit draw order;
- GUI-local update coalescing;
- continued updates only for compositor-local animation such as an active transition.

Does not own:

- visualizer simulation or visualizer cadence;
- worker scheduling;
- Settings/Edit application lifecycle;
- image source selection;
- producer acknowledgement;
- paint-local authoritative smoothing.

A future one-surface-per-display architecture must preserve this boundary.

## 14. First-frame/reveal coordinator

Owns coordinated visibility of a newly constructed runtime.

It accepts only fresh authoritative state from the current runtime, exact manager/display set, visualizer engine generation, and activation identity.

Construction, GL initialization, timer ticks, stale callbacks, cached old state, or old visualizer results cannot satisfy readiness.

`FadeCoordinator` remains the sole reveal coordinator unless a separately approved architecture replaces it.

## 15. Diagnostics and evidence

Owns:

- sampled metrics;
- immutable snapshots;
- bounded ring buffers/histograms;
- environment manifests;
- evidence/benchmark output.

Does not become control flow, request paints, mutate live Qt objects off-thread, or consume authoritative state.

# Data flow

```text
Audio source
  -> shared visualizer source/controller
  -> mode-owned logical state
  -> immutable current visualizer render state
                                      \
Image source -> decode/transform -> immutable image result
                     -> CPU cache -> GL owner/lease -----> immutable SceneSnapshot
Transition controller -------------------------------> /
Overlay/widget state -------------------------------->/
                                                       |
                                                       v
                                               display compositor
                                                       |
                                                       v
                                                     paint
```

No ordinary animation arrow returns from paint to a producer.

# Scene snapshot

A scene snapshot should contain explicit immutable references such as:

```text
SceneSnapshot
- runtime_generation
- context_generation
- display_identity
- base resource/lease
- optional transition snapshot
- optional visualizer render state
- overlay/widget state
- viewport/DPR
- scene_generation
```

The compositor may atomically replace the latest snapshot. It must not mutate producer-owned objects.

# Clock ownership

Separate logical clocks include:

- audio/source timestamps;
- visualizer logical/approved tick;
- transition monotonic time;
- Qt presentation opportunities.

A presentation stall does not create a new visualizer clock or authorize catch-up bursts/self-paints. The next paint draws the current approved state.

# Thread ownership

## GUI thread

Only owner of:

- QWidget/QOpenGLWidget/QObject UI lifecycle;
- modal wrapper validity checks and queued GUI admission;
- QOpenGLContext currentness;
- GL creation/mutation/deletion;
- QPixmap;
- compositor mutation and scene presentation.

## Workers

May perform coarse, thread-safe I/O, decode, scaling, and numerical work through approved bounded executor paths.

May not access QWidget/QPixmap/GL/context or mutate compositor/live runtime owners.

## Cross-thread handoff

Use immutable data, bounded queues/latest references, generation and exact-owner identity, and cancellation/stale rejection.

Do not use mutable shared widgets, retained bound owner methods, worker waits for GUI paint, or callbacks into destroyed generations.

# Generation policy

Generations represent real lifetime boundaries only:

- runtime generation;
- GL context generation;
- source/request generation;
- visualizer engine/activation identity where stale state must be rejected.

Do not create dirty/requested/acknowledged/presented generations for ordinary frames.

# Resource/process reconciliation

Tracked application bytes and whole-process metrics answer different questions.

The architecture must explain:

- main and child RSS/private working set;
- private commit;
- reserved/mapped regions;
- thread stacks;
- Python/Qt/native allocations;
- CPU cache/images/pixmaps;
- GPU dedicated/shared memory;
- driver mappings/overhead;
- retired-owner state.

A flat unexplained gap is still architecture debt.

# Target simplicity test

A new engineer should be able to answer from one ownership document and one diagnostic set:

1. Who owns this representation or handle?
2. Which thread/context may mutate/delete it?
3. Why is the compositor painting?
4. Who advances this visualizer state?
5. What happens if Qt misses ten paints?
6. What happens when Settings closes its modal dialog?
7. What happens when Edit Save-and-Continue is pressed?
8. Why is this memory still resident or committed?
9. What prevents a stale worker/publication from applying?
10. What exact authority permits replacement construction?

If the answer requires tracing overlapping managers, callbacks, hidden fallbacks, or several frame generations, the design has regressed.