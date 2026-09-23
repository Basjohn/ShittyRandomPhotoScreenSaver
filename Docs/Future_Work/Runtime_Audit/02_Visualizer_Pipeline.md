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

## VZ-01 — Paused idle waveform synthesized every tick for every mode · P2 · R2 · Risk Medium · `[~]`

**Evidence.** `_SpotifyBeatEngine.tick()` (`beat_engine.py:1181-1191`) calls `_update_idle_waveform()` (256 samples ×
3 `math.sin`) and `_prime_idle_bars()` on every authored tick whenever playback is paused. **Measured ≈154 µs +
24 µs = ≈178 µs per tick ≈ 16 ms/s** of GIL-held Python on the logical thread, indefinitely while paused (a common
overnight screensaver state), for Spectrum/Bubble/DevCurve/Sphere too. Only the Oscilloscope renderer reads the
waveform *samples* (`rendering/quick/visualizer/implementations/oscilloscope.py:112-116`); Sine and Oscilloscope
both use the waveform *generation* for source readiness (`logical_frame_capture.py:117-127`,
`tick_pipeline.py:103-105, 1061-1066`).

**Proposal.** Keep `_prime_idle_bars()` (cheap, feeds idle bars/energy) and keep advancing
`_latest_generation_with_waveform` on paused ticks exactly as today (Sine readiness depends on it). Make only the
256-sample synthesis demand-driven with the engine's existing demand-bit pattern
(`_pre_agc_analysis_spectrum_requested`, `beat_engine.py:970-991`): armed at Oscilloscope activation
(configure/commit), not lazily on first capture, so the first paused Oscilloscope tick is unchanged.

**Must remain true.** R-03: paused Sine/Oscilloscope idle stays alive, same phase math, same direction semantics;
R-87 CHK12: playing line-mode reveal still needs an authoritative analysis timestamp; paused idle reveal unchanged;
no second clock, no timer.

**Implemented.** The logical step calls `engine.set_idle_waveform_demand(mode == "oscilloscope")` immediately before
every `engine.tick()` (mode is read live from the controller, which `set_mode` updates before the new runtime starts),
so a paused hot switch into Oscilloscope synthesizes on its first tick; no activation bookkeeping or stale demand.
Undemanded paused ticks advance `_latest_generation_with_waveform` exactly as before and drop pre-pause live PCM once.
The engine default stays "synthesize" for any caller that never declares. Measured paused tick (idle, 64 bars):
150.6 → 36.4 µs (≈13.6 → 3.3 ms/s at 90 Hz) for every non-Oscilloscope mode; Oscilloscope unchanged.

- [x] Bars: `tests/test_visualizer_idle_waveform_demand.py` (Oscilloscope waveform identical to the frozen R-03
      synthesis for the same timestamps; non-line modes never call the synthesizer yet keep generation readiness;
      demand declared before every tick for all six modes) — 8 of 9 fail without the fix. Visualizer, Sine, Osc, BTF
      and Bubble suites green.
- [ ] Physical: paused idle for all six modes; pause→play and play→pause on Sine/Osc (R-03 artifacts: flat line,
      snap-back, direction inversion must not appear).

---

## VZ-03 — Per-tick phase instrumentation always on · P3 · R1 · Risk Low

**Evidence.** `logical_tick()` allocates a closure, a dict and nine `perf_counter()` samples every tick
(`tick_pipeline.py:1425-1520`); the data is read only when a tick exceeds 50 ms **and** `--perf` is enabled.
Violates "diagnostic instrumentation adds zero per-frame work at rest".

- [ ] Capture `is_perf_metrics_enabled()` once per runtime start; skip phase recording when disabled; keep the slow-
      tick warning path and message format identical when enabled.

---

## VZ-04 — Every mode's logical frame copies and validates the 256-sample waveform · P3 · R1 · Risk Low–Medium

**Evidence.** `_base_extras()` always calls `engine.get_waveform()` (a 256-element `list` copy,
`beat_engine.py:1369-1371`; `logical_frame_capture.py:217-224`), and `VisualizerCommonState.__post_init__`
re-validates it with `_float_tuple` (`render_state.py:225-230`). **Measured ≈34 µs/tick ≈ 3 ms/s.** Source
search on the audited tree finds only the Oscilloscope renderer reading `common.waveform`
(`implementations/oscilloscope.py:112-116`); Bubble mentions it only in comments.

