# R-253: Native scene transitions carried velocity in two 4x R16F attachments (fixed 28 Nov 2026)

## Failure

Native scene transitions with motion blur and 4x MSAA cost far more on OpenGL than Python's renderer on the same
frames. At 4K, `crumble_both_4x` took 1.289 ms of core GPU time against Python's 0.925. The cost was silent: nothing
looked wrong, and only N5.2h's cost gate (native at or below Python before the background switch) found it.

The native scene target split velocity into two single-channel R16F attachments, x and y, each 4x multisampled.
Every frame paid to clear, write and QRhi-resolve both. Python uses one RG16F attachment.

A raw-GL probe of the same target shapes at 4K:

| Velocity storage | ms |
|---|---|
| Native, two R16F | 0.855 |
| One RGBA16F, cleared by glClear | 0.510 |
| Python, one RG16F | 0.380 |

Depth format (D32F against D24) made no difference.

## Fix

- `5359b9264`: velocity is now one RGBA16F attachment, read as `.xy`; QRhi has no RG16F. The y-only output and the
  second velocity sampler are gone (`native_background.scene_program`).
- `121087442`: on OpenGL, `scenePassClearColour` (`native/core/src/scene_targets.cpp`) lets the pass's own glClear
  clear the multisampled RGBA16F target instead of a clearing draw (0.022 ms against 0.058). The velocity's unread
  alpha clears to the colour's, so both attachments share one clear colour.
- After `5359b9264`, 4K `crumble_both_4x` costs 0.944 ms on OpenGL (Python 0.925), and Vulkan drops from 0.874 to
  0.735 ms. The rest of the gap is RGBA16F holding twice RG16F's bytes. The fidelity route check (16 motion, trail and
  bloom variants, both APIs, validation on) passes.

## Related find

`d5e9371ab`: the ghost (trail) passes drew between scene passes. That split the 4x scene target into two runs, and
each run paid its own multisampled resolves. Ghosts now draw first, so the scene target is one run
(`scene_target_runs` test).

## Guards

- `tests/test_native_scene_transitions.py` and `tests/test_native_surface_clear_route.py`. They cover the
  one-attachment velocity layout, the pass-clear route and the single scene run, each with a negative control seen
  failing.
- `transition_route_check.py --cost` per-pass and run-part timing (`time_scene_passes`, `time_scene_run_parts`),
  opt-in harness controls with no cost at rest.
- Evidence: `.artifacts/evidence/native_core/n5_2h/20261128_n52h_velocity_*`.
