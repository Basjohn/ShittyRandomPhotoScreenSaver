# 02 — Operating Contract

Last reconciled: 2026-08-02

This file defines how architecture-recovery work is executed. `Current_Plan.md` owns the current task order; this contract owns execution discipline.

## 1. Work directly on `main`

Default branch:

```text
main
```

Do not create a branch, fork, or pull request unless the user explicitly requests one.

Keep changes narrow, mechanically verifiable, and independently reversible. Use separate commits when concerns can fail independently.

The donor commit `7376bb9` is read-only reference history. Do not merge it wholesale or use it as a current implementation authority.

## 2. Read current authority before editing

Before implementation:

1. read the relevant section of `Current_Plan.md`;
2. read the focused guardrail and historical bug record;
3. read the phase-specific roadmap document;
4. inspect current `main` code and tests;
5. inspect baseline/donor code only when it answers a specific historical or extraction question;
6. inspect applicable deterministic and installed evidence;
7. state confidence when the causal claim is below 90%.

Do not start from old branch instructions, stale phase completion claims, or repository-wide search-and-replace.

## 3. One dominant architecture concern per change

Do not combine independent rewrites of:

- lifecycle admission;
- Qt wrapper lifetime;
- compositor/presentation;
- visualizer behaviour;
- cache/resource ownership;
- transition completion;
- threading/scheduling;
- diagnostics.

A change should have one dominant hypothesis, one rollback point, and measurable acceptance.

## 4. The user is the visual authority

User-observed behaviour overrides averages and green tests.

Current approved Bubble/Spectrum behaviour is tied to exact commit `ff934616`, code-equivalent to restored executor commit `4bde89e`.

During infrastructure or resource work, do not alter:

- visualizer cadence or source sampling;
- attack, decay, normalization, thresholds, spring constants, damping, elasticity, or amplitudes;
- logical impulse/event consumption;
- bar count or layout semantics;
- mode activation/generation rules;
- target resolution, precision, or renderer quality;
- transition timing/easing;
- image crop/scale quality;
- artwork, shadow, widget-content, or first-frame quality.

Any intentional visualizer behaviour change requires:

- an explicit user request or approval;
- a completed visualizer change declaration;
- before/after deterministic and temporal evidence;
- installed review;
- a separate reversible commit.

A refactor claimed to be equivalent still needs the unchanged goldens and installed comparison.

## 5. Protect the visualizer family; do not blame Bubble by default

All supported modes are protected.

Aggregate CPU, task, RAM, commit, or VRAM load is presumed to arise from shared/runtime ownership until direct owner-level evidence proves otherwise.

Bubble is not a default optimization target. Do not change Bubble-specific code, cadence, batching, physics, or publication merely because a combined visualizer scenario is expensive. Mode-specific production changes require direct evidence and explicit user authorization.

## 6. Preserve the accepted executor model

The ordinary general COMPUTE executor restored at `4bde89e` is the approved production behaviour.

Do not reintroduce:

- persistent audio-analysis lanes;
- persistent Bubble lanes;
- dedicated long-lived visualizer worker loops;
- terminal batching;
- visualizer cadence caps;
- source decimation;
- paint acknowledgement;
- producer waits for presentation.

A scheduler change is a behavioural change even when equations remain identical.

## 7. Never optimize from averages alone

Every performance claim must identify:

- exact commit and scenario;
- environment and cache/warmup state;
- p50/p90/p95/p99/max timing;
- sample count and duration;
- source-to-first-visible latency where relevant;
- process and event-loop CPU;
- task category/rate/queueing;
- whole-app RSS and private commit;
- main/child process split;
- dedicated and shared GPU memory;
- tracked CPU/GL bytes;
- visual/manual result.

An average-FPS or task-count improvement with worse perceived motion, first-visible response, p99, or resource ownership is a failed optimization.

## 8. Plateau and absolute footprint are separate gates

Resource work must prove both:

1. no monotonic growth across equivalent cycles;
2. an evidence-backed reasonable steady-state footprint.

Do not declare success because usage is flat near one GiB RSS, multi-GiB private commit, or more than half a GiB dedicated VRAM.

Do not use:

- working-set trimming;
- allocator trimming;
- production `gc.collect()`;
- process/worker recycling;
- cache-budget inflation;
- reduced fidelity;
- ignored owners;

to manufacture a lower graph.

## 9. No hidden fallback architecture

