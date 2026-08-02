# R-37 — Abandonment Rotation Expiry Was Silently Dropped And Selection Walked Archive Order

Date: 2026-07-14  
Status: Resolved in code; runtime validation pending

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [x] AWAITING VALIDATION
- [ ] SOLVED

## Observed Failure Pattern

Abandonment Issues could remain on Archive `01` with the same game and rediscovery copy for an hour, even when its configured rotation interval had elapsed repeatedly.

## Log Evidence

The reviewed session was `main_mc.py` and created a 15-minute timer from the now-retired card-level value even though the shared Steam refresh interval was 5 minutes; R-40 records that separate cadence defect. Timer profiler samples showed callbacks completing in roughly `0.02 ms`, but no content transition followed. The observed 15-minute expiry was an exact multiple of the parent display's three-minute image cycle, making repeated transition collisions plausible even though 15 was not the correct configured authority.

## Root Causes

1. `_request_cache_only_rotation()` returned immediately when parent transition work was pending/running. A recurring timer expiry was therefore discarded rather than deferred, and the next attempt could collide at the same phase indefinitely.
2. `_select_rotation_candidate()` always selected the first sorted candidate initially and then the next index, so Archive position exposed a predictable sequential walk instead of varied rediscovery.
3. A callback arriving just before the persisted interval boundary could fail the due check and wait for a complete extra interval.
4. Every widget/settings/display rebuild armed a complete new interval instead of the remaining persisted duration, so several otherwise normal recreations could postpone a five-minute rotation indefinitely.
5. Explicit widget refresh bypassed source freshness but did not force semantic rotation. Owned/recent cache writes therefore appeared in logs while the same selected game was intentionally retained.

## Fix

Abandonment now reuses `defer_refresh_if_transition()` and a low-pressure one-second `ThreadManager.single_shot` retry only while a due rotation is pending. Cache state persists a profile/policy draw counter; each due interval hashes that counter into a tier-first weighted draw, then a candidate draw within the tier. Tier weights do not grow with library population, every tier remains reachable, and the current App ID is excluded when alternatives exist. A two-second due tolerance handles timer-boundary jitter. Persisted `changed_at` now arms only the remaining first interval after a rebuild or rotates immediately when overdue; the timer then returns to one ordinary recurring interval. Explicit widget refresh forces one non-repeating cache-backed draw and restarts the configured cadence after source refresh.

## Bars

`tests/test_steam_abandonment_issues.py` proves preference bias plus variety, same-seed repeatability, persisted non-sequential backlog ranks, immediate-repeat exclusion, profile-shared draw-count persistence, two-second due-boundary behavior, policy invalidation, remaining-delay timer replacement after rebuild, forced manual rotation, and a simulated parent-transition collision that resumes through the shared single-shot contract. Selection adds no owned/recent/candidate-achievement request; the narrow post-selection evidence and public-art worker boundaries are recorded in R-42 and R-39.

## Runtime Validation Target

With the shared Steam refresh interval set to 5 minutes, across settings/display rebuilds, several due intervals, and a double-click refresh, require multiple non-sequential games/ranks, no immediate repeat where alternatives exist, no cadence reset to a full interval after rebuild, one diagnostic `[STEAM][ABANDONMENT_ROTATION]` line per committed draw, and a collided expiry that logs deferral then changes through the existing sparse fade without UI-thread/DT pressure.

## Migration Record

This file is the standalone detailed record copied from the original `R-37` entry in `Docs/Historical_Bugs.md`. The monolithic source entry remains unchanged during the copy-first migration and will be replaced by a compact index summary only after the historical-bug set has been migrated and mechanically checked.
