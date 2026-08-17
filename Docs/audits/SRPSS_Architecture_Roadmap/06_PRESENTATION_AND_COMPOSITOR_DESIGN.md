# 06 — Presentation and Compositor Design

Last reconciled: 2026-08-17

## Design Objective

Provide predictable display-local presentation while preserving authoritative
simulation/source cadence, lifecycle, worker scheduling and resource ownership.

The accepted causal evidence is
`Docs/phase_reports/P05_PRESENTATION_DELIVERY_ATTRIBUTION.md`.
`Current_Plan.md` P0→P4 owns implementation order.

## Current Readiness Decision

**Do not begin Phase 8 one-surface-per-display work.**

The 2026-08-16 same-process A/B/C run provides a sharper result than earlier rate-only
evidence:

- A normal visualizer presentation on the 165 Hz display ran about `143.4 FPS / 87.12%`
  request acceptance;
- B suppressing only auxiliary visualizer `update()` requests improved it to about
  `150.2 / 91.39%`;
- C additionally hiding the still-live visualizer GL surface improved only modestly again
  to about `151.6 / 92.11%`;
- restoring A in the same process dropped it back to about `141.2 / 85.85%`;
- a separate no-visualizer-from-start control reached about `156.5 / 95.11%`.

Therefore:

1. the auxiliary repaint-request stream is a **proven shared-GUI amplifier**;
2. visible second-surface existence is a **secondary** effect in this evidence;
3. another visualizer-family GUI handoff/preparation cost remains;
4. a smaller non-visualizer queued-GUI-dispatch owner remains after the visualizer is absent.

Sampled Spectrum overlay GPU work remains about `0.02 ms p50 / 0.025 ms p95`, so shader
execution is not the primary owner.

## Closed Presentation/GPU Owners

The following are not active root-cause hypotheses unless new contradictory evidence appears:

- retained-current → next-old texture identity;
- steady retained-base full-surface QPainter draw;
- redundant ordinary native RGB32/ARGB32 upload conversion/source copying;
- ordinary transition shader duration as the owner of the large delivery tail;
- Bubble/Spectrum worker or visualizer shader duration as the owner of the large delivery tail;
- ordinary PERF GL-query observer overhead.

## Bad Smell 1 — Publication-Coupled Visualizer Presentation

Current normal shape is effectively:

```text
logical visualizer publication
        ↓
SpotifyBarsGLOverlay.set_state(...)
        ↓
_request_frame_update(...)
        ↓
QOpenGLWidget.update()
```

`_request_frame_update()` currently discards its `force` argument and issues `update()`.
When logical publication runs around 85–95 Hz, that creates an independent auxiliary Qt
presentation-request stream even on a 60 Hz display.

The A/B/A experiment proves that stream materially delays both displays on the shared GUI owner.

### Required production shape

```text
audio/events/source
        ↓ authored logical cadence unchanged
logical visualizer/model owner
        ↓
immutable render state + generation/activation + protected edge/event identity
        ↓
display-local presentation-request owner
        ↓ only when another useful request is needed
Qt presentation opportunity
        ↓
paint latest valid presentation state
```

The key distinction is **request ownership**, not a new display clock.

## Protected Edge/Event Requirement

A simple latest-state slot is insufficient for Bubble because an approved visible response
may last only one logical publication. Presentation coalescing must therefore preserve
bounded edge/event identity/history, or an explicitly approved equivalent, so skipped
render snapshots cannot erase authored response.

Logical events/steps are never dropped merely because intermediate render snapshots are.

The authored event and the visible response are on **different ticks**. Protection keyed on the
authored event can fire one publication before the response becomes visible in the Bubble
positional payload, leaving the real edge coalescable (R-62). Assert protection against the
visible edge in the versioned golden, not against the trigger.

## Forbidden Admission Mechanisms

Do not implement the P2 fix with:

- paint completion as producer acknowledgement;
- pending-until-paint backpressure;
- elapsed producer timestamps as a display-rate gate;
- a display-FPS cap on logical/source cadence;
- source/event decimation;
- a second visualizer clock;
- catch-up replay of skipped render snapshots;
- repaint retries that increase GUI pressure.

