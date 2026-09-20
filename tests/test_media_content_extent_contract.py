from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_media_declares_two_axis_custom_content_extent_with_family_floor() -> None:
    descriptors = _text("rendering/widget_descriptors.py")
    assert 'custom_layout_resize_mode="media_scale"' in descriptors
    assert 'content_extent_axes=("horizontal", "vertical")' in descriptors
    assert "content_extent_minimum_size=(520, 210)" in descriptors

    session = _text("rendering/custom_layout_session.py")
    assert "content_extent_minimum_size: ViewportExtent | None = None" in session


def test_media_direct_axis_floor_does_not_replace_uniform_resize_floor() -> None:
    size = _text("rendering/quick/custom_layout_size.py")
    owner = _text("rendering/quick/custom_layout_owner.py")
    assert "def quick_custom_content_extent_minimum_size(" in size
    assert "float(item.resize_scale)" in size
    assert "def quick_custom_minimum_size" in size
    assert "generic_floor = quick_custom_minimum_size(item)" in size
    assert "max(generic_floor.width()," in size
    assert "max(generic_floor.height()," in size
    assert "max(CUSTOM_LAYOUT_MIN_WIDGET_SIZE," not in size
    generic = size.split("def quick_custom_minimum_size", 1)[1].split(
        "def quick_custom_content_extent_minimum_size", 1
    )[0]
    assert "content_extent_minimum_size" not in generic
    edge = owner.split("def _resize_content_edge", 1)[1].split(
        "def _apply_content_extent_uniform_scale", 1
    )[0]
    assert "quick_custom_content_extent_minimum_size(item)" in edge
    uniform = owner.split("def _apply_content_extent_uniform_scale", 1)[1].split(
        "def _peer_local_rects", 1
    )[0]
    assert "quick_custom_minimum_size(item)" in uniform


def test_media_model_consumes_custom_extent_without_mutating_settings() -> None:
    source = _text("rendering/quick/widgets/media.py")
    assert "self._content_extent: tuple[int, int] | None = None" in source
    assert "def set_content_extent(" in source
    assert "resolved_width = max(520, min(4000, resolved_width))" in source
    assert "resolved_height = max(210, min(4000, resolved_height))" in source
    assert "def clear_content_extent" in source
    assert "def contentExtentActive" in source
    assert "def contentExtentWidth" in source
    assert "def contentExtentHeight" in source
    assert 'payload.get("content_extent")' in source
    assert "self._model.set_content_extent(extent[0], extent[1])" in source
    assert "self._model.clear_content_extent()" in source


def test_media_vertical_compaction_sheds_lower_priority_metadata() -> None:
    source = _text("rendering/quick/widgets/media.py")
    album = source.split("def showAlbum", 1)[1].split("def showPlaybackState", 1)[0]
    state = source.split("def showPlaybackState", 1)[1].split("def controlsAvailable", 1)[0]
    assert "self._content_extent[1] >= 255" in album
    assert "self._content_extent[1] >= 225" in state


