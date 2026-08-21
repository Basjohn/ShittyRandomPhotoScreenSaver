# Transition Change Checklist

Last updated: 2026-08-21

Use this checklist when adding, removing, renaming, retuning, enabling, disabling, or diagnosing a
transition.

Active migration sequence is owned by `Current_Plan.md`. The landed Qt Quick transition architecture
is described in `Docs/QtQuick_Migration/02_Scene_Renderer_Transitions.md`.

## 1. Canonical identity

- Canonical transition identity remains in `rendering/transition_registry.py`.
- Stable ids are the runtime/render boundary; Settings labels and legacy aliases remain
  registry/settings concerns.
- Random/Cycle eligibility is registry-owned.
- Registry parity must prove every canonical production transition has exactly one Quick
  implementation entry and ids are unique.

Do not create a second transition catalogue in Quick code.

After Phase E2 lands, application-level **activation** becomes a separate Settings authority above
ordinary manual/random selection. See `Docs/QtQuick_Migration/07_Settings_Capability_Activation.md`.

## 2. Production presentation contract

```text
Settings / transition selection
    -> canonical descriptor
    -> GUI/runtime-side immutable request resolution
    -> TransitionRequest / TransitionRun
    -> lazy Quick renderer implementation
    -> display QSGRenderNode
    -> display QQuickWindow
```

Until Phase H production cutover, the old compositor may remain as current production/reference.
New Quick code must not call back into `GLCompositorWidget`, QWidget presentation, or a compatibility
presenter.

No transition may fall back from Quick to the old compositor.

## 3. Lazy implementation boundary

Each transition implementation owns:

- authored shader/math;
- transition-specific validation;
- uniforms;
- optional mesh/buffers;
- context-local GL resources;
- resource release.

The common host owns:

- old/new immutable image textures;
- request/run lifecycle;
- monotonic progress sampling;
- generation/run fencing;
- completion/cancellation;
- shared GL-state fencing;
- presentation frame demand.

Disabled/deactivated means dormant: no transition implementation import, shader compile, GPU object,
timer, or transition-specific runtime state merely because code is installed.

Internal modularity is static and plugin-shaped. Do not add dynamic discovery, manifests, hot loading,
API versioning, dependency resolution, or a third-party transition SDK.

## 4. Request admission and settings resolution

Resolve Settings spelling, random choices, clamps, colors, and fall-through behavior before render
ownership.

Canonical Settings defaults are fallback authority. Do not duplicate constructor/default magic
numbers in the Quick resolver.

Parameterized Quick renderers reject missing/unresolved values instead of silently inventing renderer
defaults.

Per-run values such as seeds are resolved once into the immutable request/run.

After E2:

```text
activated
-> may participate in manual/random selection

deactivated
-> excluded from effective selection and renderer resolution
```

Random pool membership remains separate from activation.

## 5. Timing

Preserve authored timing rather than applying one global easing policy.

- Slide: `SINE_IN_OUT`.
- Staged shader/physics transitions normally receive a linear outer run when they already shape time
  internally.
- 3D Block Spins keeps authored cubic internal spin over a linear outer run.

Physical frame pacing is presentation-only. Missed display opportunities advance to current
monotonic sample; they are never replayed.

Never add:

- catch-up queues;
- paint acknowledgement;
- producer/display divisors;
- per-transition frame timers;
- easing used to disguise a coverage/cadence defect.

## 6. Image ownership and endpoints

Source/destination images crossing into render ownership are immutable/detached from QWidget/QPixmap
state.

Every transition proves exact source and destination endpoints.

For Slide, source/destination sampling and sole pixel owner come from one immutable progress sample in
one draw. Product directions are left/right/up/down. Do not restore diagonal full-frame Slide without
separately authored corner coverage.

## 7. Authored-rich effects

Do not replace a rich existing effect with a conceptually similar simplified port.

### 3D Block Spins

Preserve real thin 36-vertex rectangular-prism slab, depth-tested faces, black void, four authored
axes/directions, destination-face UV orientation, dark sides, moving direction-sensitive specular
band, edge-on rim, and context-local mesh/program teardown. No flat-quad fallback.

### Particle

Preserve canonical particle shader, Directional/Swirl/Converge behavior, all directional/random
placement shader modes, trail behavior, swirl strength/turns/order, wobble, texture mapping, 3D
shading, gloss size, light direction, seed, and physical-framebuffer resolution semantics.

### Burn