The rejected ~50/40 Hz divisor-collapse experiment remains the negative control: Qt
`paintGL()` completion is not a trustworthy physical-present clock.

## Bad Smell 1b — Remaining Visualizer GUI Handoff/Preparation

B/C kept logical visualizer publication and overlay handoff alive while reducing/ending
presentation work. The separate no-visualizer control still improved further.

That does not identify one method. P3 must split at least:

```text
logical producer/state build
        ↓
pure-data render-state preparation
        ↓
Qt-owned overlay state commit / geometry / QColor etc.
        ↓
presentation request
        ↓
paint
```

Only measured pure-data preparation may move off GUI. QWidget/QColor/QPixmap/GL mutation
remains on the GUI/context owner unless the owning type is replaced with an explicitly
thread-safe immutable representation before commit.

## Bad Smell 2 — Residual Queued GUI Dispatch

With no visualizer created, the 165 Hz compositor still runs roughly 155–159 FPS and
retains more dispatch-pending than paint-pending skips.

Therefore adaptive timer cadence is not “fixed” by removing the visualizer. P4 must name
the actual GUI callback/owner creating those bursts.

## GUI-Local Presentation Request Ownership

A display-local owner may coalesce redundant **presentation requests** or stale
already-integrated render snapshots.

It must not:

- acknowledge logical frames;
- block the producer until paint;
- mutate simulation state;
- decide source/event cadence;
- depend on the other display's refresh;
- leave a request permanently latched because one paint was delayed.

Geometry/reveal/clear/lifecycle boundaries may require an immediate presentation request;
those exceptions must be explicit and tested.

## P2 Attempt History (both rejected)

Two implementations have been rejected. Their shared error was adopting
`AdaptiveTimerStrategy` as a presentation source.

**Attempt 1 (R-61) — sole dependence.** Drove overlay presentation from
`AdaptiveTimerStrategy._signal_frame()`. That strategy is transition-scoped: it starts for a
transition and pauses when one ends. The visualizer received no opportunities afterwards and
froze permanently. A second defect called `QWidget.update()` from the timer worker thread.

**Attempt 2 (R-62) — while-active-only.** Deferred presentation only while the strategy ran,
restoring one-request-per-publication when it paused. Installed review rejected it: Bubble worse
in every relevant way. The candidate also attempted to protect a rising kick/snare trigger rather
than proving receipt of the actual Bubble positional-payload edge that becomes visible on the
following logical tick.

**`AdaptiveTimerStrategy` / `AdaptiveRenderStrategyManager` is disqualified as a visualizer
presentation source in any scope.**

The R-62 logs add a second durable rule: a presentation/pacing source that degrades under the
same load the change is intended to relieve is not an eligible P2 source. State-to-paint age is
now an acceptance metric, not an incidental diagnostic.

**Withdrawn inference.** Earlier revisions of this document argued that because Qt painted
about 96.7% of requested frames, only ~3.3% of the request stream could usefully be removed.
That is invalid: `paint / update_request` is not a measure of useful physical presentation.
R-27 recorded ~275 paints/s against a 60 Hz owner, and R-55 recorded ~142–154 paints/s against
~100 Hz `set_state` while the visualizer was *worse*. Do not use that ratio to bound available
headroom.

**Still true and unchanged:** the measured coupling is `update_requests / set_state == 1.0000`
across both Bubble and Spectrum, the overlay paints roughly 31% more often than the 60 Hz
display can present, and overlay paint costs about 1.7 ms CPU p95. Those measurements stand;
only the inference drawn from the paint ratio is withdrawn.

## P2 Current Design Status — dispatch-layer characterization before implementation

There is **no approved P2 wiring plan at present**. `Current_Plan.md` owns the active design work.

A proposed third direction — "dispatch-window coalescing" — must not be implemented merely by
copying the compositor's update-pending machinery. Source inspection shows an important layer
difference:

