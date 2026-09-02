"""Source-level permanent contracts for shared/lazy Widget card materials.

Qt runtime/visual behavior still requires the PySide6 user-environment gate. These
checks prevent architectural regressions that would recreate per-card capture/blur
owners or make Normal pay the material-renderer cost.
"""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "rendering" / "quick" / "qml"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_surface_style_uses_themed_combo_and_exposes_all_material_modes() -> None:
    source = _text(ROOT / "ui" / "tabs" / "widgets_tab_defaults.py")
    assert "widget_surface_style_combo = StyledComboBox()" in source
    assert 'addItem("Theme Default", "theme")' in source
    assert 'addItem("Normal", "normal")' in source
    assert 'addItem("Glass", "glass")' in source
    assert 'addItem("Acrylic", "acrylic")' in source
    assert "item.setEnabled(False)" not in source


def test_material_capture_and_blur_exist_only_in_shared_backdrop_component() -> None:
    backdrop = _text(QML / "CardMaterialBackdrop.qml")
    assert backdrop.count("ShaderEffectSource") >= 1
    assert backdrop.count("MultiEffect") >= 1

    for filename in (
        "OverlayCard.qml",
        "OverlayWidget.qml",
        "OverlayCardMaterialMask.qml",
        "VisualizerPresentation.qml",
        "ContextMenu.qml",
    ):
        source = _text(QML / filename)
        assert "ShaderEffectSource" not in source, filename
        # ContextMenu legitimately uses RectangularShadow from QtQuick.Effects;
        # the card material contract specifically forbids a card-local MultiEffect.
        assert "MultiEffect" not in source, filename


def test_shared_blur_is_bounded_and_downsampled_when_material_is_active() -> None:
    backdrop = _text(QML / "CardMaterialBackdrop.qml")
    scene = _text(QML / "DisplayScene.qml")

    assert "property real downsampleScale: 0.25" in backdrop
    assert "textureSize: Qt.size(" in backdrop
    assert "width * materialBackdrop.downsampleScale" in backdrop
    assert "height * materialBackdrop.downsampleScale" in backdrop
    assert "live: materialBackdrop.visible" in backdrop
    assert "recursive: false" in backdrop
    assert "autoPaddingEnabled: false" in backdrop
    assert "layer.enabled: cardMaterialBackdropLoader.active" in scene


def test_normal_mode_keeps_shared_material_loader_dormant() -> None:
    scene = _text(QML / "DisplayScene.qml")
    assert 'cardMaterialMode !== "normal"' in scene
    assert "active: displayScene.cardMaterialBackdropNeeded" in scene
    assert 'source: "CardMaterialBackdrop.qml"' in scene

    host = _text(ROOT / "rendering" / "quick" / "widgets" / "host.py")
    assert 'if normalized == "normal":' in host
    assert "_retire_material_mask" in host
    assert 'widget.item.property("cardShellEnabled")' in host


def test_runtime_publishes_resolved_material_instead_of_clamping_to_normal() -> None:
    selection = _text(ROOT / "ui" / "widget_theme_selection.py")
    assert "material_mode=resolved.effective_card_material_mode" in selection
    assert 'material_mode="normal"' not in selection


def test_widget_theme_link_control_is_settings_theme_styled_button() -> None:
    source = _text(ROOT / "ui" / "tabs" / "themes_tab.py")
    assert "self.widget_keep_synced=QPushButton()" in source
    assert "self.widget_keep_synced.setCheckable(True)" in source
    assert '"MODE_TOGGLE_BUTTON_STYLE"' in source
    assert '"Linked to Settings Theme"' in source
    assert '"Independent Widget Theme"' in source


def test_primary_text_semantic_baseline_is_consumed_by_all_ordinary_families() -> None:
    projection = _text(ROOT / "rendering" / "quick" / "widgets" / "theme_projection.py")
    assert 'get_active_widget_theme().color("card.text")' in projection
    for filename in (
        "weather.py",
        "clock.py",
        "media.py",
        "gmail.py",
        "reddit.py",
        "achievement_pulse.py",
        "abandonment_issues.py",
    ):
        source = _text(ROOT / "rendering" / "quick" / "widgets" / filename)
        assert "resolve_primary_text_color(" in source, filename


def test_shared_material_captures_only_the_below_widgets_background_host() -> None:
    scene_controller = _text(ROOT / "rendering" / "quick" / "scene_controller.py")
    scene = _text(QML / "DisplayScene.qml")
    assert 'root.setProperty("materialBackdropSourceItem", background_host)' in scene_controller
    assert 'objectName: "backgroundPresentationHost"' in scene
    assert 'sourceItem = Qt.binding(function()' in scene
    # The capture source must never be the whole display scene/widget layer: doing
    # so would recursively capture cards/Visualizer/Context Menu into their blur.
    assert 'root.setProperty("materialBackdropSourceItem", root)' not in scene_controller


def test_secondary_mail_and_reddit_metadata_use_sparse_theme_roles() -> None:
    roles = _text(ROOT / "ui" / "widget_visual_roles.py")
    gmail = _text(ROOT / "rendering" / "quick" / "widgets" / "gmail.py")
    reddit = _text(ROOT / "rendering" / "quick" / "widgets" / "reddit.py")
    generator = _text(ROOT / "tools" / "generate_widget_theme_mirrors.py")

    for role in ("gmail.sender", "gmail.read_sender", "gmail.read_subject", "gmail.timestamp"):
        assert f'"{role}"' in roles
        assert f'"{role}"' in gmail
        assert f'"{role}"' in generator
    assert '"reddit.age"' in roles
    assert '"reddit2.age"' in roles
    assert 'f"{self.config.widget_id}.age"' in reddit
    assert '"reddit.age"' in generator
    assert '"reddit2.age"' in generator