def test_media_qml_reflows_width_height_and_projects_full_semantic_child_roles() -> None:
    qml = _text("rendering/quick/qml/MediaPresentation.qml")
    assert "readonly property real effectivePreferredWidth: mediaModel.contentExtentActive" in qml
    assert "readonly property real effectivePreferredHeight: mediaModel.contentExtentActive" in qml
    assert "preferredContentWidth: effectivePreferredWidth" in qml
    assert "preferredContentHeight: effectivePreferredHeight" in qml
    assert "spacing: mediaRoot.sectionSpacing" in qml
    assert "rowSpacing: mediaRoot.metadataSpacing" in qml
    for role_id in (
        "header", "metadata", "artist", "playback_state", "artwork", "seek_bar",
        "volume_bar", "transport_controls", "mute_button",
    ):
        assert f'"roleId": "{role_id}"' in qml
    assert '"target": headerFrame' in qml
    assert '"target": trackMetadata' in qml
    assert '"target": trackMetadata.artistEditTarget' in qml
    assert '"target": playbackState' in qml
    assert '"target": artworkFrame' in qml
    assert '"target": progressTrack' in qml
    assert '"target": appVolumeTrack' in qml
    assert '"target": controlsRow' in qml
    assert '"target": systemMuteButton' in qml
    # Role-local containment superseded the old Media child-driven content
    # requirement. All nine roles remain editable without another outer-size
    # authority, even when a child is moved off its authored flow rail.
    assert qml.count('"requirementTarget": null') == 9
    assert "customEditableChildRequirementTarget: null" in qml
    assert "id: customChildRequirement" not in qml
    assert 'roles[i].allowParentGrowth = false' not in qml
    assert "canonicalArtworkWidth" in qml
    assert "canonicalProgressTrackWidth" in qml
    assert "canonicalControlsHeight" in qml
    assert 'id: controlsBandSlot' in qml
    assert 'objectName: "mediaControlsBandSlot"' in qml
    assert "canonicalVolumeTrackWidth" in qml
    assert "Image.PreserveAspectCrop" in qml
    # Visibility is family-authored; selected Edit may not derive a second
    # content-extent requirement from those children or from absent roles.
    assert "artworkFrame.visible" in qml
    assert "progressBand.visible" in qml
    assert "controlsRow.visible" in qml
    assert "appVolumeSlider.visible" in qml
    assert "artworkWidthExtra + seekWidthExtra" not in qml
    assert "transportWidthExtra" not in qml
    # Exact role-local containment, not a second family-side outer-extent
    # calculator, must own free CUSTOM placement.
    assert "horizontalPlacementExtra" not in qml
    assert "verticalPlacementExtra" not in qml
    # Transport remains a grouped bar while mute is its own intrinsic child;
    # the nested pair ignores only each other for hard peer collision.
    assert '"target": controlsRow' in qml
    assert '"target": systemMuteButton' in qml
    assert '"collisionIgnoreRoleIds": ["mute_button"]' in qml
    assert '"collisionIgnoreRoleIds": ["transport_controls"]' in qml
    assert '"resizeReflowRoleIds": ["transport_controls"]' in qml
    assert '"resizeReflowAxes": ["vertical"]' in qml
    assert '"resizeReflowGate": controlsRow' in qml
    assert "seekOnAuthoredRail" in qml
    assert "transportOnAuthoredRail" in qml
    assert "customEditAncestorReflowY" in qml
    assert "customEditPlacementCompensationY" in qml
    assert "progressBand.y - mediaRoot.canonicalProgressBandY" in qml
    assert "controlsBandSlot.y - mediaRoot.canonicalControlsBandY" in qml
    # A child X/Y edit must not cancel the live Y motion of its Column band.
    assert "- (mediaRoot.seekOnAuthoredRail ? 0.0 : customEditAncestorReflowY)" not in qml
    assert "- (mediaRoot.transportOnAuthoredRail ? 0.0 : customEditAncestorReflowY)" not in qml
    assert "metadata" in qml
    # The authored seek is a true 75% bar. Do not reintroduce the old hidden
    # two-sided 8% margin before applying the 75% factor.
    assert "canonicalCardContentWidth * 0.75" in qml
    assert "canonicalCardContentWidth * 0.08" not in qml
    # Every painted semantic region is an editable role. Invisible flow slots
    # remain outside collision truth.
    assert "customEditableChildObstacles: []" in qml
    assert '{"target": progressBand' not in qml
    assert '"hardResize": false' not in qml
    # No child-resize timer/poller or recurring geometry scanner is admitted.
    assert "Timer {" not in qml



