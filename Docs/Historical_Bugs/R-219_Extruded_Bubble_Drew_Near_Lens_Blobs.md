# R-219 | Extruded Bubble drew a large bubble near the camera as a defocused blob on the lens

**Status:** fixed 14 Nov 2026 (plan item 1B.10, found in the lead's review of the "Under The Ice" preset). Operator
rule (14 Nov): "We never ever want near lens blobs."

`ebLens` (`rendering/gl_programs/extruded_bubble_program.py`) is the render-only proximity owner for ordinary shells
and fused clusters. It now eases a shell out as its lens circle grows past `EB_LENS_FADE`:
- fully drawn below 0.15 of the near layer's budget;
- gone at 0.45 of it;
- back in as the shell leaves.

The shell fades and never vanishes at once. Mild near defocus is kept. The logical simulation (radii, identities,
motion) is untouched.

Regression bar: `tests/test_extruded_bubble_world_gpu.py`, with the contract rewritten on the operator's rule. These
assertions replace the old "a near giant draws as full-opacity bokeh" ones:
- a shell spanning half the view draws in neither pass, on every card size, tall cards included;
- nearing that size it already blurs at zero aperture, through the near pass only, still almost fully drawn;
- approaching the lens its opacity falls without ever rising, through partial values, to nothing before it fills
  the view;
- an off-axis shell's energy falls as its surface nears the eye;
- the eye inside a fused pair's bound draws nothing, while the same pair farther off draws without filling the gap.

Negative control: with the fade disabled (`EB_LENS_FADE` set past the budget), 8 of those cases fail.

## Symptom

"Under The Ice" (camera tilted up at the surface) showed, in its quiet stretch, a large soft bright disc over a pale
crescent in the middle of the card: an out-of-focus bubble on the lens.

## Cause

It was an ordinary large simulated bubble whose stream path passed in front of the focus distance. Proof, by
toggling one thing at a time on the same frame (evidence:
`.artifacts/evidence/visualizers/extruded_bubble/presets/20261114_arctic/near_lens_blob/`):
- No large bubbles: the blob is gone.
- Aperture 0: the blob stays exactly as soft.

`ebLens` sends any shell that covers more than about a third of the frame to the near layer's widest lens circle,
whatever the Aperture setting (the `wide` term), and drew it at full opacity until it covered 78% of the frame or its
surface was within a third of its radius of the eye. Any look whose stream passes near the camera could show it.
Hero Shell (since removed) was 0 and played no part.

## Lesson

A bubble at the lens is not a bubble the viewer can read. Fade it by how defocused it is (its lens circle), not only
by how much of the frame it covers or how close its surface is.
