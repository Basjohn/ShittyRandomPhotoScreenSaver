# R-75 — A superseded audio-analysis callback could release a serial-lane slot a newer owner held

**Status:** FIXED / GREEN (2026-09-01)

## Symptom

Surfaced by the destination gate, not the operator: `tests/test_p2_analysis_freshness.py::TestFailureAndFencing::test_a_superseded_result_does_not_claim_the_current_slot` failed with *"a stale callback released a slot it no longer owned"* — after a same-activation cancellation boundary, a stale compute callback cleared `_compute_task_active` even though a newer generation already held the single serial analysis slot.

## Mechanism

`_SpotifyBeatEngine._accept_analysis_lane_result` runs `_launch_pending_analysis_frame(releasing_active_slot=True)` in a `finally` so the callback that owned the in-flight slot hands it off to the newest pending source (or releases it when none exists). That handoff was **unconditional**: it ran even when the result was superseded (`payload.gate_token != self._compute_gate_token`).

`cancel_pending_compute_tasks()` bumps `_compute_gate_token`, and a new same-activation source is then scheduled with the new token and claims the slot (`_compute_task_active = True`). When the OLD callback (old gate token) finally returned, its unconditional `finally` released that slot. A subsequent logical tick then saw a free slot and could schedule a **second concurrent FFT** on the "single in-flight + one pending" serial lane — the exact double-compute R-71 forbids.

The discriminator is `activation_id`, not `gate_token` alone:

- **Activation replacement** (mode switch / `reset_smoothing_state`, which also bumps the gate token) — the old activation is genuinely done, so its callback *should* release its own slot and the fresh activation schedules from scratch.
- **Same-activation cancellation** (config change that cancels + reschedules within one activation) — a newer same-activation owner already holds the slot, so the stale callback must **not** release it.

## Repair

`widgets/spotify_visualizer/beat_engine.py`, `_accept_analysis_lane_result` `finally`:

```python
superseded_same_activation = (
    payload.activation_id == self._activation_id
    and payload.gate_token != self._compute_gate_token
)
if not superseded_same_activation:
    self._launch_pending_analysis_frame(releasing_active_slot=True)
```

The normal path (matching gate token) and activation-replacement path still hand off/release exactly as before; only a same-activation superseded callback now leaves the newer owner's slot untouched.

## Guardrails

- This strengthens R-71 serial-lane fencing; it changes no cadence, DSP, reactivity, freshness or newest-state behavior. Do not "simplify" it back to an unconditional release.
- The single in-flight + one pending contract stays intact: never fall back to a generic `Future`/task path or run two FFTs concurrently to work around a fencing boundary.
- Fencing is by `(gate_token, activation_id)`; the input launch path (`_launch_pending_analysis_frame`) still independently fences a stale pending frame by activation.

## Regression bar

`tests/test_p2_analysis_freshness.py` — both `test_a_superseded_result_does_not_claim_the_current_slot` (must not release) and `test_activation_replacement_discards_the_pending_source` (must release) pass together, alongside `test_visualizer_compute_lanes`, `test_visualizer_analysis_acceptance`, `test_visualizer_runtime_controller` and `test_visualizer_playback_gating`.
