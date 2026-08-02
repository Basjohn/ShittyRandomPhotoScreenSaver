# 08 — CPU, Threading, and Workload Plan

## Evidence

Both versions can consume roughly one full logical core during active operation. Both submit approximately 90–100 compute jobs per second in representative windows.

The donor branch often shows low GPU busy while CPU remains high, indicating orchestration and CPU-side work dominate.

## Primary goal

Reduce total work and coordination before adding threads.

## Work inventory

Categorize every recurring operation:

- visualizer audio polling;
- audio normalization;
- visualizer simulation;
- render-state publication;
- compositor update request;
- transition timing;
- image decode;
- image scale/crop;
- upload preparation;
- texture upload;
- cache bookkeeping;
- metadata overlay;
- cursor halo;
- diagnostics;
- settings/lifecycle polling;
- retry/backoff tasks.

For each category record:

- trigger;
- frequency;
- thread;
- typical duration;
- p95 duration;
- allocations;
- queueing delay;
- whether result may be coalesced;
- whether work occurs when hidden/static;
- whether it duplicates another display's work.

## Threading principles

### GUI thread

Keep only:

- Qt widget operations;
- GL operations;
- scene snapshot swap;
- lightweight drawing;
- minimal timer callbacks.

### Workers

Use for coarse operations:

- image file I/O;
- decode;
- expensive scaling where thread-safe;
- batch numerical analysis;
- metadata retrieval.

Avoid workers for tiny per-frame functions that return through callbacks faster than queueing overhead.

## GIL reality

Python-heavy threads do not reliably scale across cores because of the GIL.

Possible measured solutions:

- NumPy/vectorized computation that releases the GIL;
- Qt/C++ native operations;
- fewer and larger jobs;
- a dedicated long-lived analysis thread with bounded input, if justified;
- multiprocessing only for truly heavy isolated work where copy/IPC cost is acceptable.

Do not introduce multiprocessing for visualizer state without proving latency and memory costs.

## Visualizer workload

Preferred model:

- one logical controller;
- timestamped input batches;
- simulation advances in a predictable step or elapsed-time method;
- one immutable latest state publication;
- no per-display duplicate simulation;
- display renderers consume shared logical state;
- no worker task per bar/bubble/group;
- no callback cascade per frame.

## Task-rate targets

Initial targets, subject to measurement:

- no recurring general-pool task per compositor frame;
- no recurring paint-ack task;
- visualizer analysis publications at only the rate needed for fidelity;
- image pipeline tasks occur per image request, not per display paint;
- steady-state general compute submissions materially below baseline's ~100/sec;
- idle static screensaver approaches near-zero task submissions outside required monitoring.

The target is not an arbitrary number. Every remaining recurring task must justify its frequency.

## Coalescing

Coalesce:

- multiple scene invalidations before a paint;
- multiple visualizer render-state updates;
- repeated identical geometry updates;
- stale image request results;
- duplicate metadata refresh;
- repeated resource deletion requests.

Do not coalesce away:

- logical audio impulses before simulation;
- lifecycle stop commands;
- resource release;
- display topology changes;
- settings changes.

## Event-loop health

Record GUI event-loop delay separately from render time.

A frame can be cheap to draw but late because the GUI thread was occupied.

Monitor:

- timer scheduled vs actual fire time;
- longest callback;
- paint duration;
- queued signal backlog;
- synchronous filesystem or network access;
- logging cost.

## Allocation control

High-frequency allocations create CPU and memory pressure.

Avoid per-frame:

- large lists/dicts;
- whole image copies;
- string formatting;
- SHA-256 of full decoded buffers;
- repeated Qt object creation;
- rebuilding shader uniform maps;
- rebuilding geometry when unchanged.

Reuse safe CPU buffers where ownership is clear. Do not reuse mutable buffers across threads without explicit synchronization.

## Profiling method

Use:

- sampled profiler for overall CPU;
- targeted timers for known operations;
- allocation tracing in development runs;
- task queue metrics;
- Python thread stacks during stalls.

Do not optimize based only on self-reported task durations. Queueing and callbacks may dominate.

## Acceptance gates

For each optimization:

- visualizer golden tests pass;
- manual feel review passes;
- p99 frame interval improves or remains equivalent;
- task rate decreases or the increased rate has a measured reason;
- CPU falls in the relevant scenario;
- no RAM/VRAM growth;
- no new worker/GUI synchronization.
