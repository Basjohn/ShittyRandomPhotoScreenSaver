# 03 — Work Order and Phase Gates

## Why ordering matters

The failed compositor work mixed several difficult problems:

- single-surface composition;
- visualizer integration;
- scheduling;
- backpressure;
- transition terminal state;
- partial lifecycle reconstruction;
- texture sharing;
- worker/render boundaries;
- performance instrumentation.

The recovery must establish evidence and invariants before changing architecture. Otherwise later changes cannot be attributed.

## Ordered program

### Phase 0 — Repository and evidence freeze

**Goal:** Create a reproducible starting point.

**Allowed changes:** Documentation, scripts that do not alter runtime.

**Deliverables:**

- branch verification;
- evidence hashes;
- environment manifest;
- ownership inventory;
- timer/task inventory.

**Do not:**

- optimize;
- port donor code;
- change visualizer;
- change Settings/Edit.

### Phase 1 — Measurement foundation

**Goal:** Know where time and bytes go without changing behavior.

Add:

- frame interval recorder;
- event-loop stall recorder;
- task category counters;
- CPU cache byte accounting;
- GL resource byte accounting;
- lifecycle resource snapshots.

Use a fixed-size ring buffer and periodic aggregation.

**Pass criteria:**

- less than 2% CPU overhead in target scenario;
- no visualizer fidelity change;
- no material p99 regression;
- metrics survive Settings/Edit.

### Phase 2 — Visualizer fidelity lock

**Goal:** Protect the hardest-to-recover product behavior before infrastructure work.

Build deterministic replay outside Spotify timing. Capture the baseline mode state sequence.

**Pass criteria:**

- replay is deterministic within documented floating-point tolerance;
- live and replay pathways use the same simulation code;
- manual review artifacts exist;
- golden data is versioned and protected.

### Phase 3 — Lifecycle correction

**Goal:** Make Settings/Edit reliable before adding shared GL architecture.

Return to simple full teardown/recreation and formalize it.

**Pass criteria:**

- 50 Settings cycles;
- 50 Edit cycles;
- 50 mixed cycles;
- zero cross-thread context errors;
- no growth in live resource count;
- no callbacks into dead generations.

### Phase 4 — Baseline resource containment

**Goal:** Stop RAM/VRAM growth while retaining baseline rendering topology.

This phase deliberately precedes single-surface composition. Resource lifetime can be fixed independently and measured cleanly.

**Pass criteria:**

- 30-minute image cycling reaches a plateau;
- tracked bytes explain most application-owned memory;
- no image representation lacks an owner;
- visualizer unchanged.

### Phase 5 — Workload and task-rate reduction

**Goal:** Reduce one-core saturation before changing presentation topology.

Targets:

- remove unnecessary recurring tasks;
- batch tiny jobs;
- stop idle work;
- coalesce duplicate publications;
- vectorize measured numeric hotspots.

**Pass criteria:**

- materially lower CPU;
- lower task submissions per second;
- same or better p99;
- visualizer fidelity passes.

### Phase 6 — Explicit GPU resource store

**Goal:** Introduce bounded sharing/reuse as an isolated resource feature.

This is the most valuable donor idea, but it must be smaller than the donor implementation.

**Pass criteria:**

- exact byte cap;
- deterministic context-thread deletion;
- no stale generation reuse;
- no registry lock around GL operations;
- no memory growth under churn.

### Phase 7 — Visualizer/presentation decoupling

**Goal:** Establish the correct producer/consumer relationship before single-surface composition.

Visualizer simulation produces immutable latest state. Presentation may skip intermediate states but may not block simulation.

**Pass criteria:**

- deterministic output unchanged;
- no paint waits;
- no compositor-owned visualizer timer;
- input-to-state latency within baseline tolerance;
- smooth recovery after injected UI stalls.

### Phase 8 — Narrow single-surface compositor

**Goal:** Replace stacked surfaces without importing donor orchestration.

Compositor owns:

- GL surface;
- draw order;
- scene snapshot;
- local animation request.

It does not own:

- simulation;
- image selection;
- Settings lifecycle;
- worker pools;
- producer acknowledgements.

**Pass criteria:**

- no overlay stuck on display 0;
- correct z-order on every display;
- cursor halo smooth;
- p99 no worse than prior phase;
- lifecycle loops still pass.

### Phase 9 — Transition simplification

**Goal:** Remove distributed completion machinery.

A transition is a local timed draw state.

**Pass criteria:**

- no terminal transaction;
- no generation handshake with image pipeline;
- destination finalizes exactly once;
- resources release immediately;
- interrupted transitions remain correct.

### Phase 10 — Compatibility deletion

**Goal:** Remove temporary and donor-shaped scaffolding.

Delete:

- dynamic forwarding;
- legacy widget impersonation;
- duplicated overlay paths;
- obsolete retry state;
- dead flags and metrics.

**Pass criteria:**

- one runtime path;
- no silent fallback;
- architecture diagram matches code.

### Phase 11 — Full hostile validation

**Goal:** Prove the final architecture is better under realistic adversity.

Scenarios:

- idle;
- visualizer only;
- transitions only;
- visualizer plus transitions;
- background CPU;
- background disk;
- background GPU;
- mixed load;
- Settings/Edit during animation;
- long soak.

### Phase 12 — Release and documentation

**Goal:** Freeze the architecture and evidence.

## Dependency rules

- Phase 2 must complete before any visualizer integration rewrite.
- Phase 3 must complete before shared-context or single-surface work.
- Phase 4 must complete before claiming donor resource work is necessary.
- Phase 5 must complete before adding another scheduler.
- Phase 6 must complete before the final compositor depends on shared textures.
- Phase 7 must complete before single-surface visualizer rendering.
- Phase 8 must complete before deleting the legacy visualizer surface.
- Phase 11 must pass before release candidate.

## Rollback discipline

Each phase must end at a clean commit. If a phase fails:

1. preserve its report and evidence;
2. reset or revert the phase branch;
3. do not carry “temporary” corrective flags into the next phase;
4. revise the architecture decision;
5. rerun the prior phase benchmark to confirm recovery.

## Forbidden shortcut

Do not jump directly from baseline to the donor single-surface implementation and then try to optimize it.

That route recreates the original failure: too many variables change at once, visualizer feel is lost, and the runtime becomes impossible to reason about.
