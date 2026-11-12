# R-191 | Visualizer content lay under the card frame's anti-aliased inner edge, so bright lines read as reaching into the border

**Status:** fixed 12 Nov 2026 (plan 1C.4). The card is drawn on whole device pixels and the Visualizer clip ends
exactly at the frame's inner edge as Qt Quick draws it: `widgets/spotify_visualizer/presentation_geometry.py`
(`resolve_card_drawn_rect`, `resolve_card_clip_path`), used by the scene's projection
(`QuickSceneController._apply_visualizer_presentation_items`) and the render node's clip (resolved once per record at
sync, `VisualizerClipFrame.local_geometry`); pixel shift moves the cards by whole device pixels
(`QuickSceneController.apply_auxiliary_state`). Regression bar: `tests/test_visualizer_card_clip_contract.py` (every
registered mode, Normal and Glass, 100/125/150 %, a card requested off the device-pixel grid, a full-brightness white
line along every edge: no content under any straight-edge frame pixel, none under a corner pixel the frame covers by
more than half, no card surface between frame and content; red on the pre-fix clip, on an unsnapped card and on an
inset clip), `tests/test_qtquick_visualizer_geometry.py`, `tests/test_qtquick_visualizer_item.py`,
`tests/test_qtquick_auxiliary.py`.

## Symptom

Operator, after R-188: Spline Curve's white lines still show "1px or so" into the card border. The lead's Display 1
run (12 Nov) found no content pixel inside the border band, but the border's inner edge pixel was a 50/50 blend of the
border colour and the content under it: (130,114,153) over dark content, (191,132,218) over magenta fill, about
(232,216,255) over a white line, which reads as the line reaching one pixel into the border.

## Cause

The clip ended exactly at the content rect, which the resolver puts `border_width` inside the outer edge. The frame is
a Qt Quick `Rectangle` with a radius, so it is anti-aliased: a one-device-pixel ramp centred on each edge (measured on
the hidden production host). Wherever the card's edge falls inside a device pixel (pixel shift in logical pixels at
125/150 %, CUSTOM scale, centred layouts), the frame's inner edge pixel is part frame and part whatever is beneath it,
and the clip let content be beneath it. Qt also rounds the pen to whole device pixels (`border.pixelAligned`), so at
125 % and 150 % the frame's real inner edge differs from the record's by up to half a device pixel. Every carded mode
had it; most leave the card's edges dark, so the blend pixel looked like part of the border, and Spline Curve's white
lines at the edges made it visible.

## Fix and evidence

Only the card's drawing snaps (origin and size each to the nearest device pixel, at most half a pixel): the record
(outer and content rects, world, extent, scale) stays the exact geometry every consumer derives from, and the content
moves rigidly with the drawn card. Snapping the record itself was tried first and perturbed derived geometry across
the product (the expanded card's world/scale exactness, the Studio's lens parity, Edit's footprint, Bubble's specular
reference: 57 test reds), so it was dropped. The clip ends exactly at the frame's inner edge; no shader, uniform or GL
call changed, so the protected QSG/clip optimisations (`ce07b991`, `07486d83`, `985b9d53`) are untouched. A first fix
(`938aee6f`: clip one device pixel inside the frame, card unsnapped) removed the blend but left a dark seam of card
surface between frame and content; it was not accepted (a seam is a defect). Comparison of that inset, the snapped
card, and a composited corner-coverage variant (1x and 4x, white lines and Spline Curve's real frame, Normal and Glass,
100/125/150 %, with counts): `.artifacts/evidence/visualizers/20261112_1c4_variants/`.

## Lesson

A clip that meets an anti-aliased frame must not leave the frame's edge pixel half over content: put the frame's edge
on the pixel grid (where the toolkit draws it, pen rounding included) instead of insetting the clip, which trades a
bright fringe for a dark seam. Snap the drawing, not the geometry record that everything else derives from. A pixel
test on a card placed on the device-pixel grid at 100 % cannot see any of it.
