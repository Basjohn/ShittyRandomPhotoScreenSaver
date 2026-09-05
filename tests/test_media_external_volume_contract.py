from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_overlay_widget_has_one_scene_local_bidirectional_accessory_lane() -> None:
    qml = _text("rendering/quick/qml/OverlayWidget.qml")
    assert "property real accessoryExtent: 0.0" in qml
    assert 'property string accessorySide: "right"' in qml
    assert "property alias accessoryContent: accessoryLayer.data" in qml
    assert "authoredRoot.width - Math.max(0.0, accessoryExtent)" in qml
    assert 'objectName: "overlayAccessoryLayer"' in qml
    assert "authoredCardX" in qml
    assert "cardShadowVisualX" in qml


def test_media_volume_is_external_to_card_and_card_reclaims_old_width() -> None:
    qml = _text("rendering/quick/qml/MediaPresentation.qml")
    assert "readonly property real preferredCardWidth" in qml
    assert "readonly property real volumeAccessoryExtent:" in qml
    assert "readonly property bool appVolumeOnLeft:" in qml
    assert 'accessorySide: appVolumeOnLeft ? "left" : "right"' in qml
    assert "accessoryExtent: volumeAccessoryExtent" in qml
    assert "preferredContentWidth: preferredCardWidth + volumeAccessoryExtent" in qml
    assert "accessoryContent:" in qml
    assert 'objectName: "mediaAppVolumeSlider"' in qml
    assert "anchors.rightMargin: appVolumeSlider.visible ? 48.0 : 0.0" not in qml


def test_media_whole_card_volume_wheel_yields_during_custom_edit() -> None:
    qml = _text("rendering/quick/qml/MediaPresentation.qml")
    assert "property bool volumeWheelEnabled: true" in qml
    assert "WheelHandler {" in qml
    assert "mediaRoot.appVolumeStepRequested" in qml
    assert "enabled: mediaRoot.volumeWheelEnabled" in qml

    controller = _text("rendering/quick/scene_controller.py")
    assert 'media_overlay.item.setProperty("volumeWheelEnabled", False)' in controller
    assert 'media_overlay.item.setProperty("volumeWheelEnabled", True)' in controller


def test_visualizer_volume_wheel_is_event_only_and_custom_gated() -> None:
    qml = _text("rendering/quick/qml/VisualizerPresentation.qml")
    assert "property bool volumeWheelEnabled: true" in qml
    assert "appVolumeStepRequested" in qml
    assert "visualizerPresentationRoot.volumeWheelEnabled" in qml

    controller = _text("rendering/quick/scene_controller.py")
    assert 'self._visualizer_root.setProperty("volumeWheelEnabled", False)' in controller
    assert 'self._visualizer_root.setProperty("volumeWheelEnabled", True)' in controller


def test_media_settings_expose_collapsed_header_seek_and_volume_buckets() -> None:
    source = _text("ui/tabs/widgets_tab_media.py")
    for label in ("Appearance", "Seek Bar", "Volume Control"):
        assert f'"{label}"' in source
    for attr in (
        "media_volume_track_color_btn",
        "media_volume_fill_color_btn",
        "media_volume_border_color_btn",
        "media_playback_progress_track_color_btn",
        "media_playback_progress_fill_color_btn",
        "media_playback_progress_shadow_color_btn",
        "media_playback_progress_glow_color_btn",
    ):
        assert attr in source


def test_media_new_visual_role_defaults_are_persisted() -> None:
    payload = json.loads(_text("core/settings/defaults_snapshot.json"))
    media = payload["widgets"]["media"]
    assert media["spotify_volume_track_color"] == [35, 35, 35, 255]
    assert media["spotify_volume_fill_color"] == [79, 79, 79, 150]
    assert media["spotify_volume_border_color"] == [255, 255, 255, 255]
    assert media["playback_progress_track_color"] == [255, 255, 255, 74]
    assert media["playback_progress_fill_color"] == [255, 255, 255, 230]
    assert media["playback_progress_shadow_color"] == [0, 0, 0, 102]


def test_steam_family_headers_use_alpha_cropped_logo_asset() -> None:
    cropped = ROOT / "images" / "Steam_Logo_Cropped.png"
    assert cropped.is_file()
    assert cropped.stat().st_size > 0
    for relative in (
        "rendering/quick/widgets/achievement_pulse.py",
        "rendering/quick/widgets/abandonment_issues.py",
    ):
        source = _text(relative)
        assert '"Steam_Logo_Cropped.png"' in source
        assert ' / "Steam_Logo.png"' not in source
