# 03 — Work Order and Phase Gates

Last reconciled: 2026-08-08

## Purpose

The phase model exists to prevent unrelated architecture changes from being mixed and falsely attributed. `Current_Plan.md` owns the exact active order; this document owns the dependency logic and phase acceptance model.

## Current phase interpretation

| Phase | Current state |
|---|---|
| 0 — Freeze/evidence | Historical foundation complete |
| 1 — Measurement | Implemented; whole-process attribution still active |
| 2 — Visualizer fidelity | Logical package complete; temporal/installed protection reopened under P5.0 |
| 3 — Lifecycle | Core full-teardown architecture and mechanical R-53/R-56 repairs implemented; installed closure open |
| 4 — Resource containment | Known leaks/budgets improved; absolute whole-process footprint reopened |
| 5 — Workload, recreation, and resource recovery | Active |
| 6–10 | Future architecture/cleanup; blocked by Phase 5 |
| 11–12 | Final validation/release |

A completed historical phase may be reopened when later evidence disproves its gate. Preserve its report; do not erase the evidence or pretend the later failure never happened.

# Ordered program

## Phase 0 — Repository and evidence freeze

**Goal:** preserve the original baseline/donor comparison and reproducible recovery starting point.

**Status:** complete historical foundation.

Current work occurs on `main`; the old recovery branch name is not an execution instruction.

## Phase 1 — Measurement foundation

**Goal:** measure timing, work, resources, and lifecycle without altering behaviour.

Implemented foundations include:

- frame/presentation interval summaries;
- event-loop lateness;
- task categories;
- CPU image and GL resource bytes;
- lifecycle resource snapshots;
- whole-process usage sampling.

**Remaining gate:** process-level RSS/private-commit/VRAM must be reconcilable against tracked application ownership, native/Qt allocations, mappings, workers, stacks, and driver state.

Diagnostics remain passive and bounded.

## Phase 2 — Visualizer fidelity lock

**Goal:** prevent infrastructure changes from damaging supported visualizer behaviour.

The original deterministic logical replay package remains useful, but it missed scheduler/publication/first-visible failures.

**Current supplementary gate under P5.0:**

- exact approved commit/environment manifest;
- production general-executor temporal capture;
- source-to-first-visible checks;
- separate user approval by mode;
- known-bad negative controls for `666624d`, terminal batching, and `ebfec397`;
- no automatic golden regeneration.

`ff934616` is the current user-approved Bubble/Spectrum reference.

## Phase 3 — Lifecycle correction

**Goal:** reliable full stop–destroy–recreate with explicit ownership.

Implemented architecture retained:

- generation invalidation;
- producer stop before display/GL deletion;
- owner-context deterministic GL deletion;
- fail-closed destruction barriers;
- replacement construction only after retiring ownership reaches zero;
- authoritative-first-frame reveal for the new runtime.

**Reopened installed gates:**

- R-56: confirm the mechanically repaired Settings path observes/retires the dialog graph without touching an invalid wrapper after modal deletion;
- R-53: confirm the mechanically repaired Edit path persists/retires the temporary session, returns from manager/action/key-filter frames, and admits engine-owned full reload on a later GUI turn;
- zero surviving `CustomLayoutManager` wrappers;
- full graph-based placement/replay preserved.

Historical 50/50/50 harness success does not overrule a current installed failure shape absent from that harness.

## Phase 4 — Resource containment and efficiency

**Goal:** bounded and appropriately low resource usage with explainable ownership.

Implemented foundations retained:

- byte-budgeted CPU caches;
- bounded prefetch queues/future bytes;
- exact texture/PBO accounting;
- deterministic transition/resource release;
- shared-memory transfer retirement;
- owner-context teardown.

**Reopened gates:**

- absolute active whole-app RSS, private commit, and dedicated VRAM must fall substantially from current evidence;
- tracked/untracked gap must be attributed;
- R-57 installed prefetch correctness must close after the deterministic repair;
- lifecycle cycles must reach a stable equivalent plateau after R-53/R-56 repair;
- no quality, cadence, resolution, precision, artwork, shadow, widget, or visualizer cuts.

## Phase 5 — CPU, task, delivery, recreation, and resource recovery

**Goal:** close current lifecycle defects, strengthen visual fidelity protection, reduce measured unnecessary work, and lower absolute resource footprint.

Current ordered work is defined in `Current_Plan.md`. The architecture order is:

