# Slide motion options

Status: Elastic, Wobble and Flex timing correction validated automatically; physical acceptance open. Live sequence: `FWPlan.md`.
Pre-implementation comparison/rollback HEAD: `a90c0f0d26cc80e7739cc39fbe81e1c1d4e943d7`.

## Foundation and ownership

- `rendering/transition_registry.py`: the single canonical Slide descriptor; keep identity/pool/activation unchanged.
- `core/settings/default_settings.py`, `settings_manager.py`: canonical `transitions.slide` configuration/default merge.
- `ui/tabs/transitions_tab.py`: lazy Slide detail construction, hydration and guarded save of built pages.
- `rendering/quick/transitions/request_resolution.py`: resolve direction once and freeze motion configuration into
  the existing immutable request, with no heavy renderer import at the Settings/catalog boundary.
- `rendering/quick/transitions/state.py`: `TransitionRun.sample()` owns monotonic progress and completion/cancellation.
- `rendering/quick/transitions/implementations/slide.py`: one shader/fullscreen quad/program, one sealed image
  partition and `_slide_partition_sample` analytical oracle; `QuickTransitionRenderHost` owns lazy lifetime.
- `rendering/quick/render/background_node.py`: existing QSGRenderNode/GL-state fence and source/destination textures.
- `tests/test_qtquick_transition_implementations.py`, `test_qtquick_transition_request_resolution.py`,
  `test_qtquick_transition_uniform_wiring.py`, `test_transitions_tab_setup.py`: focused existing seams.
- `tools/qtquick_render_node_smoke.py`: real Quick/context/lifecycle and Slide image-sampling oracle.

## Feature contract and primitive decisions

`Slide` keeps four cardinal directions and one progress sample. A single `transitions.slide.motion_style` choice
defaults to `Linear`, preserving present behavior. Elastic, Wobble and Flex are options of Slide, never new IDs.
One choice avoids speculative cross-product settings. The renderer consumes frozen per-run parameters only.

Elastic is deterministic bounded travel/overshoot/rebound from the existing eased run progress, with exact
endpoints. Both image ownership and sampling derive from the same displaced coordinate. Overshoot
past arrival retains full destination coverage and samples from the arrived destination coordinate, clamped only at
the departing edge, rather than wrapping an opposite-image strip across the screen. No unowned/black background
branch, CPU integration, second clock or resources.

Wobble may apply a bounded perpendicular two-harmonic UV displacement under an endpoint-zero travel envelope;
clamp orthogonal UVs to prevent texture wrap. Flex may use a bounded spatially varying travel field in the same
full-screen partition; every output pixel still selects exactly one image. Implement only styles that can be
proved and visually assessed. Perspective is a separate remaining slice requiring true shallow 3D geometry and
sealed coverage, not a 2D approximation labelled as perspective.

All new equations, style metadata and shader branches are **feature-local**. Reuse the proven request/run,
textures, quad, GL fence and resource release. Generic modifier graphs, spring runtimes, mesh/camera infrastructure
and combination frameworks are **speculative reuse deferred**. No timers, polling, workers, per-frame objects or
Visualizer state/cadence changes.

## Resumable checkpoints

- [x] Inventory current production seams and commit this decomposition before substantial implementation.
- [x] Add frozen style resolution and the canonical default; reject invalid authored style values explicitly.
- [x] Implement Elastic and focused dense endpoint/coverage/overshoot/uniform/resource tests.
- [x] Implement Wobble/Flex with equivalent deterministic coverage and endpoint proof.
- [x] Expose proven options on lazy Slide detail, preserving choices through load/save/recreation and unbuilt saves.
- [x] Run real GL oracle and inspect representative captures; update contracts and checkpoint.
- [ ] **Remaining:** separately design true Perspective and any specifically justified combinations.

## Timing correction

The operator reports slow travel followed by a sudden elastic jump. Source proves a velocity discontinuity:
the old arrival equation changes slope from 1 to 10 at progress 0.78, concentrating settlement in the last
22% of eased progress. This is independent of rendering cadence and requires no new timer or frame filter.

- [x] Attribute the discontinuity to the feature-local travel equation, not the shared transition clock.
- [x] Replace the late branch with three joined quintic travel segments: source to 1.018 at progress 0.78,
  rebound to 0.995 at 0.90, then destination at 1. Each joins with zero first/second derivative; full travel
  and settlement share one continuous velocity/acceleration contract. Preserve the existing run easing.
- [x] Make Wobble/Flex deformation envelopes have zero endpoint velocity, avoiding an abrupt warp stop.
- [x] Numerically bound speed and compare one-sided velocity/acceleration at joins; preserve dense sealed
  coverage, exact endpoints and real GL source/destination texel evidence across all four directions.
- [x] Focused Slide/transition/GL/uniform gates pass (106 tests); physical settlement/refresh acceptance remains open.

## Acceptance bars

- **Deterministic:** all four directions, dense progress/pixel centres, unique source/destination ownership, exact
  source at zero and destination at one, repeatable analytic motion, frozen requests and sensitivity to style.
- **Lifecycle/resource:** same lazy program/quad/textures; no work/resources for deactivated Slide; interrupted
  runs retain exactly-once completion and existing legal context release.
- **Performance:** one draw, no new buffer/texture allocation or cadence; bounded constant shader arithmetic.
  Measure representative frame cost separately from visual acceptance; do not claim physical timing from callbacks.
- **Visual/operator:** arrival overshoot reads as subtle settlement, wobble/flex preserve image identity and
  coverage, no wrap strips/black/stale flashes, appropriate behavior at 60/165 Hz and mixed DPR. Eyes-on runtime
  acceptance remains open even if automated endpoint/pixel tests pass.
