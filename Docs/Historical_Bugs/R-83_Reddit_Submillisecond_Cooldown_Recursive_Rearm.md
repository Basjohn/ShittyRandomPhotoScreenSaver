# R-83 — Reddit Sub-Millisecond Cooldown Could Re-enter The Due Path Synchronously

Date: 2026-09-14  
Status: Resolved In Code / Installed Soak Validation Pending

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [x] AWAITING VALIDATION
- [ ] SOLVED

## Observed Failure

The overnight soak contained **854** Reddit due-timer arm records, with **721** effectively zero-delay arms. The worst burst produced **84 synchronous arms in one second**. Network rate limiting prevented corresponding request multiplication, so this appeared primarily as needless UI-thread/log churn rather than a Reddit request storm.

## Root Cause

The blocked-cooldown path started with a valid positive remaining interval measured in seconds, but conversion to milliseconds used truncation. A positive remainder below 1 ms therefore became integer `0`.

The scheduler then treated zero as "execute due now" and called the periodic due path synchronously. That path rechecked the still-positive blocked cooldown, truncated it to zero again, and synchronously re-entered itself until wall time finally crossed the boundary.

This violated the runtime's event-driven ownership contract: a still-positive cooldown became recursive execution rather than one deferred due event.

## Fix

- positive seconds-to-milliseconds conversion now uses ceiling semantics with a minimum **1 ms** delay;
- even a genuinely due-now edge is delivered through the existing `ThreadManager.single_shot` path rather than direct synchronous `_on_periodic_due()` re-entry;
- token/generation fencing remains unchanged;
- no polling loop, new timer owner, cadence, provider behavior, or Reddit request policy was introduced.

The added delay is at most the rounding remainder at an already-due boundary, roughly 1–2 ms in practice, negligible beside the ordinary Reddit refresh cadence.

## Regression Coverage

`tests/test_reddit_runtime.py` now drives a controlled positive **0.4 ms** blocked cooldown and proves:

- no synchronous periodic-due call occurs;
- exactly one positive one-shot is armed;
- firing that captured one-shot delivers the ordinary due path exactly once;
- no recursive arm/fetch chain is required to consume the remaining wall-clock fraction.

The reduced A/B reproduction changed from **1 synchronous due / 0 scheduled shots** before repair to **0 synchronous / 1 positive shot** after repair.

The existing Reddit/cache diagnostics are sufficient long-term evidence. Due-arm reason and delay already route through the cache diagnostic family; no new diagnostic flag or periodic probe is warranted.

## Validation Target

Run the focused Reddit runtime/helper suites, then perform an installed cache/service soak with Reddit and Reddit2 enabled.

Require:

- no zero-delay or same-second recursive `blocked_cooldown_due` bursts;
- blocked responses still defer rather than bypass provider/rate-limit policy;
- manual-refresh bypass rules remain unchanged;
- ordinary terminal success/failure continues to establish the intended next due horizon;
- no request multiplication or new recurring timer owner appears.

## Guardrail

A positive time interval must remain positive when converted to timer units. Never translate a positive cooldown into synchronous execution merely because integer rounding reaches zero; due ownership must remain event-driven and one-shot.
