# R-44 — Gmail CUSTOM Resize Payload Overrode Live Text Balance

Date: 2026-07-15  
Status: Resolved

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

## Observed Failure

Gmail's Text Balance ratio worked in authored layouts but appeared inert after the card entered `Custom`, even though changing the ratio should only redistribute sender and subject space inside the existing card.

## Root Cause

Gmail's `gmail_font` CUSTOM size payload captured `sender_subject_ratio` alongside the resize-derived font size. Widget creation correctly read the current ratio from Settings, but saved-layout replay ran afterward and restored the older payload copy. CUSTOM had therefore become a second authority for an internal placement setting rather than owning only the outer rect and resize axis. Legacy payloads could also carry the retired `sender_column_width` value.

## Fix

Gmail CUSTOM capture, scaling, and replay now own only `font_size`. Current `sender_subject_ratio` remains settings-owned and continues to drive the existing reserve-first row-budget painter inside the committed rect. Old payload copies of either ratio field are ignored; the post-payload outer-rect reassertion remains unchanged. No timer, repaint loop, geometry relaxation, migration write, or other widget behavior was added.

## Bars

The Gmail payload test proves resizing changes only font size and leaves a live ratio unchanged even when an old payload contains both obsolete keys. A runtime-shaped custom-layout replay test starts from a stale 35/65 payload and current 68/32 Settings authority, then proves the exact `440 x 196` rect and resize-derived font survive while 68/32 remains active.

## Runtime Validation Target

In a Gmail card with committed Custom geometry, move Text Balance through both extremes and return to 35/65. The internal sender/subject boundary must change while the outer rect, font scale, timestamp/envelope/menu lanes, and Custom position remain unchanged across settings close and restart.

## Validation

The user confirmed the internal balance visibly responds in Custom. The 2026-07-15 `--geo` run then showed post-fix Gmail replay payloads containing only `font_size` at both `810 x 442` and `567 x 352`; each stable replay kept the same local rect through payload application, position update, and final authority. Loading an older layout slot later surfaced its stale `sender_subject_ratio=35` key in input telemetry, but replay ignored it, the existing content-height exception sanitized the persisted payload back to font-only, and the recreated card again completed with identical start/final geometry. No geometry warning, replay mismatch, fallback, or extra refresh path accompanied the change.

## Migration Record

This file is the standalone detailed record copied from the original `R-44` entry in `Docs/Historical_Bugs.md`. The monolithic source entry remains unchanged during the copy-first migration and will be replaced by a compact index summary only after the historical-bug set has been migrated and mechanically checked.
