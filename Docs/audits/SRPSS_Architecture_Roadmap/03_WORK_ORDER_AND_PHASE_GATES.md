# 03 — Work Order and Phase Gates

Last reconciled: 2026-08-16

## Purpose

The phase model prevents unrelated architecture changes from being mixed and falsely
attributed. `Current_Plan.md` owns exact tasks; this document owns dependencies.

## Current Phase Interpretation

| Phase | State |
|---|---|
| 0 — evidence foundation | complete |
| 1 — measurement | delivery-stage split complete; absolute resource attribution still expanding |
| 2 — visualizer fidelity | logical protection exists; P1 edge/presentation lock active |
| 3 — lifecycle | solved architecture/incident path; regression contract |
| 4 — resource containment | bounded foundations; major texture/base/upload owners closed |
| 5 — workload/delivery/GPU/resource efficiency | **active: P0→P4 delivery queue** |
| 6 — explicit GPU resource store | conditional |
| 7 — generalized state/presentation boundary | broader follow-up only after Phase 5 P2/P3 |
| 8 — one surface per display | deferred by current evidence |
| 9–10 — simplification/cleanup | later |
| 11–12 — validation/release | later |

## Phase 5 Ordered Program

### P0 — expire completed diagnostic architecture

Remove the A/B and A/B/C helper/CLI/hotkey installation path before measuring production
presentation behaviour. Keep passive delivery-stage metrics.

**Gate:** clean checkpoint; ordinary runtime unchanged; no temporary monkeypatch remains.

### P1 — lock fidelity and presentation invariants

Add/retain tests proving logical cadence, Bubble protected edges/events, Spectrum state,
generation/activation rejection, lifecycle and mixed-refresh cross-display ownership.

**Gate:** candidate presentation coalescing can skip stale render snapshots without
altering protected logical behaviour.

### P2 — correct bad smell 1

Remove the one-accepted-logical-state → one auxiliary `QOpenGLWidget.update()` requirement.
Presentation becomes an owned consumer of integrated state.

**Gate:** same authored workload materially approaches the no-visualizer control on the
165 Hz display; 60 Hz remains healthy; no cadence/source/event changes; no paint-ack latch
or divisor collapse.

### P3 — attribute remaining visualizer-family handoff/preparation

Measure producer/state-build, pure-data render preparation, Qt state commit and repaint
request as separate owners after P2.

**Gate:** either a specific pure-data GUI owner is extracted with fidelity tests, or the
remaining visualizer-family delta is closed with evidence.

### P4 — attribute residual no-visualizer queued GUI dispatch

Repeat a visualizer-disabled control with Media still active. Correlate dispatch-pending
bursts with concrete GUI callbacks/owners.

**Gate:** owner is fixed/narrowed or explicitly classified with accepted evidence.
Do not tune timer cadence to hide it.

### P5 — return to remaining Phase 5 work

Resume absolute memory/commit/VRAM, proven service/cache work, canonical parser/logging
debt and compatibility cleanup.

## Phase 5 Prohibitions

- no visualizer source/tick/cadence cuts;
- no second visualizer clock or paint-local logical state;
- no `paintGL()` acknowledgement/backpressure;
- no pending-until-paint or producer-time display-rate gate;
- no repaint retry or display-FPS cap;
- no worker QWidget/QColor/QPixmap/GL mutation;
- no one-surface-per-display rewrite from the current A/B/C evidence;
- no catch-all background thread;
- no unrelated media/browser experiment mixed into P0–P4;
- no reopening solved Settings/Edit/Diagnostic/clock work without direct contradictory evidence.

## Phase 5 Pass Criteria

- approved visual behaviour remains equal or better than `ff934616`;
- visualizer presentation requests are no longer one-for-one with logical publication when
  useful presentation opportunity is lower;
- mixed-refresh visualizer presentation no longer materially starves the sibling display;
- any remaining visualizer-family GUI preparation owner is named or closed;
- no-visualizer residual queued dispatch is named or accepted as external/irreducible with evidence;
- GPU/CPU/memory remain owner-attributed rather than guessed;
- temporary diagnostics are removed before release.

## Phase 6 — Explicit GPU Resource Store

Conditional only after Phase 5. A shared store must prove lower duplication and simpler
lifetime; it is not the default next step.

## Phase 7 — Generalized Visualizer State / Presentation Boundary

The minimal **proven** correction is already promoted into Phase 5 P2. Phase 7 now means
broader/generalized architecture only if P2/P3 show that multiple consumers/surfaces need
the same contract.

Required invariant remains:

```text
logical integration at authored cadence
        ↓
immutable valid render state + protected edge/event identity
        ↓
display-owned presentation opportunity
        ↓
paint latest valid presentation state
```

No producer wait, catch-up replay or presentation-owned simulation.

## Phase 8 — One Compositor Surface Per Display

Deferred. C was only modestly better than B in the accepted A/B/C run, so current
evidence does not justify absorbing the visualizer GL surface into the main compositor.

## Phase 9–10 — Simplification / Remaining Cleanup

One proven dead authority at a time after active delivery work.

## Phase 11 — Full Validation

Canonical `main.py`: cold/warm, all visualizer modes, transitions, combined operation,
mixed refresh, deliberate host pressure, topology/lifecycle and long soak.

## Phase 12 — Release

Code, active plan, phase reports, cleanup ledger, roadmap, tests and known limitations agree.

## Dependency Rules

- P0 precedes P2 so temporary monkeypatch behaviour cannot contaminate production evidence;
- P1 precedes P2 acceptance;
- P2 precedes P3 attribution;
- P2/P3 precede P4 final attribution because visualizer pressure otherwise contaminates GUI dispatch;
- P2/P3 evidence precedes any generalized Phase 7 design;
- current C-vs-B evidence blocks Phase 8;
- owner attribution precedes memory/cache budget changes;
- Phase 11 precedes release.
