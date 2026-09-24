# Transition Change Checklist

Quick transition presentation is landed. Use this for future transition changes.

## Canonical flow

```text
canonical transition registry/settings
-> activation + manual/random admission
-> resolved immutable request
-> TransitionRequest / TransitionRun
-> lazy Quick implementation
-> display QSGRenderNode
```

No new transition may depend on `GLCompositorWidget`, QWidget pixels or a compatibility presenter.

## Retired transition presentation

All canonical transitions have Quick implementations. The old `transition_factory`/GL-compositor pixel stack and its presentation helpers are retired and absent from current source. They are not visual-reference authority and must not be reconstructed to satisfy stale tests or old documentation. Historical failure mechanisms belong in `Docs/Historical_Bugs/`.

## Preserve

- canonical transition ids/settings;
- application activation semantics;
- manual vs Random-pool semantics;
- deterministic invalid-state recovery;
- `TransitionRequest` / `TransitionRun` monotonic/exactly-once behavior;
- authored effect math/shaders/parameters used by Quick;
- exact endpoints;
- GL state/resource hygiene.

## Activation

Activated/deactivated is distinct from:

- manual selection;
- Random pool membership.

Effective Random candidates:

```text
activated ∩ saved pool membership ∩ runnable/hardware
```

Do not execute a deactivated Crossfade as a silent fallback.

## Timing

Use authored per-effect timing.

No:

- catch-up;
- paint acknowledgement;
- producer/display divisor;
- per-transition physical frame timer;
- easing used to hide cadence defects.

## Rich effects

Preserve actual authored behavior. Do not replace 3D Block Spins, Particle, Burn or other rich effects
with simplified lookalikes.

See `Docs/Architecture/Compositor_Architecture.md` and `Spec.md` for the durable retained transition contracts.

## Display geometry (R-63 overscan)

A transition draws at `frame.logical_size`: the background item's size. That is the monitor's device-exact rectangle
inside the R-63 window (at 150% a 2560 px monitor is 1706.67 logical px, while `display_bounds()`, Qt's rounded screen
geometry, says 1707) and, before the window's native rectangle is known, the whole overscanned window.
Anything computed for a run outside the renderer (COMPUTE-prepared geometry, caches, per-display aspect or pixel
math) must key on the renderer's own size (`QuickDisplayUnit.transition_logical_size()`), never on the monitor
rectangle, or it silently never matches and the render thread rebuilds it every run (R-95: Glass froze 43–141 ms).
A prepared-work bar must prove a *hit* when the render size differs from `display_bounds()`, not just that preparation ran.

## GL ownership

Every implementation restores touched state and owns/releases context-local resources legally.

Keep exception-path state restoration tests current.

## Future change gate

Choose the smallest falsifiable set:

- registry parity;
- activation/lazy dormancy;
- request/settings resolution;
- endpoints/midpoint behavior;
- parameter sensitivity;
- interruption/exactly-once completion;
- generation fencing;
- prepared-work hit when the render size differs from `display_bounds()` (when anything is prepared off the render thread);
- resource cleanup;
- GL-state restoration;
- focused real-GL/eyes-on evidence when the visual claim requires it.
