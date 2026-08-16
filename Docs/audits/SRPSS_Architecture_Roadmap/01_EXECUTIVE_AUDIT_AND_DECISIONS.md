# 01 — Executive Architecture Audit and Decisions

Last reconciled: 2026-08-16

## Scope

This document states current architecture findings and decisions. `Current_Plan.md`
owns execution order; the accepted Phase 5 delivery evidence is
`Docs/phase_reports/P05_PRESENTATION_DELIVERY_ATTRIBUTION.md`.

## Current Root Findings

1. **The dominant delivery loss is downstream of timer wakeup.** Target-rate adaptive
   wake opportunities remain available while queued GUI dispatch and paint-pending state
   reject later deadlines.
2. **Bad smell 1 is proven:** visualizer logical publication is coupled one-for-one to
   an auxiliary `QOpenGLWidget.update()` request. Same-process A/B/A proves that request
   stream materially slows both displays.
3. **Visible second-surface existence is secondary in the current evidence.** Hiding the
   still-live visualizer GL widget improves only modestly beyond suppressing its repaint
   requests, so one-surface-per-display is not the current fix.
4. **Another visualizer-family GUI owner remains.** A visualizer-disabled-from-start
   control improves beyond the hidden-live state while Media/GSMTC stays active. This
   proves additional family cost, but not that `set_state()` as a whole owns it.
5. **Bad smell 2 is proven:** even with visualizers absent, the 165 Hz compositor remains
   below target with queued-dispatch pending skips dominating paint-pending skips.
6. **Visualizer shader cost is not the owner.** Sampled Spectrum overlay GPU duration is
   tiny relative to the delivery loss.
7. **Bubble/Spectrum logical timing remains protected.** The evidence argues for
   presentation ownership and GUI availability work, not cadence/source/scheduler cuts.
8. **Retained texture identity/base draw/upload-copy work is closed.**
9. **Settings/Edit/Diagnostic ownership and clock shadows remain solved regression contracts.**
10. **Absolute memory/commit/VRAM is still a separate Phase 5 efficiency problem.**

## Decision Set

### ADR-A — Current `main` is implementation authority

Historical commits are read only for named forensic questions or negative controls.

### ADR-B — Visual behaviour authority

`ff93461685476bd0657aa88312fc2e35e9037880` remains the Bubble/Spectrum visual
reference until superseded by explicit installed approval.

### ADR-C — One owner per mutable concern

Runtime admission, logical visualizer state, presentation requests, GL deletion,
transition completion, persistence ordering and cache eviction each require an explicit
authority.

### ADR-D — Prepare → Commit → Persist → Present

Thread-safe pure-data work prepares immutable results away from GUI where proven.
GUI/context owners perform minimal Qt/QPixmap/GL commits. Durable writes use ordered
background ownership. Presentation consumes already-integrated state and cannot become a
simulation clock.

### ADR-E — No catch-all background thread

Different blocking/ordering/lifetime classes remain separate. Do not serialize unrelated
work through a new miscellaneous thread.

### ADR-F — Visualizer logical cadence is protected

Bubble/Spectrum source/event integration, authored step/dt semantics and publication
ordering are not reduced to match display refresh or to hide GUI pressure.

### ADR-G — Presentation is a consumer, not a publication acknowledgement

After logical integration, presentation may consume the latest valid immutable render
state and may coalesce stale **render snapshots**. It may not drop logical events/steps,
backpressure the producer or make paint completion an admission token.

### ADR-H — Short-lived authored edges must survive presentation coalescing

A latest-state slot alone is insufficient where a protected visible response can exist
for only one logical publication. The presentation contract must carry bounded
edge/event identity/history or another approved equivalent.

### ADR-I — No one-publication → one-update requirement

The normal visualizer path must not require an auxiliary `QOpenGLWidget.update()` for
every accepted logical publication when publication outruns useful presentation
opportunity. This is now a measured production problem, not a speculative Phase 7 idea.

### ADR-J — Paint/pending latches are not physical presentation clocks

Do not use `paintGL()` completion, producer elapsed-time gates or a pending-until-paint
boolean to create a display-rate scheduler. Previous divisor-collapse behaviour makes
those mechanisms unsafe.

### ADR-K — GUI handoff extraction requires measured pure-data ownership

The no-visualizer control justifies measuring logical-to-overlay preparation/commit cost.
Only proven thread-safe immutable preparation may move off GUI. QWidget/QColor/QPixmap/GL
mutation remains on the GUI/context owner.

### ADR-L — Residual no-visualizer dispatch is an independent owner

The P2 visualizer correction cannot claim delivery closure while a visualizer-disabled
run still loses deadlines for an unnamed queued-GUI-dispatch reason.

### ADR-M — GPU profiling remains truthful and non-blocking

Use explicit sampled `--gpu-timing`; ordinary `--perf` performs no GL query-driver calls.
`glFinish()` is prohibited.

### ADR-N — Compatibility/diagnostic scaffolding requires an expiry condition

The completed A/B/C monkeypatch/CLI/hotkey is P0 cleanup. Passive stage metrics remain
because they measure active P2–P4 owners.

### ADR-O — Checkpoints are rollback anchors

A risky slice gets a clean reversible commit and focused gate. Passing evidence continues;
failed evidence, dirty/conflicted state or required visual judgement stops work.

### ADR-P — Lifecycle remains full and fail-closed

Performance work does not weaken Settings/Edit teardown/recreation, generation rejection
or GL owner deletion.

### ADR-Q — Resource containment and absolute efficiency are separate

Flat ownership is necessary but not sufficient. RSS/private commit/VRAM still require
owner-level explanation after the higher-leverage delivery queue.

## Current Success Conditions

- P0 diagnostic scaffolding is removed;
- P1 protects logical fidelity and mixed-refresh presentation ownership;
- P2 removes the proven publication-coupled repaint amplifier;
- P3 names/removes or closes the remaining visualizer-family handoff cost;
- P4 names/removes the residual no-visualizer queued-GUI-dispatch owner;
- visualizer logical behaviour remains approved;
- lifecycle/GL ownership remains deterministic and fail-closed;
- absolute resources are later reduced or explicitly attributed;
- canonical `main.py` evidence and installed visual review agree.
