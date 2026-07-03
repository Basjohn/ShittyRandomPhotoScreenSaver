from __future__ import annotations

import sys

from PySide6.QtWidgets import QWidget

from core.dev_gates import force_gate, is_steam_enabled
from core.settings.defaults import get_default_settings
from rendering.widget_descriptors import (
    STEAM_SERVICE_RUNTIME_CONTRACTS,
    STEAM_WIDGET_IDS,
    build_widget_stack_preview_config,
    collect_widget_section_save_result,
    get_factory_widget_descriptors,
    get_service_runtime_contracts,
    get_widget_custom_position_option_descriptors,
    get_widget_custom_resize_lock_descriptors,
    get_widget_runtime_descriptors,
    get_widget_settings_section_descriptors,
    get_widget_stack_preview_descriptors,
)
from rendering.widget_factories import WidgetFactoryRegistry
from rendering.widget_manager import WidgetManager
from ui.tabs.widgets_tab import WidgetsTab
from core.resources.manager import ResourceManager


def _with_steam_gate(enabled: bool):
    prior = is_steam_enabled()
    force_gate(steam=enabled)
    return prior


def _restore_steam_gate(prior: bool) -> None:
    force_gate(steam=prior)


def test_steam_phase3_descriptors_are_hidden_without_dev_gate() -> None:
    prior = _with_steam_gate(False)
    try:
        assert not set(STEAM_WIDGET_IDS).intersection(
            descriptor.settings_key for descriptor in get_factory_widget_descriptors()
        )
        assert "steam" not in {descriptor.section_id for descriptor in get_widget_settings_section_descriptors()}
        assert not set(STEAM_WIDGET_IDS).intersection(
            descriptor.widget_id for descriptor in get_widget_runtime_descriptors()
        )
        assert not set(STEAM_WIDGET_IDS).intersection(
            descriptor.widget_id for descriptor in get_widget_stack_preview_descriptors()
        )
    finally:
        _restore_steam_gate(prior)


def test_steam_phase3_descriptors_are_complete_behind_dev_gate() -> None:
    prior = _with_steam_gate(True)
    try:
        factory_keys = [descriptor.settings_key for descriptor in get_factory_widget_descriptors()]
        runtime_ids = [descriptor.widget_id for descriptor in get_widget_runtime_descriptors()]
        custom_ids = [descriptor.widget_id for descriptor in get_widget_custom_position_option_descriptors()]
        preview_ids = [descriptor.widget_id for descriptor in get_widget_stack_preview_descriptors()]
        resize_sections = {descriptor.section_id: descriptor for descriptor in get_widget_custom_resize_lock_descriptors()}
        section = next(
            descriptor for descriptor in get_widget_settings_section_descriptors()
            if descriptor.section_id == "steam"
        )

        for widget_id in STEAM_WIDGET_IDS:
            assert widget_id in factory_keys
            assert widget_id in runtime_ids
            assert widget_id in custom_ids
            assert widget_id in preview_ids
            assert get_service_runtime_contracts(widget_id) == STEAM_SERVICE_RUNTIME_CONTRACTS

        assert section.persisted_widget_keys == ("steam",) + STEAM_WIDGET_IDS
        assert section.builder_module == "ui.tabs.widgets_tab_steam"
        assert section.loader_name == "load_steam_settings"
        assert section.saver_name == "save_steam_settings"
        assert resize_sections["steam"].widget_ids == STEAM_WIDGET_IDS
    finally:
        _restore_steam_gate(prior)


def test_steam_defaults_include_shared_preferences_and_disabled_cards() -> None:
    widgets = get_default_settings()["widgets"]

    assert widgets["steam"] == {"privacy_mode": "Strict", "refresh_minutes": 30}
    for widget_id in STEAM_WIDGET_IDS:
        card = widgets[widget_id]
        assert card["enabled"] is False
        assert card["monitor"] == "ALL"
        assert card["show_background"] is True
        assert card["preferred_width"] == 420
        assert card["preferred_height"] == 180


