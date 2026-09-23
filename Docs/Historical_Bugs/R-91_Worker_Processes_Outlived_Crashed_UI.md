# R-91 — Worker Processes Outlived A Crashed UI Process

Date: 2026-09-23  
Status: FIXED IN CODE — `e42fb948`; installed End-task check open (`Current_Plan.md`)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [x] AWAITING VALIDATION
- [ ] SOLVED

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

## Guardrail

Child processes must detect parent death themselves; `daemon=True` is not a crash-safe lifetime bound.
