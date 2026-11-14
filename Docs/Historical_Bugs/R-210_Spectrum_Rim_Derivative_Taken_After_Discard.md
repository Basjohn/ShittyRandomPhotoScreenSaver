# R-210 | Spectrum's rim derivative was taken after discard (undefined; differed by driver)

**Status:** fixed 14 Nov 2026 (plan item 8b, N2.5 rule (b), found by the native port's Vulkan parity check).
`widgets/spotify_visualizer/shaders/spectrum.frag` now takes every derivative in a prologue at the top of `main`,
before the first `discard` or `return`: the item-pixel size (`g_px_x`/`g_px_y`) and the rim's coverage feather
(`spectrum_rim_coverage`, for both the single-piece and the segmented path). The prologue computes the geometry the
derivatives read for every pixel, in the bar field or not (the bar read is clamped to a real bar); the discards
follow it as before, in their original order. Regression bar: `tests/test_shader_derivatives.py` refuses a
derivative (`fwidth`/`dFdx`/`dFdy` in any precision, or a call to a function that takes one) after the first
`discard` or `return` in `main`, and a deriving function that discards, in every mode the native route draws
(`NATIVE_MODE_IDS`). Its negative control is the shader before the fix: 6 findings.

## Symptom

The native core's Spectrum on Vulkan differed from the same shader on OpenGL in 128 of 162 sampled frames, by up to
15 levels, at the rounded corners of the bar tops (N2.5 round 2 to round 5). `fwidthFine` in place of `fwidth`
(round 3) and `precise` arithmetic in the corner tests (round 5) changed nothing.

## Cause

The rim glow's coverage feather was `fwidth` of the distance to the bar's edge, computed after the shader had
already discarded pixels (outside the bar field, in the gaps, outside the rounded corners) and returned early
(peak caps). A derivative in non-uniform control flow is undefined in GLSL: the quad's other lanes may be gone.
OpenGL's driver keeps a discarded lane running as a helper, so its neighbour's derivative still saw a value; Vulkan's
`discard` (SPIR-V `OpKill`) ends the lane. All 5,652 Vulkan pixels more than one level off shared a 2x2 quad with a
discarded pixel (14.9 % of randomly chosen lit pixels do). `GL_EXT_demote_to_helper_invocation` would keep the
helpers, but the shader baker compiles plain GLSL and refuses the extension. The OpenGL picture itself rested on one
driver's helper behaviour; since the Quick renderer it had never been drawn by a second one.

## Fix and evidence

With every derivative taken before any lane leaves:

- Vulkan against native OpenGL: 72 of 162 frames differ, max 1 level (was 128 of 162, max 15)
  (`.artifacts/evidence/native_core/n2_5/20261114_n25_round5_hoist/`, re-measured on the final pack in
  `20261114_n25_prologue/`). Native OpenGL still equals the Python renderer: both read the same `spectrum.frag`.
- The OpenGL picture moved in bars mode only, at bar-top corners: about 60 pixels per changed frame, max 16 levels
  on the default run (357 of 549 frames changed); the segmented mode and variant b are bit-identical at all 18 runs
  of the widened set (`conventions_identity` records `20261114_frag_window_rebuild` against `20261114_frag_prologue`).
  Crops of the worst frame (4x, and the difference x64): `20261114_prologue_gl_crops/`.

## Lesson

Take every derivative where control flow is still uniform: before the first `discard` or early `return`. A
derivative after one reads whatever the driver leaves in the quad, so a shader can look right on one backend for
years and differ on the next. The guard binds every native port; Oscilloscope, Bubble and Spline Curve still take
derivatives after a discard and must be fixed before their N5 ports admit them.
