# R-83 — Reddit Sub-Millisecond Cooldown Could Re-enter The Due Path Synchronously

Date: 2026-09-14  
Status: SOLVED — Installed 58-Minute Soak Closed The Scheduler Gate

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

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

## Installed Validation — 2026-09-14

The 58-minute Windows soak closed the scheduler gate. Two `blocked_cooldown_due` edges reached a computed **0.0** remaining delay in the log, but neither recreated the old synchronous zero-delay re-arm storm. Each edge proceeded into the legitimate due work once and then established the ordinary **900 s** horizon. Manual refreshes during active cooldown were rejected with their positive remaining delay rather than multiplying requests.

Thread telemetry over the run showed only **8 `reddit_fetch` tasks** and **3 `reddit_service_gate` tasks**. There was no same-second recursive burst comparable to the old 84-arm failure and no request/backoff cadence multiplication. R-83 is therefore closed.

## Guardrail

A positive time interval must remain positive when converted to timer units. Never translate a positive cooldown into synchronous execution merely because integer rounding reaches zero; due ownership must remain event-driven and one-shot.
