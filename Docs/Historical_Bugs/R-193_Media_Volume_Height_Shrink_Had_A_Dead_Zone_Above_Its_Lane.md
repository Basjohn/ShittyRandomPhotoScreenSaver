# R-193 | A saved Media volume height above what its lane holds did not shrink on the first Edit steps

**Status:** fixed 12 Nov 2026 (`Current_Plan.md` 1C.5). Edit's child resize now starts from what is drawn: a family
that bounds a role's drawn size exposes the drawn/requested ratio on the target item
(`customEditSizeCompensationHeight` on `mediaAppVolumeTrack`), the Edit overlay hands it to the owner at the press
(`beginChildResize`), and the shared resolver (`rendering/custom_child_geometry.resolve_child_resize_geometry`) folds
it into the saved scale on the first real sample, like move's placement compensation. A zero-motion press still
writes nothing. Regression bar:
`tests/test_qtquick_media_presentation.py::test_a_saved_volume_height_above_the_lane_shrinks_on_the_first_edit_step`
(real Media presentation and the real `QuickCustomLayoutOwner`; red before the fix: a 6 px shrink from the
descriptor's tallest scale took the scale from 2.5 to 2.44 and the drawn track stayed at the lane's 240 px).

## Symptom

On a Media card whose volume track had a saved height scale above what its lane holds (a track heightened before the
lane bound, or a card made shorter after the edit), dragging the track's edge to shrink it did nothing at first; the
track only began to move after the pointer had travelled the hidden part of the saved scale (at the descriptor's 2.5x
on a default card, more than half the track's height).

## Cause

`2a3ebb3a` (12 Nov, the same day) bounded the drawn track by its lane (`Math.min(customVolumeTrackHeight,
parent.height)`) without bounding the saved scale. The Edit owner resized from the saved scale and the visible
height in proportion, so each step shrank a scale the bound already hid: 2.5x times 0.975 is still well above the
lane's ~1.2x.

## Fix

The owner of the gesture rebases at the first real sample instead of a second, QML-side clamp or a runtime write to
the saved geometry: the saved scale changes only when the user actually resizes, and then to what was drawn, so the
first step moves the track by about the pointer's step. A profile carrying a scale above the lane loads unchanged and
draws bounded; its first resize starts from the drawn height.

## Lesson

When a presentation bounds what a saved value draws, every editor of that value must start from the drawn value, not
the saved one; otherwise the bound becomes an invisible dead zone in the editor.
