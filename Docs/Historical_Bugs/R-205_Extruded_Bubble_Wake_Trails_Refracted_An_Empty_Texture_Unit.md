# R-205 | Extruded Bubble's wake trails refracted an empty texture unit instead of the captured background

**Status:** fixed 14 Nov 2026 (Current_Plan 1D.11, first box). Present since Wake Trails landed (f0ead35b, 25 Oct
2026). Owner: `rendering/gl_programs/extruded_bubble_program.py` (the trails' `portable_family` sampler plan).
Regression bar: `tests/test_extruded_bubble_trails_background_gpu.py`, which compiles every pass-block program that
declares `uBackground` and reads the unit GL reports for it; on the code before the fix it failed with
`{'trails': 0} != {'trails': 5}`. Evidence: `.artifacts/evidence/visualizers/extruded_bubble/trails_background/
20261114_before_after/` (before | after on a PERSONALSET wallpaper, playing and idle, full frames and 2x crops).

## Symptom

None reported. The veils behind trailing bubbles looked like slightly dark, smoky glass. Their refraction term
(`bent * a`, up to 0.4 of the veil's alpha) should carry the water, shafts and particles drawn behind them, bent
sideways toward the walls; instead it carried black, so every veil darkened what lay behind it. After the fix,
84,000 to 168,000 pixels per 1600 x 900 frame change while playing (21,000 to 36,000 at idle), by up to 132 of 255.

## Cause

1. The renderer binds the captured background (`SceneTarget.background`) to unit 5 (`_UNIT_BACKGROUND`) before the
   transparent pass, and gives the loose traced-glass programs (shells, clusters, near layer, beads) the uniform
   `uBackground = 5` through `_glass`. The trails program, added in f0ead35b, was never given that value, so its
   sampler kept GL's default unit 0.
2. Unit 0 is never empty by chance: the shafts' separable blur binds its source there and ends with
   `glBindTextureUnit(0, 0)` every frame, before the scene target opens. A sampler on a unit with no texture reads
   (0, 0, 0, 1). Measured at the trails' draw in the offscreen production host: unit 0 = 0, unit 5 = the captured
   background, in every playing and idle frame.
3. N1.6 converted the trails to a std140 pass block and wrote the unit into the shader
   (`samplers={**EB_SAMPLERS, "uBackground": 0}`), on purpose, so the conversion stayed bit-identical; the comment
   called it a defect kept as it was.

## Fix

The trails family takes the shared sampler plan (`samplers=EB_SAMPLERS`): `layout(binding = 5)` on `uBackground`,
the unit the renderer already binds. No renderer change.

## Why it hid

- Black times a small alpha reads as a plausible tint of murky water; nothing errored and every test passed.
- The value came from a uniform that was simply never set. A loose sampler's default unit is 0, so a missing
  `glUniform1i` is invisible unless something checks the unit a program actually reads.
- Unit 0 was always empty within EB's frame (the shafts' blur clears it), so the frames were stable and never hinted
  at a stray texture.

## Lessons

1. A sampler's unit is part of a program's contract with its renderer. Test it by asking GL which unit the linked
   program reads (`glGetUniformiv`), against the renderer's own constant, for every program that declares it.
2. A conversion that keeps a known defect bit-identical needs a plan box for the defect in the same commit (N1.6 had
   one: 1D.11).
