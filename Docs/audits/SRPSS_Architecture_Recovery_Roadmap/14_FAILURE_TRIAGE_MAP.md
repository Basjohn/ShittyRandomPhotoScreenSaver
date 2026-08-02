# 14 — Failure Triage Map

Last reconciled: 2026-08-02

Use this map to identify ownership seams. It is not a menu of symptom patches.

## First triage questions

Before changing code, establish:

- exact commit/scenario/environment;
- direct log/source/user evidence;
- confidence in the cause;
- current owner and generation;
- whether the failure is shared or mode-specific;
- whether the comparison is warm/equivalent;
- which known-bad incident resembles the shape.

State confidence below 90% explicitly.

# Visualizer and presentation

## Visualizer becomes flat, delayed, or less reactive

Investigate:

- scheduler/executor/cadence change even if equations are unchanged;
- source sampling/normalization/smoothing change;
- impulses/events dropped before logical integration;
- terminal batching or cadence cap;
- persistent/dedicated lane queueing;
- activation/generation reset;
- stale first-frame authority;
- render coalescing before simulation.

Do not blindly raise gain, reduce damping, or add a reactivity multiplier.

`666624d` is the persistent-lane reference failure.

## Bubble looks worse or is blamed for general load

First determine whether the cost belongs to:

- shared capture/analysis;
- general executor/callback delivery;
- immutable-state conversion;
- per-display renderer/resource duplication;
- presentation/event-loop pressure;
- actual Bubble-owned physics/state.

Do not change Bubble-specific cadence, batching, physics, buffers, resolution, or precision without direct mode-owned evidence and explicit user authorization.

Stale Bubble tests/presets are not runtime evidence.

## Spectrum is less smooth after “smoothing”

Investigate:

- second presentation cadence;
- self-requested repaint loop;
- paint-local decay/state mutation;
- authoritative publication versus paint rate divergence;
- attack/decay on different clocks;
- event-loop/update pressure.

Do not tune the decay constant first. Remove the second authority.

`ebfec397`/R-55 is the negative control.

## Visualizer has microgaps under low load

Investigate:

- GUI event-loop stalls;
- tiny task queueing/callback delivery;
- logging/formatting;
- duplicate scene notifications;
- image/upload work on GUI thread;
- GIL contention;
- source age/publication gaps;
- transition/widget collision.

Do not add another timer, lane, retry, or paint loop.

## High average FPS but visible jumps

Investigate:

- p99/max intervals;
- burst delivery;
- latest source/scene age;
- paint/update/publication rate mismatch;
- transition monotonic progress during missed paints;
- event-loop starvation;
- metrics counting burst frames.

Average FPS is not the acceptance metric.

## Cursor halo or unrelated UI becomes choppy

Investigate shared pressure above any one visualizer mode:

- event-loop occupancy;
- synchronous image/GL/native work;
- callback cascades;
- logging;
- GIL saturation;
- paint duration/update storm;
- resource churn.

# Lifecycle and Qt ownership

## Settings returns but logs deleted-wrapper RuntimeError

Investigate:

- `WA_DeleteOnClose` deleting the C++ dialog during `exec()`;
- barrier/child discovery created after modal return;
- `isinstance(QObject)` used as liveness;
- duplicate `close()`/`deleteLater()`;
- animation/timer ownership separated from dialog root.

Correct shape:

- observe valid dialog graph before `exec()`;
- validate underlying C++ wrapper after return;
- never touch invalid wrapper;
- seal barrier and replace once.

Do not remove `WA_DeleteOnClose` or merely suppress the error.

R-56 is the reference incident.

## Edit Save-and-Continue persists then exits code 1

Investigate:

- synchronous reload signal entering `engine.stop()` from `CustomLayoutManager.save_session()`;
- still-running manager/action/key-filter frames;
- shell resolver/applier closures and manager-bound signals;
- class-level active manager/key filter/restack state;
- manager cleanup invalidating fields used by the returning `finally` block;
- destruction barrier Python-root survivors.

Correct shape:

1. persist graph;
2. retire temporary session/callbacks;
3. return from owner frames;
4. queue immutable engine-owned admission;
5. run the same full reinit.

Do not hide `CustomLayoutManager` from the barrier or weaken full reconstruction.

R-53 is the reference incident.

## `QOpenGLContext` different-thread/currentness failure

Investigate:

- worker/deferred callback touching context;
- wrong owner-thread deletion;
- context generation mismatch;
- renderer/FBO retained after surface destruction;
- two owners deleting one handle;
- partial reinit;
- shutdown order.

Do not retry `makeCurrent()` elsewhere, suppress the warning, or clear ownership after failed deletion.

## Replacement appears stale or too early

Investigate:

