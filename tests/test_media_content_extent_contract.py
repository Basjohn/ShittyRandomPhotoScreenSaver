from __future__ import annotations

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


def test_media_qml_reflows_width_height_and_projects_four_custom_child_roles() -> None:
    qml = _text("rendering/quick/qml/MediaPresentation.qml")
    assert "readonly property real effectivePreferredWidth: mediaModel.contentExtentActive" in qml
    assert "readonly property real effectivePreferredHeight: mediaModel.contentExtentActive" in qml
    assert "preferredContentWidth: effectivePreferredWidth" in qml
    assert "preferredContentHeight: effectivePreferredHeight" in qml
    assert "spacing: mediaRoot.sectionSpacing" in qml
    assert "rowSpacing: mediaRoot.metadataSpacing" in qml
    for role_id in ("artwork", "seek_bar", "volume_bar", "transport_controls"):
        assert f'"roleId": "{role_id}"' in qml
    assert '"target": artworkFrame' in qml
    assert '"target": progressTrack' in qml
    assert '"target": appVolumeTrack' in qml
    assert '"target": controlsRow' in qml
    assert qml.count('"requirementTarget": customChildRequirement') == 4
    assert "canonicalArtworkWidth" in qml
    assert "canonicalProgressTrackWidth" in qml
    assert "canonicalControlsHeight" in qml
    assert 'id: controlsBandSlot' in qml
    assert 'objectName: "mediaControlsBandSlot"' in qml
    assert "canonicalVolumeTrackWidth" in qml
    assert "Image.PreserveAspectCrop" in qml
    # Family overflow uses stable authored baselines, ignores temporarily absent
    # roles, and sums the two horizontal lanes that can otherwise collide.
    assert "artworkFrame.visible" in qml
    assert "progressBand.visible" in qml
    assert "controlsRow.visible" in qml
    assert "appVolumeSlider.visible" in qml
    assert "artworkWidthExtra + seekWidthExtra" in qml
    assert "transportWidthExtra" in qml
    # Placement overflow is derived exactly by the selected Edit layer from
    # mapped occupied rectangles. Media's family requirement remains size/reflow
    # only so a harmless positive move inside the card cannot inflate its parent.
    assert "horizontalPlacementExtra" not in qml
    assert "verticalPlacementExtra" not in qml
    # The transport child role owns the complete painted band, not only the
    # previous/play/next row; the mute section therefore cannot sit outside its
    # edit/collision rectangle.
    assert '"target": controlsRow' in qml
    assert 'id: systemMuteButton' in qml
    assert 'parent.width\n                            - (systemMuteButton.visible' in qml
    assert '"resizeReflowRoleIds": ["transport_controls"]' in qml
    assert '"resizeReflowAxes": ["vertical"]' in qml
    assert '"resizeReflowGate": controlsRow' in qml
    assert "seekOnAuthoredRail" in qml
    assert "transportOnAuthoredRail" in qml
    assert "customEditAncestorReflowY" in qml
    assert "customEditPlacementCompensationY" in qml
    assert "progressBand.y - mediaRoot.canonicalProgressBandY" in qml
    assert "controlsBandSlot.y - mediaRoot.canonicalControlsBandY" in qml
    assert "mediaRoot.seekOnAuthoredRail ? 0.0 : customEditAncestorReflowY" in qml
    assert "mediaRoot.transportOnAuthoredRail ? 0.0 : customEditAncestorReflowY" in qml
    assert "metadata" in qml
    # Fixed obstacles are painted non-role content only. The invisible
    # progressBand is a Column reservation, not a collision/placement owner;
    # the actual progressTrack role already protects the seek element itself.
    assert '{"target": progressBand' not in qml
    assert '"hardResize": false' not in qml
    # No child-resize timer/poller or recurring geometry scanner is admitted.
    assert "Timer {" not in qml



