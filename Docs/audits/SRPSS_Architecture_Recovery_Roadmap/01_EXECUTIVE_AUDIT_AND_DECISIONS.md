# 01 — Executive Architecture Audit and Decision Record

## Scope

This audit compares:

- behavioural baseline `00edb57`;
- donor/head `7376bb9`;
- intermediate compositor work:
  - `7eed32c`
  - `6e4a2cf`
  - `7e10589`
  - `729ef2e`
  - `7376bb9`;
- supplied runtime evidence in `logs/evidence_chest`.

The unrelated large visualizer blob-mode removal predates the comparison baseline and must not influence the architectural judgement.

## Executive conclusion

The donor branch is not a viable repair foundation.

It contains useful low-level ideas, but the complete architecture:

- couples visualizer cadence to compositor presentation;
- uses a worker-to-Qt paint acknowledgement handshake;
- spreads lifecycle authority across too many objects;
- attempts partial GL reconstruction;
- hides incompatibilities behind a large compatibility façade;
- adds terminal-frame transactions and multiple generations;
- improves selected averages while worsening frame-time tails and perceived motion;
- introduces or exposes a repeatable `QOpenGLContext` cross-thread failure after Settings/Edit.

The recovery branch should remain based on `00edb57`.

The baseline is not acceptable as a final implementation because it also shows:

- approximately one-core CPU saturation;
- a very high recurring task rate;
- RAM and private-commit growth;
- severe VRAM growth during ordinary image cycling;
- insufficient resource-lifetime accounting;
- degraded smoothness under substantial background load.

Therefore:

> Use the baseline for behaviour, visualizer feel, and lifecycle topology.  
> Use selected donor concepts for explicit resource control and diagnostics.  
> Rebuild presentation and resource architecture instead of merging either implementation wholesale.

## Runtime evidence summary

The figures below are approximate representative active-window observations from the supplied logs. They must not be treated as laboratory-identical runs.

### Baseline `00edb57`

Observed strengths:

- visibly smoother visualizer and overlay motion;
- correct or much closer visualizer reactivity and elasticity;
- no reproduced GL crash after Settings/Edit in the supplied baseline run;
- fewer signs of compositor-side presentation starvation.

Observed weaknesses:

- main-process CPU repeatedly approaches one full logical core;
- compute submissions are approximately 100 per second;
- RSS reaches roughly 1.5–1.8 GB;
- private commit reaches roughly 4–5 GB;
- dedicated VRAM climbs from roughly 0.5 GB toward roughly 1.9 GB during the run;
- resource usage appears to grow with image cycling rather than reach a clean plateau;
- frame pacing degrades under extensive background activity.

### Donor/head `7376bb9`

Observed strengths:

- dedicated VRAM is substantially more bounded in the supplied runs;
- some average `DT_Max` and FPS counters improve;
- diagnostics provide better visibility into scheduling and resource generations.

Observed regressions:

- visualizer becomes flatter, less reactive, and less elastic;
- all modes show more microgaps and stutter;
- cursor halo and general UI movement become choppy;
- transitions can advance in visible jumps despite respectable average FPS;
- logs repeatedly classify gaps as compositor cadence starvation while no transition is active;
- paint waits and pending presentation generations accumulate;
- GPU utilization remains low while CPU remains high;
- Settings/Edit eventually reaches the same cross-thread `QOpenGLContext` failure;
- partial reinitialization does not remove the ownership defect.

## Root architectural finding: one surface became many authorities

The intended goal was one compositor surface per display.

The donor implementation achieved one physical surface while creating multiple coupled software authorities:

- visualizer simulation clock;
- adaptive timer worker;
- compositor dirty generation;
- requested generation;
- acknowledged generation;
- Qt event-loop presentation;
- transition terminal transaction;
- lifecycle generation;
- renderer generation;
- resource/texture generation;
- deferred warmup/retry state;
- widget/controller compatibility state.

A single surface is not itself the problem. The problem is that the surface became a synchronization hub for unrelated subsystems.

The desired system is:

- one surface;
- one GL owner;
- several independent state producers;
- no producer waiting for paint;
- one immutable latest scene snapshot;
- local transition completion;
- explicit resource lifetime.

## Why higher FPS looked worse

Average FPS measures count over time. It does not describe delivery uniformity.