def test_media_authored_xy_reflow_survives_child_editor_and_visibility_gates() -> None:
    qml = _text("rendering/quick/qml/MediaPresentation.qml")
    # The pre-editor authored layout used available card width and remaining
    # vertical flow space. X/Y must still respond to parent content extent;
    # CUSTOM child geometry merely projects onto those existing rails.
    assert "mediaRoot.authoredCardWidth - mediaRoot.shellInset" in qml
    assert "canonicalProgressTrackWidth\n            + (authoredCardContentWidth - canonicalCardContentWidth) * 0.75" in qml
    assert "width: mediaRoot.authoredProgressTrackWidth\n" in qml
    assert "width: mediaRoot.authoredCardContentWidth\n" in qml
    assert "baseArtworkWidth + extraHorizontalRoom * 0.35" in qml
    assert "mediaRoot.authoredCardWidth - mediaRoot.canonicalPreferredCardWidth" in qml
    assert "readonly property real normalBottomInColumn: controlsBandSlot.visible" in qml
    assert "readonly property real bottomInColumn: seekWouldIntersectArtwork" in qml
    assert "readonly property real referenceHeight: Math.max(" in qml
    assert "width: visible\n                    ? authoredArtworkWidth" in qml
    assert "height: visible\n                    ? referenceHeight" in qml
    assert "mediaRoot.authoredCardContentWidth - authoredArtworkWidth" in qml
    # The semantic flip has an independent left-side authored rail; neither
    # orientation may derive its provisional seek overlap from final artwork.x.
    assert "mediaRoot.headerFlipped && mediaRoot.artworkOnAuthoredRail" in qml
    assert 'readonly property real unflippedAuthoredX:' in qml
    assert 'mediaRoot.authoredCardContentWidth - authoredArtworkWidth' in qml
    assert 'mediaRoot.headerFlipped && mediaRoot.artworkOnAuthoredRail' in qml
    # The authored reference cannot follow the edited seek target. That was a
    # child move/resize -> artwork reference -> child edit map feedback path.
    assert 'authoredSeekX + mediaRoot.authoredProgressTrackWidth' in qml
    artwork = qml.split('id: artworkFrame', 1)[1].split('id: progressBand', 1)[0]
    assert 'progressTrack.x' not in artwork and 'progressTrack.width' not in artwork
    # Visibility should not become a new persistence or parent-growth owner.
    assert "visible: mediaRoot.mediaModel.progressAvailable" in qml
    assert "visible: mediaRoot.mediaModel.controlsBandAvailable" in qml
    assert '"requirementTarget": null' in qml
    assert "customEditableChildRequirementTarget: null" in qml
    assert "roles[i].allowParentGrowth = false" not in qml


def test_authored_metadata_lane_reserves_intrinsic_artwork_rail_independent_of_child_move() -> None:
    qml = _text("rendering/quick/qml/MediaPresentation.qml")
    lane = qml.split("id: metadata", 1)[1].split("MediaMetadataColumn {", 1)[0]
    # The metadata reference must never consume the currently edited artwork
    # X/Y/width. A first artwork drag may not rebuild the sibling's authored
    # lane and then invalidate collision and pointer compensation mid-gesture.
    assert "artworkFrame.authoredArtworkWidth + 16.0" in lane
    assert "parent.width - artworkFrame.authoredArtworkWidth" in lane
    assert "artworkFrame.x" not in lane and "artworkFrame.width" not in lane
    assert "mediaRoot.artworkOnAuthoredRail" not in lane
    # Artwork's own provisional position is card-content relative, unaffected
    # by optional external volume or independently moved seek and metadata.
    assert "mediaRoot.authoredCardContentWidth - provisionalArtworkWidth" in qml
    assert "artworkFrame.x" not in qml.split(
        "readonly property real provisionalArtworkWidth:", 1
    )[1].split("readonly property real provisionalArtworkX:", 1)[0]


