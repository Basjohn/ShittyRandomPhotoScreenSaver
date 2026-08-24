# 02 — Quick Scene Renderer / Transitions

Status: **LANDED transition architecture / current authoring reference**  
Last updated: 2026-08-24

Phase-C transition implementation is complete. This document records durable transition rules, not a
Phase-C task list.

## Destination

```text
canonical descriptor/settings
-> activation/admission + parameter resolution
-> TransitionRequest / TransitionRun
-> lazy Quick transition implementation
-> display transition QSGRenderNode
-> owning QQuickWindow
```

All 12 canonical production transitions have Quick implementations.

No final Quick transition depends on `GLCompositorWidget`.

## Old transition pixels

Old `TransitionFactory`/`GLCompositor*Transition` pixel implementations are migration debris once
caller-proofed.

They are not protected as visual reference because the Quick implementations are already the accepted
transition pixel authority.

Delete them when safe before H; leave only the final physical-host edge to H if necessary.

Do not preserve an old transition presenter until I.

## Runtime semantics

`TransitionRequest` / `TransitionRun` are display-local, immutable/monotonic and exactly-once for
completion/cancellation.

Missed physical opportunities advance to the current sample. No catch-up/FIFO/paint acknowledgement.

Generation/run identity rejects stale state.

## Activation

Activation, manual selection and Random pool membership are separate.

Effective Random candidates:

```text
activated ∩ saved pool membership ∩ runnable/hardware
```

Invalid state repair is canonical/persisted; it does not authorize execution of a deactivated fallback.

## Renderer ownership

Custom GL lives inline in the Quick scene.

Context-local programs/meshes/buffers/textures are owned/released by the legal render owner.

The common state fence restores every touched GL state on normal and exception paths.

## Images

Presentation captures detached immutable image data before render-thread ownership.

Stable images are not reconverted/reuploaded every frame.

No live QWidget/QPixmap reads from the render thread.

## Timing

Preserve authored timing per transition.

- Slide: SINE_IN_OUT.
- staged shader/physics effects generally use linear outer time where they author internal staging.
- 3D Block Spins retains its authored internal spin timing.

Do not add easing to conceal cadence/coverage bugs.

## Canonical inventory

1. Crossfade
2. Slide
3. Wipe
4. Warp Dissolve
5. Block Puzzle Flip
6. 3D Block Spins
7. Blinds
8. Diffuse
9. Ripple / Raindrops
10. Crumble
11. Particle
12. Burn

Registry parity is permanent.

## Fidelity highlights

### Slide

Four product directions; source/destination ownership derives from one sample. No independent rounding
accumulation. Do not restore diagonal full-frame Slide without solving exposed-corner coverage.

### Block Puzzle Flip

Preserve shader-authoritative 3D strip/slab character, directions and exact endpoints.

### 3D Block Spins

Preserve actual slab mesh/depth/front/back/sides/axes/spin signs/UV orientation/specular/rim. No
flat-quad fallback.

### Blinds

Preserve authored slat grid/modes/feather/centre-out growth/tail.

### Diffuse / Ripple / Crumble

Preserve canonical shader/math, supported modes/seeds/parameters/endpoints.

### Particle

Preserve Directional/Swirl/Converge behavior, directions/random placement, trails, swirl, shading,
texture mapping, wobble/gloss/light/seed/resolution semantics.

### Burn

Preserve ignition, directions, noise/domain warp, jagged front, heat/glow/core/char/crackle/smoulder,
sparks/smoke/ash, seed/run-clock timing and destination tail.

## Pacing

One presentation pacer per display/window.

It requests Quick updates while transition or visible custom-GL visualizer demand exists.

No `afterRendering -> update()` self-loop, FIFO/catch-up or feedback into visualizer logical cadence.

## Permanent gates

Retain:

- registry parity;
- parameter/request wiring;
- exact endpoints;
- discriminative real-GL checks where useful;
- GL-state fence/exception restoration;
- generation/cancel fencing;
- sparse-default coverage;
- effect-specific parameter sensitivity.

Future transition changes use the smallest gate capable of falsifying the changed contract.
