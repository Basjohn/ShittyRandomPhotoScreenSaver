# 07 — GL Lifecycle and Reconfiguration

## Problem statement

The donor branch attempts partial teardown/reinitialization but still reaches the same class of failure:

```text
Cannot make QOpenGLContext current in a different thread
```

The baseline evidence does not reproduce this after Settings/Edit.

The recovery must prioritize explicit ownership over fast reconfiguration.

## Lifecycle states

Use a small runtime state machine:

```text
STOPPED
STARTING
RUNNING
STOPPING
```

Optional:

```text
FAILED
```

Do not add separate overlapping states for compositor, visualizer, renderer, scheduler, warmup, and registry unless each has a real independent lifetime and documented transitions.

## Full stop sequence

All steps are initiated by the runtime coordinator.

1. Mark runtime `STOPPING`.
2. Prevent new decode/prefetch/visualizer publications for the old runtime generation.
3. Stop GUI timers.
4. Disconnect producer-to-scene callbacks.
5. Cancel queued worker requests where possible.
6. Wait bounded time for in-flight coarse worker operations.
7. Reject any late worker completion by runtime generation.
8. On GUI thread, make each compositor context current.
9. Destroy visualizer GL renderer resources.
10. Destroy transition GL resources.
11. Release texture/FBO/PBO leases.
12. Flush deterministic deletion queues.
13. Destroy compositor-owned GL programs and buffers.
14. call `doneCurrent()` where appropriate.
15. Destroy compositor widgets/surfaces.
16. Clear CPU-side scene snapshots and Qt objects.
17. Assert zero live GL resources for the old generation.
18. Mark runtime `STOPPED`.

## Start sequence

1. Allocate a new runtime generation.
2. Discover displays and geometry.
3. Create compositor surfaces on GUI thread.
4. Initialize GL contexts and capability state.
5. Create minimal compositor resources.
6. Create/rebind GPU resource store for current context/share groups.
7. Create visualizer model/controller without requiring GL.
8. Create visualizer renderer resources on GUI thread.
9. Build initial scene snapshots.
10. Connect producers.
11. Start logical timers/workers.
12. Mark runtime `RUNNING`.

## Settings workflow

1. Perform full stop.
2. Open Settings dialog.
3. Validate and persist settings.
4. Start a completely new runtime.
5. If start fails, remain in a known stopped/failed state and report clearly.

The old GL runtime must not remain half-alive behind the dialog.

## Edit workflow

Edit may have separate user-facing behavior, but it follows the same ownership principles.

Do not retain an old context or renderer merely to reduce reentry cost until full lifecycle correctness is proven.

## Thread-affinity assertions

Development builds must assert before every GL mutation:

- current thread ID;
- expected GUI/render thread ID;
- current `QOpenGLContext`;
- expected context or share group;
- resource context generation;
- runtime generation;
- resource not already destroyed.

Assertions should include resource identity and owner.

## Deferred deletion

If a resource becomes unreferenced outside a current GL scope:

- enqueue metadata for deletion;
- schedule a GUI-thread deletion pass;
- make the correct context current;
- delete;
- update byte accounting;
- record deletion reason.

Do not rely on object destructors or garbage collection.

## Worker cancellation

Workers receive:

- runtime generation;
- request generation;
- cancellation token.

Workers return immutable results.

The GUI thread validates generations before applying.

A stale result is discarded without touching GL or widgets.

## Reconfiguration tests

Required automated/manual loop scenarios:

- open/close Settings 50 times;
- enter/exit Edit 50 times;
- alternate Settings/Edit 50 times;
- do so during active transition;
- do so during active Spectrum;
- do so during active Bubble;
- do so while image decode/prefetch is in flight;
- do so after display resolution change;
- do so after sleep/wake where supported.

For each cycle record:

- context IDs/generations;
- live GL resource count and bytes;
- worker count;
- timer count;
- callbacks connected;
- RSS;
- VRAM;
- errors/warnings.

## Pass criteria

- zero cross-thread context operations;
- zero callback into destroyed runtime;
- zero retained resource from prior generation;
- resource bytes return to expected plateau;
- no cumulative timer/worker growth;
- visualizer resumes with correct behavior;
- display overlays remain attached to correct display.

## Deferred optimization

Partial reinit may be reconsidered only through a separate architecture proposal after release-quality lifecycle stability.

The proposal must prove:

- which resources are safe to retain;
- who owns them;
- how contexts remain valid;
- how callbacks and workers are isolated;
- why the latency benefit is worth the additional states.

Until then, full rebuild is the required behavior.
