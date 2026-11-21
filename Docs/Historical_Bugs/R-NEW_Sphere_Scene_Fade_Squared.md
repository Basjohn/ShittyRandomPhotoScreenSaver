# R-NEW | Sphere's scene fade was squared

**Status:** fixed and proved 21 Nov 2026 (reproduction, guard test with its control, a rendered old/new pair).

Sphere's shader fade `uFade` was `presentation.scene_fade * presentation.content_fade`
(`rendering/quick/visualizer/implementations/sphere_voxel.py`, since 49086dbf4, September). The render owner already
folds the scene opacity into the content fade (`render_contract.scene_faded_snapshot`, R-242; before R-242 the node
folded Qt's inherited opacity the same way), so the scene fade reached Sphere's fragments twice. At a scene fade of
0.5 the shader drew 0.25; at 0.3, 0.09. Every Sphere reveal (the first appearance fade and the startup reveal gate)
ran along the square of the intended curve: slower to appear, and the first frames nearly invisible. Silent: the
fade still ended at 1, and no other mode multiplied `scene_fade` itself, so nothing compared. Found by N5.3's source
reading of the Extruded Spectrum and Sphere ports, not an R-242 regression (R-242 changed the other modes' path).

Fix: `uFade` is the content fade alone. Reproduced first: a Sphere snapshot taken through `scene_faded_snapshot` at
scene fade 0.5 (the presentation's `scene_fade` set to 0.5, as the product has it) gave `uFade` 0.25 on the old code,
0.5 now. Guard: `tests/test_sphere_scene_fade_once.py` (seen failing at 0.25 on the old line). Evidence (old drawn by
squaring the value back in, new as shipped, on a PERSONALSET wallpaper, scene fade 0.15-1.0):
`.artifacts/evidence/visualizers/sphere/20261121_scene_fade_pair/sheet.png`.

Lesson: a value that reaches a shader through the render owner's fold is never multiplied in again by a mode; the
presentation's `scene_fade` is the authored fade the owner folds, not a second input.
