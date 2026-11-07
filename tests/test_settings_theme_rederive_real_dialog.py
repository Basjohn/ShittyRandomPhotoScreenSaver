"""AC-19: Reset to Defaults and Import re-derive the active Settings and Widget themes in the same session.

Persisted ``ui.settings_theme_selection`` / ``widget_theme`` and the process-local active themes are two owners; the
dialog's reset/import reload edge re-derives the second from the first. Drives the real SettingsDialog (never shown,
``StyledPopup.exec`` patched) on a test-owned profile. Every expected theme is resolved from what is persisted at
the time, never a pinned theme id; the themes the test switches to are picked from the shipped catalog by property
(any non-default Settings theme, any unlinked Widget theme).
"""
from __future__ import annotations

import json

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from core.animation import AnimationManager
from core.settings.settings_manager import SettingsManager

pytestmark = pytest.mark.qt


@pytest.fixture
def manager(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    from ui.settings_theme_runtime import get_active_settings_theme, set_active_settings_theme
    from ui.styled_popup import StyledPopup
    from ui.widget_theme_active import get_active_widget_theme, set_active_widget_theme

    # No popup may block: a dismissed popup answers nothing.
    monkeypatch.setattr(StyledPopup, "exec", lambda popup: setattr(popup, "_result_value", None))
    before = (get_active_settings_theme(), get_active_widget_theme())
    manager = SettingsManager(application="theme_rederive", storage_base_dir=tmp_path)
    manager.set("sources.folders", [str(tmp_path)])
    yield manager
    assert manager.flush(timeout=5.0)
    set_active_widget_theme(before[1])
    set_active_settings_theme(before[0])


def _dialog(manager):
    from ui.settings_dialog import SettingsDialog
    dialog = SettingsDialog(manager, AnimationManager())
    QCoreApplication.processEvents()
    return dialog


def _destroy(dialog):
    dialog.close()
    QCoreApplication.processEvents()
    dialog.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QCoreApplication.processEvents()


def _expected(manager):
    """The active pair a fresh start would derive from what is persisted now."""
    from ui.settings_theme_catalog import get_current_settings_theme_catalog, resolve_persisted_settings_theme
    from ui.widget_theme_selection import read_widget_theme_state, resolve_widget_theme_state
    resolution = resolve_persisted_settings_theme(manager, get_current_settings_theme_catalog())
    widget = resolve_widget_theme_state(read_widget_theme_state(manager), settings_theme_id=resolution.entry.theme_id)
    return resolution.entry.theme, widget.theme


def _actives():
    from ui.settings_theme_runtime import get_active_settings_theme
    from ui.widget_theme_active import get_active_widget_theme
    return get_active_settings_theme(), get_active_widget_theme()


def _independent_choice(manager):
    """A non-default Settings theme and an unlinked Widget theme, both differing from what is active now."""
    from ui.settings_theme_catalog import get_current_settings_theme_catalog
    from ui.widget_theme_catalog import get_current_widget_theme_catalog
    active_settings, active_widget = _actives()
    settings_entry = next(e for e in get_current_settings_theme_catalog().entries
                          if not e.is_builtin and e.theme != active_settings)
    widget_entry = next(e for e in get_current_widget_theme_catalog().entries
                        if e.theme.linked_settings_theme_id is None and not e.is_builtin and e.theme != active_widget)
    return settings_entry.theme_id, widget_entry.theme_id


def _choose_in_session(manager, settings_id, widget_id):
    """What the Themes tab's selection does: persist and activate an Independent pair."""
    from ui.settings_theme_catalog import get_current_settings_theme_catalog
    from ui.settings_theme_selection import apply_settings_theme_selection
    from ui.widget_theme_runtime import WidgetThemeState
    from ui.widget_theme_selection import activate_widget_theme_state
    activate_widget_theme_state(manager, WidgetThemeState(selected_id=widget_id, keep_synced=False, custom_payload=None),
                                settings_theme_id=settings_id, persist=True)
    apply_settings_theme_selection(manager, get_current_settings_theme_catalog(), settings_id)


def test_reset_to_defaults_re_derives_both_active_themes_and_the_themes_tab(manager):
    dialog = _dialog(manager)
    try:
        themes_tab = dialog._get_tab_instance("themes")
        settings_id, widget_id = _independent_choice(manager)
        _choose_in_session(manager, settings_id, widget_id)
        chosen = _actives()
        assert chosen == _expected(manager)

        dialog._on_reset_to_defaults_clicked()

        expected = _expected(manager)
        assert expected != chosen, "the reset must persist a different pair for this test to mean anything"
        assert _actives() == expected
        # The Themes tab reloads with Settings: its lists show the persisted (reset) selections.
        current = themes_tab.theme_list.currentItem()
        from ui.settings_theme_catalog import get_current_settings_theme_catalog, resolve_persisted_settings_theme
        settings_entry = resolve_persisted_settings_theme(manager, get_current_settings_theme_catalog()).entry
        assert current is not None and current.data(0x0100) == settings_entry.theme_id
        widget_current = themes_tab.widget_theme_list.currentItem()
        assert widget_current is not None and widget_current.data(0x0100) == expected[1].theme_id
    finally:
        _destroy(dialog)


def test_a_theme_import_with_an_independent_widget_theme_applies_both_now(manager, tmp_path, monkeypatch):
    import ui.settings_import as importing
    from ui.styled_popup import StyledPopup

    dialog = _dialog(manager)
    try:
        settings_id, widget_id = _independent_choice(manager)
        path = tmp_path / "other_pc.sst"
        assert manager.export_to_sst(str(path))
        payload = json.loads(path.read_text(encoding="utf-8"))
        snapshot = payload["snapshot"]
        snapshot.setdefault("ui", {})["settings_theme_selection"] = settings_id
        snapshot["widget_theme"] = dict(snapshot.get("widget_theme") or {}, selected_id=widget_id, keep_synced=False)
        path.write_text(json.dumps(payload), encoding="utf-8")
        before = _actives()

        def choose_only_theme(popup):
            chooser = getattr(popup, "_content", None)
            if chooser is not None and hasattr(chooser, "boxes"):
                chooser.all.setChecked(False)
                chooser.boxes["theme"].setChecked(True)
                popup._result_value = "import"
            else:
                popup._result_value = None
        monkeypatch.setattr(StyledPopup, "exec", choose_only_theme)
        monkeypatch.setattr(StyledPopup, "show_success", staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(importing, "choose_snapshot_file", lambda parent: str(path))

        dialog._on_import_settings_clicked()

        assert manager.get("widget_theme.selected_id") == widget_id
        expected = _expected(manager)
        assert expected != before
        assert _actives() == expected
    finally:
        _destroy(dialog)
