# R-243: a slow parity judge cancelled the owner's mode switch

**21 November 2026. Fixed in the owner replay (`tools/visualizer_replay`). Status: FIXED.**

## Observed failure

`owner_render_parity.py --native --native-control shift` (the method proof's one-level shift control) never unbound
the native route at the mode switch. The route published every input (549 against 360 on the 5.5 s Studio clip,
5,503 against 5,314 on a 60 s take), and the native run's logical digests left the Python reference's. A stored
reference was then judged stale and drawn again (2,200 s on human_heavy1). Nothing said why; the control's frames still
failed, so the run looked like a working control.

## Root cause

Rule (a) judged each native frame inside the owner's frame loop (`on_frame=judge.frame`). Under the shift every frame
fails, and `pixel_tolerance.largest_group` grouped a frame whose every pixel differs with a per-pixel flood fill: about
0.85 s a frame. The replay runs on a logical clock, but the owner's activation transaction has a wall-clock deadline
(`_ACTIVATION_TRANSACTION_DEADLINE_MS`, 6 s). Bubble's fade-out spans about 117 inputs, so it overran the deadline, and
a deadline in `fading_out` cancels the switch and keeps the outgoing mode live (the product's correct behaviour for a
stalled fade-out). The run that followed was no longer the logical replay.

## Repair

- `native_parity` draws the native run first, writing each frame's hash line as it is drawn, and judges after (as its
  stale-reference path already did); nothing heavy runs inside the owner's frame loop.
- `owner_worker_gate.identity_run` watches the owner's deadline (`watch_transition_deadlines`) and raises
  `TransitionDeadlineFired` when one cancelled a fade-out or failed a transition, so no replay can silently become
  another run.
- `largest_group`'s fallback (no SciPy) is a union-find over row runs: 0.063 s for the shifted frame, the flood fill's
  result at every density (`tests/test_pixel_tolerance.py`).

## Validation

`tests/test_visualizer_owner_render_parity.py::test_judging_never_holds_the_owners_frame_loop_past_its_wall_clock_deadline`:
a judge slowed around the switch under a 2 s deadline leaves the switch and the digests as in a quick run; its control
puts the same slowness inside the owner's frame loop and is caught (`TransitionDeadlineFired`). A probe isolated the
cause: the shift alone and a 50 ms `on_frame` alone both switch normally (the slow run logged a deadline extension).

## Lesson

A replay on a logical clock still drives product code that keeps wall-clock watchdogs. Harness work done inside the
product's loop must be bounded or moved out, and a watchdog that fires during a replay must fail the run, never pass
unnoticed.
