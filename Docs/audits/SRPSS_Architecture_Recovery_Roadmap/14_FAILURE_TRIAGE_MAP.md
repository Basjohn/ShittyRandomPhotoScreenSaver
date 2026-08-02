# 14 — Failure Triage Map

Use this map to identify architectural seams. It is not a list of symptom patches.

## Visualizer becomes flat or less reactive

Investigate:

- simulation cadence changed;
- elapsed time derived from paint timing;
- normalization/smoothing changed;
- beat impulses dropped before simulation;
- render-state coalescing occurring before logical integration;
- state copied through compatibility façade incorrectly;
- mode state reset during publication.

Do not:

- increase gain blindly;
- reduce damping blindly;
- add a “reactivity multiplier” to compensate for timing loss.

## Visualizer has microgaps under low load

Investigate:

- producer waits for paint;
- GUI event-loop stalls;
- tiny thread-pool task queueing;
- excessive logging;
- scene update notification storm;
- repeated image/upload work on main thread;
- GIL contention.

Do not add another timer or retry.

## High average FPS but visible jumps

Investigate:

- p99/max interval;
- burst delivery;
- transition based on wall time while paints stall;
- latest-scene age;
- queued updates;
- frame-count metrics counting bursts.

Average FPS is not the acceptance metric.

## Cursor halo or unrelated UI becomes choppy

Investigate:

- main-thread event-loop pressure;
- synchronous image/GL work;
- logging/formatting;
- callback cascades;
- Python GIL saturation;
- paint duration.

This points above a single visualizer mode.

## Overlay stuck on display 0

Investigate:

- display-global singleton state;
- primary-display assumptions;
- update requests routed only to first compositor;
- shared visual state containing display-local geometry;
- z-order compatibility path.

Fix ownership, not display-index conditionals.

## `QOpenGLContext` different-thread error

Investigate:

- worker calling context methods;
- deferred cleanup callback on wrong thread;
- retained renderer/FBO after widget destruction;
- partial reinit;
- context generation mismatch;
- QObject moved or deleted on wrong thread;
- shutdown order.

Do not suppress warning or retry `makeCurrent()` elsewhere.

## RAM grows with image changes

Investigate:

- decoded images retained;
- transform variants;
- upload bytes;
- QPixmap cache;
- futures/callback closures;
- prefetch queue;
- stale scene snapshots;
- log buffers.

Require owner and byte count.

## VRAM grows with image changes

Investigate:

- old textures not deleted;
- leases not released;
- transition source retained;
- resized FBOs retained;
- per-display duplicate textures;
- context deletion queue not flushed;
- registry entry outliving actual use.

Do not rely solely on driver usage; compare tracked bytes.

## CPU pegs one core

Investigate:

- high-frequency Python loops;
- 90–100 small tasks/sec;
- callback overhead;
- duplicate per-display simulation;
- full-buffer copies/hashes;
- logging;
- Qt event-loop work;
- busy polling.

Do not add more Python threads before profiling.

## Settings/Edit memory increases each cycle

Investigate:

- old runtime callbacks;
- timers/workers not stopped;
- GL resource generation still live;
- cache not cleared or shared incorrectly;
- widget retained by closure/signal;
- partial reconstruction.

Full teardown is the reference behavior.

## Transition freezes or final frame sticks

Investigate:

- terminal transaction;
- paint acknowledgement;
- source/destination lease ownership;
- local completion logic;
- scene snapshot publication.

Prefer local transition finalization.

## Fix requires many new flags

Stop.

Re-evaluate ownership and state boundaries. A new flag may be valid, but repeated flags indicate architecture failure.
