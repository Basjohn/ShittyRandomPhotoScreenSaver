# 10 — Donor Extraction Matrix

Last reconciled: 2026-08-02

## Current role

The donor commit `7376bb9` is frozen reference history, not an active implementation queue.

The project has already selectively reconstructed several useful principles—measurement, ownership metadata, generation rejection, immutable handoff, byte accounting, and strict GL deletion—while rejecting the donor's scheduler/presentation/lifecycle orchestration.

Do not revisit donor code merely because a later phase number mentions a resource store or single-surface compositor. Begin from a current measured requirement in `Current_Plan.md` and current `main` ownership.

## Extraction rule

For any new donor-derived idea:

1. name the current product/ownership problem;
2. prove it in current `main` evidence;
3. inspect current implementation first;
4. inspect donor code only for a narrowly relevant principle/test;
5. identify rejected dependencies and historical regressions;
6. redesign under current ownership and visualizer/lifecycle contracts;
7. add known-bad negative controls where applicable;
8. benchmark the isolated change;
9. preserve a rollback point and installed user review when presentation is touched.

No large cherry-pick or donor-shaped compatibility bridge.

## Historical commit progression

### `00edb57` — original behavioural baseline

Historical value:

- smoother presentation and visualizer feel;
- simpler lifecycle topology;
- pre-donor behaviour comparison.

Known weaknesses:

- high CPU/task work;
- unbounded/duplicated representations;
- RAM/private-commit/VRAM growth;
- insufficient accounting.

Current note: it is no longer the sole behavioural authority. `ff934616` is the current user-approved Bubble/Spectrum runtime.

### `7eed32c` — texture/resource profiling

Useful historical ideas:

- resource-use visibility;
- texture/geometry instrumentation;
- tests that expose lifetime/streaming problems.

Current rule: use only if current diagnostics still lack a named measurement.

### `6e4a2cf` — orchestration expansion

Historical warning signs:

- larger widget-shaped/free-function seams;
- retry/transaction growth;
- lifecycle and transition responsibility spread.

Decision: reject orchestration shape; mine only isolated stateless logic with current tests.

### `7e10589` — single-surface visualizer layer

Historical value:

- one-surface product goal;
- potentially reusable context-agnostic shader/math ideas.

Decision: reject mega-layer, widget impersonation, dynamic forwarding, and dual long-term runtime paths.

### `729ef2e` — adaptive timing/backpressure

Historical value:

- passive diagnostics only.

Decision: reject adaptive timer, paint acknowledgement, starvation control flow, and worker/presentation handshake.

### `7376bb9` — expanded resource/lifecycle architecture

Potentially reusable principles:

- explicit resource identity and bytes;
- one deletion owner;
- context/share generation checks;
- immutable worker/render handoff;
- callbacks outside locks;
- affinity assertions;
- resource/accounting tests.

Rejected implementation shapes:

- adaptive/persistent visualizer scheduling;
- paint acknowledgement;
- compositor cadence control;
- partial Settings/Edit reinit;
- terminal-frame transactions;
- compatibility mega-layer/dynamic forwarding;
- distributed retry/fallback state;
- whole-buffer hot-path hashes/copies;
- multiple owners recording the same GL handle.

## Lessons from later current-main experiments

The donor was not the only source of bad scheduling ideas. Later current-main experiments confirmed the same principles:

- `666624d`: persistent shared-analysis/Bubble lanes degraded approved behaviour and were reverted;
- `ebfec397`: paint-local Spectrum decay introduced a second cadence and made presentation significantly less smooth;
- R-53: a full teardown can still be architecturally correct yet admitted from the wrong retiring call stack;
- R-56: Python wrapper identity cannot stand in for Qt C++ liveness;
- R-57: queue priority order cannot stand in for safe positional deletion order.

Future extraction must account for these current lessons, not merely avoid donor code names.

## Component decisions

| Principle/component | Current decision | Conditions |
|---|---|---|
| One surface per display | Future option | Only after Phase 5; compositor owns no simulation/lifecycle/scheduler authority |
| Context-agnostic visualizer renderer | Possible future reconstruction | Narrow immutable API; current temporal goldens and user approval |
| Donor visualizer layer/mega-object | Discard | Mine isolated stateless shader/math only |
| Shared resource-store concept | Reassess later | Current measurements must prove benefit over per-compositor ownership |
| Existing donor shared registry | Reference only | Never copy ownership/lock/deletion shape blindly |
| Immutable upload/result handoff | Keep principle | Avoid duplicate copy/hash; generation/owner identity required |
| Full-buffer SHA-256 identity | Reject default | Diagnostic/offline only unless measured need |
| Adaptive/persistent visualizer timers/lanes | Discard | Ordinary executor and one cadence remain approved |
| Paint generation acknowledgement | Discard | GUI-local request coalescing only; no producer wait |
| One pending GUI update principle | Keep narrowly | Display-owner deduplication, no frame acknowledgement |
| Partial Settings/Edit reinit | Discard | Full rebuild required |
| GL affinity and strict deletion | Keep/strengthen | One deletion owner; fail closed |
| Runtime/context/request generation | Keep narrowly | Real lifetime boundaries only |
| Terminal-frame transaction | Discard | Local transition completion |
| Dynamic compatibility forwarding | Discard | Explicit interfaces/DTOs |
| Passive performance/resource diagnostics | Keep selectively | Sampled, bounded, non-controlling |
| Historical tests | Adapt selectively | Must reproduce current ownership/runtime shape |

## Current comparison commands

Examples:

```bash
git diff 7376bb9..main -- <path>
git show 7376bb9:<path>
git show 00edb57:<path>
git log --oneline 00edb57..main -- <path>
```

Use exact commit SHAs in reports. Do not assume branch aliases exist locally.

## Acceptance for any donor-derived change

- current problem is measured;
- smallest principle is extracted, not implementation bulk;
- no rejected scheduler/presentation/lifecycle dependency appears;
- current visual and lifecycle contracts pass;
- whole-process resource effect is measured;
- user approval is recorded when presentation/feel is touched;
- current main remains simpler or more explainable;
- rollback is exact.