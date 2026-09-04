# Deformable Sphere visualizer

Status: reconnaissance/decomposition. Live sequencing: `FWPlan.md`.
Pre-implementation comparison/rollback HEAD: `f8def8ee8cbd99527b513494bb2068417144452c`.
The operator explicitly requested an ambitious 3D item after Glow and Slide. This is a new experiment;
it does not claim to reconstruct the lost historical Blob.

## Current foundation inventory

1. `core/settings/visualizer_mode_registry.py`: cheap canonical descriptor, runtime/renderer/builder import strings,
   shell/clip policy and enabled-mode resolution. Missing/invalid enabled lists currently mean every registered mode;
   that must become descriptor-default-enabled selection so adding an experiment cannot activate it in old profiles.
2. `widgets/spotify_visualizer/quick_display_visualizer_owner.py`: existing controller, shared BeatEngine lease,
   generation/activation lifecycle and lazy `_mode_runtime_factory`; no Sphere-owned audio or source lane.
3. `widgets/spotify_visualizer/logical_runtime.py`, `tick_pipeline.py`: the sole authored logical clock. Existing
   mode-specific dispatches gate themselves; Sphere may advance at its lazy logical capture seam, as other frame
   modes already do, without running Bubble/DevCurve solvers or introducing a sixth ticking owner.
4. `logical_frame_capture.py`: immutable shared/source context and current five-way capture dispatch. Extend the
   descriptor to carry lazy capture wiring rather than add a new unrelated central mode switch.
5. `render_state.py`: immutable `VisualizerLogicalFrame`, `VisualizerCommonState.energy`, `FrozenFields`,
   geometry/fades and concrete mode payload validation. Add only a small frozen Sphere payload and its validation.
6. `config_applier.py`, `core/settings/models/_spotify_visualizer.py`, Settings snapshot/preset normalization:
   distinguish logical vs presentation options; retain Sphere parameters through the actual production path.
7. `ui/tabs/visualizers_tab.py`, `ui/tabs/media/visualizer_mode_binding.py`, `visualizer_mode_body_host.py`:
   existing enabled-mode navigation and lazy bodies; inspect remaining mode-specific binding seams before changing.
8. `rendering/quick/visualizer/implementation_registry.py`, `render_host.py`: lazy context-local renderer, shared
   quad and GL-state fence, resource retirement. Fence currently preserves depth enable/write, but new depth function,
   clear value and face state changes must be restored locally or added only where actually required.
9. `rendering/quick/transitions/implementations/block_spins.py`, `rendering/gl_programs/blockspin_program.py`:
   proven static VAO/VBO, true Z, shader transforms, depth-tested geometry and partial-failure cleanup precedent.
10. `VisualizerModePresentationPolicy`, `VisualizerShellPolicy.FRAMELESS`, `VisualizerClipPolicy.VIEWPORT_RECT`,
    `rendering/quick/visualizer/clip_host.py`: existing transparent same-scene shell and clipping. No new window/FBO.
11. `core/settings/shadow_direction.py`: eight-way direction vocabulary/sign resolver. Resolve Sphere key-light
    configuration once; no dependency on live Widget shadow state or per-frame Settings reads.
12. `tests/test_qtquick_visualizer_geometry.py`, `test_visualizer_mode_dormancy.py`,
    `test_visualizer_mode_enable_resolver.py`, `test_visualizer_settings_lazy_bodies.py`,
    `tools/qtquick_visualizer_clip_smoke.py`: existing contract/lifecycle/real-Quick evidence routes.

## State, cadence and lifetime

Sphere is one canonical `sphere` descriptor, display name `Sphere (Experimental)`, independently disabled by default.
Enable it deliberately through existing mode Setup; family activation and enabled-mode selection remain distinct.
Its policy is FRAMELESS + VIEWPORT_RECT and supports the existing viewport resize/whole-scale contract.

`SphereFrameRuntime` owns activation-relative authored time and latest frozen Sphere state, driven only by the
existing logical clock/capture callback. Common analysis supplies bass/mid/high/overall plus transient energy;
stale generation/activation data cannot become fresh response. No FFT, source subscription, worker or timer is added.
The renderer consumes immutable time/energy/configuration and never advances simulation or reads the engine.

