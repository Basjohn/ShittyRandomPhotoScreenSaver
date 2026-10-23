"""Test theme-processing behavior with test-owned themes, never curated art values.

A former version required six named, operator-authored themes to exist and pinned
luminance, opacity and shadow limits on their artistic contents. Those are NOT
product contracts: adding/renaming/deleting/tuning themes must never fail tests.
"""
from __future__ import annotations

from dataclasses import replace

from tools.generate_widget_theme_mirrors import (
    _runtime_card_surface, _uses_dark_text_on_light_surface,
    widget_counterpart_for_settings_theme,
)
from ui.settings_theme_io import settings_theme_from_json, settings_theme_to_json
from ui.settings_theme_spec import DEFAULT_DARK_SETTINGS_THEME, Rgba
from ui.widget_theme_io import widget_theme_from_json, widget_theme_to_json


def _test_theme(*, light: bool):
    # Test-owned visual inputs. No current Settings/theme/preset values are read.
    colors = dict(DEFAULT_DARK_SETTINGS_THEME.colors)
    colors['text.primary'] = Rgba(15, 23, 29) if light else Rgba(240, 240, 245)
    colors['panel.group.surface'] = Rgba(245, 245, 239, 105) if light else Rgba(22, 26, 30, 190)
    return replace(DEFAULT_DARK_SETTINGS_THEME, name='Synthetic Test', colors=colors)


def test_light_card_projection_establishes_wallpaper_independent_alpha_floor() -> None:
    theme = _test_theme(light=True)
    assert _uses_dark_text_on_light_surface(theme)
    assert _runtime_card_surface(theme).a >= 232
    assert _runtime_card_surface(theme).r == theme.color('panel.group.surface').r


def test_dark_card_projection_does_not_force_light_theme_alpha_floor() -> None:
    theme = _test_theme(light=False)
    assert not _uses_dark_text_on_light_surface(theme)
    assert _runtime_card_surface(theme) == theme.color('panel.group.surface')


def test_fixture_settings_widget_theme_pair_round_trips_exactly() -> None:
    theme = _test_theme(light=True)
    widget = widget_counterpart_for_settings_theme(theme, settings_theme_id='file:Synthetic Test.srtheme')
    assert widget.linked_settings_theme_id == 'file:Synthetic Test.srtheme'
    assert widget.theme_id == 'mirror:file:Synthetic Test.srtheme'
    assert settings_theme_from_json(settings_theme_to_json(theme)) == theme
    assert widget_theme_from_json(widget_theme_to_json(widget)) == widget
    assert widget.name == 'Synthetic Test'
    for role in ('card.background', 'card.border', 'card.text', 'media.transport.surface'):
        assert role in widget.colors
