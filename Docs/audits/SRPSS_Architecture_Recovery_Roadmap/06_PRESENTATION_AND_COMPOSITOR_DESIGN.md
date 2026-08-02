# 06 — Presentation and Compositor Design

## Design objective

Use one compositor surface per display without recreating the donor scheduling failure.

## What must be removed

Do not port or preserve:

- adaptive timer worker waiting for paint;
- dirty/requested/acknowledged frame-generation protocol;
- producer waits for `paintGL`;
- compositor cadence starvation as a normal state;
- compositor-owned visualizer simulation cadence;
- distributed transition terminal transaction;
- widget-shaped visualizer compatibility façade;
- broad dynamic attribute forwarding;
- retained fallback layers that silently switch architecture;
- retry/backoff state for ordinary frame presentation.

## Presentation model

Qt provides paint opportunities. The application maintains a latest scene snapshot.

When state changes:

1. producer/controller updates its immutable state;
2. scene coordinator replaces the latest scene snapshot;
3. GUI thread coalesces an `update()` request if one is not already pending;
4. compositor paints the latest snapshot;
5. if a local animation remains active, compositor schedules another future update through one simple GUI-thread mechanism.

No producer blocks.

## One outstanding update

Keep the useful principle, simplify the implementation.

Possible state:

```text
paint_requested: bool
```

On scene change:

```text
if not paint_requested:
    paint_requested = True
    widget.update()
```

At paint start or end on the GUI thread:

```text
paint_requested = False
```

If state changed during paint, request one more update.

This is coalescing, not acknowledgement. No worker waits for the flag.

## Local animation scheduling

The compositor may need continued frames for transitions or other compositor-local animation.

Use one GUI-thread timer or frame callback with clear rules:

- active only while at least one local animation is active;
- stopped when the scene is static;
- does not advance visualizer simulation;
- does not wait for paint completion;
- does not submit a worker task per frame;
- uses monotonic time;
- records missed intervals but does not “catch up” by emitting bursts of `update()` calls.

## Visualizer presentation

The visualizer controller publishes latest render state independently.

When visible and animated, it may cause scene-change notifications at its logical cadence, but:

- duplicate notifications are coalesced;
- latest state replaces previous state;
- compositor may present fewer states than simulation produces;
- simulation remains correct;
- there is no direct worker-to-widget mutation.

## Scene composition order

Define explicitly, for example:

1. clear/background;
2. base image or transition;
3. visualizer;
4. metadata/text overlays;
5. cursor halo or interaction overlays;
6. diagnostics when enabled.

The order must be display-local and cannot rely on separate widget z-order.

## Display independence

Each display has:

- its own compositor surface;
- viewport;
- scene snapshot;
- local GL resources or leases;
- update coalescing state.

Global controllers may publish shared logical state, but display 0 must not become the implicit owner for overlay visibility or updates.

Tests must intentionally vary:

- primary display;
- display indexes;
- different resolutions;
- visualizer on one or all displays;
- display removal/reconnect.

## Transition design

Transition snapshot:

```text
TransitionSnapshot
- source texture lease
- destination texture lease
- start monotonic timestamp
- duration
- easing identifier/parameters
```

At paint:

```text
progress = clamp((now - start) / duration, 0, 1)
draw(source, destination, easing(progress))
if progress >= 1:
    finalize destination locally
```

Finalization:

- destination becomes base;
- source transition lease is released;
- temporary resources are released;
- transition becomes inactive;
- no worker or pipeline acknowledgement is required.

## Frame pacing metrics

Record:

- scene update publication rate;
- coalesced update count;
- `update()` request rate;
- paint rate;
- paint intervals;
- paint duration;
- latest-scene age at paint;
- number of logical visualizer states skipped;
- transition progress at presentation.

Skipped intermediate render states are acceptable. Long latest-scene age and visible jumps are not.

## Failure behavior

If a frame is late:

- draw current latest state;
- do not replay stale frames;
- do not flood Qt with queued updates;
- do not block producers;
- do not add another scheduler;
- log one aggregated late-frame event.

## Acceptance criteria

- zero paint waits;
- zero compositor cadence starvation state;
- no persistent update queue growth;
- p99 frame interval meets benchmark gate;
- cursor halo remains smooth;
- transition motion does not jump under idle conditions;
- visualizer fidelity tests pass;
- GPU stays meaningfully utilized during GL work without CPU orchestration dominating;
- Settings/Edit lifecycle remains safe.