def test_media_artwork_rail_does_not_depend_on_positioner_polish_or_expand_a_lock_owner() -> None:
    qml = _text("rendering/quick/qml/MediaPresentation.qml")
    # Qt Quick Column y coordinates can lag a content-extent geometry change;
    # the artwork must use authored band sizes and spacing directly.
    for binding in (
        "readonly property real mainRailTop:",
        "readonly property real mainRailBottom: mainRailTop + mainBand.height",
        "readonly property real progressRailTop: mainRailBottom",
        "readonly property real controlsRailTop: mainRailBottom",
        "? controlsRailTop - mediaColumn.spacing",
        "? progressRailTop - mediaColumn.spacing",
    ):
        assert binding in qml
    assert "? controlsBandSlot.y - mediaColumn.spacing" not in qml
    assert "? progressBand.y - mediaColumn.spacing" not in qml
    # Card and independent volume accessory are ALWAYS paint-bounded, including
    # authored and non-edit runtime. Clipping must not become child editability
    # or a second geometry, content-extent, or Settings owner.
    # The shared card boundary clips unconditionally; Media does not install
    # a competing content-extent-dependent clipping policy around its Column.
    assert 'clip: mediaRoot.mediaModel.contentExtentActive' not in qml
    assert "clip: true" in qml.split("id: appVolumeSlider", 1)[1].split("id: appVolumeTrack", 1)[0]
    assert "childPaintContainmentActive" not in qml
    overlay = _text("rendering/quick/qml/OverlayWidget.qml")
    card = _text("rendering/quick/qml/OverlayCard.qml")
    assert "paintContainmentActive" not in overlay
    assert "clip: true" in overlay.split("id: accessoryLayer", 1)[1]
    assert "clip: true" in card.split("id: contentPaintBoundary", 1)[1].split("id: contentArea", 1)[0]
    assert "clip: false" in card  # shell/shadow must not be clipped
    assert "readonly property real authoredVolumeTrackHeight:" in qml
    assert "mediaRoot.authoredLayoutHeight - 2.0 * mediaRoot.cardPadding - 12.0" in qml
    assert "authoredVolumeTrackHeight * mediaModel.customVolumeHeightScale" in qml
    assert "customEditableChildRequirementTarget: null" in qml
    assert "Timer {" not in qml


def test_media_nested_seek_and_transport_keep_axis_independent_band_reflow() -> None:
    qml = _text("rendering/quick/qml/MediaPresentation.qml")
    # Both roles remain descendants of their existing Column-owned bands.
    # Changing X or Y child offset must not subtract the band's live Y movement
    # during compact-height parent editing in either semantic orientation.
    seek = qml.split('id: progressTrack', 1)[1].split('id: progressFill', 1)[0]
    transport = qml.split('id: controlsRow', 1)[1].split('id: appVolumeSlider', 1)[0]
    assert 'customEditPlacementCompensationY: 0.0' in seek
    assert 'customEditPlacementCompensationY: 0.0' in transport
    assert 'mediaRoot.mediaModel.customSeekYOffset' in seek
    assert 'mediaRoot.mediaModel.customTransportYOffset' in transport
    assert '- (mediaRoot.seekOnAuthoredRail ? 0.0 : customEditAncestorReflowY)' not in seek
    assert '- (mediaRoot.transportOnAuthoredRail ? 0.0 : customEditAncestorReflowY)' not in transport
    assert 'property bool customEditReflowEnabled: true' in transport
    assert 'height: visible ? mediaRoot.canonicalProgressBandHeight : 0.0' in qml
    assert 'height: visible ? mediaRoot.canonicalControlsHeight : 0.0' in qml
    # One outer owner; child geometry never becomes a Column or parent-size input.
    assert 'customEditableChildRequirementTarget: null' in qml
    assert 'roles[i].containmentTarget = mediaColumn' in qml
    assert 'roles[i].allowParentGrowth' not in qml
    assert 'Timer {' not in qml


def test_media_card_child_x_uses_card_only_normalization_even_with_volume_accessory() -> None:
    qml = _text("rendering/quick/qml/MediaPresentation.qml")
    # The edit owner projects all non-volume roles with card-only X
    # normalization.  The displayed rectangle must use that SAME denominator:
    # otherwise enabling the optional accessory jumps edited children despite
    # no child gesture or saved-state change.
    assert 'readonly property real childNormalizationWidth: canonicalPreferredCardWidth' in qml
    for role_property in (
        'customArtworkXOffset', 'customSeekXOffset', 'customTransportXOffset',
    ):
        assert re.search(
            rf'mediaRoot\.mediaModel\.{role_property}\s*\*\s*'
            r'mediaRoot\.childNormalizationWidth\b', qml,
        ), role_property
    # Only the external volume control preserves its legacy whole-widget X
    # normalization; that is not the legal containment for ordinary card roles.
    assert 'roleId": "volume_bar"' in qml
    assert '"containmentTarget": appVolumeSlider' in qml
    assert '"normalizationWidth": canonicalPreferredCardWidth\n                    + canonicalVolumeAccessoryExtent' in qml