A stream like:

```text
16 ms, 16 ms, 16 ms, 120 ms, 2 ms, 2 ms, 2 ms
```

can retain a respectable average while looking visibly broken.

The donor logs include:

- visualizer p95 gaps in the tens of milliseconds;
- maxima around 100–300 ms;
- paint wait outliers exceeding a second;
- pending update warnings;
- compositor cadence starvation;
- broader main-thread timer gaps.

This creates burst delivery:

1. simulation or transition time advances;
2. presentation stalls;
3. the next paint consumes a much later state;
4. motion visibly jumps.

The architecture must optimize p95/p99/max frame intervals and input-to-presentation latency, not merely average FPS.

## Why “more multithreading” is not the direct answer

Both versions use worker pools, yet the main process can saturate approximately one logical core.

Reasons include:

- Python GIL contention for Python-heavy work;
- Qt GUI and OpenGL thread affinity;
- high-frequency tiny task submission;
- callback and publication overhead;
- repeated state conversion and logging;
- queueing and wake-up costs;
- duplicate work across display or mode boundaries.

Twenty-three workers do not make small Python jobs free. The correct response is:

- less recurring work;
- larger/coarser jobs;
- latest-state coalescing;
- native/vectorized numeric paths where measured;
- explicit idle behaviour;
- no producer-to-paint blocking.

## Architecture decisions

### ADR-A: Recovery foundation

**Decision:** Continue from `recovery-00edb57`.

**Reason:** Better behavioural fidelity, smoother runtime, and safer Settings/Edit lifecycle.

**Constraint:** Baseline memory, GPU-resource, and task architecture must be replaced incrementally.

### ADR-B: Donor role

**Decision:** Keep `donor-7376bb9` intact as read-only donor/reference.

**Reason:** It contains useful implementation ideas and tests, but is not a safe mainline.

**Prohibition:** No wholesale merge or large blind cherry-pick.

### ADR-C: Visualizer priority

**Decision:** Visualizer feel is a protected product contract.

**Reason:** Reactivity and elasticity are difficult to reconstruct after infrastructure changes blur the cause.

**Consequence:** Infrastructure phases may not alter visualizer equations without a separate declared change.

### ADR-D: Presentation model

**Decision:** Producers publish latest state; painters consume latest state.

**Reason:** Blocking producers on paint acknowledgement caused starvation and burst delivery.

**Consequence:** No adaptive timer/presentation-ack handshake.

### ADR-E: Lifecycle

**Decision:** Restore full orderly teardown and recreation.

**Reason:** Partial reconstruction added lifecycle states without eliminating context ownership failures.

**Consequence:** Optimization of reconfiguration latency is deferred until correctness is proven.

### ADR-F: GL ownership

**Decision:** One explicit GUI/context owner performs all GL creation, mutation, and destruction.

**Reason:** Cross-thread context operations are invalid and difficult to recover from.

### ADR-G: Resource management

**Decision:** Adopt bounded, byte-accounted CPU and GPU stores.

**Reason:** Baseline RAM/VRAM growth is unacceptable.

**Consequence:** Every representation has one owner, a byte size, a generation, and deterministic retirement.

### ADR-H: Single surface

**Decision:** One compositor surface per display remains the long-term target.

**Reason:** It can remove stacked GL widget and z-order problems.

**Constraint:** It must not own simulation cadence, application lifecycle, or worker scheduling.

### ADR-I: Transition completion

**Decision:** Transition completion is local to the transition controller/compositor.

**Reason:** Distributed terminal transactions add failure modes without product value.

### ADR-J: Hashing

**Decision:** Whole decoded/upload buffer SHA-256 is not a default hot-path identity mechanism.

**Reason:** It adds a full memory-bandwidth pass and may force copies.

**Replacement:** Stable source identity plus transform metadata and generation.

## Success conditions relative to both versions

The final architecture must be:

- at least as responsive and elastic as baseline;
- smoother than baseline under background load;
- free from donor lifecycle crash;
- materially lower in CPU than both;
- materially lower and bounded in RAM;
- bounded below donor worst-case VRAM and far below baseline growth;
- simpler in ownership and number of runtime state machines;
- explainable from a single resource dump;
- testable through deterministic visualizer replay and hostile lifecycle loops.