Do not keep two complete runtime paths behind an automatic fallback.

A temporary comparison path requires:

- explicit development-only activation;
- separate metrics;
- no shared mutable authority;
- a removal criterion;
- no silent production fallback.

## 10. No broad compatibility façade

Do not introduce:

- broad dynamic forwarding;
- giant forwarded-attribute registries;
- widget/controller impersonation;
- whole-owner objects passed through generic free functions;
- generic managers owning unrelated responsibilities.

Use narrow interfaces and immutable intent/state.

## 11. GL rules are absolute

Never:

- call `makeCurrent()` or mutate GL from workers;
- create/delete textures, FBOs, PBOs, buffers, programs, or GL-owned Qt objects off the owner GUI/context thread;
- clear handle ownership after failed deletion;
- retain handles across context generations;
- rely on finalizers/GC for GL deletion;
- suppress affinity failures;
- make two local owners responsible for deleting the same numeric handle.

Share-group accessibility is not deletion ownership.

## 12. Producers do not wait for painters

Normal state producers may not wait for:

- `paintGL()`;
- `update()` completion;
- presentation generation;
- paint acknowledgement;
- terminal-frame acknowledgement.

There is one authoritative visualizer presentation cadence. Do not create self-requested paint loops, paint-derived clocks, or authoritative mutation inside `paintGL()`.

## 13. Lifecycle correctness precedes speed

Settings and committed CUSTOM Edit use full stop–destroy–recreate.

Teardown may not begin from inside a retiring session owner's call stack.

For Edit:

1. persist the complete graph-based layout;
2. explicitly retire temporary shells/callbacks/key-filter/session state;
3. return from manager/action/key-filter frames;
4. queue one engine-owned immutable reload intent on a later GUI turn;
5. validate generation and exact manager identity;
6. perform the same full fail-closed teardown and reconstruction.

For modal Qt objects, a Python wrapper is not proof of a live C++ object. Observe destruction before the deletion boundary and validate wrapper liveness before every later method call.

No partial reinit without a separate approved architecture proposal.

## 14. Every retained representation is accounted

For every cache, image, pixmap, upload buffer, texture, FBO, PBO, mapping, queue item, and fallback frame, development diagnostics must identify:

- stable identity;
- owner;
- logical/physical byte size where available;
- dimensions/format;
- runtime/context/source generation;
- lease/reference state;
- creation/last-use time;
- retirement reason.

Count-only limits are insufficient. Tracked counters must also reconcile against process-level memory.

## 15. Logging must not become workload

Use bounded counters, histograms, sampled summaries, ring buffers, and deferred formatting.

No per-frame INFO logging. Diagnostics must not request paints, alter cadence, enumerate live Qt objects off-thread, or become control flow.

## 16. Tests must reproduce the real ownership shape

A stub that only increments a counter does not prove synchronous signal/lifecycle safety.

Tests for lifecycle and scheduling changes must reproduce:

- real signal relay timing;
- GUI-turn boundaries;
- weakref death without `gc.collect()`;
- stale generation/identity rejection;
- exact known-bad negative controls;
- installed runtime behaviour where automation cannot judge feel.

Do not rewrite expected output merely to make a candidate pass.

## 17. Commit discipline

Each commit should state:

- the concern changed;
- the invariant protected;
- evidence/test added;
- rollback relevance.

Do not claim installed success from source inspection or deterministic tests alone.

## 18. Repository artifacts required for closure

When a phase or incident closes, update the appropriate artifacts:

- `Current_Plan.md` for active-state removal or next work;
- the live roadmap checklist for phase status;
- focused historical bug record;
- phase/benchmark report;
- decision record for architecture deviations;
- guardrail only when the rule is durable and compact.

## 19. Stop conditions

Stop and mark the candidate failed when:

- the user reports worse visual behaviour;
- approved goldens change unexpectedly;
- a known-bad negative control also passes;
- first-visible latency or p99/max materially worsens;
- lifecycle emits invalid wrapper/context/owner evidence;
- a retired owner survives;
- RAM/commit/VRAM grows monotonically or remains unacceptably high without attribution;
- task rate rises without measured benefit;
- a solution needs another scheduler, cadence, retry, generation, or flag to hide unclear ownership;
- the fix requires weakening full teardown, graph replay, first-frame authority, or resource accounting.

The correct response is rollback and model revision, not another compensating patch.