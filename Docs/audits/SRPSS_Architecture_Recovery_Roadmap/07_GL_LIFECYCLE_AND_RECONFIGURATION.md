# 07 — GL Lifecycle and Reconfiguration

Last reconciled: 2026-08-08

## Current boundary

Full stop–destroy–recreate remains mandatory for Settings and committed CUSTOM Edit.

The core owner-context GL teardown architecture is valuable and retained. The latest installed evidence reopened lifecycle closure through:

- R-56: post-modal calls on an already-deleted `SettingsDialog` C++ object;
- R-53: synchronous full teardown from inside the retiring `CustomLayoutManager` save/action graph, followed by two surviving manager wrappers and fail-closed exit.

These were lifecycle ownership failures even though tracked GL deletion itself reached zero. Both have subsequent production-shaped mechanical repairs; installed Settings and dual-display Edit confirmation remain mandatory.

## Runtime states

Use a small process/runtime state model:

```text
STOPPED
STARTING
RUNNING
STOPPING
FAILED (only when needed)
```

Subsystem-local states are allowed only for real independent lifetimes with documented ownership/transitions. Do not replace clear sequencing with overlapping scheduler, renderer, warmup, registry, or presentation state machines.

## Full stop sequence

The process/runtime coordinator initiates full stop only after the request is owned by the coordinator rather than a retiring session graph.

1. Admit one immutable stop/reload intent; reject stale/duplicate requests.
2. Mark runtime `STOPPING` and invalidate old runtime/publication generation.
3. Prevent new decode/prefetch/visualizer publications for the retiring runtime.
4. Stop GUI timers and recurring producer work.
5. Disconnect/reject producer-to-runtime callbacks and subscriptions.
6. Cancel queued work where possible; do not block unboundedly.
7. Reject late completions by generation and exact manager/owner identity.
8. On the GUI thread, clean display-local widgets/producers and make each compositor context current.
9. Destroy visualizer GL renderer resources.
10. Finalize/cancel transitions and release terminal ownership.
11. Delete textures/FBOs/PBOs/programs/buffers through their sole deletion owners.
12. Flush deterministic owner-context deletion queues.
13. Verify zero live tracked GL ownership for the retiring generation.
14. Call `doneCurrent()` where appropriate.
15. Destroy compositor surfaces/widgets only after child GL ownership is gone.
16. Clear scene/display/cache sidecars and Qt owners according to their contracts.
17. Arm/seal the runtime-destruction barrier and wait asynchronously for all watched ownership to reach zero.
18. Admit replacement construction only after barrier completion.
19. On failure/timeout, retain diagnostic ownership and exit/fail closed; never fake zero.

Do not use nested `processEvents()`, production `gc.collect()`, retry sleeps, longer timeout, ignored owners, or handle clearing after failed deletion.

## Destruction barrier contract

The barrier observes:

- retiring QObjects;
- weak-observed Python roots;
- generation-owned resources;
- tasks/timers/animations/subscriptions/callbacks;
- visualizer and display owners.

It proves release. It does not force release.

Replacement construction while any destruction barrier is pending is forbidden.

## Start/replacement sequence

1. Allocate a new runtime generation.
2. Discover requested displays and complete participating display registration.
3. Create exact `DisplayManager`/display ownership on the GUI thread.
4. Create compositor surfaces/contexts and minimal resources.
5. Create/rebind display-local resource owners for the new context generation.
6. Create shared visualizer source/controller without requiring GL.
7. Create display renderer resources on owner contexts.
8. Build current-generation scene/widget state.
9. Connect producers with runtime generation and exact-manager identity.
10. Start logical timers/workers.
11. Keep displays hidden until fresh current-generation authoritative first frames arrive.
12. Reveal through the sole coordinated reveal authority.
13. Mark runtime `RUNNING`.

Delayed display/show callbacks validate runtime generation, exact manager, and display membership.

## Settings workflow and R-56

Correct sequence:

1. fully stop and destroy the old display runtime;
2. construct the Settings dialog/animation graph;
3. create and populate its destruction barrier while the QObjects are valid;
4. set `WA_DeleteOnClose` as intended;
5. execute the modal dialog;
6. after `exec()` returns, validate the underlying C++ wrapper before any QObject method call;
7. do not call `findChildren()`, `close()`, or `deleteLater()` on an invalid/deleted dialog wrapper;
8. clean/cancel the separately owned animation/timer/generation callbacks;
9. seal the pre-registered dialog barrier;
10. construct exactly one replacement runtime only after dialog ownership reaches zero.

