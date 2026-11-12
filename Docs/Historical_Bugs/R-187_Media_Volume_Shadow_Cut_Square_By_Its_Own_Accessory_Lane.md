# R-187 | Media's volume track shadow was cut square by its own accessory lane whenever the track came near the lane edge

**Status:** fixed 11 Nov 2026 (`Current_Plan.md` 1C.5). The lane's paint boundary takes in the track shadow's reach:
`OverlayWidget.accessoryPaintOutset` grows the clipping `overlayAccessoryLayer` on every side, Media sets it from its
volume shadow (blur plus the larger displacement, `MediaPresentation.volumeShadowReach`), places
`mediaAppVolumeSlider` back on the lane with that margin, and the slider no longer clips a second time. The lane's
geometry, the track's clamp and every Edit mapping are unchanged. Regression bar:
`tests/test_qtquick_media_presentation.py::test_media_child_shadows_are_never_clipped_by_their_lane_or_card` (the
shadow's painted extent, derived from its own blur/spread/offset, lies inside every clipping ancestor across the
volume's Edit range on both sides of the card and both shadow directions, and the transport bar's at its default
geometry; red before the fix: 0.3 px past the lane at the default geometry with an SE shadow, 8.7 px with NW).

## Symptom

The operator saw the volume bar's drop shadow end in a hard edge instead of fading. In off-screen renders the cut is
plain once the track nears the lane edge: an Edit-widened track (the descriptor admits up to 45 px in the fixed 48 px
lane) has its shadow cut along the card side, and a heightened or moved track has the shadow under it cut by a
horizontal line at the widget's bottom edge. Normal and every material alike; dark and light themes alike.

## Cause

`b5bb788e` (5.0.4, Edit-mode child work) gave the external volume accessory its own paint containment twice: the
`overlayAccessoryLayer` lane (`clip: true`, exactly the lane's width and the widget's height) and the
`mediaAppVolumeSlider` filling it (`clip: true`). The track's `RectangularShadow` (blur up to 6 px, displaced about 4 px
in the shadow direction) paints outside the track, so both clips cut it wherever the track sits within that reach of
the lane edge. At the default geometry the SE shadow fits with 0.3 px to spare in the worst corner, so nothing showed
in the default captures; any Edit of the volume, or a shadow direction pointing away from the lane's free side, brings
the cut into view. It is not M1 or M2 (4674e801, 63e22431): renders of the three states (before M1, after M1, after M2)
are pixel-identical on Normal and differ on the materials only in the light-tinted children's former inner hairline
and the card rims, never in a shadow.

## Fix and evidence

The lane's clip is grown by the shadow's reach; the controls stay on the lane. Default-geometry frames are unchanged
(max 2 levels, renderer jitter, zero pixels above 3 levels in the volume, transport and mute crops); with the track
edited against the lane the shadow now fades past the widget edge and across the card border, as Normal would draw it
unclipped. Crops (4x, Default Dark and Polished Chrome, Normal and Glass, both PERSONALSET wallpapers, DPR 1.5):
`.artifacts/evidence/materials/20261111_m2b/c15_volume_shadow/` (`root_cause_commits_*_4x.png`,
`before_after_{default,wide,tall}_*_4x.png`).

## Follow-up (12 Nov 2026)

The same cut, from the track rather than its shadow: the `volume_bar` descriptor admits 2.5x the authored height, but
the lane is only the widget's height, so a track heightened past about 1.2x (saved geometry, or a card made taller
after the edit) ran past the lane and was cut square. The track's height is now bounded by the lane in
`MediaPresentation.qml` beside its existing x/y bound; the R-187 regression test now walks the descriptor's full
height range and also asserts the track lies inside its lane. Crops:
`.artifacts/evidence/materials/20261112_followups/box4_volume_height/`.

## Lesson

A paint boundary written for a control must include the control's own shadow; a clip sized to the control's layout
box is a shadow cutter. Derive the boundary from the shadow parameters at the owner of the clip, and check it
structurally rather than in the default capture, where the margin happens to hide the cut.
