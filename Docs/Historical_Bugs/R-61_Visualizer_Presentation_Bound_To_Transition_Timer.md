# R-61 — Visualizer Presentation Bound To The Transition-Scoped Render Timer

Date: 2026-08-17
Status: Resolved by exact revert to the pre-P2 anchor

## Commits

```text
pre-P2 anchor (restored):        30e66e08
rejected P2 implementation:      caab5a10
follow-up attach fix:            cd3ffc55
follow-up GUI-thread fix:        02b097ea
revert on main:                  50a7f93e
```

## Observed Failure

Phase 5 P2 attempted to replace the one-publication → one auxiliary `update()` contract with
a "display-owned presentation opportunity". The installed runtime froze: after the first
transition the display stopped updating entirely, while the Qt event loop stayed alive so the
context menu still responded and allowed an escape. The operator reported it recurring after
**every** transition.

## Cause

Two defects. The second is the architectural one.

### 1. Wrong thread

`AdaptiveTimerStrategy._signal_frame()` runs on the timer worker thread. The auxiliary
presentation path called `present_if_pending()` — and therefore `QWidget.update()` — directly
from it, instead of marshalling through `ThreadManager.run_on_ui_thread` as the compositor's
own path does. Off-GUI-thread `update()` corrupts Qt repaint state, which produces exactly the
observed signature: presentation dead, event loop alive. It also raced the revision counters
against `set_state()` on the GUI thread.

### 2. Wrong clock (fatal by design)

`AdaptiveTimerStrategy` is a **transition-scoped render strategy**, not a continuous
presentation clock:

- `_start_render_timer()` — "Start the render timer to drive repaints **during transitions**";
- `_pause_render_strategy()` — "Pause render strategy **after transition ends**".

Run evidence agrees: `time_running=9185 ms`, `time_paused=5014 ms`, `paused_waits=3374`.

Binding visualizer presentation to `_signal_frame()` therefore supplies opportunities only
while a transition is running and **none afterwards**. Once the first transition completed the
overlay was never offered another opportunity, so it never repainted again. Fixing defect 1
only made the frozen state survive longer.

The visualizer runs continuously — before, between and after transitions. It can never be
driven by a transition-scoped timer.

## Why The Documentation Already Forbade This

Every rule needed to prevent this was written down before the work started, in documents that
were not read:

- `Docs/Visualizer_Change_Checklist.md` §4 Runtime Bridge: *"Visualizer ticks stay owned by
  the dedicated recurring timer, not transition animation callbacks."*
- `Docs/Guardrails/Visualizer_Presentation.md` — "One Cadence Authority", and Required
  Validation item 5: *"Run irregular GUI-stall, **transition**, pause/resume, mode-switch, and
  generation-reset cases."* A transition-state case would have caught this immediately.
- `Current_Plan.md` Non-Negotiable Guardrails: *"Qt/QWidget/QPixmap/GL mutation stays on the
  correct GUI/context owner."* — defect 1.
- The `srpss-guardrails` project skill, which mandates a document pass including the
  visualizer checklist and `Docs/Harness_Index.md`, was never invoked.

## Process Failures

1. **Borrowed a clock without establishing its lifetime.** The wiring plan asserted
   `_signal_frame()` was "the display's owned frame opportunity" from reading its call site
   only. Its start/stop scope was never checked. A borrowed mechanism must be characterised by
   when it runs, not only by what it does.
2. **Tests modelled the caller incorrectly.** Unit tests called `present_if_pending()`
   directly, so neither the worker-thread caller nor the paused-strategy state existed in the
   suite. Thread affinity and clock lifetime were the two properties the seam depended on, and
   the tests asserted neither. Green tests were treated as readiness for runtime.
3. **A previous-behaviour fallback masked an inert first attempt**, and a wrong-log-file check
   then produced a false "P2 is inert" report when it was in fact active and freezing.
4. **A performance symptom was attributed to a visualizer mode.** Withdrawn separately; mode
   is a covariate, never a cause.

## Resolution

Exact revert of the four production files to `30e66e08`. The P1 contract bars are retained and
pass. No part of the rejected design was retuned in place.

## Anti-Regression

- Any presentation-opportunity source for the visualizer must be **live whenever the visualizer
  is live**. A candidate must be characterised by its start/stop/pause scope before use, and
  covered by a test in the paused/idle state, not only the active one.
- Any component invoked from `AdaptiveTimerStrategy._signal_frame()` runs on a worker thread
  and must marshal Qt work to the GUI owner.
- Presentation-ownership tests must model the real caller — its thread and its lifecycle state —
  rather than calling the seam directly.

P2 itself remains required. The defect it targets is measured and real:
`update_requests / set_state` is exactly `1.0000` across both Bubble and Spectrum, with the
overlay painting roughly 31% more often than the 60 Hz display can present. A replacement
approach must begin from the visualizer's own dedicated recurring timer — the cadence authority
the checklist already names — not from a transition-scoped one.
