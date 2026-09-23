# 02 — Visualizer Pipeline (source → logical → publication)

Owners audited: `widgets/spotify_visualizer/{beat_engine,audio_worker,tick_pipeline,logical_runtime,logical_frame_capture,render_state,runtime_controller,config_applier}.py`,
`core/threading/compute_lanes.py`.

**Binding for every item here:** Visualizer_Presentation.md, Bubble_Temporal_Fidelity.md (BTF), R-69, R-71, R-22 /
A-06 (activation bleed), R-87 CHK12 (line-mode readiness). Any item touching per-tick payload or source readiness
requires the BTF active-music lane before `[x]`.

## What is already healthy (do not re-audit)

- One persistent `visualizer.audio_analysis` lane, one in flight + newest pending, retained DSP state, slot tokens
  (R-71, R-87 CHK12) — `beat_engine.py:894-968`.
- Audio callback is lean NumPy + one detached copy + latest-wins buffer (`audio_worker.py:569-616`).
- Authored clock: non-daemon thread, `perf_counter` deadlines, missed deadlines skipped, joined on retire
  (`logical_runtime.py:304-500`).
- Mailbox wakes the GUI only on empty→populated; wake object closes before join (`logical_runtime.py:177-226`,
  `quick_display_visualizer_owner.py:1050-1083`). The retire/wake race was traced and is safe.

---

## VZ-07 — Logical runtime sleeps in 4 ms slices (≈3 wakeups per 11 ms step) · Parked

`_wait_until()` sleeps `min(remaining, 4 ms)` (`logical_runtime.py:62-65, 442-448`) so `stop()`/`wake()` are prompt.
Removing slicing would save ≈180 GIL reacquisitions/s but touches the BTF clock for a small, unmeasured gain;
`Event.wait` was proven to quantize to 15.6 ms on this platform. **Parked** (reaffirmed 2026-09-23; the soak shows no
cadence problem) unless a trace shows these wakeups in a render-entry tail. Do not reopen without that evidence.
