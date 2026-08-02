# R-45 — Clock CUSTOM Payload Overrode Settings Mode To Preserve Geometry

Date: 2026-07-15  
Status: Resolved

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

## Observed Failure

Clock CUSTOM entries captured and replayed `display_mode`. This preserved the digital/analogue-shaped outer rect during restart, but it also made the saved layout a second behavior authority: changing `Use Analogue Clock` in Settings could be reverted by the older CUSTOM payload after the factory had already applied the current setting.

## Root Cause

An earlier hot-swap repair correctly established that digital and analogue clocks need different CUSTOM outer shapes, but represented that geometry dependency by storing the behavior setting itself. Ordinary replay then called `set_display_mode()` before applying the resize-derived font, conflating “which shape this rect was authored for” with “which mode the user currently selected.”

## Fix

`clock_font` payloads now contain resize-derived `font_size` plus `geometry_variant`, an outer-shape marker that is never applied as widget behavior. Replay keeps the factory/Settings baseline authoritative. If the saved shape marker differs, the manager rebuilds a centered, clamped target-mode rect using the saved CUSTOM font scale, then persists the canonical marker. Legacy `display_mode` payload keys migrate through that one geometry comparison and are removed. The R-48 follow-up preserves double-click as an explicit screen-signature behavior override while the rebuilt CUSTOM payload still writes only `geometry_variant` and font size. No timer, retry, repaint, thread, or broad widget refresh was added.

## Bars

The full CUSTOM manager suite (`94 passed`) proves direct payload application cannot change mode, legacy digital-to-analogue restart rebuilds the exact target rect with base and CUSTOM font sizes intentionally different, and canonical persistence strips the legacy key. The Clock suite (`19 passed`) preserves both double-click rect transformations and setting writes; descriptor/layout integration adds `16 passed`.

## Runtime Validation Target

In normal and MC builds, place Clock in CUSTOM at a clearly non-default scale. Switch digital/analogue from Settings and by double-click in both directions, restart each time, and require the current setting, centered mode-appropriate rect, position, display route, and scale to survive. `--geo` must show `font_size` plus `geometry_variant`, never `display_mode`, with no repeated migration write, fallback, paint burst, or DT spike.

## Validation

The user validated Clock in all requested normal/mixed-display scenarios, including the mode/geometry combinations that exercised this payload boundary. R-48's per-display override remained intact, so this entry is closed rather than retained as duplicate plan work.

## Migration Record

This file is the standalone detailed record copied from the original `R-45` entry in `Docs/Historical_Bugs.md`. The monolithic source entry remains unchanged during the copy-first migration and will be replaced by a compact index summary only after the historical-bug set has been migrated and mechanically checked.
