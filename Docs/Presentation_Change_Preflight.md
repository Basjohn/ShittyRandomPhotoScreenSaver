# Presentation / Cadence Change Preflight

Last updated: 2026-08-17

A **rejected-mechanism register** and door-map for changes to visualizer presentation, repaint
requests, cadence, render-state delivery, or compositor frame pacing.

This file adds no policy and **grants no authority over `Current_Plan.md`**. It exists so that
past failures are discoverable before designing, not so that past conclusions outrank the
active plan. Where this file and `Current_Plan.md` disagree, `Current_Plan.md` wins — it is the
execution authority.

**It does not say any planned work is closed.** Phase 5 P2 is active and required.

## 1. What is barred, and what is not

Barred are **mechanisms**, established by dated failures. Not outcomes, and not goals.

| Rejected mechanism | Source | Failure signature |
|---|---|---|
| Producer-timestamp gate against a display-rate divisor | R-27 (2026-08-13 reconstruction) | `0.92 x 1/60 s` accepts a 100 Hz source every second tick → 50 Hz |
| Pending-until-`paintGL()` admission latch | R-27, negative controls | Variable Qt delivery becomes producer admission → 39–40 Hz collapse |
| `paintGL()` self-scheduling `update()` | R-27 | Child-GL overpaint: `paint≈275 fps`, `update≈364 fps` on a 60 Hz owner |
| Pending-paint requeue / rescue timers | R-27 | 134 rescues; `--perf` materially worse; delivery unfixed |
| Any cadence gate placed *before* logical integration | R-54 | 2,566 offered steps → 1,723 submissions; edges decayed before first publication |
| Latest-state sampling at display rate without edge identity | Bubble v1 golden | A one-tick authored edge is missed entirely |
| Visualizer presentation driven *solely* by `AdaptiveTimerStrategy` | R-61 | Transition-scoped source; visualizer froze permanently after the first transition |
| Visualizer ticks on a transition `AnimationManager` | R-27 | Visualizer cost became part of transition progress cadence |

**Required regression bar for any candidate:** it must not reproduce
`set_state ≈ 90–100 Hz` with `paint/update ≈ 39–40 Hz` (R-27's stutter signature).

## 2. What is explicitly NOT barred

- **Reducing presentation requests below one-per-publication.** R-27's sentence declaring
  one-repaint-per-accepted-payload the correct contract is **superseded** — see its
  2026-08-17 supersession note. It over-generalised from one broken mechanism.
  `Current_Plan.md` P1 requires proving logical publication *may* outrun presentation without
  one `update()` per publication, so treating `update_requests / set_state == 1.0` as an
  invariant contradicts the active plan.
- **A display presentation owner deciding when already-integrated state is presented.**
  Guardrails' prohibition on "compositor-owned visualizer cadence" protects *logical/simulation*
  cadence — source sampling, integration, dt, event consumption, publication order. It does not
  reserve presentation timing to the producer.
- **Coalescing after integration.** Permitted once every logical input has been integrated and
  the mode's visible publication semantics remain intact.
- **Using a transition-scoped presentation source while it is running**, provided the overlay
  still presents when that source is paused or absent. R-61 bars *sole* dependence, not use.

## 3. Corpus reading order

| Order | Document | Decides |
|---|---|---|
| 1 | `Current_Plan.md` | **Execution authority.** What is actually being attempted now |
| 2 | `Docs/phase_reports/P05_PRESENTATION_DELIVERY_ATTRIBUTION.md` | Accepted causal evidence and its limits |
| 3 | This register | Which mechanisms are already disproven |
| 4 | `Docs/Guardrails/Visualizer_Presentation.md` | One cadence authority; required validation |
| 5 | `Docs/Visualizer_Change_Checklist.md` §4 | Runtime bridge; tick ownership |
| 6 | roadmap `06_PRESENTATION_AND_COMPOSITOR_DESIGN.md` | Forbidden admission mechanisms; required shape |
| 7 | `Docs/Compositor_Architecture.md` §4 | Logical cadence vs presentation |

Historical records are evidence about mechanisms. They are not a veto over current plans.

## 4. Eligibility rules for a presentation opportunity source

- The overlay must still present when the source is **paused or absent** (R-61).
- Anything reached from `AdaptiveTimerStrategy._signal_frame()` runs on a **worker thread** and
  must marshal Qt work to the GUI owner (R-61).
- It must not derive admission from paint acknowledgement, producer timestamps, or a
  display-rate divisor (R-27).
- Logical integration always happens first, for every input (R-54).

## 5. Test bars before runtime

Tests must model the **real caller** — thread and lifecycle state — not call the seam directly.
A suite that only exercises the active state cannot detect a source that stops.

- paused/idle **and** active source states;
- worker-thread caller, not direct invocation;
- transition running, transition ended, no-transition steady state;
- mode switch, activation change, generation reset, teardown;
- Bubble one-tick discrete edge still visible;
- Spectrum authoritative tick trace unchanged;
- **both** overpaint and under-delivery detectable;
- the R-27 stutter signature does not reproduce.

Owning suites: `tests/test_visualizer_presentation_contract.py`,
`tests/test_visualizer_presentation_negative_controls.py`, `tests/test_bubble_cadence.py`,
`tests/test_spectrum_presentation_smoothing.py`, `tests/test_visualizer_replay.py`.

## 6. Where runtime evidence actually lands

| Evidence | File |
|---|---|
| Overlay `set_state` / `update_requests` / `paint` / `state_to_paint` | `logs/screensaver_spotify_vis.log` |
| Delivery-stage cadence and skip attribution | `logs/screensaver_perf.log` |
| Lifecycle / teardown | `logs/screensaver_lifecycle.log` |
| Human narrative and WARNING+ fan-in | `logs/screensaver.log` |

The main log does not carry everything. Check the owning sidecar before reporting a null result.

**`paint / update_request` is not a measure of useful presentation.** R-27 recorded ~275
paints/s against a 60 Hz owner, and R-55 recorded ~142–154 paints/s against ~100 Hz
`set_state` while the visualizer was *worse*. A high paint-to-request ratio does not mean the
request stream is efficient, and must not be used to argue that little headroom exists.

## 7. Existing tooling — prefer over new probes

`tools/phase5_frame_owner_benchmark.py`, `tools/visualizer_replay.py`,
`tools/bubble_parity_harness.py`, `tools/spotify_vis_metrics_parser.py`,
`tools/perf_measure.py`, `tools/visualizer_distribution_harness.py`,
`tools/transition_perf_health_parser.py`. See `Docs/Harness_Index.md`.

## 8. Standing interpretation rules

- A performance result is **never** attributed to a visualizer mode or a transition type. Modes
  and transitions are load conditions and detectors, not causes. Bubble is the most sensitive
  detector of a bad change.
- UI pressure is never the answer to a cadence problem (R-27).
- A change with no measurable effect is "not proven active" until activation is confirmed in the
  owning sidecar (`Docs/Guardrails.md` §3).
