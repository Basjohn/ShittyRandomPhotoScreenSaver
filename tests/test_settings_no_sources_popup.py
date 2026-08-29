"""Current Settings-dialog no-source recovery contract.

The Settings GUI now uses the shared :class:`ui.styled_popup.StyledPopup` rather
than a dedicated ``NoSourcesPopup`` class.  These tests deliberately exercise
the SettingsDialog methods as unbound behavior so they verify routing without
constructing the entire heavy/lazy Settings window.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from ui.settings_dialog import SettingsDialog


class _Settings:
    def __init__(self, values=None):
        self.values = dict(values or {})
        self.save_calls = 0

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value

    def save(self):
        self.save_calls += 1


@pytest.mark.parametrize(
    ("folders", "feeds", "expected"),
    (
        (["C:/Pictures"], [], True),
        ([], ["https://example.invalid/feed"], True),
        (["C:/Pictures"], ["https://example.invalid/feed"], True),
        ([], [], False),
    ),
)
def test_has_image_sources_uses_folders_or_rss(folders, feeds, expected):
    host = SimpleNamespace(
        _settings=_Settings(
            {
                "sources.folders": folders,
                "sources.rss_feeds": feeds,
            }
        )
    )
    assert SettingsDialog._has_image_sources(host) is expected


@pytest.mark.parametrize(
    ("result_value", "expected_action"),
    (("defaults", "defaults"), ("exit", "exit")),
)
def test_no_sources_uses_central_styled_popup_and_routes_result(
    monkeypatch,
    result_value,
    expected_action,
):
    import ui.settings_dialog as settings_dialog_module

    captured = {}

    class _Popup:
        def __init__(
            self,
            parent,
            title,
            message,
            *,
            icon_type,
            buttons,
            default_button_index,
        ):
            captured.update(
                parent=parent,
                title=title,
                message=message,
                icon_type=icon_type,
                buttons=buttons,
                default_button_index=default_button_index,
            )
            self.result_value = result_value

        def exec(self):
            captured["exec_called"] = True

    monkeypatch.setattr(settings_dialog_module, "StyledPopup", _Popup)

    actions = []
    host = SimpleNamespace()
    host._on_add_default_sources = lambda: actions.append("defaults")
    host._on_exit_without_sources = lambda: actions.append("exit")

    SettingsDialog._show_no_sources_popup(host)

    assert captured["parent"] is host
    assert captured["title"] == "No Image Sources"
    assert captured["icon_type"] == "warning"
    assert captured["buttons"] == [
        ("Just Make It Work", "defaults"),
        ("Ehhhh", "exit"),
    ]
    assert captured["default_button_index"] == 0
    assert captured["exec_called"] is True
    assert actions == [expected_action]


def test_add_default_sources_uses_curated_rss_contract_and_closes():
    from sources.rss.constants import DEFAULT_RSS_FEEDS

    settings = _Settings({"sources.rss_feeds": []})
    reload_calls = []
    close_calls = []
    sources_tab = SimpleNamespace(_load_settings=lambda: reload_calls.append(True))
    host = SimpleNamespace(
        _settings=settings,
        _get_tab_instance=lambda key: sources_tab if key == "sources" else None,
        close=lambda: close_calls.append(True),
    )

    SettingsDialog._on_add_default_sources(host)

    assert settings.values["sources.rss_feeds"] == list(DEFAULT_RSS_FEEDS.values())
    assert settings.save_calls == 1
    assert reload_calls == [True]
    assert close_calls == [True]


def test_exit_without_sources_uses_application_exit_contract():
    host = SimpleNamespace()
    with patch("ui.settings_dialog.sys.exit") as exit_mock:
        SettingsDialog._on_exit_without_sources(host)
    exit_mock.assert_called_once_with(0)
