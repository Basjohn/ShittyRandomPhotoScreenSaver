"""Explicit light-theme modifier at the global shadow/style projection seam."""
from dataclasses import asdict, replace
from importlib import import_module
import math

import pytest

from core.settings.default_contract import require_canonical_default
from core.settings.models import ShadowSettings
from rendering.quick.shadow_snapshot import QuickShadowSnapshot
from ui.settings_theme_spec import Rgba
from ui.theme_semantics import uses_dark_text_on_light_surface, widget_theme_is_light
from ui.widget_theme_spec import DEFAULT_DARK_WIDGET_THEME


def _theme(light):
    colors = dict(DEFAULT_DARK_WIDGET_THEME.colors)
    colors["card.text"] = Rgba(30, 25, 35) if light else Rgba(240, 235, 245)
    colors["card.background"] = Rgba(240, 235, 245, 110) if light else Rgba(30, 25, 35, 110)
    return replace(DEFAULT_DARK_WIDGET_THEME, name="Fixture", colors=colors)


def _shadows(**changes):
    return {"enabled": True, "text_enabled": True, "soft_text_on_light_themes": False,
            "header_enabled": True, "color": [12, 16, 20, 200], "blur_radius": 9,
            "text_opacity": .61, "frame_opacity": .37, "direction": "NW",
            "frame_extra_offset": 5, "text_extra_offset": 3, **changes}


def _style(family, shadows):
    if family == "steam":
        from rendering.quick.widgets.steam_common import project_steam_card_style
        return project_steam_card_style(show_background=True, background_color=(20,30,40,100),
            background_opacity=.6, border_color=(100,110,120,200), border_opacity=.7,
            shadow_values=shadows, border_width=2.)
    module = import_module("rendering.quick.widgets." + family)
    name = {"feeds": "Feed", "system_stats": "SystemStats"}.get(family, family.title())
    config_type = getattr(module, name + "PresentationConfig")
    if family == "clock":
        config = config_type.from_widgets_mapping("clock", {})
    elif family == "feeds":
        config = config_type.from_widgets_mapping({}, widget_id="feeds_news_anime")
    else:
        config = config_type.from_widgets_mapping({})
    return getattr(module, name + "PresentationStyle").project(config, shadows)


@pytest.mark.parametrize("family", ["clock", "weather", "feeds", "gmail", "media", "reddit", "steam", "system_stats"])
def test_light_modifier_changes_only_text_filter_style(family, monkeypatch):
    import rendering.quick.widgets.theme_projection as projection
    monkeypatch.setattr(projection, "get_active_widget_theme", lambda: _theme(True))
    off = _style(family, _shadows())
    on = _style(family, _shadows(soft_text_on_light_themes=True))
    assert off.text_shadow_enabled is True
    assert on.text_shadow_enabled is True
    assert off.text_shadow_soft is False
    assert on.text_shadow_soft is True
    assert replace(off, text_shadow_soft=True) == on
    assert (on.text_shadow_offset_x, on.text_shadow_offset_y) == (-5., -5.)
    assert on.text_shadow_color.alpha() == round(200 * .61)
    assert _style(family, _shadows(text_enabled=False, soft_text_on_light_themes=True)).text_shadow_enabled is False
    assert _style(family, _shadows(text_enabled=False, soft_text_on_light_themes=True)).text_shadow_soft is False


@pytest.mark.parametrize("family", ["clock", "weather", "feeds", "gmail", "media", "reddit", "steam", "system_stats"])
def test_dark_projection_is_identical_with_either_light_modifier(family, monkeypatch):
    import rendering.quick.widgets.theme_projection as projection
    monkeypatch.setattr(projection, "get_active_widget_theme", lambda: _theme(False))
    assert _style(family, _shadows()) == _style(family, _shadows(soft_text_on_light_themes=True))


def test_classification_uses_shared_palette_polarity_not_name_or_alpha():
    light = _theme(True)
    assert widget_theme_is_light(light)
    assert widget_theme_is_light(replace(light, name="Dark label on a light fixture"))
    assert not widget_theme_is_light(_theme(False))
    assert uses_dark_text_on_light_surface(Rgba(30,25,35), Rgba(240,235,245,0))


@pytest.mark.parametrize("module_name,class_name", [
    ("clock", "Clock"), ("weather", "Weather"), ("feeds", "Feed"),
    ("gmail", "Gmail"), ("media", "Media"), ("reddit", "Reddit"),
    ("system_stats", "SystemStats"), ("games_you_follow", "GamesYouFollow"),
    ("achievement_pulse", "AchievementPulse"), ("friend_pulse", "FriendPulse"),
    ("abandonment_issues", "AbandonmentIssues"),
])
def test_every_ordinary_model_exposes_its_projected_soft_style_to_qml(module_name, class_name):
    model = getattr(import_module("rendering.quick.widgets." + module_name), class_name + "PresentationModel")
    assert model.staticMetaObject.indexOfProperty("textShadowSoft") >= 0


@pytest.mark.parametrize("family,helper", [
    ("clock", "_shadow_values"), ("weather", "_shadow_values"),
    ("media", "_shadows"), ("gmail", "_shadows"), ("reddit", "_shadows"),
    ("achievement_pulse", "_shadows"), ("abandonment_issues", "_shadows"),
])
def test_native_smoke_fixture_supplies_the_complete_strict_shadow_contract(family, helper):
    smoke = import_module("tools.qtquick_" + family + "_smoke")
    resolved = QuickShadowSnapshot.from_mapping(getattr(smoke, helper)("NW"))
    assert resolved.direction.value == "NW"


