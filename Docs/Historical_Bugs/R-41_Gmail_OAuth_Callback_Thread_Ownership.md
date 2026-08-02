# R-41 — Gmail OAuth Callback Server Escaped ThreadManager Lifecycle Ownership

Date: 2026-07-14  
Status: Resolved

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

## Observed Risk

Gmail already submitted token exchange through `ThreadManager`, but its loopback `HTTPServer.serve_forever()` ran on a raw daemon `threading.Thread`. Browser cancellation, callback timeout, settings destruction, and application shutdown therefore had split ownership over the listener, task, and port.

## Root Cause

The callback listener was treated as incidental HTTP plumbing rather than bounded asynchronous business work. It had no generation identity, no manager task id, and no single close-once lifecycle context shared by success and cancellation paths.

## Fix

Each authorization attempt now captures state, PKCE verifier, redirect URI, generation, task id, stop/finished events, and close-once socket ownership in one context. A bounded `handle_request()` loop runs on a `ThreadManager` IO worker; success submits token exchange with the captured values, while browser rejection, malformed callback, timeout, explicit cancellation, credential clearing, settings-owner destruction, and application teardown converge on the same release path. Qt completion signals remain marshalled to the UI thread, and no UI polling, repaint loop, or rescue timer was added.

## Bars

`tests/test_gmail_oauth.py` uses a real helper manager and proves off-UI exchange plus success, user-cancel, timeout, settings-owner, and application-shutdown cleanup with no active task or listener left behind. `tests/unit/test_policy_compliance.py` rejects a return to raw production thread creation.

## Security And Behavior Boundary

PKCE, callback-state validation, browser handoff, token exchange, and DPAPI credential behavior are unchanged; lifecycle ownership was repaired without widening token/log/export exposure.

## Migration Record

This file is the standalone detailed record copied from the original `R-41` entry in `Docs/Historical_Bugs.md`. The monolithic source entry remains unchanged during the copy-first migration and will be replaced by a compact index summary only after the historical-bug set has been migrated and mechanically checked.
