# R-39 — Abandonment Automatic Rotation Lost Uncached Selected Artwork

Date: 2026-07-14  
Status: Resolved in code; runtime validation pending

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [x] AWAITING VALIDATION
- [ ] SOLVED

## Observed Failure Pattern

Automatic Abandonment rotation changed the game and text but twice committed no artwork; forced double-click refreshes changed games and restored artwork normally.

## Log And Cache Evidence

Interval draws committed successfully and changed selection, and backlog ranks formed a non-sequential sequence rather than a linear walk. The follow-up failure near the end of the reviewed run allowed asset network work, then logged no artwork because the selected app's requested portrait `library_600x900.jpg` returned HTTP 404 while its allowlisted wide `header.jpg` variant returned valid JPEG data. The 404 had been collapsed into generic network failure, so no valid alternate was considered.

## Root Causes

The original `_request_cache_only_rotation()` path prepared a newly selected game with `allow_asset_network=False`, unlike manual/provider refresh. After that boundary was corrected, selected-art hydration still requested only the configured shape and treated a definitive 404 like a transient network error. A game lacking Steam's portrait capsule could therefore render blank even though its wide artwork existed.

## Fix

Semantic selection still reads only owned/recent/profile/achievement cache state. When automatic updates are allowed, the same existing IO task resolves cached requested/fallback shapes first and hydrates only the selected app before atomically committing the game/title/art fade. A definitive requested-shape 404 or invalid image permits one alternate allowlisted shape; ordinary timeout/network failures do not trigger a second request. HTTP 404 is classified as `NOT_FOUND`, `--noupdates` retains strict automatic artwork-cache-only behavior, and diagnostics include requested/resolved shapes and fallback outcomes without credentials or account identity. R-42 later permits one similarly bounded selected-app achievement-evidence hydration for enabled shelves without changing this no-candidate-work rule. The redundant discarded Abandonment layout pass remains removed from paint.

## Bars

`tests/test_steam_profile_assets_events.py` proves HTTP 404 classification and bounded shape order. `tests/test_steam_abandonment_issues.py` proves non-sequential draws, ordinary/`--noupdates` asset-network decisions, requested-shape hydration, 404-to-wide fallback into worker-prepared cover art, and no fallback fanout after a transient failure. The full Steam bar passes.

## Runtime Validation Target

On the next long normal and MC runs, require `ABANDONMENT_ROTATION` ranks to remain non-sequential, ordinary misses to log `outcome=hydrated`, portrait-missing/wide-valid apps to log `outcome=fallback_hydrated:wide requested_shape=portrait resolved_shape=wide` before a complete sparse fade, `--noupdates` misses to log `cache_miss_network_disabled`, and no owned/recent/candidate provider request, duplicate selected-evidence request, UI-thread stall, paint burst, or new visualizer DT spike attributable to the low-frequency worker task.

## Migration Record

This file is the standalone detailed record copied from the original `R-39` entry in `Docs/Historical_Bugs.md`. The monolithic source entry remains unchanged during the copy-first migration and will be replaced by a compact index summary only after the historical-bug set has been migrated and mechanically checked.