def test_soft_shadow_capture_preserves_logical_geometry_and_follows_source_edges(qt_app):
    from pathlib import Path
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression
    from PySide6.QtQuick import QQuickItem
    engine = QQmlEngine()
    component = QQmlComponent(engine)
    root = Path(__file__).resolve().parents[1] / "rendering/quick/qml"
    component.setData(b'import QtQuick; import "."; ShadowedText { width: 300; height: 60; text: "Before"; shadowSoft: true; shadowOffsetX: -7; shadowOffsetY: 9 }',
                      QUrl.fromLocalFile(str(root / "test_fixture.qml")))
    item = component.create()
    assert item is not None, component.errors()
    main = item.findChild(QQuickItem, "shadowedTextMain")
    shadow = item.findChild(QQuickItem, "shadowedTextShadow")
    def value(expression):
        query = QQmlExpression(engine.rootContext(), shadow, expression)
        result, undefined = query.evaluate()
        assert not undefined and not query.hasError(), query.error()
        return result
    try:
        assert (main.x(), main.y(), shadow.x(), shadow.y()) == (0, 0, -3.5, 4.5)   # soft: half the offset
        assert value("layer.enabled")
        dpr = qt_app.primaryScreen().devicePixelRatio()
        assert value("layer.textureSize.width") == math.ceil(300 * dpr * .5)
        item.setProperty("text", "After")
        item.setWidth(200)
        assert main.property("text") == shadow.property("text") == "After"
        assert main.width() == shadow.width() == 200
        assert value("layer.textureSize.width") == math.ceil(200 * dpr * .5)
        item.setProperty("shadowSoft", False)
        assert not value("layer.enabled")
        assert value("layer.textureSize.width") == 0
        assert (shadow.x(), shadow.y()) == (-7, 9)                                    # hard: the full offset
    finally:
        item.deleteLater()


def test_soft_separator_shadow_sits_at_half_the_offset(qt_app):
    from pathlib import Path
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtQuick import QQuickItem
    engine = QQmlEngine()
    component = QQmlComponent(engine)
    root = Path(__file__).resolve().parents[1] / "rendering/quick/qml"
    component.setData(b'import QtQuick; import "."; Separator { width: 100; shadowEnabled: true; shadowSoft: true; shadowOffsetX: -6; shadowOffsetY: 8 }',
                      QUrl.fromLocalFile(str(root / "test_fixture.qml")))
    item = component.create()
    assert item is not None, component.errors()
    try:
        shadow = item.findChild(QQuickItem, "overlaySeparatorShadow")
        assert (shadow.x(), shadow.y()) == (-3, 4)
        item.setProperty("shadowSoft", False)
        assert (shadow.x(), shadow.y()) == (-6, 8)
    finally:
        item.deleteLater()


def test_global_model_repairs_old_profiles_and_round_trips_the_explicit_modifier(tmp_path):
    from core.settings import SettingsManager
    expected = require_canonical_default("widgets.shadows.soft_text_on_light_themes")
    assert ShadowSettings.from_widgets_map({"shadows": {"text_enabled": True}}).soft_text_on_light_themes == expected
    manager = SettingsManager(application="LightShadowFixture", storage_base_dir=tmp_path)
    manager.set("widgets.shadows.soft_text_on_light_themes", not expected)
    model = ShadowSettings.from_settings(manager)
    assert model.soft_text_on_light_themes == (not expected)
    assert model.to_dict()["widgets.shadows.soft_text_on_light_themes"] == (not expected)
    assert QuickShadowSnapshot.from_mapping(asdict(model)).soft_text_on_light_themes == (not expected)
    assert manager.flush()
    reopened = SettingsManager(application="LightShadowFixture", storage_base_dir=tmp_path)
    assert ShadowSettings.from_settings(reopened).soft_text_on_light_themes == (not expected)


def test_general_checkbox_load_save_and_reset_preserve_other_shadow_controls(qt_app, tmp_path):
    from PySide6.QtCore import QCoreApplication, QEvent
    from core.settings import SettingsManager
    from ui.tabs.widgets_tab import WidgetsTab
    from ui.settings_theme_runtime import get_active_settings_theme
    manager = SettingsManager(application="LightShadowUiFixture", storage_base_dir=tmp_path)
    tab = WidgetsTab(manager, lazy_sections=True, initial_view_state={"subtab_id": "defaults"})
    before = ShadowSettings.from_settings(manager)
    settings_theme_before = get_active_settings_theme()
    try:
        checkbox = tab.widget_soft_text_shadows_on_light_themes
        assert checkbox.isChecked() == before.soft_text_on_light_themes
        checkbox.setChecked(not before.soft_text_on_light_themes)
        tab._save_settings_now()
        assert ShadowSettings.from_settings(manager) == replace(before, soft_text_on_light_themes=not before.soft_text_on_light_themes)
        assert get_active_settings_theme() == settings_theme_before
        tab._load_settings()
        assert checkbox.isChecked() == (not before.soft_text_on_light_themes)
        manager.reset_to_defaults()
        tab._load_settings()
        assert checkbox.isChecked() == require_canonical_default("widgets.shadows.soft_text_on_light_themes")
    finally:
        tab.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
