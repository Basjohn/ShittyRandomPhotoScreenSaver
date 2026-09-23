# R-89 — Recurring Timer Released Its Owner Inside Its Own Deferred Deletion

Date: 2026-09-23  
Status: SOLVED — fix `ae26d809`, automated bar green

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

## Observed Failure

A native abort while running several test files in one process (the "cross-file abort" that forced the
runtime audit's gates to run per file). It surfaced in the next nested event loop (`QDialog.exec`) after an
unrelated retirement, never in the file that caused it.

## Root Cause

`ThreadManager.schedule_recurring` built a `_GapTrackedTimer` whose Python callback held its Qt owner
strongly. Retirements (`OverlayTimerHandle.stop()` for Weather/Media/Gmail/Steam services, among others)
called `deleteLater()` on that timer. When the callback held the owner's **last** reference, the deferred
delete released the owner **inside the timer's own C++ destructor**; the owner's destructor then deleted the
half-destroyed timer again, and the next nested event loop aborted natively.

## Why It Was Hard To Find

The crash fired far from its cause (a later dialog in a later test file), only when reference counts happened
to make the callback the last holder, and looked like generic cross-file Qt pollution. It was bisected by file
pairs to the timer retirement path.

## Fix

The recurring timer keeps its callback in a releasable payload; `_GapTrackedTimer.deleteLater()` stops the
timer, disconnects it and drops the payload **before** queueing deletion (as `single_shot` already did), so the
owner is released in ordinary Python context.

## Regression Coverage

`tests/test_thread_manager.py::test_retiring_a_recurring_timer_releases_its_owner_before_deferred_deletion`.

## Guardrail

Recorded in `Docs/Guardrails.md` (release callbacks before deferred deletion): a QObject whose Python callback
may hold its owner's last reference must release that callback before `deleteLater()`. Never let owner
destruction run inside a child's C++ destructor.
