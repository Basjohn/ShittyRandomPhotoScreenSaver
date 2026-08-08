# 08 — CPU, Threading, and Workload Plan

Last reconciled: 2026-08-02

## Current evidence and correction

Historical baseline/donor runs could consume roughly one logical core and submit around 90–100 compute jobs per second.

A later attempt to solve this through persistent shared-analysis and Bubble lanes changed temporal behaviour and was rejected. The ordinary general COMPUTE executor restored at `4bde89e` is the current approved production model.

Therefore this plan does **not** treat lower task count, dedicated visualizer threads, or lower publication cadence as goals by themselves.

## Primary goal

Reduce unnecessary work, duplication, allocations, callbacks, and retained representations while preserving:

- exact approved visualizer logical and temporal behaviour;
- source-to-first-visible response;
- p99/max frame pacing;
- image/transition/widget quality;
- lifecycle and ownership boundaries.

Move work between threads only after proving that the work itself is necessary and the new handoff preserves timing.

## Attribution rule

Aggregate application or visualizer load is presumed shared/runtime-owned until direct evidence isolates a mode-specific owner.

Bubble is not a default optimization target. Do not reduce Bubble authored-step frequency, batch its simulation, alter physics, or move it to a persistent lane to improve general CPU/task numbers.

Mode-by-mode profiling may identify ownership differences; it is diagnostic, not permission to degrade a mode.

## Work inventory

Categorize recurring work by owner, trigger, and useful result:

- audio capture and shared analysis;
- mode-owned visualizer work;
- render-state publication;
- scene/update notification;
- transition timing and terminal release;
- image source selection, decode, transform, prefetch, and upload preparation;
- cache accounting/eviction;
- texture/PBO/FBO/program work;
- widget/provider polling and unchanged-state handling;
- metadata/artwork layout and publication;
- cursor/interaction overlays;
- lifecycle/barrier callbacks;
- logging/diagnostics;
- retries/backoff/fallback paths.

For each category record:

- owner and generation;
- trigger and requested frequency;
- accepted/completed/published frequency;
- thread/process;
- p50/p95/p99/max duration and queue age;
- allocations/copies/bytes retained;
- callback/GUI-delivery cost;
- behaviour while hidden/static/unchanged;
- cross-display duplication;
- whether state/result may be safely coalesced **after** logical integration;
- fidelity/lifecycle/resource invariants.

## Approved threading model

### GUI thread

Keep GUI-affine work only:

- QObject/QWidget/QPixmap lifecycle;
- GL operations and scene presentation;
- lightweight immutable-state commit/swap;
- minimal GUI timers and queued lifecycle admission;
- exact-wrapper validity checks.

Remove synchronous I/O, decode, expensive transforms, repeated allocation, broad logging, and callback cascades from GUI paths where evidence identifies them.

### General workers

Use existing bounded executors for coarse thread-safe work such as:

- file I/O and decode;
- expensive scaling/processing;
- approved shared visualizer analysis and Bubble authored work;
- metadata/provider work;
- bounded diagnostics parsing.

Do not create a worker task per bar/bubble/group or per paint.

When the same heavy, non-latency-critical periodic worker activity exists once per
display, phase it with a small deterministic offset derived from stable display
identity so all displays do not submit/complete together. This applies to maintenance,
prefetch, diagnostics, or equivalent background work only. It must not delay user
input, authoritative first frame, visualizer ticks, transition completion, lifecycle
barriers, or change logical source ordering. Measure queue age and first-visible tails
before accepting the offset; random drift and accumulating timers are not substitutes
for deterministic phase separation.

### Process workers

Use multiprocessing only for already-justified isolated heavy work where IPC/copy/commit cost is measured and bounded. The ImageWorker is not permission to move latency-sensitive visualizer state into another process.

### Rejected threading strategies

Do not introduce:

- persistent visualizer analysis/Bubble lanes;
- dedicated long-lived visualizer loops;
- more Python threads as a GIL workaround without measured native release;
- worker-to-paint acknowledgement;
- worker mutation of Qt/GL/compositor state;
- process recycling to reclaim memory;
- thread proliferation to hide tiny-job overhead.

## GIL and native work

Possible improvements require measurement:

