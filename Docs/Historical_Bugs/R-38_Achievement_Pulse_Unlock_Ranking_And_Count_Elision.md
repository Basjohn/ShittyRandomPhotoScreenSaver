# R-38 — Achievement Pulse Ranked Recent Play Instead Of Recent Unlock And Elided Unlocked Counts

Date: 2026-07-14  
Status: Resolved in code; runtime validation pending

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [x] AWAITING VALIDATION
- [ ] SOLVED

## Observed Failure Pattern

A second recent-play candidate had the newest achievement unlock, but the first recently-played game remained in `Most Recent` and pushed the true newest-unlock game into `PREVIOUSLY`. After the Portrait artwork addition, ordinary `Unlocked` totals also rendered as an ellipsis in Portrait and then every artwork mode.

## Root Causes

Achievement Pulse resolved the recent-game ordinal before reading achievement data and refreshed only that chosen app, so it had no evidence with which to compare unlock recency across candidates. The `Unlocked` metric rail also inherited the exact artwork width and used final text elision rather than locally fitting a normal/high count.

## Fix

Recent play now supplies only a bounded candidate set of at most five apps. Exact cached/fetched per-app achievement rows rank known positive latest unlock timestamps newest-first, with missing/zero evidence retained stably behind timestamped candidates in recent-play order; Settings labels, `Most Recent`, Recent #2-#5, and Previous share that order. Refresh uses the existing worker/cache/coalescing/backoff path and fetches schema only for the selected winner. The centered metric rail is wider than the artwork and locally fits down to an explicit floor before any exceptional elision.

## Bars

`tests/test_steam_achievement_pulse.py` proves play-order/achievement-order disagreement selects the newest unlock, matching cache-only Settings labels, five-candidate request bounds, and selected-schema-only fetch. `tests/test_steam_phase4_mock_visuals.py` proves `Unlocked: 999/999` reaches the painter intact in Wide, Square, and Portrait layouts.

## Runtime Validation Target

With real cache data whose play order and latest-unlock order disagree, require the newest unlock's game in `Most Recent`, the prior unlock game in `PREVIOUSLY`, matching Settings labels, and a complete non-elided `Unlocked` line in Portrait/Wide/Square/art-off without moving the artwork or capsule rails.

## Migration Record

This file is the standalone detailed record copied from the original `R-38` entry in `Docs/Historical_Bugs.md`. The monolithic source entry remains unchanged during the copy-first migration and will be replaced by a compact index summary only after the historical-bug set has been migrated and mechanically checked.