def test_media_metadata_crossfade_accepts_vertical_spacing_projection() -> None:
    qml = _text("rendering/quick/qml/MediaMetadataColumn.qml")
    assert "property real rowSpacing: 7.0" in qml
    assert qml.count("spacing: metadataFade.rowSpacing") == 2


def test_media_artist_child_is_one_role_with_two_crossfade_projections() -> None:
    descriptor = _text("rendering/widget_descriptors.py")
    media = descriptor.split('widget_id="media"', 1)[1].split('widget_id="reddit"', 1)[0]
    qml = _text("rendering/quick/qml/MediaPresentation.qml")
    crossfade = _text("rendering/quick/qml/MediaMetadataColumn.qml")
    assert '"artist"' in media
    assert '"roleId": "artist"' in qml
    assert '"collisionIgnoreRoleIds": ["metadata"]' in qml
    assert '"collisionIgnoreRoleIds": ["artist"]' in qml
    assert 'artistOffsetX: mediaRoot.childOffsetX("artist")' in qml
    assert 'artistOffsetY: mediaRoot.childOffsetY("artist")' in qml
    assert 'artistScale: mediaRoot.childWidthScale("artist")' in qml
    assert 'property alias artistEditTarget: currentArtistText' in crossfade
    assert crossfade.count('x: metadataFade.artistOffsetX') == 2
    assert crossfade.count('y: metadataFade.artistOffsetY') == 2
    assert crossfade.count('scale: metadataFade.artistScale') == 2
    assert crossfade.count('horizontalAlignment: metadataFade.artistAlignment === "right"') == 2
    # Both authored zero-offset/scale-1 lines retain a separate row slot in
    # each crossfade Column; no new flow or global Settings authority.
    assert crossfade.count('height: visible ? currentArtistText.implicitHeight : 0.0') == 1
    assert crossfade.count('height: visible ? outgoingArtistText.implicitHeight : 0.0') == 1
    assert 'Timer {' not in crossfade


def test_media_landscape_permission_is_retired_and_custom_artwork_frame_is_freeform() -> None:
    defaults = _text("core/settings/default_settings.py")
    snapshot = _text("core/settings/defaults_snapshot.json")
    model = _text("core/settings/models/_widget_settings.py")
    quick = _text("rendering/quick/widgets/media.py")
    settings_ui = _text("ui/tabs/widgets_tab_media.py")
    qml = _text("rendering/quick/qml/MediaPresentation.qml")

    for source in (defaults, snapshot, model, quick, settings_ui, qml):
        assert "allow_landscape_artwork" not in source
        assert "allowLandscapeArtwork" not in source
    assert 'QCheckBox("Allow Landscape Artwork")' not in settings_ui
    assert "customArtworkWidthScale" in qml
    assert "customArtworkHeightScale" in qml
    assert "Image.PreserveAspectCrop" in qml
    assert "ArtworkFadeImage {" in qml


