# R-92 — Random Transition Rotation Overwrote The User's Authored Direction

Date: 2026-09-22  
Status: FIXED IN CODE — `e3c6ce82` (runtime audit TX-02); physical check open (`Current_Plan.md`)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [x] AWAITING VALIDATION
- [ ] SOLVED

## Observed Failure

With Random transitions on, the user's authored `transitions.slide.direction` / `transitions.wipe.direction`
silently changed to whatever the last random pick was. Each rotation also cost 2–6 `settings.set()` calls
(each deep-copying the store and fanning out `settings_changed`) plus a `save()`.

## Root Cause

The engine used persisted Settings as its channel to `DisplayManager` for the random pick, anti-repeat state and
per-transition direction — writing scratch values into the same keys the user authors.

## Why It Was Hard To Find

It looked like the user changing their own setting; nothing logged a write, and the Settings UI showed a valid
value.

## Fix

The engine keeps `RandomTransitionHistory` (current pick, anti-repeat choice, per-transition direction) in
memory and hands a `RandomTransitionSelection` to `DisplayManager`; resolution takes it as input. Random still
randomizes direction (operator 2026-09-23); nothing is written to Settings.

## Guardrail

Persisted Settings are user-authored state, never inter-component scratch space or IPC.