```text
compositor timer worker
    -> queued GUI callback is pending
    -> GUI callback executes
    -> QWidget.update()
    -> Qt asynchronous update/paint machinery
```

The compositor's `_srpss_timer_update_dispatch_pending` flag covers the **queued GUI callback
before `QWidget.update()` is called**. It is cleared once that callback reaches the GUI thread and
issues `update()`.

The current visualizer overlay path is structurally different:

```text
display_image_ops._push_spotify_bars_overlay_state()
    -> SpotifyBarsGLOverlay.set_state()
    -> _request_frame_update()
    -> QWidget.update()
```

Before using "dispatch pending" as a P2 admission concept, the exact production thread and
boundary of that direct path must be characterized. Do not assume the compositor's flag is a
generic Qt-widget "update pending" flag.

Qt's widget update machinery is itself asynchronous and normally merges repeated `update()`
requests before painting. That does **not** invalidate the A/B result — suppressing the calls
still measurably helps — but it means a second manual coalescer at the same layer can be redundant
while leaving the actual call/invalidation/composition pressure untouched.

### Binding design prohibitions for attempt 3

- Do not add a new queued GUI hop merely to create a coalescible "dispatch window".
- Do not wrap overlay updates in a new timer, worker, thread, lane, `singleShot`,
  queued `invokeMethod`, or `run_on_ui_thread` solely for P2 admission.
- Do not copy `_srpss_timer_update_dispatch_pending` unless the overlay is proven to have the
  same existing cross-thread boundary and lifetime semantics.
- Do not call Qt's post-`update()` event state "dispatch pending". If the state begins after
  `update()` and clears at paint delivery, it is the pending-until-paint family regardless of
  its variable name.
- Do not intercept/suppress `UpdateRequest`, paint, or other Qt events to manufacture admission
  without a separately reviewed design.
- Do not claim a dropped request is latency-neutral by construction. Equivalent-run
  state-to-paint and first-visible evidence must prove it.
- Do not use a latest-state-only slot as Bubble edge protection. A newer publication may erase the
  one-tick positional edge before a queued paint reads the state.
- Do not substitute a rising kick/snare bypass for receipt of the actual protected Bubble edge.
- Do not add broad immediate-request bypasses that recreate the GUI pressure P2 is trying to
  remove.
- Do not move to Phase 8 merely because this candidate is disproved.

### Required decision before production wiring

`Current_Plan.md` Step 1 must establish whether there is an **already-existing, safely observable
pre-GUI redundant dispatch layer** on the visualizer path. If there is not, the dispatch-window
candidate is rejected before implementation.

Any subsequent coalescing design must also define a bounded presentation-side edge/event
identity/history contract (or explicitly approved equivalent) that preserves Bubble's real
visible one-tick response without turning paint into producer acknowledgement or changing logical
simulation/cadence.

## Scene / Surface Ownership

Current evidence supports retaining separate surfaces during P2/P3 while fixing request
ownership first.

Phase 8 may be reconsidered only if later evidence shows substantial residual cost from
the second surface/context **after** request/handoff pressure is corrected.

One compositor surface per display, if ever accepted, still must not absorb visualizer
simulation/source cadence.

## Presentation-Rate Attribution

Record together per display:

- physical refresh/route/DPR;
- logical visualizer publication rate;
- overlay handoff/commit rate;
- update-request rate;
- paint rate;
- adaptive wake lateness;
- queued GUI dispatch wait;
- paint-pending wait;
- source/state age at paint;
- transition/image-install activity;
- sampled GPU duration and process GPU busy.

A publication rate above physical refresh is not itself a bug. A one-to-one repaint
request stream that measurably starves delivery is.

## Phase 8 Acceptance Prerequisites

All must hold:

- P2 presentation-request ownership corrected;
- P3 remaining visualizer handoff cost named/closed;
- P4 residual non-visualizer dispatch named/closed enough to avoid false attribution;
- stronger Bubble/Spectrum temporal/edge/paint-receipt bars pass;
- GPU/context evidence shows second-surface existence remains a material owner after the above;
- lifecycle/GL teardown remains strict and byte-accounted.
