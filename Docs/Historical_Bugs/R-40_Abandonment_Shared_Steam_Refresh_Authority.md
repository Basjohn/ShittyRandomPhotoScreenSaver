# R-40 — Abandonment Ignored The Shared Steam Refresh Interval

Date: 2026-07-14  
Status: Resolved in code; runtime validation pending

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [x] AWAITING VALIDATION
- [ ] SOLVED

## Observed Failure Pattern

The active MC profile's Steam refresh interval was 5 minutes, but Abandonment armed a 15-minute timer and reported roughly 15 minutes of remaining duration. Automatic game changes therefore occurred around three times later than the setting promised.

## Log And Settings Evidence

The reviewed MC run constructed a 900,000 ms Abandonment timer while `snapshot.widgets.steam.refresh_minutes` was `5`. A separate legacy `snapshot.widgets.abandonment_issues.rotation_interval_minutes` value was `15`; Normal likewise carried a separate 30-minute card value while its shared Steam interval was 10. Treating those card values as valid made two visible settings contracts compete.

## Root Cause

Abandonment introduced a private user-facing rotation setting and passed it through Settings, defaults, descriptors, the factory, cache remaining-duration math, and the widget timer independently of the family refresh interval. The generic `Refresh Window` label did not make the conflict clear, but clearer labels would not solve the underlying duplicate authority.

## Fix

`widgets.steam.refresh_minutes` is now the sole automatic-change cadence. The per-card control/default/descriptor/factory argument was removed; card save drops a legacy `rotation_interval_minutes` key; installed Normal/MC profiles no longer retain it; and the cache API now receives the shared refresh interval explicitly. At closure, MC used 5 minutes and Normal used 10; the later Foundry-authoritative canonical default is 6 minutes for both profiles. Rebuild/remaining-duration math evaluates persisted `changed_at` against the current shared value, so shortening an interval rotates when due rather than honoring stale duration. Cadence diagnostics name `widgets.steam.refresh_minutes` as authority.

## Bars

Settings/default tests prove no second control, emitted default, or duplicate widget cadence field exists; a conflicting legacy card value of 45 is ignored; UI save retains shared 5 and removes the legacy key; direct and descriptor-driven factories construct `_refresh_minutes` as 5; stale 15-minute state reports 60 seconds remaining after four minutes under shared 5 and advances at five; and the widget recurring timer is exactly 300,000 ms. Defaults JSON/SST artifacts were regenerated without touching unrelated installed settings.

## Runtime Validation Target

In the next MC run, require `[STEAM][ABANDONMENT_CADENCE] shared_refresh_minutes=5 rotation_minutes=5 authority=widgets.steam.refresh_minutes`, a 300,000 ms recurring timer, and automatic non-repeating draws at that cadence except for a visible bounded parent-transition deferral. No 15/30-minute card cadence may reappear, and cadence changes must not add provider, timer, paint, or UI-thread pressure.

## Migration Record

This file is the standalone detailed record copied from the original `R-40` entry in `Docs/Historical_Bugs.md`. The monolithic source entry remains unchanged during the copy-first migration and will be replaced by a compact index summary only after the historical-bug set has been migrated and mechanically checked.
