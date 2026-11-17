# R-239: Bubble's hero mask clipped its own antialias fringe

**Repaired 17 November 2026 (058ab3291, merged in 4227fede0); found by the N5.1 native port's rule (a).** Long-lived and
silent: the shipping Python Bubble drew it since its ambient layer gained the hero mask.

## What was wrong

Bubble's ambience (micro-bubbles and particles) is drawn into an ambient target, and every hero bubble erases the
ambience under it through a mask pass (`bubble_ambient_mask.vert` / `.frag`; `bubble_ambient_gl.py`
`_draw_occluders`). The mask's fragment antialiases the circle's edge over about one texel of `fwidth` support, which
reaches past the circle's radius. Its geometry ended exactly at the circle: CPU triangles before 903396393, then an
instanced quad of exactly the circle's diameter. The antialias fringe outside the radius was therefore never
rasterised. Where the quad's edge was tangent to the circle (its top, bottom, left and right) the erase stopped on a
straight segment instead of a soft arc; elsewhere the fringe was simply cut. Nothing failed and nothing logged: the
ambience showed short straight edges against hero bubbles, worst at input 218 of the 5.5 s replay.

## How it was found

The native port draws the same mask shader through the core. Its rule (a) residual clustered on hero edges, and a
reference-fringe probe showed the Python reference's own fringe was the clipped one
(`Docs/Future_Work/Native_Bubble_Parity_Investigation.md`, "Mask antialias repair: accepted").

## The repair

The mask's quad is padded by the fragment's antialias support (`2 * max(2, 0.0001 * r)` px) and its unit-circle
varying is rescaled by `padded / diameter`, an affine map, so the circle itself is unchanged and only the fringe is
restored. Both renderers draw the one shader file, so the Python Bubble and the native port change together.

## Proof

- The fringe gate (`.artifacts/evidence/native_core/n5_1_bubble/20261117_mask_fringe_gate/fringe_gate.json`): the
  repair changes 3,862 Python pixels over 342 inputs (3,556 by one level, at most nine), every one within 1.32 px of a
  live hero circle; the same gate with the circles displaced by 8 px fails 2,454 of them.
- The old vertex shader's archive reproduces all 549 retained Python hashes exactly (the control,
  `20261117_mask_reference_old_control`); the current one is `20261117_mask_reference_current`.
- Checkpoint audit 7 reran the negative control: the old shader gives [0, 127, 127, 0] at the four cardinal points of
  the new test, the repaired one [127, 127, 127, 127] (`tests/test_bubble_ambient_big_occlusion.py`).

## Known follow-up

A sub-pixel hero circle now erases a fixed soft dot of about 0.7 px² (checkpoint audit 7 L2: cosmetic; the simulation
floors the radius at 0.001), left as the lead decided.
