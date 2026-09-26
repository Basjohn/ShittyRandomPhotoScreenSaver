"""Shared Settings-theme selection transaction regression bars."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from ui.widget_theme_runtime import WidgetThemeState
import ui.settings_theme_selection as selection


@dataclass
class _Entry:
    theme_id: str


class _Catalog:
    def __init__(self): self.entries = {"old": _Entry("old"), "new": _Entry("new")}
    def entry_by_id(self, theme_id): return self.entries.get(theme_id)


def _wire(monkeypatch, *, linked: bool, fail_activate: bool = False):
    calls = []
    state = WidgetThemeState(selected_id="independent", keep_synced=linked, custom_payload=None)
    monkeypatch.setattr(selection, "read_widget_theme_state", lambda _settings: state)
    monkeypatch.setattr(selection, "synced_widget_theme_id_for_settings", lambda _catalog, theme_id: "mirror:new" if theme_id == "new" else "mirror:old")
    monkeypatch.setattr(selection, "get_current_widget_theme_catalog", lambda: object())
    monkeypatch.setattr(selection, "read_persisted_theme_id", lambda _settings: "old")
    monkeypatch.setattr(selection, "get_active_settings_theme", lambda: "old-theme")
    monkeypatch.setattr(selection, "set_active_settings_theme", lambda theme: calls.append(("restore-runtime", theme)))
    monkeypatch.setattr(selection, "persist_settings_theme_selection", lambda _settings, _catalog, theme_id: calls.append(("persist", theme_id)))
    def activate(entry):
        calls.append(("activate", entry.theme_id))
        if fail_activate: raise RuntimeError("renderer failed")
    monkeypatch.setattr(selection, "activate_catalog_theme", activate)
    monkeypatch.setattr(selection, "activate_widget_theme_state", lambda _settings, next_state, **kwargs: calls.append(("widget", next_state.selected_id, kwargs["settings_theme_id"])))
    return calls


def test_shared_theme_selection_preserves_decoupled_widget_identity(monkeypatch):
    calls = _wire(monkeypatch, linked=False)
    selection.apply_settings_theme_selection(object(), _Catalog(), "new")
    assert calls == [("activate", "new"), ("persist", "new")]


def test_shared_theme_selection_persists_exact_linked_widget_identity(monkeypatch):
    calls = _wire(monkeypatch, linked=True)
    selection.apply_settings_theme_selection(object(), _Catalog(), "new")
    assert ("widget", "mirror:new", "new") in calls


def test_shared_theme_selection_rolls_back_renderer_failure(monkeypatch):
    calls = _wire(monkeypatch, linked=True, fail_activate=True)
    with pytest.raises(RuntimeError, match="renderer failed"):
        selection.apply_settings_theme_selection(object(), _Catalog(), "new")
    assert ("restore-runtime", "old-theme") in calls
    assert ("persist", "old") in calls
    assert ("widget", "independent", "old") in calls
