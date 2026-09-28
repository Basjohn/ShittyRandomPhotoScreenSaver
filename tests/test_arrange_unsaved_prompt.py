"""Leaving Arrange with an unapplied draft asks Apply / Discard / Stay.

Settings → Quick Start's Arrange applies nothing until Apply. Closing Settings,
switching tab or starting Guided Setup with a draft asks first; staying keeps
the draft and Quick Start in view. No window is shown: the popup's exec is
replaced by the operator's choice.
"""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QRect

from core.settings.default_settings import DEFAULT_SETTINGS
from ui.styled_popup import StyledPopup

pytestmark = pytest.mark.usefixtures("qt_app")


class _Settings:
    def __init__(self):
        widgets = deepcopy(DEFAULT_SETTINGS["widgets"])
        widgets["family_activation"] = {family: family == "weather" for family in widgets["family_activation"]}
        widgets["weather"].update(enabled=True, monitor="ALL")
        self.values = {"widgets": widgets, "display": {"show_on_monitors": "ALL"}}
        self.writes = []

    def get(self, key, default=None):
        value = self.values
        for part in key.split("."):
            if not isinstance(value, dict) or part not in value:
                return deepcopy(default)
            value = value[part]
        return deepcopy(value)

    def set(self, key, value):
        self.writes.append(key)
        self.values[key] = deepcopy(value)


def _choose(monkeypatch, choice, asked):
    def fake_exec(popup):
        asked.append(popup)
        popup._result_value = choice
        return 1
    monkeypatch.setattr(StyledPopup, "exec", fake_exec)


def _page_with_draft():
    from ui.onboarding.arrange import ArrangePage

    settings = _Settings()
    page = ArrangePage(settings)
    item = page.model.session.items()[0]
    page.model.move(item.source_key, QRect(item.current_global_rect).translated(40, 20), snap=False)
    assert page.model.pending
    return page, settings


@pytest.mark.parametrize("choice,leaves,applied", [("apply", True, True), ("discard", True, False),
                                                   ("stay", False, False), (None, False, False)])
def test_leaving_with_a_draft_applies_discards_or_stays(monkeypatch, choice, leaves, applied) -> None:
    page, settings = _page_with_draft()
    asked = []
    _choose(monkeypatch, choice, asked)
    try:
        assert page.resolve_pending() is leaves
        assert len(asked) == 1
        assert ("widgets" in settings.writes) is applied
        assert page.model.pending is (not leaves)  # staying keeps the draft
    finally:
        page.deleteLater()


def test_nothing_is_asked_without_a_draft(monkeypatch) -> None:
    from ui.onboarding.arrange import ArrangePage

    asked = []
    _choose(monkeypatch, "stay", asked)
    page = ArrangePage(_Settings())
    try:
        assert page.resolve_pending() is True
        assert asked == []
    finally:
        page.deleteLater()


def test_settings_asks_quick_start_and_stays_on_its_tab(monkeypatch) -> None:
    from ui.settings_dialog import SettingsDialog

    answers = []
    quick_start = SimpleNamespace(resolve_pending_arrange=lambda: answers.pop(0))
    buttons = [SimpleNamespace(checked=False, setChecked=None) for _ in range(3)]
    for button in buttons:
        button.setChecked = lambda value, b=button: setattr(b, "checked", value)
    host = SimpleNamespace(
        tab_buttons=buttons, _tab_widgets={"quick_start": quick_start},
        _admit_top_level_tab_index=lambda index: index, _tab_index_for_key=lambda key: 2,
        content_stack=SimpleNamespace(currentIndex=lambda: 2), isVisible=lambda: True,
        _ensure_tab_built=lambda index: (_ for _ in ()).throw(AssertionError("switched despite Stay")),
    )
    host._resolve_pending_arrange = lambda: SettingsDialog._resolve_pending_arrange(host)

    answers.append(False)  # Stay In Arrange
    SettingsDialog._switch_tab(host, 0)
    assert [b.checked for b in buttons] == [False, False, True]

    # Without a Quick Start page there is nothing to settle.
    assert SettingsDialog._resolve_pending_arrange(SimpleNamespace(_tab_widgets={})) is True
