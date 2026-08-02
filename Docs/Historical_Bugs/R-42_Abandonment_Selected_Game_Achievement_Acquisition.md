# R-42 — Abandonment Achievement Shelves Had No Selected-Game Acquisition Path

Date: 2026-07-15  
Status: Resolved

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

## Observed Failure

`ACHIEVEMENTS` and `LAST UNLOCK` remained absent even while both default-on shelves were enabled. Privacy-safe shelf diagnostics repeatedly reported both as requested but unavailable with `achievements:missing,last_unlock:missing`.

## Root Cause

Abandonment probed only existing Achievement Pulse cache paths. Achievement Pulse acquires per-app records for at most five recent games, while Abandonment deliberately selects old inactive games; selected backlog games therefore had no realistic producer for their exact achievement cache file. The renderer and evidence guards were correct, but the source contract made their success state unreachable for most selections.

## Fix

Cache-only ranking and weighted selection remain unchanged. After one identity is committed, Abandonment's existing startup/refresh/rotation worker may hydrate exactly that app's `GetPlayerAchievements` record only when `ACHIEVEMENTS` or `LAST UNLOCK` is enabled. It reuses Achievement Pulse's canonical cache key, the process-shared source lock, app-scoped request/backoff identity, and a 24-hour automatic freshness window. The result enriches the already-selected immutable snapshot and cannot rerank, replace, or fan out across candidates. `--noupdates` suppresses automatic hydration; explicit manual refresh retains its deliberate force behavior.

## Pressure And Security Boundary

No timer, thread, UI retry, paint work, cache enumeration, schema request, or library-wide achievement sweep was added. The new sidecar record contains only selected app ID, cache/network outcome, source status, and loaded/missing state; it does not log titles, achievement names, counts, credentials, or raw payloads.

## Bars

`tests/test_steam_abandonment_issues.py` proves default/explicit shelf demand, one provider-shaped selected-app request, exact cache persistence, count/latest-unlock enrichment, 24-hour cache reuse, stable selected identity, automatic-rotation worker wiring, and no hydration when automatic updates are disabled. Runtime validation must observe one `hydrated` record for a supported selected game, subsequent `cache_hit`, visible shelves, no same-job identity change, and no DT/repaint spike.

## Validation

The 2026-07-15 run selected two different apps. Each initially reported the requested achievement shelves unavailable, performed one exact selected-app achievement cache write, then logged `outcome=hydrated status=success evidence=loaded` and rendered `playtime,achievements,last_unlock,last_played`; artwork hydration also completed and widget paint cost stayed inexpensive. The user confirmed the resulting shelf data appeared correct.

## Migration Record

This file is the standalone detailed record copied from the original `R-42` entry in `Docs/Historical_Bugs.md`. The monolithic source entry remains unchanged during the copy-first migration and will be replaced by a compact index summary only after the historical-bug set has been migrated and mechanically checked.
