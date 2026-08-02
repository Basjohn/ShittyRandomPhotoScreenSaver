# 01 — Executive Architecture Audit and Decisions

Last reconciled: 2026-08-02

## Scope and historical basis

The original audit compared:

- behavioural baseline `00edb57`;
- donor/reference `7376bb9`;
- intermediate compositor work `7eed32c`, `6e4a2cf`, `7e10589`, and `729ef2e`;
- supplied baseline/donor runtime evidence.

That comparison remains useful architectural history. It no longer describes the complete current state of `main`.

## Original conclusion that remains valid

The donor branch was not a viable repair foundation.

It contained useful low-level ideas, but its complete orchestration:

- coupled visualizer cadence to compositor presentation;
- used producer-to-paint acknowledgement;
- spread lifecycle authority across too many objects;
- attempted partial GL reconstruction;
- hid incompatibilities behind compatibility machinery;
- added terminal-frame transactions and overlapping generations;
- improved selected averages while worsening perceived motion and frame-time tails;
- retained invalid GL-context ownership paths.

The original baseline was also not an acceptable final implementation because of high CPU/task rate, RAM/private-commit growth, severe VRAM growth, duplicate representations, and insufficient lifetime accounting.

The durable conclusion remains:

> Preserve approved behaviour and visualizer feel.  
> Adopt only isolated resource/accounting principles.  
> Reject donor orchestration, paint acknowledgement, partial reinit, and compatibility mega-layers.  
> Require one owner and evidence for every optimization.

## Current state amendments

The project now works directly on `main`, not `recovery-00edb57`.

Current behavioural references:

```text
pre-persistent-lane reference: 6f188adadabb77b1a9d47a0fe1685c86ad39fb77
rejected lane checkpoint:       666624d421b08f978c5f610571a078570150a1e7
restored executor behaviour:    4bde89e8e39177dc4dd7b5e64b9ac99256ab9486
approved visual behaviour:      ff93461685476bd0657aa88312fc2e35e9037880
rejected Spectrum smoothing:    ebfec397fb2ae0bbc1f3e95c5298c0e7d6ff1db9
```

Later evidence established:

1. A dedicated/persistent analysis lane and persistent Bubble lane changed scheduling semantics and degraded behaviour despite plausible throughput goals. The ordinary general COMPUTE executor is the approved production model.
2. Paint-local Spectrum decay created a second presentation cadence and visibly reduced smoothness. Presentation may not self-schedule from paint or mutate authoritative state in `paintGL()`.
3. Settings full runtime destruction/recreation now succeeds, but modal wrapper lifetime remains invalid in R-56.
4. CUSTOM/Edit still admits teardown synchronously from inside the retiring manager save graph. R-53 proves the admission boundary failure above 99% confidence.
5. Application-owned resource accounting and deterministic GL teardown improved substantially, but active whole-process usage remains excessive even when it plateaus.
6. Logical visualizer goldens alone were insufficient to detect scheduling and first-visible-response damage. Stronger temporal and installed approval artifacts are mandatory.

## Current resource conclusion

Latest active evidence reports approximately:

- 847–1074 MiB whole-app resident RAM;
- 2.86–3.17 GiB private commit;
- 554–777 MiB dedicated VRAM;
- 84–121 MiB shared GPU memory.

Those values are too high for a screensaver. Containment is necessary but no longer sufficient. The project must attribute and reduce absolute usage without lowering perceivable fidelity.

## Root architectural finding

The failed donor architecture turned one physical surface into a synchronization hub for unrelated authorities:

- visualizer simulation;
- adaptive scheduling;
- dirty/requested/acknowledged presentation generations;
- Qt paint delivery;
- transition terminal transactions;
- runtime/context/resource generations;
- deferred warmup/retry state;
- compatibility widget/controller state.

The target remains:

- one owner per mutable concern;
- no producer waiting for paint;
- immutable/latest handoffs only after logical integration;
- full lifecycle boundaries;
- explicit resource lifetime;
- local transition completion;
- no additional cadence hidden inside presentation.

A one-surface compositor is a later target, not a justification to centralize simulation, scheduling, lifecycle, or resource policy.

