# SRPSS Architecture Roadmap

Last reconciled: 2026-08-17

## Purpose

This package is the maintained architecture, dependency and validation roadmap for current
`main`. It must not become a second active task list.

Historical commits remain negative controls, provenance and forensic references only.

## Authority Order

1. `Current_Plan.md` — unfinished work and immediate execution order.
2. `Spec.md` — stable product/architecture contracts.
3. `Docs/Guardrails.md` and focused guardrails — durable prohibitions.
4. `Docs/phase_reports/` — accepted detailed evidence for completed/active phase checkpoints.
5. this roadmap — owner model, dependencies, audit priorities and release gates.
6. `Future_Cleanup.md` — deferred cleanup, temporary-code removal and test debt.
7. `Docs/Historical_Bugs/` — solved incidents and anti-regression lessons.
8. `Docs/audits/OLD/` — historical audits only.

When documents appear to disagree, resolve them in that order. A phase report may contain
more detail than `Current_Plan.md`, but it does not own execution order.

## Current References

| Role | Reference |
|---|---|
| Working branch | `main` |
| Approved Bubble/Spectrum behaviour | `ff93461685476bd0657aa88312fc2e35e9037880` |
| Rejected persistent-lane negative control | `666624d421b08f978c5f610571a078570150a1e7` |
| Rejected paint-local Spectrum negative control | `ebfec397fb2ae0bbc1f3e95c5298c0e7d6ff1db9` |
| Active execution owner | `Current_Plan.md` |
| Current Phase 5 delivery evidence | `Docs/phase_reports/P05_PRESENTATION_DELIVERY_ATTRIBUTION.md` |
| Cleanup/test-debt owner | `Future_Cleanup.md` |

Do not freeze raw log/ZIP paths here. Durable interpretation belongs in phase reports;
active sequencing belongs in `Current_Plan.md`.

## Current Architecture Reality

Phase 5 has two established delivery smells plus one high-severity platform-recovery lane:

1. **publication-coupled visualizer presentation — proven material amplifier.** Same-process
   A/B/A evidence proves the auxiliary visualizer `QOpenGLWidget.update()` stream slows
   both the 165 Hz and 60 Hz compositors while logical visualizer state keeps publishing.
2. **residual queued GUI dispatch without visualizers — proven existence, owner unknown.**
   The no-visualizer control improves further but leaves the 165 Hz display below target
   with dispatch-pending skips dominating paint-pending skips.
3. **physical monitor sleep/wake recovery — repeatable high-severity failure, exact blocking
   owner not yet proven.** When both displays are physically off while the screensaver is
   active, wake can leave one display frozen, its sibling blank and Qt input unresponsive
   until Ctrl+Alt+Delete disturbs the Windows desktop/display state.

Between delivery smells 1 and 2, another visualizer-family GUI handoff/preparation cost
still requires measurement. The physical-wake lane must not be “fixed” by weakening
Phase 3 GL teardown, adding retries/polling or reverting to hide/reuse.

Current topology/recovery direction:

- one authoritative engine/display-manager topology decision owner;
- native/Qt monitor events become invalidation inputs, not competing mutation authorities;
- trailing-edge quiet-period settlement plus a bounded maximum settle window;
- one frozen topology snapshot per replacement transaction;
- strict retire-once → destruction-barrier → construct/register-all → staged reveal;
- visualizer CUSTOM monitor ownership remains sticky through temporary non-participation;
- cross-display visualizer fallback only after settled-topology absence plus one coarse
  ~60-second owned confirmation; no polling/dedicated thread/exact timing requirement;
- return to the configured visualizer monitor is event-driven from later authoritative
  topology plus normal display-runtime readiness;
- `screen.grabWindow(0)` remains for ordinary desktop→screensaver anti-flash startup but is
  removed from physical-wake/topology-recovery critical reconstruction.

Other current facts remain:

- adaptive-render wake opportunity is not the dominant delivery owner;
- retained-current texture identity, retained-base presentation and redundant ordinary
  upload-copy work are closed;
- visualizer shader GPU time is far too small to explain the delivery loss;
- Settings/Edit/Diagnostic ownership remains solved regression architecture;
- absolute RSS/private commit/driver VRAM still requires separate owner-level attribution;
- Phase 8 one-surface-per-display work is not justified by current A/B/C evidence.

## Audit Priority

The compact priority ledger is `00_INDEX_AND_LIVE_CHECKLIST.md`. Exact checkboxes live
only in `Current_Plan.md`.

```text
P0 remove completed diagnostic scaffolding   [closed]
 ↓
P1 lock fidelity/presentation tests          [closed]
 ↓
P2 correct publication-coupled presentation requests
 ↓
P3 measure remaining visualizer handoff/preparation cost
 ↓
P4 name/fix residual non-visualizer queued GUI dispatch
 ↓
P5 harden authoritative monitor topology / physical sleep-wake recovery
 ↓
P6 resume lower-leverage Phase 5 resource/debris work
```

## Operating Principles

**Prepare → Commit → Persist → Present** remains the workload rule.

For topology, use **Notify → Settle → Snapshot → Retire → Rebuild → Reveal**:

- notifications invalidate topology but do not independently rebuild it;
- settlement is event-coalesced, not polling-driven;
- the accepted snapshot is immutable for one replacement transaction;
- old runtime retirement remains strict/fail-closed;
- replacement is registered completely before staggered reveal;
- visualizer ownership decisions derive from authoritative topology, not transient widget participation.

## Definition Of Success

Approved visual behaviour survives stronger validation; the proven presentation-request
amplifier is removed without cadence hacks; remaining visualizer and non-visualizer GUI
owners are named; physical display-off/wake recovers deterministically without Ctrl+Alt+Delete
or eager visualizer migration; lifecycle remains strict/fail-closed; and GPU/CPU/memory
have named owners under canonical `main.py` validation.