Preserve canonical Burn shader and ignition delay, six directions, four-octave/domain-warped noise,
jagged front, heat distortion, warm glow, white-hot core, char progression/crackle/smoulder,
sparks/embers, smoke wisps, falling ash, density controls, per-run seed, animated effect time, and
delayed clean-destination tail fade.

## 8. GL state/resource hygiene

A transition may use shaders, depth, meshes, VAOs/VBOs, textures, and other GL state inside the Quick
render node, but must leave the scene graph safe for subsequent nodes.

Keep common state fence current for any state introduced, including:

- viewport/scissor;
- program;
- VAO/VBO;
- active textures/bindings;
- blend;
- cull;
- depth enable/write/function/clear;
- stencil;
- other modified state.

Create/delete context-local resources on legal render owner.

A permanent regression must prove state restoration both on normal render and when the transition
renderer raises.

## 9. Tests and evidence

Use the smallest gate that can falsify the change:

- registry/catalog parity;
- lazy import/dormancy;
- request/settings resolution;
- parameter validation;
- shader/source reuse where required;
- start/mid/end behavior;
- authored direction/mode variants;
- interruption/exactly-once completion;
- generation fencing;
- resource cleanup;
- GL-state restoration;
- focused real-GL smoke where useful.

### 9.1 Real-GL smoke must be effect-discriminative

A midpoint smoke oracle is insufficient if a generic wipe/crossfade/spatial reveal could satisfy it.

For Diffuse/Ripple/Crumble/Particle/Burn:

- keep the real-GL harness;
- use deterministic inputs/seeds;
- assert effect-specific spatial/geometry behavior;
- add pairwise contrast cases for parameters that should change output.

At minimum prove sensitivity for:

- Ripple count1/count3/count8;
- Crumble weighting modes;
- Particle directions/modes;
- Burn smoke/ash toggles.

### 9.2 Direct request → uniform wiring

Add direct renderer-boundary wiring tests for Diffuse, Ripple, Crumble, Particle and Burn.

Particle must cover:

```text
mode, direction, radius, overlap, trails,
swirl strength/turns/order,
3D shading, texture mapping, wobble,
gloss, light direction, seed,
physical framebuffer resolution
```

Burn covers all authored effect uniforms plus run-clock-derived `u_time`.

These wiring tests supplement rather than replace real-GL smoke.

### 9.3 Sparse defaults

Sparse Settings/default coverage must include Blinds and Ripple in addition to
Diffuse/Crumble/Particle/Burn.

### 9.4 Crumble mosaic_mode

Do not claim visual mosaic behavior while the canonical fragment shader does not consume
`u_mosaic_mode`.

Test only optional uniform-upload behavior if the uniform exists.

### 9.5 Controller fence test shape

`test_runs_require_explicit_interruption_and_are_generation_fenced` must assert cancellation outside
the expected-raise block. Only generation-mismatched `start(...)` is expected to raise.

### 9.6 Inventory maintenance

Do not maintain a second hard-coded `_ALL_QUICK_TRANSITION_IDS` inventory when registry parity already
owns that correctness gate.

### 9.7 Environment fidelity

A deterministic source/contract test is not a visual-parity claim.

Do not weaken Windows/Qt/OpenGL/physical-display tests because another environment cannot execute
them.

Manual/agent sign-off commands belong in `Docs/Harness_Index.md`.

## 10. Git/checkpoint discipline

Normal local slice:

```text
focused gate
-> inspect diff/status
-> commit intended paths only
-> push
```

High-risk effect or test-exposed implementation repair:

```text
focused gate
-> inspect diff/status
-> commit
-> push
-> independent audit
```

Repository connector/API writes are not the normal SRPSS mutation path.

## 11. Migration closure

Phase C **implementation** is structurally complete once canonical registry and Quick implementation
registry are in exact parity and each renderer is isolated from the old compositor.

Phase-C **test-hardening and acceptance/sign-off remain separate states**.

Before Phase-C acceptance is marked closed:

- complete the Section 7.5 test-hardening debt from `Current_Plan.md`;
- run focused deterministic Phase-C tests;
- run applicable real-GL commands in `Docs/Harness_Index.md`;
- record exact command/result/commit/environment;
- leave hardware/eyes-on-only gates unchecked until actually performed.

Source review, "should pass", or a missing execution result is not execution evidence.

Later implementation phases may proceed while explicit Phase-C acceptance remains open when they do
not depend on that evidence.

Failing deferred evidence reopens only the smallest demonstrated transition/runtime defect.
