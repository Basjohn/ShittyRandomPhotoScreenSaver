# R-189 | A child part flush with the edge of a parent at a fractional place could not be resized (the gesture froze at its start)

**Status:** fixed 12 Nov 2026 (plan 1C.3, found while restoring Now Playing's artwork rule). `rendering/quick/qml/
CustomLayoutOverlay.qml` `containChildResize` allows half a pixel (0.51 px) instead of 0.0001 px when it asks whether a
part already lies inside its parent. Regression bar:
`tests/test_visualizer_expansion_fullscreen_edit.py::test_a_part_flush_with_the_blocks_edge_still_resizes_by_its_strip`
(real pointer events through the hidden production scene; red on the pre-fix QML, the artwork staying 93 px wide after
a 20 px strip drag; green after).

## Symptom

In Fullscreen Edit, dragging the side strip of Now Playing's artwork did nothing: the strip took the press (the cursor
changed, the gesture began) but the artwork kept its size, with no message. Its natural artwork is exactly as tall as
the block, so this held for the block's default layout at most placements. The same check guards every widget's child
resize in ordinary Edit, so any child flush with the edge of a parent drawn at a fractional position was affected.

## Cause

The Edit frame of an item is its rectangle rounded to whole pixels, while the item itself may sit at a fractional place
(Now Playing's block: offsets are fractions of the safe area). A child flush with the parent's edge therefore maps into
the Edit frame up to half a pixel outside it (measured 0.43 px left and 0.48 px above). `containChildResize` treats a
start rectangle that is not inside the frame as "an inherited layout that already protrudes" and returns the press
point for every sample, so the resize never moved; its tolerance was 0.0001 px.

## Fix and evidence

The containment slack is 0.51 px: the rounding the whole-pixel frame introduces, and no more (a real protrusion of a
pixel or more is still refused). The shared child-editor tests (`tests/test_qtquick_child_*`,
`test_qtquick_custom_layout_overlay.py`, `test_quick_child_paint_containment_contract.py`) pass unchanged.

## Lesson

A containment check comparing a fractional drawn rectangle against a frame rounded to whole pixels needs the rounding's
own tolerance. A tolerance meant for float noise (1e-4) silently refuses legitimate gestures when the two sides are
rounded differently.
