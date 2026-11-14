# R-NEW | Bubble, Spline Curve and Oscilloscope took derivatives after a discard (undefined at the content edge on OpenGL too)

**Status:** fixed 14 Nov 2026 (N2.5 leftover "Derivatives after a `discard`", with audit 14 Nov N25 L5). The three
shaders take every derivative before the first discard a pixel can take alone, in uniform control flow:
`bubble.frag` reads its pixel footprint (`dFdx`/`dFdy` of `uv.y`) and both ambient textures (implicit-LOD `texture`)
before its content-rect discard; `devcurve.frag` and `oscilloscope.frag` move their content-rect discard to the end
of `main`, `_draw_layer` takes its `fwidth` before its early return, and `_specular_lobe`'s idle-slot test moved to a
uniform `if` at the call. Regression bar: `tests/test_shader_derivatives.py` now binds every 2D mode's shader and
refuses the four shapes the first guard admitted (a helper's early return before its derivative, a derivative in a
non-uniform branch, a discarding helper called first, an implicit-LOD `texture` after a discard); a discard or return
on uniforms alone is not an exit. Negative control: the shaders before the fix give 4, 10 and 12 findings.

## Symptom

None reported: a 2x2 quad straddling the content rect's edge (its outer pixel discarded) took the derivative with
one lane gone. R-210 assumed OpenGL keeps that lane running as a helper; on this NVIDIA OpenGL driver the outcome was
not the helper's value. Drawing the same frames before and after the fix (`conventions_identity` runs, both spec
variants and every Choice offer, every frame) changed only pixels on the content's first or last row or column:
Bubble up to 21 levels (about 28 px a frame where a bubble outline or wake meets the edge), Spline Curve up to 18
levels (one or two px a frame where an outline meets a side), and in a direct draw of `oscilloscope.frag` with the
card edge off the 2x2 grid, a whole edge pixel lost (223 levels) in every straddling quad.

## Cause

Each shader discarded outside its content rect first and then took derivatives (`fwidth` of the curve distance,
`dFdx`/`dFdy` of the pixel footprint, implicit-LOD texture reads), directly or in helpers. A derivative in a quad with
a discarded lane is undefined in GLSL; Vulkan's discard ends the lane outright (R-210).

## Lesson

R-210's "OpenGL keeps a discarded lane as a helper" is not a guarantee even on OpenGL: the pixels next to a
non-uniform discard read whatever the driver leaves. Take every derivative, implicit ones included, before a lane can
leave, and let the guard be the judge.
