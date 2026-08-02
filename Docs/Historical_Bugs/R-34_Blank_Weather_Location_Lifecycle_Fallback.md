# R-34 — Blank Weather Location Entered Lifecycle Error/Fallback And Collapsed Its Card

Date: 2026-07-10  
Status: Resolved

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

## Observed Failure Pattern

With no Weather location, the card was visually squashed and offered no route to configure it. Logs showed lifecycle activation failing, setup falling back to legacy `start()`, and legacy start logging the same missing-location error.

## Root Cause

Blank location was treated as an activation exception. The fallback then called `setText()` on the QLabel-backed overlay despite the real content living in child layouts, bypassing normal card geometry and creating two divergent lifecycle branches.

## Fix

Blank location is now a successful provider-inert state. It renders a minimum-height `Weather location required` / `Open Weather Settings` composition, joins the normal fade, submits no ThreadManager/provider/timer work, and routes only the action-label hit area through centralized input to Weather's `source_layout` bucket.

## Bars

`tests/test_weather_widget.py` proves initialize/activate and legacy start are thread/timer inert, spacing is retained, action hit-testing emits the narrow target, and central navigation primes the Weather section/bucket.

## Runtime Validation Target

Start a compiled run with Weather enabled and location blank; the inert card should be comfortably spaced, its link should open Weather Location settings, and logs must contain neither lifecycle fallback nor missing-location fetch errors.

## Validation

User-observed spacing/navigation behavior was accepted on 2026-07-12; the latest reviewed logs contained no blank-location lifecycle fallback or missing-location fetch error.

## Migration Record

This file is the standalone detailed record copied from the original `R-34` entry in `Docs/Historical_Bugs.md`. The monolithic source entry remains unchanged during the copy-first migration and will be replaced by a compact index summary only after the historical-bug set has been migrated and mechanically checked.
