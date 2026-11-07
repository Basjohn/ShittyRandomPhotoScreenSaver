"""AC-09: one card-border width, the same on every card and on the General page.

Every consumer path reads the stored ``widgets.global.card_border_width_px``
through its own production entry point; all must agree for test-owned values,
including out-of-range and malformed ones. The expected width is derived from
the canonical default, never pinned.
"""
from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from core.settings.default_contract import require_canonical_default

_MISSING = object()
_CANONICAL = float(require_canonical_default("widgets.global.card_border_width_px"))

# TEST INPUT: (label, stored value or _MISSING, expected drawn width)
_CASES = (
    ("nan", float("nan"), _CANONICAL),
    ("inf", float("inf"), _CANONICAL),
    ("-inf", float("-inf"), _CANONICAL),
    ("negative", -1, 0.0),
    ("over range", 12.5, 12.0),
    ("text", "x", _CANONICAL),
    ("numeric text", "3.5", 3.5),
    ("fraction", 2.5, 2.5),
    ("in range", 7, 7.0),
    ("none", None, _CANONICAL),
    ("missing", _MISSING, _CANONICAL),
)


def _widgets(value: object) -> dict:
    return {"global": {} if value is _MISSING else {"card_border_width_px": value}}


def _family_binder_width(qt_app, widgets: dict) -> float:
    from rendering.quick.widgets.family_binder import ClockFamilyAdapter

    adapter = ClockFamilyAdapter()
    model = adapter.presentation_model(
        widget_id="clock", widgets_config=widgets,
        shadow_values=require_canonical_default("widgets.shadows"),
        display_identity="screen:a", runtime_generation=991,
    )
    try:
        return float(adapter.presentation_card_style(model).border_width)
    finally:
        if hasattr(model, "retire"):
            model.retire()
        qt_app.processEvents()


def _games_you_follow_width(_qt_app, widgets: dict) -> float:
    from rendering.quick.widgets.games_you_follow import followed_card_style

    return float(followed_card_style(widgets).border_width)


def _system_audio_osd_width(_qt_app, widgets: dict) -> float:
    from rendering.quick.widgets.system_audio_osd import SystemAudioOSDConfig

    return float(SystemAudioOSDConfig.from_widgets_mapping(widgets).card_style.border_width)


def _studio_card_style_width(_qt_app, widgets: dict) -> float:
    from ui.studio.settings_link import VisualizerSettingsStore

    store = VisualizerSettingsStore.__new__(VisualizerSettingsStore)
    store._tab = SimpleNamespace(_settings=SimpleNamespace(get=lambda key, default=None: widgets))
    style = store.card_style()
    assert style is not None, "the Studio lost its live card style"
    return float(style["border_width"])


class _CapturedCard(Exception):
    pass


def _visualizer_card_width(_qt_app, widgets: dict, monkeypatch) -> float:
    """The live Visualizer card: the kwargs its single owner is constructed with."""

    import widgets.spotify_visualizer.quick_display_visualizer_owner as owner_module
    from tests.test_visualizer_custom_route_contract import _live_unit, _manager

    captured: dict = {}

    def _capture(*_args, **kwargs):
        captured.update(kwargs["card_shadow_kwargs"])
        raise _CapturedCard

    monkeypatch.setattr(owner_module, "QuickDisplayVisualizerOwner", _capture)
    manager = _manager("Center")
    manager._widgets_config_snapshot.update(widgets)
    with pytest.raises(_CapturedCard):
        manager._construct_quick_visualizer_owner_on(_live_unit(0))
    return float(captured["border_width"])


_CARD_CONSUMERS = {
    "family binder": _family_binder_width,
    "games you follow": _games_you_follow_width,
    "system audio osd": _system_audio_osd_width,
    "studio card style": _studio_card_style_width,
}


@pytest.mark.qt
@pytest.mark.parametrize("label, value, expected", _CASES, ids=[case[0] for case in _CASES])
def test_every_card_consumer_draws_the_same_border_width(qt_app, monkeypatch, label, value, expected) -> None:
    widgets = _widgets(value)
    drawn = {name: consumer(qt_app, widgets) for name, consumer in _CARD_CONSUMERS.items()}
    drawn["visualizer card"] = _visualizer_card_width(qt_app, widgets, monkeypatch)
    for name, width in drawn.items():
        assert math.isfinite(width), (label, name, width)
    assert drawn == {name: pytest.approx(expected) for name in drawn}, label


@pytest.mark.qt
@pytest.mark.parametrize("label, value, expected", _CASES, ids=[case[0] for case in _CASES])
def test_the_general_page_shows_and_saves_the_cards_width_in_whole_pixels(
    qt_app, settings_manager, label, value, expected,
) -> None:
    from ui.tabs.widgets_tab import WidgetsTab
    from ui.tabs.widgets_tab_defaults import load_defaults_settings, save_defaults_settings

    tab = WidgetsTab(settings_manager)
    try:
        load_defaults_settings(tab, _widgets(value))
        assert tab.card_border_width_spin.value() == int(expected), label
        _shadows, global_config = save_defaults_settings(tab)
        assert global_config["card_border_width_px"] == int(expected), label
        assert isinstance(global_config["card_border_width_px"], int)
    finally:
        tab.deleteLater()
        qt_app.processEvents()


def test_a_malformed_global_section_resolves_like_a_missing_one(qt_app, monkeypatch) -> None:
    widgets = {"global": "not a mapping"}
    drawn = {name: consumer(qt_app, widgets) for name, consumer in _CARD_CONSUMERS.items()}
    drawn["visualizer card"] = _visualizer_card_width(qt_app, widgets, monkeypatch)
    assert drawn == {name: pytest.approx(_CANONICAL) for name in drawn}


@pytest.mark.parametrize("label, value, expected", _CASES, ids=[case[0] for case in _CASES])
def test_the_one_resolver_owns_the_drawn_and_admitted_widths(label, value, expected) -> None:
    from core.settings.default_contract import (
        CARD_BORDER_WIDTH_MAX_PX,
        CARD_BORDER_WIDTH_MIN_PX,
        resolve_card_border_width_px,
        resolve_card_border_width_setting_px,
    )

    widgets = _widgets(value)
    assert resolve_card_border_width_px(widgets) == pytest.approx(expected), label
    setting = resolve_card_border_width_setting_px(widgets)
    assert isinstance(setting, int)
    assert CARD_BORDER_WIDTH_MIN_PX <= setting <= CARD_BORDER_WIDTH_MAX_PX
    assert setting == int(expected), label