def test_lazy_widgets_tab_does_not_import_steam_settings_section_on_general_open(
    qt_app,
    settings_manager,
) -> None:
    prior = _with_steam_gate(True)
    sys.modules.pop("ui.tabs.widgets_tab_steam", None)
    try:
        tab = WidgetsTab(settings_manager, lazy_sections=True, initial_view_state={"subtab_id": "clock"})
        try:
            assert hasattr(tab, "clock_enabled")
            assert not hasattr(tab, "steam_privacy_mode")
            assert "ui.tabs.widgets_tab_steam" not in sys.modules
        finally:
            tab.deleteLater()
    finally:
        _restore_steam_gate(prior)


def test_steam_settings_section_load_save_roundtrip_is_non_secret_and_inert(qt_app, settings_manager) -> None:
    prior = _with_steam_gate(True)
    try:
        tab = WidgetsTab(settings_manager, lazy_sections=True, initial_view_state={"subtab_id": "steam"})
        try:
            assert hasattr(tab, "steam_privacy_mode")
            tab.steam_progress_enabled.setChecked(True)
            tab._set_combo_text(tab.steam_progress_position, "Center")
            tab._set_combo_text(tab.steam_progress_monitor_combo, "1")
            tab.steam_progress_font_size.setValue(18)

            preview = build_widget_stack_preview_config(tab)
            assert preview["steam_progress"]["enabled"] is True
            assert preview["steam_progress"]["position"] == "Center"

            steam_payload, progress_payload, *_rest = collect_widget_section_save_result(tab, "steam")
            assert steam_payload["privacy_mode"] == tab.steam_privacy_mode.currentText()
            assert progress_payload["enabled"] is True
            assert progress_payload["position"] == "Center"
            assert "api_key" not in steam_payload
        finally:
            tab.deleteLater()
    finally:
        _restore_steam_gate(prior)


def test_steam_factories_are_dev_gated_and_disabled_cards_create_nothing(
    qt_app,
    settings_manager,
) -> None:
    prior = _with_steam_gate(False)
    try:
        hidden_registry = WidgetFactoryRegistry(settings_manager)
        assert hidden_registry.get_factory("steam_progress") is None
    finally:
        _restore_steam_gate(prior)

    prior = _with_steam_gate(True)
    try:
        parent = QWidget()
        parent.resize(1280, 720)
        registry = WidgetFactoryRegistry(settings_manager)
        try:
            assert registry.get_factory("steam_progress") is not None
            assert registry.create_widget("steam_progress", parent, {"enabled": False}) is None

            widget = registry.create_widget(
                "steam_progress",
                parent,
                {
                    "enabled": True,
                    "position": "Top Right",
                    "font_size": 16,
                    "preferred_width": 420,
                    "preferred_height": 180,
                },
            )
            assert widget is not None
            assert widget.objectName() == "steam_progress_overlay"
            widget.deleteLater()
        finally:
            parent.deleteLater()
    finally:
        _restore_steam_gate(prior)


class _SteamSetupSettings:
    def __init__(self, widgets: dict) -> None:
        self._widgets = widgets

    def get_widgets_map(self) -> dict:
        return self._widgets


def test_steam_cards_flow_through_descriptor_widget_setup_when_enabled(qt_app) -> None:
    prior = _with_steam_gate(True)
    try:
        parent = QWidget()
        parent.resize(1280, 720)
        manager = WidgetManager(parent, ResourceManager())
        settings = _SteamSetupSettings({
            "steam_progress": {
                "enabled": True,
                "monitor": "ALL",
                "position": "Top Right",
                "font_size": 14,
                "preferred_width": 420,
                "preferred_height": 180,
            },
            "achievement_pulse": {"enabled": False, "monitor": "ALL"},
            "abandonment_issues": {"enabled": False, "monitor": "ALL"},
            "friend_pulse": {"enabled": False, "monitor": "ALL"},
            "shadows": {"enabled": True},
        })
        try:
            created = manager.setup_all_widgets(settings, screen_index=0, thread_manager=None)
            assert "steam_progress_widget" in created
            assert created["steam_progress_widget"] is getattr(parent, "steam_progress_widget")
            assert "achievement_pulse_widget" not in created

            created_again = manager.setup_all_widgets(settings, screen_index=0, thread_manager=None)
            assert created_again["steam_progress_widget"] is created["steam_progress_widget"]
        finally:
            parent.deleteLater()
    finally:
        _restore_steam_gate(prior)