`isinstance(dialog, QObject)` is not a liveness test. Use a Shiboken-validity or equivalent explicit contract.

Do not remove `WA_DeleteOnClose` or bypass the dialog barrier merely to avoid the error.

## CUSTOM/Edit workflow and R-53

The full reinit and graph-based placement/replay architecture stay unchanged.

### Stage A — persist and retire temporary Edit ownership

While displays/managers are valid:

1. calculate and persist the complete CUSTOM graph/scene;
2. retire each shell idempotently: release pointer grabs, disconnect manager-bound signals, clear resolver/applier closures, remove temporary event filters, clear snapshots/guides;
3. destroy grid overlays and manager-owned temporary state;
4. empty class-level active-manager participation;
5. uninstall the global key filter;
6. neutralize restack/menu/deferred manager state;
7. clear edit-active and reload-pending flags;
8. discard deferred old-runtime image state for committed reload actions;
9. return from all save/reset/slot/action/key-filter frames.

The session manager does not call `engine.stop()` synchronously.

### Stage B — engine-owned queued admission

On a later GUI turn:

1. receive an immutable intent containing request kind, expected runtime generation, exact manager identity, and optional settings/scene revision;
2. capture no manager, display, shell, widget, pixmap, shell state, or bound manager method;
3. coalesce duplicates and reject stale identity;
4. execute the normal full stop sequence;
5. wait for zero retiring ownership;
6. construct one complete replacement runtime;
7. replay the persisted graph-based layout;
8. reveal only from fresh authoritative state.

The preserved installed logs prove the former synchronous re-entry above 99% confidence: manager cleanup cleared `_display`, then the still-running save `finally` touched that cleaned manager. The implemented repair now performs explicit callback/session retirement and later immutable engine admission; production-shaped zero-owner tests pass, while installed dual-display confirmation remains open.

## GL thread-affinity and deletion

Development checks include:

- current versus expected thread;
- current versus expected context/share group;
- runtime/context generation;
- resource identity, owner, bytes, and deletion state.

A failed delete retains ownership and blocks successful teardown. Do not transfer the same numeric handle into two deletion-owner records.

## Worker cancellation/publication

Work carries the necessary runtime/request/source identity. Completions return immutable results. GUI/runtime owners reject stale results before touching widgets or GL.

Cancellation is bounded. No worker is allowed to publish into a destroyed or replaced runtime merely because its task completed successfully.

## First-frame separation

Destruction completion authorizes replacement construction. It does not authorize reveal.

The replacement remains hidden until its own current runtime, exact manager/display, visualizer engine generation, and activation identity produce authoritative state. Old cached state, GL initialization, timer ticks, stale callbacks, or prior mode state cannot satisfy readiness.

## Required tests

### Settings

- real `WA_DeleteOnClose` modal shape;
- dialog barrier populated before execution;
- no invalid-wrapper touch after execution;
- animation/timer ownership reaches zero;
- exactly one replacement;
- stale/cancel paths do not replace.

### Edit

- two-display real relay shape;
- teardown begins only on a later GUI turn after originating frames return;
- manager/shell weakrefs die without `gc.collect()` before continuation;
- shell callback retirement is idempotent;
- queued closure contains no retiring owner;
- stale/duplicate intent rejected;
- committed reload discards deferred image; cancel restores it;
- graph placement/replay remains correct;
- exactly one replacement after zero ownership.

### Installed loops

After focused fixes, run alternating Settings/Edit under transitions, image work, all supported visualizer modes, mode switches, playing/paused, dual/selected display, normal and Media Center.

## Pass criteria

- zero invalid Qt-wrapper touches;
- zero cross-thread/context ownership errors;
- zero callback/publication into retired runtime;
- zero retired Python/QObject/resource/task/subscription owners;
- no cumulative timer/worker/handle/thread growth;
- tracked GL bytes reach zero before surface destruction;
- full graph-based layout replays correctly;
- replacement reveals from current authoritative state only;
- equivalent-state RSS/private commit/VRAM plateau;
- full lifecycle does not rely on GC, trimming, retries, or hidden fallback.

## Deferred optimization

Partial reinit remains prohibited until release-quality full-rebuild stability and a separate approved design prove retained ownership, context validity, callback isolation, resource savings, and a product benefit worth the additional states.