def test_media_nested_seek_and_transport_detach_from_reflowing_bands_after_placement() -> None:
    qml = _text("rendering/quick/qml/MediaPresentation.qml")

    # Seek/transport live inside Column-managed bands. A real free-placement
    # offset must therefore stop inheriting later ancestor-band motion while
    # still using the one shared child_geometry carrier. The current band
    # displacement is exposed as first-move compensation; once off-rail, the
    # retained binding subtracts later displacement instead of accumulating it.
    assert "readonly property bool seekOnAuthoredRail" in qml
    assert "readonly property bool transportOnAuthoredRail" in qml
    assert "progressBand.y - mediaRoot.canonicalProgressBandY" in qml
    assert "controlsBandSlot.y - mediaRoot.canonicalControlsBandY" in qml
    assert "mediaRoot.seekOnAuthoredRail ? customEditAncestorReflowY : 0.0" in qml
    assert "mediaRoot.transportOnAuthoredRail ? customEditAncestorReflowY : 0.0" in qml
    assert "- (mediaRoot.seekOnAuthoredRail ? 0.0 : customEditAncestorReflowY)" in qml
    assert "- (mediaRoot.transportOnAuthoredRail ? 0.0 : customEditAncestorReflowY)" in qml

    # A manually placed transport is no longer a seek-resize reflow exemption.
    # It becomes an ordinary hard peer for the shared edit-only collision pass.
    assert "property bool customEditReflowEnabled: mediaRoot.transportOnAuthoredRail" in qml
    assert '"resizeReflowGate": controlsRow' in qml

    # The containing progress band is an invisible structural reservation, not
    # a fixed collision obstacle after seek becomes a freely placed role.
    assert '{"target": progressBand' not in qml

    # Once nested children are manually placed, their invisible Column slots
    # return to canonical authored reservations rather than continuing to grow
    # from the detached child's edited size. Exact mapped containment then owns
    # the free rectangle, preventing a ghost second layout authority.
    assert "mediaRoot.seekOnAuthoredRail\n                    ? progressTrack.height + 8.0" in qml
    assert "mediaRoot.transportOnAuthoredRail\n                    ? Math.max(mediaRoot.canonicalControlsHeight, controlsRow.height)" in qml
    assert "progressBand.visible\n                && mediaRoot.seekOnAuthoredRail" in qml
    assert "controlsRow.visible\n                && mediaRoot.transportOnAuthoredRail" in qml

    # Detachment is retained arithmetic only. Do not sneak a helper cadence into
    # ordinary CUSTOM runtime to keep nested placements stable.
    assert "Timer {" not in qml
    assert "QTimer" not in qml


def test_media_metadata_crossfade_accepts_vertical_spacing_projection() -> None:
    qml = _text("rendering/quick/qml/MediaMetadataColumn.qml")
    assert "property real rowSpacing: 7.0" in qml
    assert qml.count("spacing: metadataFade.rowSpacing") == 2


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
    for role_id in ("seek_bar", "volume_bar", "transport_controls"):
        assert f'"{role_id}"' in media_descriptor


def test_media_custom_settings_lock_matches_child_geometry_authority() -> None:
    descriptors = _text("rendering/widget_descriptors.py")
    block = descriptors.split('section_id="media"', 1)[1].split(
        'section_id="reddit"', 1
    )[0]
    assert '"media_artwork_size"' in block
    assert '"media_playback_progress_height"' in block


def test_media_metadata_compaction_preserves_left_visual_anchor() -> None:
    qml = _text("rendering/quick/qml/MediaPresentation.qml")
    metadata = qml.split("id: metadata", 1)[1].split("MediaMetadataColumn {", 1)[0]
    assert "anchors.left: parent.left" in metadata
    assert "transformOrigin: Item.Left" in metadata
    assert "transformOrigin: Item.Center" not in metadata


def test_media_child_edit_targets_follow_actual_bands_and_accessory_side_changes() -> None:
    qml = _text("rendering/quick/qml/MediaPresentation.qml")
    assert '"target": controlsRow' in qml
    assert '"target": progressTrack' in qml
    assert '"target": appVolumeTrack' in qml
    # Card children must invalidate mapToItem chrome when the external volume
    # accessory flips left/right and shifts the authored card origin.
    assert qml.count("+ mediaRoot.authoredCardX") >= 3
    assert "property real customEditMappingDependency:" in qml
