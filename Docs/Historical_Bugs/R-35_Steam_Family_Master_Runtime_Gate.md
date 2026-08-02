# R-35 — Steam Family Master Hid Settings But Did Not Gate Runtime Cards

Date: 2026-07-10  
Status: Resolved

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

## Observed Failure Pattern

`Enable Steam Widget` could be off while a card such as Achievement Pulse still appeared. The settings shell disappeared, but card-level `enabled` remained sufficient to create the overlay.

## Root Cause

The top-level Steam flag was documented and implemented as UI-only. Descriptor setup and the Steam factory checked only environment/card gates, so runtime creation and fade-expected truth ignored the family flag.

## Fix

Steam factory descriptors now declare a base `steam.enabled` gate. Setup applies it before expected-overlay registration or factory creation, and the factory repeats the check as a defensive direct-call boundary. The UI hides all subordinate settings and now groups card controls into Layout, Appearance, and Content buckets. Card-level choices remain persisted while the family is off.

## Bars

`tests/test_steam_phase3_settings_descriptors.py` proves descriptor metadata, hidden subordinate controls, retained card payloads, no created card, no expected overlay, and direct-factory refusal while the master is disabled.

## Runtime Validation Target

In a compiled normal run, turning the family off must remove every Steam card on all displays; reopening Steam settings should show only the master. Re-enabling must restore the previously selected card choices without a fade stall.

## Validation

User-observed runtime behavior was accepted on 2026-07-12; the latest reviewed multi-display logs contained no Steam master/fade-expected regression or compositor loss.

## Migration Record

This file is the standalone detailed record copied from the original `R-35` entry in `Docs/Historical_Bugs.md`. The monolithic source entry remains unchanged during the copy-first migration and will be replaced by a compact index summary only after the historical-bug set has been migrated and mechanically checked.
