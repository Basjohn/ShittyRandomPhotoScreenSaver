# R-218 | Glow, light shafts and the Neon sky stepped into 8-bit contour bands

**Status:** fixed 14 Nov 2026 (plan item 1B.10, found in the lead's review of the Neon Lake presets).
`rendering/gl_programs/scene3d.py` owns one dither, `SCENE_OUTPUT_DITHER_GLSL` (`sceneOutputDither`): a triangular
dither of one 8-bit output step per channel at a pixel, built on the exact integer hash (R-94). It has a mean of zero
and gives the same value at a pixel every frame. Two writers use it:
- The overlay-bloom composites (`rendering/quick/scene3d/target.py`, `sceneOverlayBloom`, with the light-shaft,
  multisampled and oriented variants) add it only where they add glow (`SCENE_DITHER_FLOOR`). A pixel without glow
  (a photograph, the empty card) stays exact.
- Neon Lake's sky background pass (`neon_lake_basin_program.NEON_SKY_FRAGMENT_SOURCE`) adds it to its gradient before
  the 8-bit scene colour stores it.

Regression bar: `tests/test_scene_output_dither.py`.
- A GPU probe writes a gradient four output steps wide over 256 px to an 8-bit target. Plain, it stands flat for a
  quarter of the width between steps. Dithered, its flat stretches average at most 4 px. It stays within one step of
  the true level, averages to the true level (no tint), and gives the same pixels on every draw.
- Every overlay-glow composite variant dithers, gated on the glow it adds; the shafts join the glow before the gate.
- The Neon sky dithers its background.

Negative control: with the dither scaled to zero, the probe fails (flat stretches average 51 px). Before the change
the test cannot import `SCENE_OUTPUT_DITHER_GLSL`.

## Symptom

Neon Lake's "Red Sun Desert" preset (a dark red sky, a large sun with a wide halo and light rays) showed concentric
rings round the sun and a stair-stepped dark block in the upper left of the sky, where the rays ran out. Raised four
times in level, the 8-bit frame showed each ring as one code value. The block's edge was the last few output steps of
the rays fading over hundreds of pixels. Nothing failed and nothing was logged. Any look with a dark, slowly changing
glow, halo, shaft or sky gradient could show it, in any Visualizer drawn through the overlay-bloom composite.

## Cause

The glow (half-size half-float bloom) and the shafts (half-size R16F) are smooth float light. The composite added
them and wrote the result to Quick's 8-bit target with no dither. The Neon sky wrote its gradient to the scene's 8-bit
colour attachment the same way. In a dark, saturated colour a slow gradient changes one code value every 30-80
pixels, and the eye reads each step as a contour line.

Isolation, by rendering the preset with one feature off at a time and raising the frame's levels four times
(`render_neon_evidence.py stills --preset 5 --look` with `{"sun_rays_enabled": false}` or
`{"volumetric_clouds": false}`, in `.artifacts/evidence/visualizers/shockwave_grid/presets/20261114_round1/`):
- Clouds off: unchanged.
- Rays off: the stair-stepped block was gone and the halo rings remained.
- The rays-only difference image: smooth light, cut into contour bands by the 8-bit write.

The terrain was not the cause: neither the flattened far land nor its mesas reach that part of the sky.

## Lesson

Any smooth light that ends in an 8-bit target needs one output step of dither where it is written. Dither only where
the smooth light is present, so the exact pixels around it stay exact. Use the exact integer hash, so a static frame
does not shimmer and the dither is the same on every GPU.
