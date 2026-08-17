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

## P2 Implementation Decision (2026-08-17)

Traced seam, confirmed against current `main`:

```text
visualizer tick
  → rendering/display_image_ops.py::_push_spotify_bars_overlay_state()
  → SpotifyBarsGLOverlay.set_state()            [logical integration]
  → SpotifyBarsGLOverlay._request_frame_update() [unconditional]
  → QOpenGLWidget.update()                       [independent GUI dispatch demand]
```

`set_state()` ends with an unconditional `_request_frame_update()`, so every accepted
logical publication injects one auxiliary repaint request into the shared GUI dispatch
lane. `AdaptiveTimerStrategy._signal_frame()` drives only `self._compositor`; the overlay
is not part of that owned opportunity today.

### Corrected by 2026-08-17 Bubble evidence — a pending flag alone is insufficient

An initial reading of this seam proposed reusing only the compositor's GUI-local
pending-update coalescing (`rendering/adaptive_timer.py::_queue_safe_widget_update` /
`_mark_widget_update_consumed`). The 2026-08-17 installed Bubble run rejects that as
sufficient. Measured over 13,978 publications on the configured 60 Hz display:

```text
update_requests / set_state = 1.0000    (the coupling, confirmed in production)
paints          / set_state = 0.9669
publication rate            = 81.1 Hz
overlay paint rate          = 78.4 Hz   (~31% above what a 60 Hz display can present)
overlay paint_cpu p95       = 1.695 ms  → ~133 ms/s of GUI thread on overlay paint alone
```

Qt is already painting 96.7% of requests, so a pending-until-painted flag would remove only
the ~3.3% Qt collapses on its own. It is close to a no-op here and would not be worth the
fidelity risk.

The request rate must instead be bounded by the **owning display's real presentation
opportunity** — the per-display owned frame boundary that already drives that display's
compositor — not by whether a paint is outstanding, and not by a synthetic FPS divisor.
That is the distinction that keeps this legal: the forbidden mechanism is a display-FPS cap
on *logical/source cadence*; bounding *presentation* to the display's own owned opportunity
is precisely the "display-local presentation-request owner" this document already requires.
Logical publication stays at 81 Hz; only the auxiliary repaint request is owned.

`set_state()` must still return without waiting; Guardrails §6 permits a GUI-local pending
`update()` flag, and it remains useful as a secondary guard, but it is not the mechanism.

Two constraints make this more than a flag, and both are mandatory:

1. **Edge preservation.** Plain coalescing is insufficient for Bubble. Between two paints,
   publications carrying a discrete edge followed by an already-decayed value would present
   only the decayed value, which is the failure
   `tests/test_visualizer_presentation_negative_controls.py::test_latest_at_60_hz_can_hide_the_protected_bubble_edge`
   already models. The coalesced render state must retain bounded edge/event identity
   across the window so a skipped snapshot cannot erase authored response. Note that
   `_line_kick_event_strength` / `_line_snare_event_strength` are decaying envelopes and
   Bubble edges live in the bubble payload, so this is a state-commit change, not a flag.
2. **No permanent latch.** The outstanding-request flag must not remain set because one
   paint was delayed, and must be cleared by teardown/geometry/reveal boundaries. Geometry
   change, becoming visible, and buffer clear remain explicit immediate-request exceptions
   (`set_state()` already computes `geometry_changed` / `became_visible`).

Acceptance is not satisfiable from tests alone. Required before P2 is accepted:

- installed mixed-refresh (165 Hz + 60 Hz) run on ordinary `main.py` with `--perf` and
  `--gpu-timing`, compared against the accepted A-state figures in
  `Docs/phase_reports/P05_PRESENTATION_DELIVERY_ATTRIBUTION.md` — not against the retired
  monkeypatch;
- Bubble and Spectrum manual visual review. Per Guardrails §7 an operator-reported fidelity
  regression rejects the change regardless of green goldens or improved counters.

Regression bars that must stay green: `tests/test_visualizer_presentation_contract.py`
(publication/presentation separation, mixed-refresh delivery bar), the negative controls,
`test_bubble_cadence.py`, `test_spectrum_presentation_smoothing.py`, `test_visualizer_replay.py`.

Rollback anchor: `30e66e08` (P1 close, pre-P2).

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
