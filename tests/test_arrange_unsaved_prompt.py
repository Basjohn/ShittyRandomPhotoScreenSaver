"""Leaving Arrange with an unapplied draft asks Apply / Discard / Stay.

Quick Start (a real SettingsDialog: tab switch and close) and Guided Setup
(Back/Next from its Arrange step) ask the same question. No window is shown:
the popup's exec is replaced by the operator's choice and the dialog reports
itself visible so its close checks run.
"""
from __future__ import annotations

from copy import deepcopy

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


def _answer(monkeypatch, answers, asked):
    """Each popup takes the next answer (None = closed without choosing)."""
    def fake_exec(popup):
        asked.append(popup)
        popup._result_value = answers.pop(0)
        return 1
    monkeypatch.setattr(StyledPopup, "exec", fake_exec)


def _drag_first_box(page) -> None:
    item = page.model.session.items()[0]
    page.model.move(item.source_key, QRect(item.current_global_rect).translated(40, 20), snap=False)
    page._pending_changed()
    assert page.model.pending


@pytest.mark.parametrize("choice,leaves,applied", [("apply", True, True), ("discard", True, False),
                                                   ("stay", False, False), (None, False, False)])
def test_leaving_with_a_draft_applies_discards_or_stays(monkeypatch, choice, leaves, applied) -> None:
    from ui.onboarding.arrange import ArrangePage

    settings = _Settings()
    page = ArrangePage(settings)
    _drag_first_box(page)
    asked = []
    _answer(monkeypatch, [choice], asked)
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
    _answer(monkeypatch, ["stay"], asked)
    page = ArrangePage(_Settings())
    try:
        assert page.resolve_pending() is True
        assert asked == []
    finally:
        page.deleteLater()


@pytest.fixture
def dialog(tmp_path):
    from core.animation.animator import AnimationManager
    from core.settings.settings_manager import SettingsManager
    from ui.settings_dialog import SettingsDialog

    settings = SettingsManager(organization="SRPSS_Test", application=f"arrange_prompt_{tmp_path.name}",
                               storage_base_dir=tmp_path)
    settings.set("sources.folders", [str(tmp_path)])  # an image source: close reaches the Arrange check
    animations = AnimationManager()
    result = SettingsDialog(settings, animations)
    result.isVisible = lambda: True  # never shown; its close checks apply as if it were
    yield result
    result.deleteLater()
    animations.cleanup()


def _quick_start_with_draft(dialog):
    index = dialog._tab_index_for_key("quick_start")
    dialog._switch_tab(index, animate=False)
    quick_start = dialog.quick_start_tab
    quick_start.arrange_toggle.setChecked(True)
    arrange = quick_start.arrange
    if not arrange.model.session.items():
        pytest.skip("default settings enable no arrangeable widget")
    _drag_first_box(arrange)
    return index, arrange


def test_quick_start_draft_asks_before_another_tab_and_before_closing(dialog, monkeypatch) -> None:
    index, arrange = _quick_start_with_draft(dialog)
    asked = []

    _answer(monkeypatch, ["stay"], asked)
    dialog._switch_tab(0, animate=False)
    assert len(asked) == 1
    assert dialog.content_stack.currentIndex() == index  # stayed on Quick Start
    assert arrange.model.pending

    _answer(monkeypatch, ["stay"], asked)
    assert dialog.close() is False  # Stay In Arrange cancels the close
    assert len(asked) == 2 and arrange.model.pending

    _answer(monkeypatch, ["discard"], asked)
    dialog._switch_tab(0, animate=False)
    assert len(asked) == 3
    assert dialog.content_stack.currentIndex() == 0
    assert not arrange.model.pending


def test_guided_setup_arrange_step_asks_on_back_and_next(monkeypatch) -> None:
    from ui.onboarding.wizard import GuidedSetupPanel

    class _Real(_Settings):
        def save(self):
            pass

    panel = GuidedSetupPanel(_Real())
    try:
        panel.show_page("arrange")
        arrange = panel.pages["arrange"][0]
        _drag_first_box(arrange)
        asked = []
        _answer(monkeypatch, ["stay", "stay"], asked)
        panel.go_back()
        assert panel.current_key == "arrange"
        panel.go_next()
        assert panel.current_key == "arrange" and len(asked) == 2 and arrange.model.pending

        _answer(monkeypatch, ["apply"], asked)
        panel.go_next()
        assert len(asked) == 3
        assert panel.current_key == "ready"
        assert not arrange.model.pending
    finally:
        panel.close_setup(False)
        panel.deleteLater()
