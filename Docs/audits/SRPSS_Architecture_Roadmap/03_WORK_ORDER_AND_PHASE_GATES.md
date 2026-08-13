# 03 — Work Order and Phase Gates

Last reconciled: 2026-08-10

## Purpose

The phase model prevents unrelated architecture changes from being mixed and falsely
attributed. `Current_Plan.md` owns exact active order; this document owns dependencies.

## Current Phase Interpretation

| Phase | State |
|---|---|
| 0 — evidence foundation | historical foundation complete |
| 1 — measurement | implemented; GPU timing and absolute attribution still expanding |
| 2 — visualizer fidelity | logical protection exists; stronger temporal/paint receipt active |
| 3 — lifecycle | solved architecture/incident path; regression contract |
| 4 — resource containment | bounded foundations; exact texture reuse and absolute footprint active |
| 5 — workload/delivery/GPU/resource efficiency | **active** |
| 6 | conditional GPU-resource architecture |
| 7 | visualizer state/presentation boundary + late logging taxonomy |
| 8 | optional one-surface-per-display compositor |
| 9–10 | simplification/remaining cleanup |
| 11–12 | full validation/release |

## Phase 5 Ordered Program

1. **Repair the proven texture identity/reuse defect.** Current texture must be the next old texture under unchanged identity; measure before/after setter/request-age/GPU effects.
2. **Extract broad avoidable GUI work.** Queue ordinary logging, serialize settings persistence off GUI, and move proven Reddit/Weather/Gmail prepare/cache work away from GUI/paint paths.
3. **Make GPU attribution truthful.** Shared compositor paint/GPU timing across transition families; explicit sampled `--gpu-timing` only, with ordinary `--perf` query-free; separate upload/transition/visualizer/presentation costs.
4. **Remove high-confidence temporary compatibility/fallback debt.** Start with the Bubble executor façade; then audit the unused persistent compute-lane subsystem and other proven dead surfaces. One concern per checkpoint.
5. **Remeasure the same mixed-load authored scenario.** Use deliberate load timestamps and unchanged visualizer/source/cache conditions.
6. **Complete stronger visualizer temporal/paint-receipt protection.** This is a prerequisite to Phase 7, not permission to alter authored cadence in Phase 5.
7. **Reduce/attribute absolute memory/commit/VRAM.** Tune only after owner evidence; no quality/cadence cuts.

### Phase 5 Prohibitions

- no visualizer source/tick/cadence cuts to reduce CPU/GPU;
- no Bubble terminal batching or dedicated persistent lane;
- no second Spectrum clock or paint-local state;
- no `glFinish()` profiling;
- no worker Qt/QPixmap/GL mutation;
- no catch-all background thread;
- no hidden fallback runtime;
- no reopening solved Settings/Edit/Diagnostic/clock work without new direct evidence.

### Phase 5 Pass Criteria

- current visual behaviour remains equal or better than `ff934616`;
- old/current texture reuse is correct and steady paired uploads are gone;
- UI request-age/tick tails improve for named removed owners;
- logging/persistence/service/cache work no longer performs avoidable synchronous GUI I/O/data preparation;
- GPU busy is attributable enough to guide Phase 7/8 rather than guessed from a driver total;
- dead temporary alternate authorities are removed or justified by a current contract;
- absolute resources are materially reduced or explicitly explained.

## Phase 6 — Explicit GPU Resource Store

Conditional only. Reassess after Phase 5 texture identity, GPU timing and memory
attribution. A shared store must prove lower active duplication and simpler lifetime;
it is not a default next step.

## Phase 7 — Visualizer State / Presentation Decoupling

Goal: preserve exact logical/source cadence while narrowing physical presentation work.

Required model:

- logical events/steps integrate at current authoritative boundaries;
- publish current immutable render state with generation/activation identity;
- presentation consumes latest valid state when Qt/display has an opportunity;
- missed paints may skip intermediate render snapshots, never logical events/steps;
- no paint acknowledgement/backpressure or new simulation clock.

Late Phase 7 also performs the full logging-family taxonomy/routing refinement so Phase
8 evidence is readable: routine family INFO/DEBUG to sidecars, main = high-level
narrative + all WARNING+.

## Phase 8 — One Compositor Surface Per Display

Only if Phase 7 proves presentation separation and GPU/context evidence justifies
removing the separate visualizer GL surface/context. One surface per display, never one
global surface. Compositor owns draw/presentation, not simulation or source cadence.

## Phase 9 — Transition Simplification

Keep completion local and exactly once; remove remaining terminal/temporary scaffolding
only where current source still carries it.

## Phase 10 — Remaining Legacy/Deprecated Cleanup

Lower-priority compatibility/migration cleanup after active leverage items. Require
production-use, dynamic-import, frozen-build and migration-contract proof.

## Phase 11 — Full Validation

Canonical `main.py`: cold/warm, all modes, transitions, combined operation, CPU/disk/GPU
and mixed load, topology/system lifecycle, resource churn and long soak.

## Phase 12 — Release

Freeze current architecture, evidence, limitations, rollback point and release
candidate. Historical candidates remain history, not a completion comparator unless a
specific question requires them.

## Dependency Rules

- texture identity and broad GUI extraction precede visualizer scheduler/presentation changes;
- truthful GPU attribution precedes Phase 8;
- stronger temporal visualizer protection precedes Phase 7;
- Phase 7 presentation separation precedes Phase 8 surface merge;
- owner attribution precedes memory/cache budget changes;
- checkpoints are rollback anchors and do not halt passing work;
- Phase 11 precedes release.
