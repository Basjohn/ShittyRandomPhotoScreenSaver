# Presentation / Cadence Change Preflight

Last updated: 2026-08-17

A single door-map for any change to visualizer presentation, repaint requests, cadence,
render-state delivery, or compositor frame pacing. Read this **before designing**, not after a
failure. It exists because two separate attempts walked into rules that were already written
down but not linked from anywhere reachable (R-61).

This file adds no new policy. It routes to the documents that already own it.

## 1. Mandatory reading, in order

| Order | Document | What it decides |
|---|---|---|
| 1 | `Docs/Historical_Bugs/R-27_Pending_Paint_Requeue_UI_Pressure.md` | **The barred experiments.** Read this first; it already rejected several obvious-looking fixes. |
| 2 | `Docs/Guardrails/Visualizer_Presentation.md` | One cadence authority; eligible presentation sources; required validation |
| 3 | `Docs/Visualizer_Change_Checklist.md` §4 | Runtime bridge; tick ownership |
| 4 | `Docs/audits/SRPSS_Architecture_Roadmap/06_PRESENTATION_AND_COMPOSITOR_DESIGN.md` | Forbidden admission mechanisms; required production shape |
| 5 | `Docs/Compositor_Architecture.md` §4 | Logical cadence vs presentation |
| 6 | `Docs/Guardrails.md` §§1–3, 6 | Priority order, stop conditions, presentation rules |
| 7 | `Docs/phase_reports/P05_PRESENTATION_DELIVERY_ATTRIBUTION.md` | Accepted delivery evidence and its limits |

## 2. Already-rejected designs — do not re-propose without new contradictory evidence

| Design | Rejected by | Failure |
|---|---|---|
| Capping overlay `update()` requests to the owning display's target rate | R-27 | Counters looked cleaner; **visible Display 1 stutter**. `set_state≈90–100 fps` while `paint/update≈39–40 fps`. Barred as producer-side visualizer throttling. |
| Producer-timestamp gate against a display-rate divisor | R-27 (2026-08-13 reconstruction), `test_visualizer_presentation_negative_controls.py` | A `0.92 × 1/60 s` gate accepts a 100 Hz source every second tick → 50 Hz. |
| Pending-until-`paintGL()` latch | R-27, negative controls | Turns variable Qt delivery into producer admission; observed collapse toward 39–40 Hz. `paintGL()` is neither scanout nor present acknowledgement. |
| `paintGL()` self-scheduling `update()` | R-27 | Child-GL overpaint: `paint≈275 fps`, `update≈364 fps` on a 60 Hz owner. |
| Pending-paint requeue / rescue timers | R-27 | Added UI pressure, made `--perf` materially worse (134 rescues), did not fix delivery. |
| Latest-state sampling at display rate without edge identity | Bubble v1 golden, negative controls | Misses a one-tick authored edge entirely. |
| Driving visualizer presentation from `AdaptiveTimerStrategy` | R-61 | Transition-scoped clock; visualizer froze permanently after the first transition. |
| Visualizer ticks on a transition `AnimationManager` | R-27 | Made visualizer cost part of transition progress cadence. |

## 3. The standing contract

From R-27, after the throttling attempt failed:

> the correct contract is **one repaint request per accepted visualizer payload**, no
> `paintGL()` self-update loop, and parser coverage for both overpaint and under-delivery.

Treat `update_requests / set_state == 1.0` as **the intended contract**, not a defect, unless a
change is explicitly approved to supersede R-27. Overpaint *and* under-delivery are both
regressions.

## 4. Eligibility rules for any presentation opportunity source

- It must be **live whenever the visualizer is live** — before, between and after transitions.
  Characterise its start/stop/pause scope before adopting it. `AdaptiveTimerStrategy` fails
  this (R-61).
- Anything reached from `AdaptiveTimerStrategy._signal_frame()` runs on a **worker thread** and
  must marshal Qt work to the GUI owner.
- It must not derive from paint acknowledgement, producer timestamps, or a display-rate divisor.
- The visualizer's own dedicated recurring tick is the cadence authority
  (`Docs/Visualizer_Change_Checklist.md` §4).

## 5. Test bars a presentation change must clear before runtime

Tests must model the **real caller** — its thread and its lifecycle state — not call the seam
directly. A suite that only exercises the active state cannot detect a clock that stops.

- paused/idle state as well as active;
- worker-thread caller, not direct invocation;
- transition running, transition ended, and no-transition steady state;
- mode switch, activation change, generation reset, teardown;
- Bubble one-tick discrete edge still visible;
- Spectrum authoritative tick trace unchanged;
- both overpaint and under-delivery detectable.

Owning suites: `tests/test_visualizer_presentation_contract.py`,
`tests/test_visualizer_presentation_negative_controls.py`, `tests/test_bubble_cadence.py`,
`tests/test_spectrum_presentation_smoothing.py`, `tests/test_visualizer_replay.py`.

## 6. Runtime evidence — where it actually lands

| Evidence | File |
|---|---|
| Overlay `set_state` / `update_requests` / `paint` / `state_to_paint` | `logs/screensaver_spotify_vis.log` |
| Delivery-stage cadence and skip attribution | `logs/screensaver_perf.log` |
| Lifecycle / teardown | `logs/screensaver_lifecycle.log` |
| Human narrative and WARNING+ fan-in | `logs/screensaver.log` |

The main log does not carry everything. Check the owning sidecar before reporting a null result.

## 7. Existing tooling — prefer over new probes

`tools/phase5_frame_owner_benchmark.py`, `tools/visualizer_replay.py`,
`tools/bubble_parity_harness.py`, `tools/spotify_vis_metrics_parser.py`,
`tools/perf_measure.py`, `tools/visualizer_distribution_harness.py`,
`tools/transition_perf_health_parser.py`. See `Docs/Harness_Index.md`.

## 8. Standing interpretation rules

- A performance result is **never** attributed to a visualizer mode or a transition type. Modes
  and transitions are load conditions and detectors, not causes. Bubble is the most sensitive
  detector of a bad change.
- UI pressure is never the answer to a cadence problem (R-27, `srpss-guardrails` skill).
- A change with no measurable effect is "not proven active" until activation is confirmed in
  the owning sidecar (`Docs/Guardrails.md` §3).
