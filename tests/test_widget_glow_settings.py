"""Focused Settings and DisplayTab coverage for widget interaction glow."""

import uuid
from dataclasses import replace

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtGui import QColor

from core.settings import SettingsManager
from core.settings.models import InputSettings
from ui import widget_theme_active
from ui.settings_theme_spec import Rgba
from ui.tabs.display_tab import DisplayTab
from ui.widget_theme_spec import DEFAULT_DARK_WIDGET_THEME


def _theme_with_border(color: Rgba):
    colors = dict(DEFAULT_DARK_WIDGET_THEME.colors)
    colors["card.border"] = color
    return replace(DEFAULT_DARK_WIDGET_THEME, colors=colors)


def _settings(tmp_path, name: str):
    return SettingsManager(
        organization="Test",
        application=f"{name}_{uuid.uuid4().hex}",
        storage_base_dir=tmp_path,
    )


def test_widget_glow_defaults_inherit_theme_and_model_roundtrip(tmp_path):
    settings = _settings(tmp_path, "WidgetGlowDefaults")

    assert settings.get("input.widget_glow_on_hover") is False
    assert settings.get("input.widget_glow_on_click") is False
    assert settings.get("input.widget_glow_color") is None

    model = InputSettings.from_settings(settings)
    assert model.widget_glow_color is None
    assert model.to_dict()["input.widget_glow_color"] is None

    settings.set("input.widget_glow_on_hover", True)
    settings.set("input.widget_glow_on_click", True)
    settings.set("input.widget_glow_color", [12, 34, 56, 200])
    model = InputSettings.from_settings(settings)
    assert model.widget_glow_on_hover is True
    assert model.widget_glow_on_click is True
    assert model.widget_glow_color == [12, 34, 56, 200]
    assert model.to_dict()["input.widget_glow_color"] == [12, 34, 56, 200]


def test_display_tab_inherited_swatch_and_unrelated_save_keep_none(qt_app, tmp_path):
    theme = _theme_with_border(Rgba(22, 77, 155, 211))
    widget_theme_active.set_active_widget_theme(theme)
    try:
        settings = _settings(tmp_path, "WidgetGlowInherited")
        tab = DisplayTab(settings)

        assert tab._widget_glow_color_override is None
        assert tab.widget_glow_color_btn.color().getRgb() == (22, 77, 155, 211)
        tab.load_from_settings()
        tab._save_settings()
        assert settings.get("input.widget_glow_color") is None
        tab.deleteLater()
    finally:
        qt_app.processEvents()
        widget_theme_active.reset_active_widget_theme()


def test_display_tab_explicit_choice_is_retained_even_when_equal_to_theme(
    qt_app, tmp_path
):
    theme_color = Rgba(44, 88, 132, 220)
    widget_theme_active.set_active_widget_theme(_theme_with_border(theme_color))
    try:
        settings = _settings(tmp_path, "WidgetGlowExplicit")
        tab = DisplayTab(settings)
        tab._on_widget_glow_color_changed(QColor(*theme_color.as_tuple()))

        assert tab._widget_glow_color_override == list(theme_color.as_tuple())
        assert settings.get("input.widget_glow_color") == list(theme_color.as_tuple())
        tab.deleteLater()
    finally:
        qt_app.processEvents()
        widget_theme_active.reset_active_widget_theme()


def test_display_tab_use_theme_clears_override_and_refreshes_swatch(qt_app, tmp_path):
    theme = _theme_with_border(Rgba(90, 130, 170, 180))
    widget_theme_active.set_active_widget_theme(theme)
    try:
        settings = _settings(tmp_path, "WidgetGlowUseTheme")
        settings.set("input.widget_glow_color", [1, 2, 3, 4])
        tab = DisplayTab(settings)
        tab.widget_glow_use_theme_btn.click()

        assert tab._widget_glow_color_override is None
        assert settings.get("input.widget_glow_color") is None
        assert tab.widget_glow_color_btn.color().getRgb() == (90, 130, 170, 180)
        tab.deleteLater()
    finally:
        qt_app.processEvents()
        widget_theme_active.reset_active_widget_theme()


def test_display_tab_widget_theme_subscription_unsubscribes_on_destroy(qt_app, tmp_path):
    settings = _settings(tmp_path, "WidgetGlowLifecycle")
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qt_app.processEvents()
    before = len(widget_theme_active._listeners)
    tab = DisplayTab(settings)
    assert len(widget_theme_active._listeners) == before + 1

    tab.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qt_app.processEvents()
    assert len(widget_theme_active._listeners) == before
