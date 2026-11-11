# R-187 | The Visualizer's card clip followed the retained snapshot's record, not the card being drawn, so a mode could paint past the card's rounded corners

**Status:** fixed 11 Nov 2026 (plan 1C.4). `rendering/quick/visualizer/node.py` builds the stencil clip from the record
the scene draws the card from at this sync (the retained `VisualizerRenderItem`'s own, handed to
`VisualizerRenderNode.synchronize(presentation=...)`), never from the snapshot it keeps. Regression bar:
`tests/test_visualizer_card_clip_contract.py` (every registered mode, Normal and Glass card material, the ordinary card,
the display-wide card, a card shrunk and a card collapsed from display-wide before a coherent snapshot exists; red on
the pre-fix node for every carded mode, green after).

## Symptom

Operator, 11 Nov: "Lines from Spline Curve slightly escape our borders, nothing from any visualizer should be capable
of that. Most seen in full but its there in small/normal mode too." The crop showed a magenta band crossing the left
border near its foot: Spline Curve (`devcurve`) fill and outline drawn outside the card's rounded bottom-left corner.

## Cause

The card's content is bounded by one render-node-local clip (`clip_host.py`: an SDF writes a nested stencil value over
the rounded inner path, the mode draws against it). `VisualizerRenderNode.render` built that clip from
`snapshot.presentation`, the record inside the snapshot the node *holds*. Outside CUSTOM, the bridge refuses a
snapshot whose record differs from the item's (`render_bridge.take_for_render`) and the node keeps the last admitted
snapshot until a coherent one arrives (the intended "keep the last pixels" rule). Its size (`logical_size`) came from
the item's current record. So between a geometry change of the card (a resize, the collapse from the display-wide
card, any commit that reaches the item before the next publication) and the next coherent publication, the clip was
the *old* card's: larger than the card the scene draws. The mode drew its quad over the whole current item, and the
oversized mask let it through everywhere the current card's rounded corners leave the item's rectangle; the card frame
(drawn above the content) covers the border band, so what showed was content outside the corner arcs, worst after a
collapse from the display-wide card (its mask covers the whole ordinary card).

Every carded mode had the same exposure (the regression test's pre-fix run: 9-43 changed pixels outside the inner edge
per check for Spectrum, Oscilloscope, Bubble, Spline Curve, Neon Lake, Extruded Bubble and Waveform Ribbon). Spline
Curve shows it most because its fill reaches both bottom corners in bright, opaque layers and its outlines meet the
left and right edges; most modes leave the corners dark or empty.

Steady coherent frames were clean at every size, DPR (1.0, 1.25, 1.5), scale and on Glass: the shared clip itself is
correct; only the record it was built from was wrong.

## Fix and evidence

The node receives the item's record at every sync and builds the clip (and its own size) from it; the retained
snapshot still supplies the pixels. No per-frame cost (one reference), no GL state change, and the protected QSG/clip
optimisations (`ce07b991`, `07486d83`, `985b9d53`: the inherited-state capture, the carried GL fence, the clip trace
stages) are untouched. Before/after 4x crops of the left foot, bottom left and bottom right of a Spline Curve card,
shrunk (1x) and collapsed from display-wide (2560 x 1440 at 150 %):
`.artifacts/evidence/visualizers/devcurve/20261111_card_clip/`.

## Lesson

A clip is a property of what is drawn now, not of the data being drawn. When a renderer keeps old content across a
geometry change, the bound must come from the current geometry; a test of steady frames alone cannot see it, so the
guard includes a retained-snapshot case.