- NumPy/vectorized computation that releases the GIL;
- Qt/native operations with identical output;
- fewer allocations/copies;
- larger/coarser jobs only when temporal goldens prove identical source/event integration and first-visible response.

A native/vectorized rewrite is still a behaviour change candidate if ordering, precision, event consumption, or timing changes.

## Visualizer workload contract

Preserve:

- one shared source/analysis authority;
- timestamped source/event identity;
- ordinary general-executor submission/publication semantics;
- mode-owned logical state;
- immutable current render state;
- no per-display duplicate simulation where shared state is truly identical;
- no logical event loss before simulation;
- no paint feedback.

Potential visualizer-adjacent optimization is limited to measured equivalent removal of allocations, copies, diagnostics, or duplicate immutable conversions until stronger temporal goldens exist.

## High-value non-visualizer targets

Prioritize owners that can lower CPU/memory without risking feel:

- unchanged provider/media polls that still publish/layout/repaint;
- duplicate image transforms or display representations;
- scaled-prefetch queue/accounting defects and fallback churn;
- per-display duplicate source work where transform/DPR are identical;
- redundant callback/signal delivery;
- stale timers/tasks/subscriptions after lifecycle changes;
- repeated formatting/logging;
- rebuilding immutable metadata, geometry, uniform maps, or shadows when unchanged;
- cache misses caused by unstable identity rather than insufficient budget;
- dead compatibility/retry paths with proven no production consumer.

## Task-rate interpretation

Task rate is a diagnostic, not a product target.

Acceptable conclusions require:

- named category/owner;
- useful work/result frequency;
- queueing and callback cost;
- fidelity and first-visible result;
- before/after p99 and CPU;
- no increased memory/latency.

Do not set an arbitrary lower visualizer publication rate. A lower task count that loses impulses, authored steps, reactivity, or smoothness is a failure.

Idle/static operation should approach low work where state is genuinely unchanged, but required monitoring and approved visualizer activity remain active.

## Safe coalescing

May coalesce after logical integration:

- duplicate scene invalidations;
- replaceable immutable render snapshots;
- identical geometry/style publications;
- stale image/provider results;
- duplicate deletion requests under one owner;
- unchanged metadata/layout commits.

May not coalesce away:

- audio/transient events before simulation;
- Bubble authored steps/events;
- lifecycle stop/reload commands;
- resource release;
- topology/settings changes;
- activation/generation boundaries;
- first authoritative frame.

## Allocation and copy control

Investigate high-frequency:

- image/QImage/QPixmap copies;
- bytes/memoryview/shared-memory conversions;
- list/dict/DTO rebuilds;
- string/log formatting;
- full-buffer hashing;
- Qt object creation;
- shader/uniform/geometry map rebuilds;
- per-display duplicate immutable state.

Reuse is allowed only with clear single ownership or immutable handoff. Do not share mutable buffers across threads without an explicit synchronization/lifetime contract.

## Event-loop and delivery health

Measure separately:

- scheduled versus actual GUI callback time;
- longest callbacks;
- worker completion-to-GUI commit;
- accepted-state-to-update and update-to-paint;
- paint duration;
- scene/source age at paint;
- synchronous I/O/network/lock/logging activity;
- transition and lifecycle overlap.

Cheap drawing can still be late because the GUI thread is occupied.

## Profiling method

Use sampled whole-process profiling, task-category snapshots, targeted timers, allocation/native-memory tools, and bounded stall traces.

Compare identical authored scenarios and cache state. Do not use self-reported worker duration alone; queueing, callback delivery, and retained outputs may dominate.

## Acceptance gates

For each optimization:

- exact owner and removed work are identified;
- current visualizer goldens and known-bad negative controls remain correct;
- user visual review passes when shared presentation/source paths are touched;
- source-to-first-visible and p99/max improve or remain equivalent;
- CPU falls in the named scenario;
- task/callback/allocation reduction is measured rather than assumed;
- whole-app RSS/private commit/VRAM do not worsen;
- no new lane, scheduler, timer, queue, process, retry, or synchronization authority is added;
- canonical-main behaviour remains correct and shared package routes pass bounded smoke coverage without a separate Media Center capture.

A candidate that merely shifts work, reduces task count, or lowers average CPU while harming feel or increasing memory is rejected.