1. freeze the exact approved visual behaviour/environment;
2. repair narrow proven correctness failures R-57 and R-56;
3. repair R-53 Edit admission and deterministic temporary-session retirement;
4. prove one Settings and one dual-display Edit installed cycle;
5. capture controlled equivalent-state resource baselines;
6. attribute process/resource gaps before optimization;
7. remove only measured duplication, unchanged work, idle work, callback/queue overhead, logging overhead, and redundant representations;
8. run alternating lifecycle, churn, pressure, normal, and Media Center matrices;
9. complete stronger temporal visualizer goldens before scheduler/presentation/visualizer optimization or lane-scaffolding deletion.

### Phase 5 prohibitions

Do not:

- reduce visualizer cadence/source sampling;
- batch away logical impulses;
- target Bubble because a combined visualizer scenario is expensive;
- reintroduce dedicated/persistent analysis lanes;
- add a second presentation cadence;
- trim working sets or recycle processes;
- raise budgets to conceal usage;
- weaken full teardown or first-frame authority.

### Phase 5 pass criteria

- user-approved visual behaviour remains equal or better than `ff934616`;
- known-bad scheduling/presentation controls fail the strengthened suite;
- R-53/R-56/R-57 close deterministically and in installed runs;
- Settings/Edit repeatedly reach zero retiring ownership;
- CPU/task work falls for named owners;
- p99/max and first-visible response do not regress;
- RAM/private commit/VRAM both plateau and meet evidence-backed reasonable targets;
- all supported visualizer modes pass shared-source validation;
- canonical `main.py` evidence passes; Media Center owns no parallel capture and receives shared route/build smoke coverage only.

## Phase 6 — Explicit GPU resource store

**Goal:** introduce bounded reuse only if current evidence proves it remains necessary.

This is no longer an automatic donor-extraction step. Reassess after Phase 5 absolute-resource attribution.

**Pass criteria if implemented:**

- exact byte caps and dumpable ownership;
- one deletion owner per handle;
- explicit leases;
- context/share generation correctness;
- no GL under registry locks;
- no stale generation reuse;
- no worse active VRAM or lifecycle complexity than current ownership.

## Phase 7 — Visualizer/presentation decoupling

**Goal:** narrow immutable state boundaries without changing approved timing or feel.

**Constraints:**

- preserve ordinary general-executor semantics unless explicit approved evidence supports a change;
- no paint waits;
- no compositor-owned visualizer timer;
- no self-requested presentation loop;
- no paint-local authoritative state;
- coalescing only after logical integration.

## Phase 8 — Narrow one-surface compositor

**Goal:** one surface per display without donor orchestration.

This remains a future architecture option, not a Phase 5 shortcut.

The compositor may own surface, draw order, immutable scene snapshot, and compositor-local transition continuation. It may not own visualizer simulation/cadence, image selection, worker pools, Settings/Edit, or producer acknowledgement.

## Phase 9 — Transition simplification

**Goal:** local exactly-once completion and immediate temporary-resource release.

No terminal transaction or producer/pipeline acknowledgement.

## Phase 10 — Temporary and legacy scaffolding removal

**Goal:** remove proven-unused forwarding, duplicate paths, retries/backoff, obsolete metrics, settings, and compatibility shells.

Require production search, dynamic/frozen-build audit, fallback audit, tests, and rollback. Do not delete evidence or adapters still needed for migration.

## Phase 11 — Full hostile validation

Scenarios include:

- cold/idle/warm static;
- each supported visualizer mode;
- transitions;
- combined normal operation;
- CPU/disk/GPU/mixed load;
- Settings/Edit during active work;
- image churn and memory pressure;
- display topology/sleep-wake where supported;
- two-hour soak;
- canonical `main.py` only; Media Center receives no duplicate hostile/soak capture.

## Phase 12 — Release and documentation

**Goal:** freeze current architecture, evidence, limitations, rollback point, and release candidate.

## Dependency rules

- active work follows `Current_Plan.md`;
- stronger temporal visualizer protection precedes any new scheduler/presentation/visualizer optimization;
- R-53/R-56 closure precedes lifecycle plateau conclusions;
- lifecycle plateau precedes broad cache/resource retuning;
- owner attribution precedes resource reduction changes;
- Phase 5 passes before Phase 6–10 architecture expansion;
- Phase 11 passes before a release candidate.

## Rollback discipline

Each independently risky change gets a clean reversible commit. If a candidate fails:

1. preserve its evidence and historical record;
2. revert exactly;
3. confirm accepted behaviour returns;
4. revise the causal model;
5. do not carry compensating flags, retries, lanes, or hidden fallbacks forward.

## Forbidden shortcut

Do not jump from an approved behavioural baseline to a broad donor or speculative architecture and then attempt to recover feel afterward. Do not use resource pressure as permission to lower perceivable fidelity.