- [ ] Add a per-mode payload test that pins which modes consume `common.waveform` (guards future modes).
- [ ] Pass `()` for non-Oscilloscope modes (the field already defaults to `()`); keep `waveform_count`/generation
      semantics used for Sine readiness unchanged.

---

## VZ-05 — Config-static render extras re-collected and re-frozen every tick · P2 · R1–R2 · Risk Medium · `[~]`

**Evidence.** Each capture builds a fresh dict from `_populate_shared_visualizer_extras` (~28 keys,
`config_applier.py:650-680`) plus mode extras (Sine/Osc ≈60 more, `:686-765`; DevCurve ≈50 via
`_devcurve_parameter_snapshot`, `tick_pipeline.py:229-273`) and freezes them through `freeze_render_fields`
(sort + per-value validation + tuple allocation, `render_state.py:106-157`) every tick. Most values change only at
configuration/activation boundaries; a few are per-tick (`heartbeat_intensity`, Bubble arrays, line-mode event
strengths).

**Evidence step first.** `_tick_phase_ms` already separates `publish` (capture + mailbox); log its per-mode
distribution once under `--perf` (or use a focused benchmark of `capture_visualizer_logical_frame`). Proceed only if
capture is a material share of tick cost.

**Proposal if admitted.** Split static vs dynamic keys; freeze the static set once per **configuration epoch**
(bumped by `_apply_configuration`, mode/preset activation, technical config and presentation-state writes) and
reuse the same immutable `FrozenFields` object; merge dynamic keys per tick. Reuse of an immutable object is not
shared mutable state (R-71 rule).

**Must remain true.** R-22/A-06: no value from a previous mode/preset/activation may survive an activation boundary
— the epoch must reset in the activation transaction itself, and bars must poison-test hot switch and preset cycle.

- [x] Evidence captured; decision recorded (2026-09-23). Production-shaped logical ticks (real owner/controller,
      fixed engine), unprofiled, `freeze_render_fields` per tick before the fix: Spectrum 41 µs, Oscilloscope 105,
      Sine 104, Bubble 93, DevCurve 280, Sphere 16 (≈4–25 ms/s at 90 Hz); whole capture 111–289 µs.
      **Root cause found:** `freeze_render_fields` froze every value and then built `FrozenFields` through its public
      constructor, which froze and validated every value again; nested `FrozenFields` values were rebuilt recursively.
- [x] **Landed (no caching, no epoch):** `FrozenFields._from_frozen_entries` adopts the already-frozen, validated
      entries, and an existing `FrozenFields` is returned as-is (deep-frozen by construction). Output equal and hash-
      equal to the constructor path; NaN/empty-name/type validation unchanged. 61-key record 155.8 → 65.4 µs.
      Bar: `tests/test_visualizer_render_state_freeze.py` (fails without the fix).
- **Parked:** the configuration-epoch cache for static keys. After the single-freeze fix the remaining cost is
  ≈17–117 µs/tick of preemptible logical-thread Python, which does not justify R-22/A-06 activation-bleed risk.
  Reopen only if `--perf` tick phases show capture dominating a stall.

---

## VZ-06 — Folded into VZ-05

`_devcurve_parameter_snapshot()` + four `list()` shape-node copies per tick are the DevCurve instance of VZ-05.

---

## VZ-07 — Logical runtime sleeps in 4 ms slices (≈3 wakeups per 11 ms step) · Parked

`_wait_until()` sleeps `min(remaining, 4 ms)` (`logical_runtime.py:62-65, 442-448`) so `stop()`/`wake()` are prompt.
Removing slicing would save ≈180 GIL reacquisitions/s but touches the BTF clock for a small, unmeasured gain;
`Event.wait` was proven to quantize to 15.6 ms on this platform. **Parked** unless a trace shows these wakeups in a
render-entry tail. Do not reopen without that evidence.