def test_media_custom_child_geometry_stays_on_retained_payload_owner_and_narrow_signal() -> None:
    source = _text("rendering/quick/widgets/media.py")
    descriptors = _text("rendering/widget_descriptors.py")

    assert "customGeometryChanged = Signal()" in source
    assert "def set_custom_child_geometry(" in source
    assert "self._custom_child_geometry: dict[str, CustomChildSize]" in source
    assert "def customChildGeometry" in source
    assert 'payload.get("child_geometry")' in source
    assert "self._model.set_custom_child_geometry(child_geometry)" in source
    for prop in (
        "customArtworkWidthScale",
        "customArtworkHeightScale",
        "customSeekWidthScale",
        "customSeekHeightScale",
        "customVolumeWidthScale",
        "customVolumeHeightScale",
        "customTransportWidthScale",
        "customTransportHeightScale",
        "customArtworkXOffset",
        "customArtworkYOffset",
        "customSeekXOffset",
        "customSeekYOffset",
        "customVolumeXOffset",
        "customVolumeYOffset",
        "customTransportXOffset",
        "customTransportYOffset",
    ):
        assert f"def {prop}" in source
    media_descriptor = descriptors.split('widget_id="media"', 1)[1].split(
        'widget_id="reddit"', 1
    )[0]
    assert "freeform_artwork_child_role(" in media_descriptor
    for role_id in (
        "header", "metadata", "playback_state", "seek_bar", "volume_bar",
        "transport_controls", "mute_button",
    ):
        assert f'"{role_id}"' in media_descriptor
    assert '"header"' in media_descriptor and "semantic_corner_anchor=True" in media_descriptor
    assert '"mute_button"' in media_descriptor and "uniform_scale=True" in media_descriptor


def test_media_custom_settings_lock_matches_child_geometry_authority() -> None:
    descriptors = _text("rendering/widget_descriptors.py")
    block = descriptors.split('section_id="media"', 1)[1].split(
        'section_id="reddit"', 1
    )[0]
    assert '"media_artwork_size"' in block
    assert '"media_playback_progress_height"' in block


def test_media_metadata_compaction_preserves_orientation_specific_visual_anchor() -> None:
    qml = _text("rendering/quick/qml/MediaPresentation.qml")
    metadata = qml.split("id: metadata", 1)[1].split("MediaMetadataColumn {", 1)[0]
    assert "x: 2.0" in metadata
    assert "transformOrigin: mediaRoot.headerFlipped ? Item.Right : Item.Left" in metadata
    assert "transformOrigin: Item.Center" not in metadata


def test_media_seek_has_no_hidden_right_padding_and_mute_shrinks_uniformly_with_controls() -> None:
    qml = _text("rendering/quick/qml/MediaPresentation.qml")
    assert "canonicalCardContentWidth * 0.75" in qml
    assert "canonicalCardContentWidth * 0.08" not in qml
    mute = qml.split("id: systemMuteButton", 1)[1].split("gradient: Gradient", 1)[0]
    assert 'mediaRoot.childWidthScale("mute_button")' in mute
    assert "readonly property real fitScale" in mute
    assert "height: mediaRoot.canonicalSystemMuteHeight * fitScale" in mute
    assert "width: mediaRoot.canonicalSystemMuteWidth * fitScale" in mute
    assert "customTransportWidthScale" not in mute
    assert "customTransportHeightScale" not in mute


def test_media_child_edit_targets_follow_actual_bands_and_accessory_side_changes() -> None:
    qml = _text("rendering/quick/qml/MediaPresentation.qml")
    assert '"target": controlsRow' in qml
    assert '"target": progressTrack' in qml
    assert '"target": appVolumeTrack' in qml
    # Card children must invalidate mapToItem chrome when the external volume
    # accessory flips left/right and shifts the authored card origin.
    assert qml.count("mediaColumn.y, mediaRoot.authoredCardX") == 3
    assert qml.count('property string customEditMappingDependency: [') == 4
    assert 'mainBand.y, mediaColumn.y, mediaRoot.authoredCardX' in qml
    assert 'progressBand.y, mediaColumn.y, mediaRoot.authoredCardX' in qml
    assert 'controlsBandSlot.y, mediaColumn.y, mediaRoot.authoredCardX' in qml
    assert 'appVolumeSlider.x, appVolumeSlider.y' in qml
    mapper = _text("rendering/quick/qml/CustomLayoutOverlay.qml")
    assert 'String(\n                                            targetItem.customEditMappingDependency' in mapper
    assert 'String(\n                                            occupiedItem.customEditMappingDependency' in mapper