- destruction barrier bypass;
- delayed callback missing runtime and exact-manager validation;
- old visualizer/transition/image state satisfying first frame;
- construction/GL init/timer fire treated as readiness;
- multiple reveal coordinators;
- graph replay occurring after visible reveal.

Keep replacement hidden until fresh authoritative state.

# Cache and image pipeline

## `IndexError: pop index out of range` in scaled prefetch

Investigate:

- priority selection order versus numeric deletion order;
- later preferred index selected before earlier general index;
- `reversed(selected_indices)` rather than descending sort/partition;
- duplicate selection and byte/key bookkeeping;
- stale generation entries.

Fix by stable-identity partitioning or descending unique numeric deletion. Do not add retry/broad exception masking.

R-57 is the reference incident.

## Repeated scaled misses or worker fallback

Investigate:

- unstable transform/DPR/cache identity;
- preferred/raw producer ordering;
- premature raw-source release;
- bounded backlog too small for authored preview window;
- failed callback leaving accounting/inflight inconsistent;
- stale generation repopulation.

Do not raise cache budget before proving the miss cause.

## RAM grows with image changes

Investigate:

- decoded/raw/scaled variants;
- QImage/QPixmap/display aliases/copies;
- upload/shared-memory buffers;
- futures/callback closures;
- pending prefetch/results;
- previous/fallback frames;
- stale snapshots;
- cache key/eviction failure;
- logs/diagnostics.

Require owner, generation, count, and bytes.

## VRAM grows with image changes

Investigate:

- old textures/FBOs/PBOs/programs;
- transition/source pins;
- resized resources;
- per-display duplicates;
- failed deletion queue/currentness;
- stale context/store entry;
- driver sample age.

Compare tracked GL bytes and teardown idle-driver baseline; do not rely on driver total alone.

# Whole-process resource use

## Memory is flat but still around one GiB RSS

Treat as unresolved absolute-footprint debt.

Investigate separately:

- main versus child RSS/private working set;
- private commit versus VMS/reserved mappings;
- thread stacks;
- Python/Qt/native allocations;
- image/cache logical bytes;
- shared-memory/mapped files/DLLs;
- allocator high-water pages;
- driver mappings/shared GPU memory;
- retained callbacks/owners.

Do not add RSS and private commit. Do not call flat usage acceptable merely because it stopped climbing.

## Settings first cycle rises, second does not

Before calling a leak or allocator issue, verify:

- identical warmup duration;
- same visualizer mode/input;
- same image/cache/transition state;
- asynchronous GPU sample age;
- main/child split;
- handles/threads/resources;
- zero retiring ownership.

A one-time uplift can be warmup/high-water/mapping or retention. Cause remains below 90% without attribution.

## Private commit is multi-GiB while RSS is lower

Investigate:

- private bytes versus resident private pages;
- process/child VMS and mappings;
- allocator arenas;
- thread stacks;
- shared-memory regions;
- Qt/native/driver reservations;
- pagefile-backed commitment.

It is commitment pressure, not an additional amount of physical RAM to add to RSS.

Do not trim/recycle to hide it.

# CPU/tasking

## CPU pegs one core

Investigate:

- high-frequency Python/shared loops;
- queueing/callback overhead;
- duplicate cross-display transforms/state;
- unchanged provider/media/layout work;
- full-buffer copies/hashes;
- logging;
- GUI-thread work;
- busy polling/retries;
- allocation/native conversion.

Do not add more Python threads or persistent visualizer lanes before profiling.

## Task count falls but feel worsens

The optimization failed.

Investigate dropped logical events, cadence reduction, terminal batching, source age, first-visible delay, and scheduler ownership.

Restore accepted executor semantics before further tuning.

# Transition and display

## Transition freezes or final frame sticks

Investigate:

- terminal transaction/acknowledgement;
- source/destination ownership;
- local completion exactly-once logic;
- interrupted/cancelled/resize path;
- scene publication and resource release.

Prefer local completion and deterministic release.

## Overlay appears only on display 0

Investigate:

- display-global singleton state;
- primary-display assumptions;
- requests routed only to first compositor;
- shared logical state carrying display-local geometry;
- z-order/compatibility path;
- missing exact display membership.

Fix ownership, not index conditionals.

# Architecture smell

## Fix requires several new flags, retries, generations, or timers

Stop and re-evaluate ownership.

One new state may be valid. A chain of compensating states usually means the wrong object owns the concern or two authorities exist.

## Tests pass but installed behaviour fails

Check whether tests use:

- counter-only lifecycle stubs;
- immediate executor instead of production executor;
- logical final state without temporal/first-visible assertions;
- offscreen QObject destruction without PySide callback wrappers;
- regenerated expected outputs;
- no known-bad negative control;
- no user review.

Strengthen the oracle; do not weaken the runtime to satisfy stale tests.