Payload interface: `SphereFrame(authored_time: float, parameters: FrozenFields)` under `logical.mode_state`;
reactive energy is `logical.common.energy`. Generation/source/fades stay on the enclosing established snapshot.
Sphere parameters are bounded `sphere_*` values: material (Chrome/Obsidian/Magma/Silver), deformation strength,
rotation speed, gloss/specular and key-light direction. Initial defaults are feature-local and do not alter existing
mode defaults, presets, shared colour controls or logical parameters.

One modest static sphere mesh is generated/uploaded only at first admitted render/context creation. CPU topology
is never rebuilt per frame. One vertex deformation pass and one lit fragment pass form a real three-dimensional
surface; finite tangent samples reconstruct deformed normals. Broad bass breathing, low-order mid lobes and
restrained high ripples remain independent and do not form an audio hedgehog. Arbitrary-axis rotation derives
from authored time. Bounded specular/Fresnel/material treatment makes surface deformation readable.

Perspective uses a fixed camera distance in sphere-local units and scales into current content pixel geometry with
one common X/Y pixel scale. Uniform resize changes object size; viewport-edge resize changes framing/playroom,
without ellipse distortion or viewport-dependent audio damping. Clip to the existing assigned viewport.

Depth/cull/function/clear state is restored through the existing fence plus narrowly scoped Sphere-local state where
needed. Clear depth only inside the admitted content scissor; never clear colour, overwrite stencil or create a
second depth/window owner. Program, VAO and VBO retire through renderer `release_resources`, including allocation
failure and context recreation. No meaningful 3D work survives retirement/deactivation.

## Primitive classification

- **Feature-local:** Sphere mesh generator, deformation/normal equations, audio mappings, material palette,
  perspective constants, settings controls and immutable mode frame/runtime.
- **Justified reusable infrastructure:** cheap descriptor default-enabled and lazy-capture metadata needed by this
  real sixth consumer; preserve existing mode behavior while replacing closed central dispatch where necessary.
- **Reuse existing:** run/generation clock, source bands, immutable transport, presentation geometry/fades,
  shader compilation, context release, GL fence, eight-way direction vocabulary and lazy Settings body host.
- **Speculative reuse deferred:** general camera/MVP library, mesh/resource framework, lighting/material hierarchy,
  scene graph, physics, 3D object manager. Extract only after a second real consumer proves identical requirements.

## Resumable checkpoints

- [x] Inventory current owners and commit decomposition before substantial coding.
- [ ] **S1 — admission/state:** descriptor default-enabled policy, frozen Sphere payload, lazy frame runtime/capture,
  production source/config propagation, tests of source identity and independent dormancy.
- [ ] **S2 — geometry/render:** modest static sphere mesh, analytic deformation/normals, arbitrary rotation,
  perspective, material/key-light uniforms, depth/resource cleanup and focused CPU/fake-GL proof.
- [ ] **S3 — real Quick prototype:** deterministic frame fixtures and actual GL capture; inspect geometry, band
  response, four materials, shell transparency and aspect variants; measure bounded callback cost/resources.
- [ ] **S4 — Settings:** isolated lazy body and defaults/config roundtrip; no eager body or preset destruction.
  Add polished options only after the prototype earns retention. Existing modes' shared controls remain intact.
- [ ] **S5 — integration:** focused current-mode regression floor + destination gate, durable docs/navigation,
  compact FW status, commit/push coherent slices. Separate automatic results from operator acceptance.

## Acceptance bars

- **Deterministic/source:** unit sphere topology/finite outward normals/real Z; same time+bands gives same payload;
  distinct bass/mid/high influence; exact immutable generation identity; renderer cannot advance authored time.
- **Lifecycle/resource:** disabled old/default profiles import no Sphere runtime/builder/renderer; first enable resolves
  only Sphere; disable/mode switch/recreation retires its program/buffers; failure cleanup preserves recoverability.
- **Geometry:** fixed pixel metric on both axes across wide/tall extents; whole-scale uniformity; viewport clipping;
  no card fill/border/shadow. Preserve the five established modes' R-69/BTF behavior exactly.
- **Performance:** one mesh upload per renderer/context lifetime, one sphere draw, constant bounded uniform transport,
  no per-frame topology/upload/source jobs. Measure 1080p/4K/extents separately; callbacks are not physical cadence proof.
- **Eyes-on/operator:** it reads as a deforming 3D body with normals/specular following dents/bulges; materials differ
  meaningfully, no clipping surprises, responsive real music/idle, 60/165 Hz and mixed-DPR/recreation acceptance.
  Retain this checklist as Awaiting Validation when automation cannot honestly close it.
