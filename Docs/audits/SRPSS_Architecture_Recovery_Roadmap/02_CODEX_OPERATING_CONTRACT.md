# 02 — Codex Operating Contract

This file defines how Codex must execute the recovery. It is intentionally strict.

## 1. Work only from the recovery line

Default branch:

```text
recovery-00edb57
```

Create a short-lived child branch per phase, for example:

```text
recovery/p01-measurement
recovery/p03-gl-lifecycle
recovery/p04-memory-bounds
```

Do not work directly on `donor-7376bb9`.

Do not merge `donor-7376bb9`.

Do not cherry-pick a large donor commit merely because it contains a desired feature. Reconstruct the smallest coherent idea after reviewing its dependencies.

## 2. Read before editing

Before a phase:

1. read this contract;
2. read the live checklist;
3. read the phase-specific document;
4. inspect relevant baseline code;
5. inspect relevant donor code;
6. inspect applicable logs;
7. write a brief phase plan in the phase report.

Do not start with repository-wide search-and-replace.

## 3. One architecture concern per phase

Do not combine:

- lifecycle rewrite;
- compositor rewrite;
- visualizer behavior changes;
- cache rewrite;
- transition rewrite;
- threading rewrite;

into one commit or phase.

A phase should have one dominant hypothesis and measurable outcome.

## 4. Behaviour is frozen unless explicitly declared

During infrastructure work, do not alter:

- visualizer smoothing coefficients;
- spring constants;
- decay curves;
- amplitude normalization;
- bar count/layout semantics;
- bubble force/elasticity;
- mode-specific thresholds;
- user transition timing/easing;
- image scale/crop quality.

Any intentional visualizer change requires:

- `templates/VISUALIZER_CHANGE_DECLARATION.md`;
- before/after deterministic replay;
- manual approval;
- separate commit.

A refactor that “should be equivalent” is still subject to fidelity tests.

## 5. Never optimize from averages alone

Every performance claim must include:

- p50;
- p90;
- p95;
- p99;
- maximum;
- sample count;
- scenario duration;
- CPU;
- GPU busy;
- RSS;
- private commit where available;
- tracked GPU bytes;
- task submission rate.

An average FPS improvement with worse p99 or worse manual motion is a failed optimization.

## 6. No hidden fallback architecture

Do not keep two complete runtime paths behind automatic fallback unless the phase explicitly requires a temporary comparison switch.

Temporary dual paths must have:

- an explicit development flag;
- a removal deadline;
- separate metrics;
- no automatic silent activation;
- no shared mutable state.

At the end of the phase, remove the losing path or mark the phase incomplete.

## 7. No broad compatibility façade

Do not introduce:

- dynamic attribute forwarding;
- giant `_LOCAL_ATTRS` registries;
- duck-typed widget impersonation;
- free functions receiving a full widget/controller instance;
- generic “manager” objects owning unrelated responsibilities.

Use narrow typed interfaces.

## 8. GL rules are absolute

Codex must not:

- call `makeCurrent()` from a worker;
- create/delete textures or FBOs from a worker;
- destroy GL-owned Qt objects after their context is gone;
- retain GL handles across context generation changes;
- rely on Python finalizers for GL deletion;
- swallow context-affinity assertion failures;
- “fix” the crash by suppressing the warning.

Every GL mutation must have a named owner and a current context.

## 9. Producers do not wait for painters

Never add:

- paint acknowledgement waits;
- event waits for `paintGL`;
- worker loops blocked on presentation generation;
- compositor starvation classification as normal flow.

Producers publish latest state. The compositor consumes it when Qt paints.

Critical control events may use explicit bounded acknowledgement, but normal animation frames may not.

## 10. Lifecycle correctness precedes fast reconfiguration

Settings/Edit initially use full teardown and recreation.

Do not optimize to partial reinit until:

- 100 mixed lifecycle cycles pass;
- resource accounting returns to expected baseline each cycle;
- context ownership is formally documented;
- the partial alternative has a separate design review.

Fast-but-fragile Settings/Edit is unacceptable.

## 11. Every resource is byte-accounted

For every cache or GPU resource:

- identity;
- owner;
- byte size;
- dimensions/format;
- generation;
- lease/reference count;
- creation time;
- last-use time;
- deletion reason;

must be available in development diagnostics.

Count-only cache limits are insufficient.

## 12. Logging must not become workload

No per-frame INFO logging.

Use:

- aggregated counters;
- histograms;
- periodic summaries;
- debug-only ring buffers;
- deferred formatting;
- sampling.

Measure instrumentation overhead with it enabled and disabled.

## 13. Commit discipline

Each commit message should state:

- phase;
- architecture concern;
- invariant protected;
- benchmark or test added;
- rollback relevance.

Example:

```text
P04: bound decoded-image cache by bytes

- adds exact decoded/scaled image accounting
- preserves visualizer and compositor behavior
- evicts only unpinned entries
- adds 30-minute plateau benchmark
```

## 14. Required end-of-phase output

For every phase, Codex must update:

- `00_INDEX_AND_LIVE_CHECKLIST.md`;
- a completed phase report;
- benchmark report where applicable;
- decision record for any architecture deviation;
- relevant diagrams or ownership tables.

Do not claim completion in chat without updating repository artifacts.

## 15. Stop conditions

Stop implementation and mark `[!]` when:

- visualizer golden tests change unexpectedly;
- manual visualizer review reports flatter or less elastic behavior;
- p99 frame interval worsens materially;
- lifecycle produces a context warning;
- RAM/VRAM grows monotonically in a plateau test;
- resource accounting cannot explain usage;
- task rate rises without a measured benefit;
- the solution requires another generation/flag/retry to compensate for unclear ownership.

The correct action is to revisit the model, not add another patch.
