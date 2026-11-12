# R-NEW | Visualizer content lay under the card frame's anti-aliased inner edge, so bright lines read as reaching into the border

**Status:** fixed 12 Nov 2026 (plan 1C.4; commits 938aee6f, d1b989b4). The Visualizer clip now ends one device pixel
(the frame's anti-aliasing width) inside the frame's inner edge as Qt Quick draws it:
`widgets/spotify_visualizer/presentation_geometry.py::resolve_card_clip_path`, consumed by
`VisualizerClipFrame.from_presentation` (`rendering/quick/visualizer/clip_host.py`). Regression bar:
`tests/test_visualizer_card_clip_contract.py` (every registered mode, Normal and Glass, 100/125/150 %, a card off the
device-pixel grid, a full-brightness white line along every edge; every pixel the frame covers must equal the frame
with the Visualizer hidden; red on the pre-fix clip for every case) and `tests/test_qtquick_visualizer_item.py`.

## Symptom

Operator, after R-188: Spline Curve's white lines still show "1px or so" into the card border. The lead's Display 1
run (12 Nov) found no content pixel inside the border band, but the border's inner edge pixel was a 50/50 blend of the
border colour and the content under it: (130,114,153) over dark content, (191,132,218) over magenta fill, about
(232,216,255) over a white line, which reads as the line reaching one pixel into the border.

## Cause

The clip ended exactly at the content rect, which the resolver puts `border_width` inside the outer edge. The frame is
a Qt Quick `Rectangle` with a radius, so it is anti-aliased: a one-device-pixel ramp centred on each edge (measured on
the hidden production host). Wherever the inner edge falls inside a device pixel (an off-grid card, a fractional DPR),
that pixel is part frame and part whatever is beneath it, and the clip let content be beneath it. Qt also rounds the
pen to whole device pixels (`border.pixelAligned`), so at 125 % and 150 % the frame's real inner edge differs from the
record's by up to half a device pixel. On the rounded corners Qt's tessellated ramp reaches further still (up to 18 %
coverage 0.56 device pixel inside the arc, also onto the straight edges next to the corners). Every carded mode had
it; most leave the card's edges dark, so the blend pixel looked like part of the border, and Spline Curve's white
lines at the edges made it visible.

## Fix and evidence

The canonical resolver derives the clip path from the frame's own geometry: inner edge at `round(border_width * dpr)`
device pixels, then one anti-aliasing width further in, corners as the parallel curve. `content_rect` (the authored
content geometry, R-21) is unchanged; no shader, uniform or GL call changed, so the protected QSG/clip optimisations
(`ce07b991`, `07486d83`, `985b9d53`) are untouched. Half a pixel (enough on straight edges) and a wider corner alone
were both measured and left corner pixels with 5-18 % frame coverage. Trade-off: depending on where the edge falls
within a pixel, up to one device pixel of the card's own surface shows between the frame's edge pixel and the content.
Before/after 4x crops (left edge, both bottom corners, 100/125/150 %, Normal and Glass) and the frame-pixel table:
`.artifacts/evidence/visualizers/20261112_1c4_card_frame_edge/`.

## Lesson

A clip that meets an anti-aliased frame must end where the frame's coverage ends, not at its geometric edge; and the
frame's edge is where the toolkit draws it (pen rounding), not where the record says. A pixel test on a card placed on
the device-pixel grid at 100 % cannot see either.
