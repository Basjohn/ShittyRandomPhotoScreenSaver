# R-105 | Bubble Remaining Small-Radius Judder

**STRONG RETENTION VALUE DOCUMENT**

Status: **TINY-BREATH EXPERIMENT REJECTED AND REMOVED / PHYSICAL LOCALIZATION OPEN**
Binding contract: `Docs/Guardrails/Bubble_Temporal_Fidelity.md`.
Live acceptance: `Current_Plan.md` section 1.

## Accepted baseline and protected behavior

The operator reported 1-2px drawn-radius vibration between breathing states. The first repair (`800bf70f18`) keeps raw
simulation/pulse/motion authority and gives drawn loudness, drawn body energy and the hero size gate an immediate rise plus
`RENDER_SIZE_RELEASE_S` release. Feeding that envelope into `pulse_energy` was rejected because it changed excursion/feel.
The accepted render-release repair remains; small drawn radii now follow every resulting authored target directly.
`tests/test_bubble_render_judder.py` protects both the instant-release negative control and exact small-radius reversals.

The remaining symptom must never license general audio smoothing, delayed attack, flatter amplitude, weaker elasticity,
hot-passage pinning, another clock or a cadence reduction. Shared presentation stalls are separately actionable.

## Rejected directional micro-breath experiment

The removed experiment added presentation history to each non-big bubble. It suppressed the first small reversal, admitted
an established reversal on the second sample, and could advance an established half-breath by one reference pixel.
Pulse endpoints, strong edges, promotion, pop and exit bypassed it; it attempted to remain on the raw target's side of the
shader's dot/outline threshold. Its synthetic helper test demonstrated changed output, not musical benefit.

The evaluation used the canonical operator-authored schema-2 recordings and an exact OFF/ON control, with identical
resolved settings and deterministic replay. Production-object identity replaced nearest-position tracking: close bubbles
could previously be assigned to the wrong track. At a supplied response-height projection of 300px:

| Recording | Tiny alternating steps OFF -> ON | All-radius steps OFF -> ON |
| --- | --- | --- |
| balanced | 0 -> 3 | 127 -> 130 |
| heavy1 | 0 -> 3 | 57 -> 60 |
| quiet_intro | 0 -> 3 | 39 -> 42 |
| quiet_intro2 | 0 -> 0 | 27 -> 27 |

The candidate did not improve the affected band. It changed reference-projected extrema and excursions on musical/clean
fixtures, and reached 1.071429px deviation at the 300px projection despite its claimed one-pixel bound. The old
nearest-position analyser also reported worse/no-better outcomes, but its counts are not the maintained oracle.
Local evidence: `logs/bubble_judder_acceptance/tiny_candidate_300.json` and `tiny_candidate_fixtures_300.json`.
Reports carry the source revision, diagnostic fingerprints, input/settings hashes, per-clip counts, frame-aligned extrema,
first radius movement and excursion, plus bounded differing-window examples. They are local evidence, not normal GODZIP payload.

The scale error matters independently of the failed result: the helper used cached **logical viewport height**, while Quick
projects radius through the equal-area response height and the committed presentation/DPR. Logical height cannot establish
physical-device-pixel eligibility, deviation or the shader representation boundary across CUSTOM shapes/scales/displays.
The helper, constants, extra BubbleState history, helper-only tests and comparison CLI spelling were removed together.
Do not restore them as a disabled feature or fallback.

## Maintained evidence and limits

`python -m tools.visualizer_replay.bubble_judder --compare-release --report <path>` compares the accepted render envelope
against instant release through the production logical/snapshot seam. The optional supplied projection is not a physical
display measurement. Identity tracking is replay-only and adds no product telemetry, IDs, timers or dormant-mode work.
Input-anchored first radius change on an already moving track is not causal audio-response latency; isolated response,
attack/decay and protected golden checks remain separate. The report does not establish installed delivery or subjective feel.

Before another repair, identify the physical symptom's actual radius band, representation changes, song passage, authored
settings and renderer/DPR projection. The current corpus at this projection does not reproduce alternating runs in the
formerly eligible <=8px band. Keep missing physical localization/acceptance open rather than inventing another filter.
