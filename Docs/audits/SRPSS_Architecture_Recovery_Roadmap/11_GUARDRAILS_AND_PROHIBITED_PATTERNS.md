# 11 — Guardrails and Prohibited Patterns

## Purpose

These guardrails exist because the failed architecture accumulated individually plausible fixes that collectively created an unmanageable state machine.

## Hard architectural guardrails

### G-1: One owner per mutable concern

No object may jointly own more than one of:

- application lifecycle;
- GL resource lifetime;
- visualizer simulation;
- transition simulation;
- image pipeline;
- presentation scheduling.

A coordinator may invoke owners but not absorb their internal state.

### G-2: No producer-to-paint wait

Normal frame producers may never wait on:

- `paintGL`;
- Qt `update()` completion;
- presentation generation;
- compositor acknowledgement;
- terminal frame acknowledgement.

### G-3: No GL outside owner thread/context

No exceptions, retries, or warnings-only mode.

### G-4: No partial reinit until separately approved

Full teardown/recreate is mandatory.

### G-5: No visualizer behavior changes in infrastructure commits

Automated and manual fidelity gates apply.

### G-6: No unbounded cache or queue

Every cache/queue has:

- byte/count cap;
- eviction/drop policy;
- metrics;
- owner;
- lifecycle reset.

### G-7: No silent fallback

Fallback activation must be explicit and observable.

### G-8: No dynamic compatibility façade

No broad `__getattr__`, `__setattr__`, or giant forwarded attribute lists.

### G-9: No state-machine expansion without deletion

If a change introduces a new state, flag, generation, retry counter, or event:

- identify which old state it replaces;
- prove why ownership cannot express the requirement;
- document transitions;
- add state-transition tests.

Adding a new state without removing complexity requires architecture review.

### G-10: No optimization without a baseline scenario

Every optimization names:

- scenario;
- before data;
- after data;
- fidelity result;
- rollback.

## Performance guardrails

- p99 and max matter more than average FPS.
- CPU reduction may not come from lowering visualizer fidelity.
- RAM/VRAM must plateau.
- task rate must be categorized.
- instrumentation overhead must be measured.
- idle/static work must approach zero where practical.
- no full-buffer hash/copy in a recurring hot path without evidence.

## Visualizer guardrails

- golden input fixtures are immutable during infrastructure work;
- logical simulation is independent of paint cadence;
- beat impulses cannot be dropped before simulation;
- elapsed-time handling is explicit;
- mode-specific state is not reconstructed through generic smoothing;
- manual review is required.

## Lifecycle guardrails

- stop producers first;
- disconnect callbacks;
- cancel/drain workers;
- destroy GL resources with current context;
- invalidate generation;
- destroy surface last;
- assert no old resource remains;
- start from clean state.

## Resource guardrails

- exact byte accounting;
- deterministic release;
- context generation;
- no Python-GC-owned GL lifetime;
- no registry GL calls under lock;
- no stale texture ID reuse;
- no per-display duplicate if shareable and identical;
- no retained fallback frame without a bounded reason.

## Prohibited anti-patterns

### “Fix the symptom with another flag”

Examples:

- `paint_pending_but_not_really`;
- `terminal_ack_deferred`;
- `visualizer_retry_after_pause`;
- `force_reinit_on_next_gap`;
- `ignore_generation_once`.

These indicate unclear ownership.

### “Thread pool as animation loop”

Submitting one general compute task per visual frame creates queueing and callback overhead.

### “Compatibility forever”

Temporary adapters must have removal criteria and a deadline.

### “Metrics as control flow”

A profiler or starvation classifier must not trigger normal scheduling decisions.

### “More averaging to hide jitter”

Smoothing values to conceal presentation gaps damages feel.

### “Keep all representations for speed”

Retaining decoded, scaled, pixmap, bytes, texture, and fallback copies without a byte budget is not optimization.

### “Fast Settings by retaining unknown state”

A quick partial restart is not a win if it corrupts context ownership.

### “Tests passed, therefore feel passed”

Logical tests do not replace deterministic temporal replay and manual review.

## Code review questions

Every review must answer:

1. Who owns this mutable state?
2. Which thread mutates it?
3. Can it outlive its runtime/context generation?
4. What happens when paint is late?
5. What happens when Settings opens now?
6. What bytes does it retain?
7. What work happens while hidden/static?
8. Does it alter visualizer timing or equations?
9. Does it add a state/flag/retry?
10. What evidence proves improvement?

A review that cannot answer these questions is incomplete.
