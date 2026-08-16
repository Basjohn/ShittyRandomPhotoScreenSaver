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
| 3 — lifecycle | Settings/Edit architecture solved; physical sleep/wake never fully platform-proven |
| 4 — resource containment | bounded foundations; major texture/base/upload owners closed |
| 5 — workload/delivery/topology/GPU/resource efficiency | **active: P0→P5, then P6** |
| 6 — explicit GPU resource store | conditional |
| 7 — generalized state/presentation boundary | broader follow-up only after P2/P3 |
| 8 — one surface per display | deferred by current evidence |
| 9–10 — simplification/cleanup | later |
| 11–12 — broad validation/release | later |

## Phase 5 Ordered Program

### P0 — expire completed diagnostic architecture
Remove A/B and A/B/C helper/CLI/hotkey installation; keep passive delivery-stage metrics.

**Gate:** ordinary runtime unchanged; no temporary monkeypatch remains.

### P1 — lock fidelity and presentation invariants
Protect logical cadence, Bubble edges/events, Spectrum state, generation/activation, lifecycle and mixed-refresh ownership.

**Gate:** stale render snapshots can be skipped without altering protected logical behaviour.

### P2 — correct bad smell 1
Remove one-accepted-logical-state → one auxiliary `QOpenGLWidget.update()` requirement.

**Gate:** authored workload materially approaches the no-visualizer control without cadence/source/event changes or paint-ack/divisor collapse.

### P3 — attribute remaining visualizer-family handoff/preparation
Measure producer/state-build, pure-data render preparation, Qt state commit and repaint request separately.

**Gate:** one measured owner is extracted with fidelity tests or the remaining visualizer-family delta is closed with evidence.

### P4 — attribute residual no-visualizer queued GUI dispatch
Repeat visualizer-disabled control with Media active and correlate dispatch-pending bursts with concrete GUI owners.

**Gate:** owner fixed/narrowed or explicitly classified with evidence; no timer cadence tuning.

### P5 — harden monitor topology and physical sleep/wake recovery

#### P5-A one authority
DisplayManager/engine-level topology owner decides no-op/re-anchor/full replacement. Native/Qt/per-window events only invalidate/report.

#### P5-B settle and snapshot
Use trailing-edge quiet-period debounce plus bounded maximum settle; freeze one authoritative screen count/order/geometry/DPR snapshot before replacement.

#### P5-C transactional replacement
Stop old-runtime topology mutation → retire once → pass destruction barrier → construct/register complete replacement against frozen snapshot → staged reveal. Preserve strict GL teardown and all-displays-registered-before-staggered-show.

#### P5-D sticky visualizer ownership
Temporary participation/readiness loss never changes configured display ownership. Only settled-topology absence starts one generation-owned coarse ~60-second confirmation. Still absent at that single check may fallback once. New topology invalidates the candidate. Configured-display return is topology/readiness-event driven and restores ownership once with no reverse polling timer.

#### P5-E recovery-specific desktop-capture bypass
Keep `grabWindow(0)` for normal stable cold-start anti-flash. Do not make synchronous desktop capture a prerequisite of physical-wake/topology reconstruction; use retained SRPSS image/replay or wait for real first frame.

#### P5-F installed gate
Repeated ordinary installed both-off→screensaver→wake cycles, simultaneous and reversed sequential wake, genuine absence >~60 s, return-before-grace, return-after-fallback, and overnight-equivalent idle. Both displays/input recover; no Ctrl+Alt+Delete; no eager visualizer migration; no new polling/thread/timer machinery.

**Gate:** physical-wake recovery passes installed validation or the remaining blocking native boundary is named by before/after breadcrumbs.

### P6 — return to remaining Phase 5 work
Resume absolute memory/commit/VRAM, proven service/cache work, canonical parser/logging debt and compatibility cleanup.

## Phase 5 Prohibitions

- no visualizer source/tick/cadence cuts;
- no second visualizer clock or paint-local logical state;
- no `paintGL()` acknowledgement/backpressure;
- no pending-until-paint or producer-time display-rate gate;
- no repaint retry or display-FPS cap;
- no worker QWidget/QColor/QPixmap/GL mutation;
- no one-surface-per-display rewrite from current A/B/C evidence;
- no catch-all background thread;
- no monitor polling loop or dedicated monitor-watch thread;
- no exact/frame-timed requirement for the ~60-second absence grace;
- no fallback from temporary non-participation while configured monitor still exists in authoritative topology;
- no weakening strict GL teardown, hide/reuse revival, timeout extension, nested event pumping or forced paints for wake recovery;
- no global removal of cold-start `grabWindow(0)` anti-flash behaviour;
- no unrelated media/browser/memory experiment mixed into P0–P5.

## Dependency Rules

- P0 precedes P2 production measurement;
- P1 precedes P2 acceptance;
- P2 precedes P3; P2/P3 precede P4 final attribution;
- P0–P4 complete before P5 so delivery work is not confounded with topology architecture changes;
- P5-A/B precede P5-C/D/E because fallback/rebuild decisions require one settled topology authority;
- P5-C preserves Phase 3 lifecycle invariants;
- P5-D uses P5-B snapshots and existing lifecycle-owned one-shot scheduling only;
- P5-D return-home uses existing topology/readiness events, not a new timer;
- P5-F precedes P6 lower-leverage work and release;
- current C-vs-B evidence blocks Phase 8.