## Why higher FPS can look worse

Average FPS does not describe delivery uniformity. Burst delivery can retain a respectable average while producing visible jumps.

Performance decisions must use:

- p50/p90/p95/p99/max intervals;
- source-to-first-visible latency;
- latest-state age at paint;
- GUI event-loop lateness;
- user visual judgement;
- resource and task ownership.

Manual rejection overrides favorable averages.

## Why more threads are not the default answer

Python-heavy work, Qt/GL affinity, callback delivery, queueing, repeated conversion, logging, and duplicate work can dominate even with many workers.

The accepted direction is:

- remove work before moving it;
- preserve the ordinary executor where its timing is behaviourally approved;
- use larger/coarser jobs only where temporal goldens prove equivalence;
- reduce duplicate representations and publications;
- stop unchanged/hidden work;
- use native/vectorized paths only after owner-level measurement;
- never lower visualizer cadence or impulses merely to reduce task rate.

## Architecture decisions

### ADR-A — Working line

**Decision:** Work directly on `main`.

**Constraint:** No branches, forks, or pull requests unless the user explicitly requests them.

### ADR-B — Behavioural authority

**Decision:** `ff934616` is the current user-approved Bubble/Spectrum behavioural authority; `00edb57` remains historical context.

**Consequence:** Later documentation or optimization commits do not replace visual approval automatically.

### ADR-C — Donor role

**Decision:** Keep `7376bb9` as reference-only history.

**Consequence:** No wholesale merge, large blind cherry-pick, or active donor-driven work without a current measured requirement.

### ADR-D — Visualizer family protection

**Decision:** All supported modes are protected. Aggregate load is presumed shared/runtime-owned unless direct evidence proves a mode-specific owner.

**Consequence:** Bubble is not a default CPU, memory, task, cadence, or fidelity target. Mode-specific changes require explicit user authorization.

### ADR-E — Approved visualizer execution

**Decision:** Preserve the ordinary general COMPUTE executor semantics restored at `4bde89e`.

**Rejected:** persistent analysis/Bubble lanes, cadence caps, terminal batching, source decimation, and producer-to-paint control.

### ADR-F — Presentation authority

**Decision:** One authoritative visualizer presentation cadence; painters consume immutable/current state.

**Rejected:** self-requested paint loops, paint-derived clocks, and authoritative mutation inside `paintGL()`.

### ADR-G — Lifecycle

**Decision:** Full orderly teardown and recreation remain mandatory.

**Addition:** teardown may not begin from inside a retiring session owner's call stack. Persist and retire temporary Edit state first; queue engine-owned admission on a later GUI turn.

### ADR-H — Qt wrapper lifetime

**Decision:** Python wrapper identity is not QObject liveness.

**Consequence:** Observe destruction before modal/deletion boundaries and validate Shiboken/QPointer state before later touches.

### ADR-I — GL ownership

**Decision:** GL creation, mutation, and destruction occur on one explicit GUI/context owner. Failed deletion retains ownership and fails closed.

### ADR-J — Resource management

**Decision:** Every representation is byte-accounted and deterministically retired.

**Addition:** whole-process RSS/private-commit/VRAM must be reconciled against tracked resources and reduced to reasonable levels; accounting alone is not completion.

### ADR-K — Transition completion

**Decision:** transition completion is local and exactly-once; no pipeline/worker terminal acknowledgement.

### ADR-L — Identity and hashing

**Decision:** stable source/transform/generation metadata is the default identity. Full-buffer hashing is diagnostic-only unless separately justified.

## Current success conditions

The architecture succeeds only when it is:

- equal or better than `ff934616` in user-observed visualizer feel;
- temporally protected against `666624d`, terminal batching, and `ebfec397` known-bad shapes;
- free from invalid wrapper touches and re-entrant Edit teardown;
- repeatable through Settings/Edit with zero retired owners;
- materially lower in CPU/task work without cadence or quality cuts;
- both bounded and appropriately low in RSS/private commit/VRAM;
- explainable from resource plus process-level diagnostics;
- simpler in authority, state machines, callbacks, and generations;
- validated in normal and Media Center builds under hostile and long-duration scenarios.