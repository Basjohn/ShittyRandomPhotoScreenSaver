# R-NEW | Waveform Ribbon's travelling pulse was sized for the ordinary card while the Visualizer was expanded

**Status:** fixed 12 Nov 2026 (plan item 8b, N0.4 in the worker). The logical side sizes the pulse from the drawn
card's framed view, the numbers the renderer reads from the card it draws (`core/framed_view.py`,
`rendering/quick/visualizer/framed_view.py`, published by `QuickSceneController` at its geometry edges, held by
`VisualizerRuntimeController.framed_view`, carried to the engine worker in `VIS_SET_VIEW` version 2;
`core/waveform_ribbon_view.card_span(camera, view)`). Regression bar: `tests/test_framed_view_camera.py`
(`test_the_sessions_waveform_capture_spans_the_drawn_cards_frustum`: on the display-wide card every tick's span is the
renderer's frustum; the bit-for-bit camera tests, red with the extent-built inputs on Expanded and edge-resized CUSTOM
stages), `tests/test_framed_view_record.py`.

## Symptom

None reported. Found while making the worker's camera inputs exact: with the Visualizer expanded, the capture's
"part of the scene axis the camera shows" was that of the ordinary card, not of the display-wide card being drawn.

## Cause

`card_span` built its frustum from `controller.presentation_viewport_extent` (the committed layout extent) and its
height over the canonical card's. The display-wide record never reaches the controller's committed metrics (by design:
collapsing restores the ordinary card exactly), so while expanded the span used the ordinary card's aspect (1.5 on the
rig's display against the expanded card's 1.79): a narrower span than the renderer's. Edge swells (Head To Tail, Tail
To Head) are born `VIEW_MARGIN` envelope sigmas beyond that span's edge and age only once inside it, so on the wider
expanded card they could be born, and start fading, inside the visible part of the card. On ordinary cards the extent
approximation also ignored the card's border inset and its device-pixel rounding ("within a few percent").

## Why it stayed hidden

Silent: no log, the pulse still travels, and the difference is where along the card a swell first appears and how
faded it is when it does. Not verified on a real display (no visible window from an agent); the numbers are the
renderer's own frustum against the old one.

## Lesson

A logical input derived from the layout record is not the drawn card: a variant record (Expanded) or the drawing's own
rounding (R-191) can differ from it. Feed the logical side the numbers the renderer reads from the card it draws.
