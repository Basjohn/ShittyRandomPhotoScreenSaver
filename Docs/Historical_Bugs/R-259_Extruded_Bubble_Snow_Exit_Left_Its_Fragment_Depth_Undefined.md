# R-259: Extruded Bubble's marine snow tested an undefined depth (its exit left gl_FragDepth unwritten)

**28 November 2026. Fixed in the shader source (`rendering/gl_programs/extruded_bubble_program.py`, BUBBLE_FRAGMENT),
commit `7a089950b`; packs `eb_beads.frag.qsb` and `eb_shells.frag.qsb` rebaked, no module change. Found by N5.6's
native self-comparison: two Vulkan runs of one delivery differed on 2,576 of 2,586 frames (p50 68 px, max 149 levels),
which made rule (b) unjudgeable.**

## What happened

The glass passes (shells, beads, clusters) draw into the scene's transparency target: weighted OIT that borrows the
scene's 4x depth, tests it "less" and never writes it. Their fragment shader writes `gl_FragDepth` (the sphere's
depth at the fragment, `sceneSphereDepth`), so the test compares the impostor's true surface and not the quad's.

BUBBLE_FRAGMENT has several exits. The marine-snow one (`vExtra.y` near 1, outside `NEAR_LAYER`) drew its glitter
with `sceneTransparent` and returned without writing `gl_FragDepth`. GLSL says a shader that statically writes
`gl_FragDepth` leaves it undefined on any path that does not. The depth test then compared whatever the hardware
held, so snow fragments were kept or rejected at random, differently on every run and every frame. Nothing reported it:
synchronisation validation was clean (only Qt's known VUID-12478), and each frame looked plausible on its own.

Python draws the same BUBBLE_FRAGMENT, so its references carried the same exit; whether earlier references varied run to
run was not measured.

## How it was found

On the smoke delivery, two Vulkan runs were compared while families were removed and inputs pinned
(`.artifacts/scratch/n56c/vk_self.py`, edits baked into packs on the fly):

- snow alone still differed; with drift reads zeroed, fixed snow uniforms and constant snow positions it still did;
- making the snow's depth test pass by any means (`gl_FragDepth = 0`, `= gl_FragCoord.z`, the beads pass at depth
  "always") made the runs identical 8/8, and those variants agreed with each other frame for frame, so the rejections
  were spurious;
- discarding near-plane fragments or refreshing the depth through the backdrop changed nothing;
- removing the shells' and clusters' depth writes reduced the differences, which pointed at an unwritten-depth path.

## The fix

The snow exit writes `gl_FragDepth = sceneSphereDepth(front, uProjection)` before it returns, as its sibling exits do.
The sorted (fallback) packs are unchanged: their bake strips depth writes.

## Proof

- `tests/test_native_eb_shaders.py::test_every_exit_of_a_depth_writing_glass_fragment_writes_its_depth` preprocesses
  each transparent `eb_*.frag` text and the Python BUBBLE_FRAGMENT and CLUSTER_FRAGMENT, walks every `return` and the
  end of `main`, and fails any exit that leaves the depth unwritten. It failed on the pre-fix source (BUBBLE_FRAGMENT,
  `eb_beads.frag`, `eb_shells.frag`: one unwritten exit each); a synthetic control removes the snow write and expects 1.
- Vulkan, two runs of `l_human_heavy1_base`, 400 inputs: identical 400/400
  (`.artifacts/evidence/native_core/n5_6/20261128_vulkan_self_identical/`).
- OpenGL, the same delivery (`.artifacts/evidence/native_core/n5_6/20261128_opengl_self_after_snow_fix/`): with the
  fix reverted 342/400 frames differ, up to 255 levels (most 114-164); with it 324/400 still differ, p50 254 px,
  mostly 1-7 levels (two frames at 30 and 38), scattered speck and glint pixels. The snow's share is gone; the
  OpenGL-only remainder is a separate cause, recorded under N5.6.

## Rule

A shader that writes `gl_FragDepth` writes it on every exit that is not a `discard`. A new exit in such a shader is
checked by the exit walk above, not by eye.
