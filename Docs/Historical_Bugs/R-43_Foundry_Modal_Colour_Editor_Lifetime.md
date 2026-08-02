# R-43 — Defaults Foundry Modal Colour Picker Destroyed Its Delegate Editor

Date: 2026-07-15  
Status: Resolved

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

## Observed Failure

Foundry colour cells opened the styled alpha picker, but accepting a colour left the visible value and saved canonical default unchanged. The existing direct-delegate test passed despite the complete runtime failure.

## Root Cause

The swatch is a transient `QStyledItemDelegate` editor. Opening the modal picker transfers focus away from that editor; the delegate's default `FocusOut` handling committed the old value and destroyed the swatch before `get_color()` returned. The returning callback could therefore neither store nor emit the selected `QColor`, and could raise `Internal C++ object (ColorSwatchButton) already deleted`. The previous test constructed the editor manually and returned a colour synchronously, bypassing the modal focus transfer and real `QTreeWidget` lifecycle.

## Fix

A Foundry-local swatch marks only the interval in which its modal picker is active. The Foundry delegate suppresses its normal close-on-focus-out behavior only for that marked editor, then the existing synchronous `color_changed -> commitData -> model` path runs after acceptance. Cancel leaves the model untouched. The shared application swatch, ordinary delegates, focus routing, and save authority are unchanged; no timer, polling, repaint, persistent editor population, or UI retry was added.

## Bars

`tests/test_default_settings_editor.py` now opens the actual tree editor, transfers focus through a modal dialog, proves cancellation retains the original RGBA, proves acceptance keeps the swatch alive and updates both tree/model authority, then saves and reloads a temporary canonical defaults source to prove RGBA persistence. The full Foundry suite remains green.

## Runtime Validation Target

In Defaults Foundry, edit Abandonment Accent (including alpha), accept the picker, confirm the cell updates immediately, then Save and Regenerate and reopen the Foundry to confirm the same RGBA. An installed Normal/MC profile must remain unchanged.

## Validation

The user confirmed the repaired swatch flow and successfully saved a new Abandonment accent. The authoritative source plus Normal/MC generated JSON/SST artifacts all contain the same replacement RGBA value, with no unrelated defaults drift.

## Migration Record

This file is the standalone detailed record copied from the original `R-43` entry in `Docs/Historical_Bugs.md`. The monolithic source entry remains unchanged during the copy-first migration and will be replaced by a compact index summary only after the historical-bug set has been migrated and mechanically checked.
