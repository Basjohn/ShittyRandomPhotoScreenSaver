from types import SimpleNamespace

from core.cache_maintenance import CacheClearResult
from rendering.widget_descriptors import (
    get_widget_settings_section_descriptors,
    get_widgets_tab_settings_section_descriptors,
)
from ui.tabs import widgets_tab_defaults as general_tab
from ui.tabs.widgets_tab import WidgetsTab


def test_general_section_renames_only_user_facing_defaults_surface(qt_app, settings_manager) -> None:
    tab = WidgetsTab(
        settings_manager,
        lazy_sections=True,
        initial_view_state={"subtab_id": "defaults"},
    )
    try:
        descriptor = next(
            item for item in get_widget_settings_section_descriptors() if item.section_id == "defaults"
        )
        # V7 scoped Visualizers out of WidgetsTab; its subtabs follow the
        # WidgetsTab-scoped descriptor list.
        labels = [
            tab._subtab_group.button(index).text()
            for index in range(len(get_widgets_tab_settings_section_descriptors()))
        ]
        assert descriptor.button_label == "General"
        assert labels[-1] == "General"
        assert tab._defaults_container.title() == "General Widget Settings"
        assert tab._general_appearance_toggle.text() == "Appearance"
        assert tab._general_layout_toggle.text() == "Layout"
        assert tab._general_cache_toggle.text() == "Cache Maintenance"
        assert tab._general_appearance_toggle.isChecked() is True
        assert tab._general_layout_toggle.isChecked() is True
        assert tab._general_cache_toggle.isChecked() is False
        assert tuple(tab.cache_family_checks) == (
            "rss",
            "reddit",
            "weather",
            "gmail",
            "steam",
            "settings",
        )
        assert tab.clear_selected_caches_btn.isEnabled() is False
        tab.cache_family_checks["weather"].setChecked(True)
        assert tab.clear_selected_caches_btn.isEnabled() is True
    finally:
        tab.deleteLater()


def test_general_cache_clear_confirms_selected_scope_and_reports_completion(
    qt_app,
    settings_manager,
    monkeypatch,
) -> None:
    tab = WidgetsTab(
        settings_manager,
        lazy_sections=True,
        initial_view_state={"subtab_id": "defaults"},
    )
    confirmation_messages: list[str] = []

    class _ImmediateManager:
        def submit_io_task(self, function, *, task_id, callback):
            assert task_id == "general_clear_selected_caches"
            callback(SimpleNamespace(success=True, result=function()))

    try:
        tab.cache_family_checks["weather"].setChecked(True)
        tab.cache_family_checks["gmail"].setChecked(True)
        monkeypatch.setattr(
            general_tab.StyledPopup,
            "question",
            lambda _parent, _title, message, **_kwargs: confirmation_messages.append(message) or True,
        )
        monkeypatch.setattr(general_tab, "_get_cache_thread_manager", lambda _tab: _ImmediateManager())
        monkeypatch.setattr(general_tab.ThreadManager, "run_on_ui_thread", lambda callback: callback())
        monkeypatch.setattr(
            general_tab,
            "clear_cache_families",
            lambda selected_ids, *, descriptors: CacheClearResult(
                selected_ids=tuple(selected_ids),
                removed_files=3,
                removed_bytes=1536,
                skipped_files=0,
                errors=(),
            ),
        )

        general_tab._on_clear_selected_caches(tab)

        assert len(confirmation_messages) == 1
        assert "Weather" in confirmation_messages[0]
        assert "Gmail Messages" in confirmation_messages[0]
        assert "Steam" not in confirmation_messages[0]
        assert tab.clear_selected_caches_btn.text() == "Clear Selected Caches"
        assert tab.clear_selected_caches_btn.isEnabled() is True
        assert tab.cache_clear_status_label.text() == "Cleared 3 files (1.5 KB)."
        assert "#7fe0a3" in tab.cache_clear_status_label.styleSheet()
    finally:
        tab.deleteLater()
