"""Permanent contract for the post-material Widget Theme/runtime architecture.

The abandoned Qt Quick Glass/Acrylic card-backdrop experiment must not creep back
into runtime composition, Widget Theme schema/state, or Widgets -> General UI.
Settings-window Glass/Acrylic remain a separate native QWidget theme concern.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "rendering" / "quick" / "qml"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_material_only_qml_components_are_gone() -> None:
    assert not (QML / "CardMaterialBackdrop.qml").exists()
    assert not (QML / "OverlayCardMaterialMask.qml").exists()


def test_display_background_is_direct_and_has_no_material_capture_layer() -> None:
    scene = _text(QML / "DisplayScene.qml")
    controller = _text(ROOT / "rendering" / "quick" / "scene_controller.py")
    presenter = _text(ROOT / "rendering" / "quick" / "display_presenter.py")
    frame_pacer = _text(ROOT / "rendering" / "quick" / "frame_pacer.py")

    for forbidden in (
        "cardMaterial",
        "CardMaterial",
        "materialBackdrop",
        "materialConsumer",
        "ShaderEffectSource",
        "backgroundPresentationHost",
    ):
        assert forbidden not in scene
    assert "BackgroundRenderItem(\n            root," in controller
    assert "set_card_material_mode" not in controller
    assert "describe_card_material_state" not in controller
    assert "get_active_widget_material_mode" not in presenter
    assert "layered_background" not in frame_pacer


def test_card_shells_are_plain_rgba_surfaces() -> None:
    card = _text(QML / "OverlayCard.qml")
    widget = _text(QML / "OverlayWidget.qml")
    visualizer = _text(QML / "VisualizerPresentation.qml")
    context = _text(QML / "ContextMenu.qml")
    host = _text(ROOT / "rendering" / "quick" / "widgets" / "host.py")

    assert "color: card.backgroundColor" in card
    assert "materialMode" not in card
    assert "cardMaterialMode" not in widget
    assert "cardMaterialMode" not in visualizer
    assert "materialSurfaceTint" not in context
    assert "material_mask" not in host
    assert "card_material" not in host


def test_widget_theme_schema_is_colour_only_v3() -> None:
    spec = _text(ROOT / "ui" / "widget_theme_spec.py")
    io = _text(ROOT / "ui" / "widget_theme_io.py")
    runtime = _text(ROOT / "ui" / "widget_theme_runtime.py")
    selection = _text(ROOT / "ui" / "widget_theme_selection.py")
    active = _text(ROOT / "ui" / "widget_theme_active.py")

    assert "WIDGET_THEME_SCHEMA_VERSION = 3" in spec
    for source in (spec, io, runtime, active):
        assert "default_card_material_mode" not in source
        assert "card_material_override" not in source
        assert "effective_card_material_mode" not in source
    # Selection contains the retired persisted key names only for a one-time
    # rewrite of an existing user's settings root; it never writes them back.
    assert selection.count('"card_material_override"') == 1
    assert selection.count('"default_card_material_mode"') == 1
    assert 'custom_payload.pop("default_card_material_mode", None)' in selection
    assert '"card_material_override" in values' in selection
    assert '"card_material_override":' not in selection
    assert '"default_card_material_mode":' not in selection
    assert "effective_card_material_mode" not in selection
    assert "get_active_widget_material_mode" not in active

def test_style_overrides_keep_colours_and_border_width_but_no_surface_style() -> None:
    source = _text(ROOT / "ui" / "tabs" / "widgets_tab_defaults.py")
    style_bucket = source.index('"Style Overrides"')
    layout_bucket = source.index('"Layout"', style_bucket)
    assert style_bucket < layout_bucket
    assert 'style_overrides_layout,\n        "Card Surface:"' in source
    assert 'style_overrides_layout,\n        "Card Border:"' in source
    assert 'style_overrides_layout,\n        "Card Border Width:"' in source
    assert '"Surface Style:"' not in source
    assert "widget_surface_style_combo" not in source


def test_widget_mirrors_are_strict_colour_only_v3_with_clean_names_and_filenames() -> None:
    paths = tuple((ROOT / "themes" / "widgets").glob("*.srwtheme"))
    assert len(paths) == 58
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["schema_version"] == 3, path.name
        assert "default_card_material_mode" not in payload, path.name
        assert not payload["name"].endswith(" [Glass]"), path.name
        assert not payload["name"].endswith(" [Acrylic]"), path.name
        assert not path.stem.endswith(" [Glass]"), path.name
        assert not path.stem.endswith(" [Acrylic]"), path.name


def test_only_preexisting_local_image_multieffects_remain() -> None:
    allowed = {
        "AbandonmentIssuesPresentation.qml",
        "AchievementPulsePresentation.qml",
        "BrandedHeader.qml",
        "MediaPresentation.qml",
    }
    found = set()
    for path in QML.glob("*.qml"):
        text = _text(path)
        if "MultiEffect" in text and not path.name in {"ShadowedText.qml", "Separator.qml"}:
            # Ignore explanatory comments in the two explicitly no-effect helpers.
            found.add(path.name)
    assert found == allowed
    for path in QML.glob("*.qml"):
        text = _text(path)
        code = re.sub(r"//.*?$", "", text, flags=re.MULTILINE)
        uses_qtquick_effect_type = "MultiEffect" in code or "RectangularShadow" in code
        has_effects_import = "import QtQuick.Effects" in code
        # QtQuick.Effects is still required by the accepted cached RectangularShadow
        # card/menu/header shadows. The rollback rejects backdrop/card MultiEffect,
        # not the module import needed by those pre-existing local shadow primitives.
        assert has_effects_import is uses_qtquick_effect_type, path.name


def test_cleanup_gui_targets_stale_material_named_widget_mirrors_only() -> None:
    helper = _text(ROOT / "tools" / "material_rollback_cleanup_gui.py")
    assert '" [Glass].srwtheme"' in helper
    assert '" [Acrylic].srwtheme"' in helper
    assert 'path.name.endswith' in helper
    assert 'root / "themes" / "widgets"' in helper
    assert 'root / "themes"' not in helper.replace('root / "themes" / "widgets"', "")


def test_settings_native_backdrops_remain_separate_and_supported() -> None:
    settings_spec = _text(ROOT / "ui" / "settings_theme_spec.py")
    settings_dialog = _text(ROOT / "ui" / "settings_dialog.py")
    assert 'NATIVE_BACKDROP_MODES = frozenset({"off", "acrylic", "glass"})' in settings_spec
    assert "Acrylic" in settings_dialog
    assert "Glass" in settings_dialog
