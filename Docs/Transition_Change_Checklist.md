# Transition Change Checklist

Last updated: 2026-08-28

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

## Old transition implementation status

All canonical transitions have Quick implementations.

The old:

- `rendering/transition_factory.py` pixel-construction role;
- `transitions/gl_compositor_*_transition.py`;
- old compositor transition presentation tests/helpers

are **not visual-reference authority**.

Delete them as soon as exact caller proof makes that safe. If the final call edge is inseparable from the old physical
`DisplayWidget`, that edge leaves at H with the physical presenter. Do not preserve or reconstruct the old transition
stack merely to keep the half-migrated app runnable, and do not postpone caller-dead transition pixels to I.

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

See `Docs/QtQuick_Migration/02_Scene_Renderer_Transitions.md` for the durable effect contracts.

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
- resource cleanup;
- GL-state restoration;
- focused real-GL/eyes-on evidence when the visual claim requires it.
