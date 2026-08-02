# R-54 — Phase 5 Bubble Cadence Gate Delayed And Flattened Visible Reactions

Date: 2026-08-01  
Status: Resolved

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

## Observed Failure

Bubble still painted around 89–93 FPS and its workers remained cheap at roughly 1–2 ms, but reactions felt late, stale, and less elastic. In the decisive 29.38-second interval, 2,566 Bubble steps were offered while only 1,723 worker tasks were submitted: 842 were cadence-token deferrals, compared with one actual worker-busy deferral and three overload coalesces. Roughly one-third of overlay publications therefore repeated unchanged Bubble arrays.

## Root Cause

The Phase 5 attempt imposed a second 60 Hz token clock on the visualizer tick and batched up to two authored packets while publishing only the terminal snapshot. An impulse in the older packet could be integrated and partially decay before its first visible publication. The shallow-copied settings packet also retained the live event scheduler, allowing an older batch item to consume a newer discrete edge that the terminal packet would then miss.

## Correction

The artificial token budget, packet queue, coalescing, and multi-step worker batch were removed. Bubble now checks its existing single-worker/pending-result ownership lane before reading audio, advancing its authored timestamp, or exposing the event scheduler; every lane-free tick freezes one payload, runs exactly one simulation/snapshot step, and publishes it with the existing activation-token stale-result guard.

## Guardrail

P5.0 task reduction remains open, but task-count success cannot override Bubble feel. Future reduction must preserve discrete input edges, loud-passage elasticity, input-to-visible attack, and one visible result for every integrated logical step. Transition-time 44–97 ms GUI/frame-delivery gaps remain separate P5.1 evidence and are not a reason to retune Bubble or reinstate batching.

## Validation

The latest installed run offered and submitted 50,106 lane-free Bubble steps with a 1.000 publication ratio, no cadence deferrals, and worker execution remaining roughly 1–2 ms. Later intervals remained around 89 FPS with only isolated genuine worker-lane deferrals. The operator confirmed that immediate reaction and elasticity are restored, including the formerly stale-feeling case; Settings ingress/exit also remained functional. First-frame and mode-switch generation/activation identities stayed matched.

## Why Automation Missed It

The original checks protected final state, ordering, task bounds, and deterministic packet outcomes, but did not measure source/discrete-edge to first visible publication under the real recurring-tick and GUI-delivery shape. A terminal-only batch could therefore pass while an impulse decayed before anyone saw it. Cadence work now requires the temporal runtime-shaped oracle and installed visual review recorded in `Docs/Guardrails.md` and `Docs/Visualizer_Change_Checklist.md`.

## Migration Record

This file is the standalone detailed record copied from the original `R-54` entry in `Docs/Historical_Bugs.md`. The monolithic source entry remains unchanged during the copy-first migration and will be replaced by a compact index summary only after the historical-bug set has been migrated and mechanically checked.
