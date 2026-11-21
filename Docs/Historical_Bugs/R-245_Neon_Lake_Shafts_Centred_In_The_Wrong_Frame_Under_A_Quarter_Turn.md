# R-245: Neon Lake's light shafts were centred in the wrong frame under a quarter turn

**21 November 2026. Fixed in the shipped Python renderer (59ea58c28). Status: FIXED.**

## Observed failure

Found by reading the source for the native port (N5.5), not by a user report. With rays on and the content turned a
quarter (Rotate in Edit, the Studio or the hover glyph), Neon Lake's light shafts converged away from the Sun: about
85 to 100 px off on a 560 x 560 card at quarters 1 to 3, and at quarters 2 and 3 the rays' peak fell to about a third of
its unturned strength, leaving a flat disc. Quarter 0 was right. Nothing logged it.

## Root cause

`rendering/quick/scene3d/target.py`: `end()` replaces `frame` with the physical output frame (`scene_output_frame`)
whenever a content quarter turn is active, so the composites map into the window. `_apply_shafts` then mapped the Sun's
item point through that physical matrix and viewport, while the Sun and the shaft texture live in the oriented frame the
scene was drawn in. The rays' centre was therefore rotated or mirrored for quarters 1 to 3.

## Repair

The shafts pass takes the oriented frame (kept as `scene_frame`); the composites keep the output frame.
`tests/test_neon_lake_shaft_quarter_turn.py` renders the real Neon Lake through the host at quarters 0 to 3 and requires
the ray peak within 4 % of the item size of the Sun disc; with the fix reverted, quarters 1 to 3 fail (gaps 58, 47 and
54 px) and quarter 0 passes. After the fix every quarter peaks at the same strength. Crops:
`.artifacts/evidence/visualizers/shockwave_grid/shaft_quarter_turn/20261121_{before,after}/`.

## For the native port

The native Neon Lake must map the shaft centre in the oriented scene frame too; the turned-card anchoring work
(`"scene_frame"` declarations, ABI 29) is where that lands.

## Lesson

A pass that reads a texture drawn in one frame must map its points in that frame, even when the stage around it
switches to another. Reading the source closely enough to port it found what no test watched.
