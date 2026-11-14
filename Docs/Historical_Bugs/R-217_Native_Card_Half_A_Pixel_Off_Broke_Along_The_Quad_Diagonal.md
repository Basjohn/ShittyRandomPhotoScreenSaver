# R-217 | The native Visualizer item sat half a device pixel off its card, and the composite's quad broke the bars along its diagonal on Vulkan

**Status:** fixed 14 Nov 2026 (Current_Plan N2.8, the operator's defect box), in two parts. The owner (Python, landed
on ABI 12): the native route places its item relative to the content host's real origin, the drawn card. The core
(C++, ABI 13, proved in the build round): the composite's vertex stage puts the item's quad on whole pixels of its
render target wherever the item is placed. Regression bars: `tests/test_native_visualizer_route.py::
test_the_native_item_lies_on_whole_window_pixels_in_the_drawn_card_host` (red on the pre-fix route);
`native/core/python/spectrum_check.py`'s pixels and seam rounds at every `PLACEMENTS` entry (the seam round red on
ABI 12's Vulkan at the half-pixel placement: 57 of 57 counts); `tools/visualizer_replay/owner_render_parity.py
--native`'s `overscan` placement (Display 1's R-63 window, the card's origin half a device pixel off the grid).

## Symptom

On Display 1 (3840 x 2163 device pixels at 150 %, the window 3 device rows above its monitor for the R-63 overscan) the
native Spectrum card on Vulkan showed a thin slanted line from its bottom-left corner up to its top-right: below and
left of it every bar was one device pixel further left, so bar borders broke along the line (with a transparent fill
and an outline, a rainbow-like break). OpenGL, drawn by the Python renderer, was clean. It persisted at ABI 12. A
hidden-host reproduction placing the card on whole device pixels was green at every size.

## Cause

The scene draws the card on whole device pixels (1C.4: `resolve_card_drawn_rect` snaps the record's outer rect by up to
half a pixel) and puts the Visualizer's loader, and so its content host, at that drawn rect. The native route placed
its item in the content host relative to the record's exact outer origin instead
(`NativeVisualizerRoute._sync`: `origin = presentation.outer_rect[:2]`, a comment saying the host lay there). Wherever the
outer origin was off the grid, the item lay off it by the difference: on the operator's card by half a pixel.

The composite reads its content texel-exact: the fragment's item pixel is `floor(v_uv x the item's device size)`, whose
thresholds lie on pixel edges only while the item's origin is on a pixel corner (R-197). At a half-pixel origin every
pixel centre fell exactly on a threshold, and each of the two triangles of Qt's textured-rect strip (TL, BL, TR, BR:
their shared edge runs from the bottom-left to the top-right corner) interpolated `v_uv` to its own side of it in the
last bits. Vulkan's lower-left triangle read the texel one to the right; OpenGL's happened to agree. The hidden-host
repro placed its content host at the record's outer origin, as the route assumed, so it never saw the offset.

Reproduced in the hidden host by placing the content host where the scene puts it (the drawn rect) inside a scene 3
device rows down, at half-pixel outer origins: Vulkan broke 785 of 808 band rows along the item's diagonal, OpenGL none
(`.artifacts/evidence/visualizers/spectrum/border_diagonal/20261114_quad_seam/`, `summary_before.txt` and the
`vulkan_*_route_*.png` frames).

## Fix and evidence

- The route's origin is `native_route.content_host_origin` (the drawn rect's origin, the scene's one resolution): the
  item's device origin is the composite rect's, on whole (even) device pixels. The repro is green on ABI 12 with it
  (`summary_route_fixed.txt`); rule (a) on ABI 12 is hash-identical with and without it on the rig's whole-pixel card.
- The card's item is the Python renderer's (`spectrum_presentation(host_origin, item_origin)`): it lies at the content
  host and, in the window, wherever the display lies (the route reads the host's scene position). Before, the card
  modelled an item at the outer origin with the display at the window's origin; that matched the Python content only
  while the native item itself sat half a pixel off. Found by the new owner-level placement: with the route fix alone,
  rule (a) at `spectrum@overscan` was 237 levels off; with both, max 1 level and the window map float32-identical to
  the Python renderer's (392 of 392); the pre-fix route there is 236 levels off on OpenGL too
  (`.artifacts/evidence/native_core/n2_8/20261114_quad_seam_rule_a_overscan_abi12_{fixed,control}/`).
- `composite.vert` moves the item's origin onto the nearest pixel corner of its render target and the quad rigidly with
  it, computed from the block alone (the new `viewport` member, Qt's `viewportRect`) and independent of the backend's
  NDC and framebuffer orientation; the item's state reports the shift (`origin_shift`). A composite placed anywhere is
  a pure copy; one already on whole pixels moves by float rounding only.
- The parity harnesses draw the class: `spectrum_check`'s pixels and seam rounds at a half and a quarter pixel in a
  scene under an overscan (Vulkan against OpenGL per placement; `origin_shift` proves each placement), and
  `owner_render_parity --native`'s `overscan` placement (an R-63 window, the authored origin half a device pixel off).

## Lesson

A child placed relative to its parent must use the parent's real origin, read from the owner that places the parent,
never a value the parent was once at. A texel-exact read keyed on interpolated coordinates is exact only while its
thresholds stay off the pixel centres: place the geometry on whole pixels at the draw (the vertex stage), not by trust
in every caller. A reproduction must place things the way the product does, offsets included.
