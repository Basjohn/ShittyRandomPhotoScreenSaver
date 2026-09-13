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


def test_media_qml_reflows_width_height_artwork_and_volume_without_new_owner() -> None:
    qml = _text("rendering/quick/qml/MediaPresentation.qml")
    assert "readonly property real effectivePreferredWidth: mediaModel.contentExtentActive" in qml
    assert "readonly property real effectivePreferredHeight: mediaModel.contentExtentActive" in qml
    assert "preferredContentWidth: effectivePreferredWidth" in qml
    assert "preferredContentHeight: effectivePreferredHeight" in qml
    assert "spacing: mediaRoot.sectionSpacing" in qml
    assert "rowSpacing: mediaRoot.metadataSpacing" in qml
    assert "baseArtworkWidth + extraHorizontalRoom * 0.35" in qml
    assert "mediaRoot.mediaModel.allowLandscapeArtwork" in qml
    assert "Math.min(referenceHeight, metadataLimitedArtworkWidth)" in qml
    assert "width: 32.0" in qml
    assert "anchors.top: parent.top" in qml
    assert "anchors.bottom: parent.bottom" in qml
    # No resize-specific timer/poller was introduced in presentation QML.
    assert "Timer {" not in qml


def test_media_metadata_crossfade_accepts_vertical_spacing_projection() -> None:
    qml = _text("rendering/quick/qml/MediaMetadataColumn.qml")
    assert "property real rowSpacing: 7.0" in qml
    assert qml.count("spacing: metadataFade.rowSpacing") == 2


def test_media_landscape_artwork_is_canonical_default_off_and_only_removes_shape_cap() -> None:
    defaults = _text("core/settings/default_settings.py")
    model = _text("core/settings/models/_widget_settings.py")
    quick = _text("rendering/quick/widgets/media.py")
    settings_ui = _text("ui/tabs/widgets_tab_media.py")
    qml = _text("rendering/quick/qml/MediaPresentation.qml")

    assert "'allow_landscape_artwork': False" in defaults
    assert 'allow_landscape_artwork: bool = bool(_default("widgets.media", "allow_landscape_artwork"))' in model
    assert "def allowLandscapeArtwork" in quick
    assert 'QCheckBox("Allow Landscape Artwork")' in settings_ui
    assert "tab._default_bool('media', 'allow_landscape_artwork')" in settings_ui
    assert "tab._config_bool('media', media_config, 'allow_landscape_artwork')" in settings_ui
    assert "'allow_landscape_artwork': tab.media_allow_landscape_artwork.isChecked()" in settings_ui
    assert "mediaRoot.mediaModel.allowLandscapeArtwork" in qml
    assert "? metadataLimitedArtworkWidth" in qml
    assert ": Math.min(referenceHeight, metadataLimitedArtworkWidth)" in qml
    assert "ArtworkFadeImage {" in qml
