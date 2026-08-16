# 01 — Executive Architecture Audit and Decisions

Last reconciled: 2026-08-16

## Scope

This document states current architecture findings and decisions. `Current_Plan.md` owns
execution order. Accepted Phase 5 delivery evidence lives in
`Docs/phase_reports/P05_PRESENTATION_DELIVERY_ATTRIBUTION.md`.

## Current Root Findings

1. **The dominant measured delivery loss is downstream of timer wakeup.** Queued GUI
   dispatch and paint-pending state reject later deadlines.
2. **Bad smell 1 is proven:** one logical visualizer publication currently implies one
   auxiliary `QOpenGLWidget.update()` request; same-process A/B/A proves material shared-GUI cost.
3. **Visible second-surface existence is secondary in current evidence.** Hiding the live
   visualizer GL widget adds only a modest improvement beyond suppressing its update requests.
4. **Another visualizer-family GUI owner remains.** The no-visualizer control improves
   beyond hidden-live state but does not prove `set_state()` as a whole owns the difference.
5. **Bad smell 2 is proven:** with visualizers absent, the 165 Hz compositor still loses
   deadlines, predominantly as queued-GUI-dispatch pending skips.
6. **Visualizer shader cost is not the owner.** Sampled Spectrum GPU duration is tiny.
7. **Physical monitor sleep/wake is a separate high-severity platform failure.** The
   ordinary installed screensaver can freeze after both monitors were physically off,
   leaving one display frozen, its sibling blank and all normal Qt input dead until
   Ctrl+Alt+Delete disturbs the Windows desktop/display state.
8. **The physical-wake root call is not yet proven.** Current code nonetheless has durable
   improvement targets: duplicate topology authority, first-event settlement, non-transactional
   mutation/replacement overlap, eager visualizer ownership fallback, and synchronous desktop
   capture in the recovery-critical show path.
9. **R-26 is directly relevant precedent:** D0 can return before D1 and temporary display
   participation is not authoritative topology.
10. **Phase 3 lifecycle architecture remains correct but did not prove physical-off/wake.**
    Strict owner-context GL teardown and destruction barriers must not be weakened.
11. **Absolute memory/commit/VRAM remains separate Phase 5 efficiency work.**

## Decision Set

### ADR-A — Current `main` is implementation authority
Historical commits are named forensic/negative controls only.

### ADR-B — Visual behaviour authority
`ff93461685476bd0657aa88312fc2e35e9037880` remains the Bubble/Spectrum visual reference until explicitly superseded.

### ADR-C — One owner per mutable concern
Runtime admission, topology decisions, logical visualizer state, presentation requests, GL deletion, transition completion, persistence ordering and cache eviction each require one explicit authority.

### ADR-D — Prepare → Commit → Persist → Present
Pure-data work may prepare off GUI when proven; Qt/QPixmap/GL commit remains on the owning GUI/context; presentation consumes integrated state and is not a simulation clock.

### ADR-E — No catch-all background thread
Do not solve independent blocking/ordering classes with one miscellaneous thread.

### ADR-F — Visualizer logical cadence is protected
No source/event/tick/dt reduction to hide GUI pressure.

### ADR-G — Presentation is a consumer, not publication acknowledgement
It may coalesce stale render snapshots after logical integration, never logical events/steps.

### ADR-H — Short-lived authored edges survive presentation coalescing
Latest-state-only presentation is insufficient where an approved edge can exist for one logical publication.

### ADR-I — No one-publication → one-update requirement
The normal visualizer path must not require one auxiliary Qt update for every accepted logical publication.

### ADR-J — Paint/pending latches are not physical presentation clocks
No paint acknowledgement, pending-until-paint admission or producer elapsed-time display-rate gate.

### ADR-K — GUI handoff extraction requires measured pure-data ownership
Only proven immutable preparation may move off GUI; QWidget/QColor/QPixmap/GL mutation remains GUI/context owned.

### ADR-L — Residual no-visualizer dispatch is independent
P2 cannot claim delivery closure while visualizer-disabled queued-GUI-dispatch loss remains unnamed.

### ADR-M — GPU profiling remains truthful and non-blocking
Use sampled `--gpu-timing`; ordinary `--perf` makes no GL query-driver calls; never `glFinish()` for profiling.

### ADR-N — Completed diagnostic scaffolding expires
The A/B/C monkeypatch/CLI/hotkey is P0 removal debt; passive stage metrics remain useful.

### ADR-O — Checkpoints are rollback anchors
Risky slices are independently reversible and evidence-gated.

### ADR-P — Lifecycle remains full and fail-closed
Physical-wake work may not restore hide/reuse, ignore failed GL deletion, move GL teardown to a worker, extend destruction timeout to mask blocking, or construct replacement before retired ownership reaches zero.

### ADR-Q — Resource containment and absolute efficiency are separate
Flat ownership does not explain excessive RSS/private commit/VRAM.

### ADR-R — One authoritative monitor-topology decision owner
`DisplayManager` or one equivalent engine-level owner decides no-op/re-anchor/full replacement. `WM_DISPLAYCHANGE`, Qt screen events and per-window callbacks are invalidation inputs/local bookkeeping, not competing global mutation authorities.

### ADR-S — Monitor recovery is Notify → Settle → Snapshot → Retire → Rebuild → Reveal
Every relevant topology event restarts a trailing-edge quiet-period settlement. A bounded maximum settle window prevents indefinite postponement. One accepted screen count/order/geometry/DPR snapshot is frozen before destructive replacement and remains the transaction input.

### ADR-T — Visualizer configured-monitor ownership is sticky
Temporary sleep/wake/non-participation is not absence. The hard-won same-display geometry/aspect correction remains intact. Cross-display fallback is permitted only when settled authoritative topology says the configured monitor is absent and a single intentionally coarse ~60-second lifecycle-owned confirmation still finds it absent. No polling, periodic timer, dedicated thread or exact timing requirement is introduced.

### ADR-U — Return-home is event-driven
If a visualizer has legitimately fallen back, later authoritative topology plus the normal configured-display runtime-readiness boundary transfers ownership home once and retires the fallback. There is no reverse polling timer.

### ADR-V — Desktop capture remains startup polish, not recovery dependency
`screen.grabWindow(0)` remains available on stable desktop→screensaver cold startup to avoid a black flash. Physical-wake/topology reinit instead reuses retained SRPSS imagery/replay state or waits for a real first frame.

## Current Success Conditions

- P0–P4 delivery work passes without cadence hacks;
- P5 centralizes topology authority and settlement;
- physical dual-display wake no longer freezes the runtime;
- temporary monitor non-participation never migrates configured visualizer ownership;
- genuine absence beyond the coarse grace can yield exactly one fallback owner;
- stable configured-display return restores ownership once with saved CUSTOM geometry;
- normal cold-start anti-flash remains unchanged;
- lifecycle/GL ownership remains deterministic and fail-closed;
- absolute resources are later reduced or explicitly attributed.
