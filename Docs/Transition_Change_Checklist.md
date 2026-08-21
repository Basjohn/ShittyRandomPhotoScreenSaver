# Transition Change Checklist

Last updated: 2026-08-21

Use this checklist when adding, removing, renaming, retuning, enabling, disabling, or diagnosing a transition.

Active migration sequence is owned by `Current_Plan.md`. The landed Qt Quick transition architecture is described in `Docs/QtQuick_Migration/02_Scene_Renderer_Transitions.md`.

## 1. Canonical identity

- Canonical transition identity remains in `rendering/transition_registry.py`.
- Stable ids are the runtime/render boundary; Settings labels and legacy aliases remain registry/settings concerns.
- Random/Cycle eligibility is registry-owned.
- A transition may remain visible in Settings while disabled from runtime selection.
- The permanent Phase-C registry-parity gate must continue to prove that every canonical production transition has exactly one Quick implementation entry and that ids are unique.

Do not create a second transition catalogue in Quick code.

## 2. Production presentation contract

The target/landed renderer path is:

```text
Settings / transition selection
    -> canonical descriptor
    -> GUI/runtime-side immutable request resolution
    -> TransitionRequest / TransitionRun
    -> lazy Quick renderer implementation
    -> display QSGRenderNode
    -> display QQuickWindow
```

Until Phase H production cutover, the old compositor may remain in the repository as the current production/reference implementation. New Quick code must not call back into `GLCompositorWidget`, QWidget presentation, or a compatibility presenter.

No transition may fall back from Quick to the old compositor.

## 3. Lazy implementation boundary

Each transition implementation owns its own:

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

Disabled means dormant: no transition implementation import, shader compile, GPU object, timer, or transition-specific runtime state merely because the code is installed.

Internal modularity is static and plugin-shaped. Do not add dynamic discovery, manifests, hot loading, API versioning, dependency resolution, or a third-party transition SDK.

## 4. Request admission and settings resolution

Resolve Settings spelling, random choices, clamps, colors, and legacy fall-through behavior before render ownership.

Parameterized Quick renderers should reject missing/unresolved values instead of silently inventing renderer defaults.

Canonical Settings defaults are the fallback authority. Do not duplicate constructor/default magic numbers in the Quick resolver when the current Settings schema already owns them.

Random/per-run values such as seeds are resolved once into the immutable request/run. Do not re-randomize per rendered frame.

## 5. Timing

Preserve authored timing rather than applying one global easing policy.

- Slide: `SINE_IN_OUT`.
- Staged shader/physics transitions normally receive a linear outer run when they already shape time internally.
- 3D Block Spins keeps its authored cubic internal spin timing over a linear outer run.

Physical frame pacing is presentation-only. Missed display opportunities advance to the current monotonic sample; they are never replayed.

Never add:

- catch-up queues;
- paint acknowledgement;
- producer/display divisors;
- per-transition frame timers;
- easing used to disguise a coverage/cadence defect.

## 6. Image ownership and endpoints

Source/destination images crossing into render ownership must be immutable/detached from QWidget/QPixmap state.

Every transition must prove exact source and destination endpoints.

For Slide, source and destination sampling and the sole pixel owner come from one immutable progress sample in one draw. The four product directions are left/right/up/down. Do not restore diagonal full-frame Slide without separately authored corner coverage.

## 7. Authored-rich effects

Do not replace a rich existing effect with a conceptually similar simplified port.

### 3D Block Spins

Preserve the real thin 36-vertex rectangular-prism slab, depth-tested faces, black void, four authored axes/directions, destination-face UV orientation, dark sides, moving direction-sensitive specular band, edge-on rim, and context-local mesh/program teardown. No flat-quad fallback.

### Particle

Preserve the canonical particle shader, Directional/Swirl/Converge behavior, all directional/random-placement shader modes, trail behavior, swirl strength/turns/order, wobble, texture mapping, 3D shading, gloss size, light direction, seed, and physical-framebuffer resolution semantics.

### Burn

Preserve the canonical Burn shader and its ignition delay, six directions, four-octave/domain-warped noise, jagged front, heat distortion, warm glow, white-hot core, char progression/crackle/smoulder, sparks/embers, smoke wisps, falling ash, density controls, per-run seed, animated effect time, and delayed clean-destination tail fade.

## 8. GL state/resource hygiene

A transition may use shaders, depth, meshes, VAOs/VBOs, textures, and other GL state inside the Quick render node, but it must leave the scene graph safe for subsequent nodes.

Keep the common state fence current for any state introduced by new effects, including viewport/scissor, program, VAO/VBO, active textures/bindings, blend, cull, depth enable/write/function/clear, stencil, and other modified state.

Create and delete context-local resources on the legal render owner. Resource deletion failures remain accounted/loud; do not silently leak ownership.

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

A deterministic source/contract test is not a visual-parity claim. Physical-display cadence, mixed-refresh behavior, subjective motion feel, GPU utilization, and real multi-monitor topology require the proper Windows/Qt/OpenGL/hardware environment.

Manual/agent sign-off commands belong in `Docs/Harness_Index.md` and the Phase-C closure ledger in `Current_Plan.md`.

## 10. Git/checkpoint discipline

For normal local work:

```text
focused gate
-> inspect diff/status
-> commit intended paths only
-> push
-> independent audit
```

## 11. Migration closure

Phase C **implementation** is structurally complete once the canonical registry and Quick implementation registry are in exact parity and each renderer is isolated from the old compositor.

Phase-C **acceptance/sign-off is a separate state and must remain open until its listed tests and sign-off gates have actually been executed and their results recorded**. Before any agent marks Phase-C acceptance closed, it must run the focused deterministic Phase-C tests and the applicable real-GL commands listed in `Docs/Harness_Index.md`, record the exact command/result/commit/environment, and leave any genuinely hardware/eyes-on-only gate unchecked until that gate is actually performed. Source review, a missing execution result, or "should pass" is never a substitute for execution evidence.

Later implementation phases may proceed while explicit Phase-C acceptance items remain open when they are not dependencies of the later work. Failing deferred evidence reopens only the smallest demonstrated transition/runtime defect; it does not authorize a second presentation architecture.

Old compositor-only transition classes are removed after production cutover through Phase I / `Future_Cleanup.md`.
