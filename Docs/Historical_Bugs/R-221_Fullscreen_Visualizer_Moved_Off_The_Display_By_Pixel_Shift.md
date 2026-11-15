# R-221 | Pixel shift moved the edge-to-edge Fullscreen Visualizer off the display, baring a strip of wallpaper on two edges

**Status:** fixed 15 Nov 2026 (Current_Plan 1D.13, first box; the second box, Borders To Edge's uneven frame, had the
same cause and is fixed with it). A Visualizer card that is the display (`card_is_the_display`: a display-wide card in
a non-Default display style) holds its place under pixel shift; only its full-display overlays keep moving. Regression
bar: `tests/test_fullscreen_visualizer_edges.py` (hidden production host in the R-63 placement, 100 % and 150 %, three
entries into Fullscreen at different shifts plus a shift step in each: no wallpaper or border pixel on any display edge
in Hide Borders, Borders To Edge's four frame edges the same whole width; red on the pre-fix scene).

## Symptom

Fullscreen (Hide Borders) showed a thin line down one edge of the display (the operator's screenshot: about 1 px down
the left edge of Extruded Bubble at 150 %, with a notch halfway down), and "sometimes the side, sometimes the
bottom". Right after a saver start it was edge-perfect. Borders To Edge drew its frame thicker on some display edges
than others.

## Cause

`DisplayScene.qml` draws every card, the Visualizer's included, inside `pixelShiftLayer`, whose `Translate` is the
pixel shift (burn-in protection: the operator has it on, one step a minute, up to 4 logical pixels on each axis). Since
1D.2 (d6c4e928, 12 Nov) the Hide Borders and Borders To Edge records put the card exactly on the display's visible
rect (margin 0). A card that is the display cannot move: a shift of (sx, sy) pushed it sx, sy device-snapped pixels
off one side of the display and bared the same strip of what lies beneath (the wallpaper under dimming) on the other.
The step direction changes with each shift, so the bare strip moved between the left, right, top and bottom edges;
the first minute of a run has no shift, so the style looked edge-perfect at first. Measured on the hidden production
host at the development machine's placements (Display 0: window 1708 x 962 logical with the display at (4/3, 2);
Display 1: 2560 x 1442 with the display at (0, 2); both 150 %): a shift of (1, 1) bared 2 device pixels on the left and
top, (-1, -1) 1 pixel on the right and bottom, (3, -2) 5 on the left and 3 on the bottom, (-4, 4) 6 on the right and
top. Borders To Edge's 8 px frame read 8 beside a 5 px strip on one side and 3 on the other at (3, -2).

Not the overscan, not the 1C.4 snapping, not today's native-core merges (81a14dda, 07433be2, 36096bf2, 5239796b): the
record, the drawn rect and the visible rect were exact in every case (at shift (0, 0) every edge is clean, and the
window and overscan are untouched by the fix).

## Why it stayed hidden

Every guard of the display styles was geometry or a stand-in scene: `tests/test_expanded_display_styles.py` checks the
resolver's rects on whole device pixels inside the monitor, `tests/test_visualizer_card_clip_contract.py` and
`native/core/python/composite_check.py`'s `expanded_*` cases read the card's clip in a scene without pixel shift, and
`tools/expanded_display_styles_evidence.py` renders without the auxiliary state. None applied a pixel shift to a
display-wide card. The Default style hides the same movement under its margin, which is why Fullscreen was "fine"
until a card met the display's edges.

## Fix

- `widgets/spotify_visualizer/presentation_geometry.py`: `card_is_the_display(presentation)` (the predicate
  `renderer_overflow_held` already used; it now delegates to it).
- `rendering/quick/scene_controller.py` (`_apply_visualizer_presentation_items`): sets the scene root's
  `visualizerCardIsTheDisplay` with each record, before the item takes it.
- `rendering/quick/qml/DisplayScene.qml`: while it is true, the Visualizer loader and its shadow underlay take the
  shift back (a counter `Translate`), so the card stays on the display's edges, and the shift is handed to the card's
  `heldPixelShiftX/Y`.
- `rendering/quick/qml/VisualizerPresentation.qml`: the full-display overlays' loader translates by the held shift, so
  Now Playing and the preset toast keep their burn-in movement (inside the safe area, at least 24 px from the edge).

Event-bound bindings only: nothing runs per frame, no timer. The ordinary card and the Default style move with the
shift exactly as before. The window and its R-63 overscan are untouched.

Evidence: `.artifacts/evidence/visualizers/shared/fullscreen_edges_1d13/20261115_before_fix/` and
`20261115_after_fix/` (per display and style, `report.json` with each edge's wallpaper and frame runs at five shifts,
and an x8 sheet of the four edge midpoints on a real wallpaper), `20261115_negative_control/negative_control.txt`.

## Lesson

A card whose edges are the display's edges is not a card that can move. Whatever moves cards (pixel shift, a
transition, a drag) has to know when a card has become the display. Prove display-edge contracts on the product's
scene with every whole-scene transform the product applies, not only on the resolver's rectangles.
