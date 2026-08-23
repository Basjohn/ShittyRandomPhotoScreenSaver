# Transition Change Checklist

Last updated: 2026-08-23

Use this checklist when adding, removing, renaming, retuning, activating/deactivating, selecting,
randomizing or diagnosing a transition.

Active migration sequence/work admission is owned by `Current_Plan.md`. Landed Qt Quick transition
architecture is described in `Docs/QtQuick_Migration/02_Scene_Renderer_Transitions.md`. The landed
capability/`SETUP` contract is described in
`Docs/QtQuick_Migration/07_Settings_Capability_Activation.md`.

## 1. Canonical identity

- Canonical transition identity remains in `rendering/transition_registry.py`.
- Stable ids/settings names are the runtime/render boundary; Settings labels and legacy aliases remain
  registry/settings concerns.
- Registry parity proves every canonical production transition has exactly one Quick implementation
  entry and ids are unique.
- Do not create a second transition catalog in Quick code.

## 2. Activation, pool membership and manual selection are separate

Application-level transition activation is landed runtime authority:

```text
activated / deactivated
    = may implementation/runtime selection resolve at all?

saved Random-pool membership
    = preference used only while activated + Random is effective

manual transition selection
    = ordinary concrete choice used when Random is off
```

A deactivated transition is excluded from effective manual/cycle/random selection and must not gain
renderer/runtime ownership merely because its implementation exists.

Saved pool preference survives deactivation so reactivation restores user intent.

The operator-facing `SETUP`/pill UI is **already landed E2 behavior**. Do not describe it as a future
activation store or restore the old dropdown/pool UI as authority.

Do not use “disabled” and “deactivated” interchangeably where the distinction matters.

### 2.1 Random authority

The one live Random authority is:

```text
transitions.random_always
```

Legacy `type="Random"` is migration input only.

Effective runtime candidates are:

```text
activated ∩ saved pool membership ∩ runnable/hardware
```

Do not silently broaden an empty effective Random pool.

### 2.2 Invalid-state repair

Canonical normalization is landed:

```text
zero activated transitions
    -> activate Crossfade in canonical settings
    -> persist repair

Random on + empty activated saved pool
    -> random_always = false
    -> persist deterministic activated manual selection
    -> preserve saved pool membership
```

This is state repair, not permission for a renderer/factory to execute a deactivated Crossfade.

## 3. Production presentation contract

```text
Settings / transition selection
    -> canonical descriptor
    -> activation admission
    -> GUI/runtime-side immutable request resolution
    -> TransitionRequest / TransitionRun
    -> lazy Quick renderer implementation
    -> display QSGRenderNode
    -> display QQuickWindow
```

Until production cutover, the old compositor may still have live callers. It is
**CURRENT-LEGACY — WILL BE OBSOLETE at H/I**, not destination authority.

New Quick code must not call back into `GLCompositorWidget`, QWidget presentation or a compatibility
presenter. No transition may fall back from Quick to the old compositor.

## 4. Lazy implementation boundary

Each transition implementation owns:

- authored shader/math;
- transition-specific validation;
- uniform upload;
- optional mesh/buffers;
- context-local GL resources;
- resource release.

The common host/controller owns:

- immutable old/new images/textures;
- request/run lifecycle;
- monotonic progress sampling;
- generation/run fencing;
- exactly-once completion/cancellation;
- shared GL-state fencing;
- presentation frame demand.

A deactivated transition is dormant: no heavy implementation import, shader compile, GPU object,
transition-specific timer or transition-specific runtime state solely because code is installed.

Internal modularity is static/plugin-shaped. Do not add dynamic discovery, manifests, hot loading, API
versioning, dependency resolution or a third-party transition SDK.

## 5. Request admission and Settings resolution

Resolve Settings spelling, aliases, Random choices, clamps, colors and supported legacy fall-through
behavior before render ownership.

Canonical Settings defaults are the default-resolution authority. Do not duplicate constructor/default
magic numbers in the renderer.

Parameterized Quick renderers reject missing/unresolved required values instead of silently inventing
renderer defaults.

Per-run values such as seeds resolve once into immutable request/run state.

Activation filtering occurs before implementation admission.

### 5.1 Final admission is LANDED

The old `829446c8` pre-E2 gap is closed and must **not** be treated as current work.

Current contract:

- an already-populated `transitions.random_choice` is revalidated against current activation and
  hardware/runnability before factory admission;
- stale/deactivated/hardware-invalid choices are re-resolved or fail closed;
- engine/factory/C-key empty-candidate paths do not silently execute a deactivated literal Crossfade;
- the explicit Crossfade recovery path repairs canonical activation state first and then follows normal
  admission.

Retain the direct regressions. Do not re-open this merely because old phase prose says “before E2
exit.”

## 6. Timing

Preserve authored timing instead of applying one global easing policy.

- Slide: `SINE_IN_OUT`.
- Staged shader/physics transitions normally receive a linear outer run when they shape time internally.
- 3D Block Spins keeps authored cubic internal spin over a linear outer run.

Physical frame pacing is presentation-only. Missed display opportunities advance to current monotonic
sample and are never replayed.

Never add:

- catch-up queues;
- paint acknowledgement;
- producer/display divisors;
- per-transition frame timers;
- easing used to disguise coverage/cadence defects.

## 7. Image ownership and endpoints

Source/destination images crossing into render ownership are detached/immutable from live
QWidget/QPixmap state.

Every transition proves exact source and destination endpoints.

For Slide, source/destination sampling and sole pixel ownership derive from one immutable progress
sample in one draw. Product directions are left/right/up/down. Do not restore diagonal full-frame
Slide without separately authored corner coverage.

## 8. Authored-rich effects

Do not replace a rich existing effect with a conceptually similar simplified port.

### 8.1 3D Block Spins

Preserve the real thin 36-vertex rectangular-prism slab, depth-tested faces, black void, authored axes/
directions, destination-face UV orientation, dark sides, moving direction-sensitive specular band,
edge-on rim and context-local mesh/program teardown. No flat-quad fallback.

### 8.2 Particle

Preserve canonical particle shader, Directional/Swirl/Converge behavior, directional/random-placement
modes, trail behavior, swirl strength/turns/order, wobble, texture mapping, 3D shading, gloss/light,
seed and physical-framebuffer resolution semantics.

### 8.3 Burn

Preserve canonical Burn shader and ignition delay, six directions, domain-warped noise, jagged front,
heat distortion, glow, white-hot core, char/crackle/smoulder progression, sparks, smoke, ash,
densities/toggles, seed, run-clock effect time and destination tail.

## 9. GL state/resource hygiene

A transition may use shaders, depth, meshes, VAOs/VBOs, textures and other GL state inside the Quick
render node, but must leave the scene graph safe for subsequent nodes.

Keep common state-fence coverage current for modified state including:

- viewport/scissor;
- program;
- VAO/VBO;
- active texture/bindings;
- blend;
- cull;
- depth enable/write/function/clear;
- stencil;
- newly introduced state.

Create/delete context-local resources on the legal render owner.

Permanent regression must prove restoration on the normal path and when renderer execution raises.

## 10. Landed Phase-C regression hardening

The following are **already landed permanent obligations**, not work instructions to repeat.

### 10.1 Effect-discriminative real-GL smoke

Diffuse/Ripple/Crumble/Particle/Burn midpoint checks must distinguish the actual authored effect from a
generic wipe/crossfade/spatial reveal.

Use deterministic inputs/seeds and effect-specific spatial/geometry/statistical properties rather than
brittle exact screenshots where possible.

### 10.2 Parameter sensitivity

Retain deterministic contrast coverage for parameters that should visibly alter output, including:

- Ripple count1/count3/count8;
- Crumble weighting modes;
- Particle directions/modes;
- Burn smoke/ash toggles.

### 10.3 Request -> uniform wiring

Retain direct renderer-boundary wiring tests for parameter-rich renderers.

Particle coverage includes mode/direction/radius/overlap/trails/swirl settings/3D shading/texture
mapping/wobble/gloss/light/seed/physical framebuffer resolution.

Burn coverage includes authored effect uniforms plus run-clock-derived `u_time`.

Wiring tests supplement rather than replace real-GL smoke.

### 10.4 Sparse defaults

Sparse canonical-default coverage includes Blinds and Ripple alongside the other parameterized effects.

### 10.5 Crumble `mosaic_mode`

Do not claim visual mosaic behavior while the canonical fragment shader does not consume
`u_mosaic_mode`. Test optional uniform-upload behavior only until authored shader behavior changes.

### 10.6 Controller generation/cancel fence

The controller test must execute/assert cancellation independently. Only the generation-mismatched
`start(...)` operation belongs inside the expected-raise assertion.

### 10.7 Inventory maintenance

Registry parity is the canonical independent inventory gate. Do not reintroduce a competing hard-coded
`_ALL_QUICK_TRANSITION_IDS` authority.

### 10.8 Environment fidelity

A deterministic source/contract test is not a visual-parity claim. Do not weaken Windows/Qt/OpenGL/
physical-display tests merely because another environment cannot run them.

## 11. Adding/changing a transition now

For a real future transition change, use the smallest gate capable of falsifying that change:

- catalog/registry parity;
- activation/lazy dormancy;
- request/settings resolution;
- parameter validation;
- shader/math preservation where required;
- endpoints/midpoints/directions/modes;
- interruption/exactly-once completion;
- generation fencing;
- resource cleanup;
- GL-state restoration;
- focused real-GL visual discrimination where useful.

Do not mechanically rerun/rewrite every historical Phase-C hardening item if the new change does not
touch that contract.

## 12. Git/checkpoint discipline

Normal local slice:

```text
focused gate
-> inspect diff/status
-> commit intended paths only
-> push
```

High-risk authored effect or test-exposed implementation repair:

```text
focused gate
-> inspect diff/status
-> commit
-> push
-> independent audit when Current Plan requires it
```

Repository connector/API writes are not the normal SRPSS mutation path.

## 13. Closure/acceptance state

Phase-C **implementation and deterministic hardening are complete**.

Current Plan owns remaining operator-scheduled acceptance state. Preserve runnable real-GL harnesses
and physical/eyes-on criteria without turning them back into implementation TODOs.

A later failing acceptance result reopens only the smallest demonstrated transition/runtime defect.
