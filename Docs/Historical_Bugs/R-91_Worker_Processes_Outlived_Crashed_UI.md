# R-91 — Worker Processes Outlived A Crashed UI Process

Date: 2026-09-23  
Status: SOLVED — `e42fb948`; validated on a frozen Nuitka build 2026-09-24

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

## Observed Failure

Nineteen orphaned worker processes had accumulated from crashing test runs, each polling its request queue
every 100 ms indefinitely. Found while gating the runtime audit.

## Root Cause

`multiprocessing` `daemon=True` only reaps children from the parent's normal `atexit` path. After a native
crash or forced termination the ImageWorker/RSS workers never received SHUTDOWN and never noticed the parent
was gone.

## Fix

`BaseWorker` checks `multiprocessing.parent_process().is_alive()` (a zero-timeout wait on the parent handle)
on each empty poll and exits cleanly.

## Regression Coverage

`tests/test_worker_parent_death.py` — an intermediate parent `os._exit()`s; the real worker process must
disappear.

## Validation

2026-09-24, frozen Nuitka build of the fix: a parent that owned a live worker died through `os._exit(3)` (no `atexit`, no multiprocessing finalizers) and the worker exited on its own 0.20 s later.

## Guardrail

Child processes must detect parent death themselves; `daemon=True` is not a crash-safe lifetime bound.
