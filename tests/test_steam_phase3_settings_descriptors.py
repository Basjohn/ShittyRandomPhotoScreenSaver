from __future__ import annotations

import importlib
import sys

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QDialog, QGroupBox, QLabel, QLineEdit, QToolButton, QWidget

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


def _find_toggle(container, text: str) -> QToolButton | None:
    for toggle in container.findChildren(QToolButton):
        if toggle.text() == text:
            return toggle
    return None


def _with_steam_gate(enabled: bool):
    prior = is_steam_enabled()
    force_gate(steam=enabled)
    return prior


def _restore_steam_gate(prior: bool) -> None:
    force_gate(steam=prior)


def _steam_settings_module():
    """Resolve the live lazy-loaded Steam section module for handler tests."""
    return importlib.import_module("ui.tabs.widgets_tab_steam")


def test_achievement_pulse_descriptors_are_public_while_unfinished_cards_stay_gated() -> None:
    prior = _with_steam_gate(False)
    try:
        unfinished = set(STEAM_WIDGET_IDS) - {"achievement_pulse"}
        factory_ids = {descriptor.settings_key for descriptor in get_factory_widget_descriptors()}
        runtime_ids = {descriptor.widget_id for descriptor in get_widget_runtime_descriptors()}
        preview_ids = {descriptor.widget_id for descriptor in get_widget_stack_preview_descriptors()}
        custom_ids = {descriptor.widget_id for descriptor in get_widget_custom_position_option_descriptors()}

        assert "achievement_pulse" in factory_ids & runtime_ids & preview_ids & custom_ids
        assert "steam" in {descriptor.section_id for descriptor in get_widget_settings_section_descriptors()}
        assert not unfinished.intersection(factory_ids)
        steam_factories = [
            descriptor
            for descriptor in get_factory_widget_descriptors()
            if descriptor.settings_key in STEAM_WIDGET_IDS
        ]
        assert steam_factories
        assert all(descriptor.base_settings_key == "steam" for descriptor in steam_factories)
        assert all(descriptor.base_enabled_gate is True for descriptor in steam_factories)
        assert not unfinished.intersection(runtime_ids)
        assert not unfinished.intersection(preview_ids)
        assert not unfinished.intersection(custom_ids)
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

    steam = widgets["steam"]
    assert isinstance(steam["enabled"], bool)
    assert steam["privacy_mode"] in {"Strict", "Balanced", "Rich"}
    assert 5 <= steam["refresh_minutes"] <= 240
    assert isinstance(steam["show_connection_info_icon"], bool)
    for widget_id in STEAM_WIDGET_IDS:
        card = widgets[widget_id]
        assert card["enabled"] is False
        assert str(card["monitor"]) in {"ALL", "1", "2", "3"}
        assert card["show_background"] is True
        expected_size = (540, 290) if widget_id == "achievement_pulse" else (420, 180)
        assert (card["preferred_width"], card["preferred_height"]) == expected_size
    achievement = widgets["achievement_pulse"]
    assert isinstance(achievement["show_artwork"], bool)
    assert achievement["artwork_shape"] in {"wide", "square"}
    assert 1 <= achievement["latest_unlock_count"] <= 5
    for bool_key in (
        "show_latest",
        "show_latest_achievement_artwork",
        "show_total",
        "show_playtime",
        "show_previous",
        "show_source",
        "show_selected",
        "double_capsules",
    ):
        assert isinstance(achievement[bool_key], bool)
    for color_key in ("capsule_fill_color", "capsule_border_color"):
        color = achievement[color_key]
        assert len(color) == 4
        assert all(0 <= channel <= 255 for channel in color)
    assert 140 <= achievement["square_artwork_size"] <= 190
    assert 8 <= achievement["capsule_font_size"] <= 32
    assert "double_capsule_long_data" not in achievement


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
            assert tab.steam_enabled.isChecked() is bool(
                get_default_settings()["widgets"]["steam"]["enabled"]
            )
            assert any(box.title() == "Steam Widget" for box in tab.findChildren(QGroupBox))
            tab.steam_enabled.setChecked(True)
            assert tab._steam_controls_container.isHidden() is False
            tab.steam_show_connection_info_icon.setChecked(False)
            tab.steam_enabled.setChecked(False)
            assert tab._steam_controls_container.isHidden() is True
            assert _find_toggle(tab, "Layout") is not None
            assert _find_toggle(tab, "Appearance") is not None
            assert _find_toggle(tab, "Content") is not None
            tab.steam_progress_enabled.setChecked(True)
            tab._set_combo_text(tab.steam_progress_position, "Center")
            tab._set_combo_text(tab.steam_progress_monitor_combo, "1")
            tab.steam_progress_font_family.setCurrentFont(QFont("Jost"))
            tab.steam_progress_font_size.setValue(18)
            tab.achievement_pulse_selection_mode.setCurrentIndex(5)
            tab.achievement_pulse_custom_appid.setValue(367520)
            tab.achievement_pulse_show_artwork.setChecked(False)
            tab.achievement_pulse_artwork_shape.setCurrentIndex(1)
            tab.achievement_pulse_square_artwork_size.setValue(190)
            tab.achievement_pulse_double_capsules.setChecked(False)
            tab.achievement_pulse_capsule_font_size.setValue(22)
            assert tab.achievement_pulse_square_artwork_size.isEnabled() is False
            tab.achievement_pulse_show_latest.setChecked(False)
            tab.achievement_pulse_show_latest_artwork.setChecked(False)
            tab.achievement_pulse_latest_unlock_count.setValue(5)
            tab.achievement_pulse_show_previous.setChecked(False)
            tab.achievement_pulse_show_source.setChecked(False)
            tab.achievement_pulse_capsule_fill_color_btn.color_changed.emit(QColor(12, 34, 56, 78))
            tab.achievement_pulse_capsule_border_color_btn.color_changed.emit(QColor(90, 87, 65, 43))

            preview = build_widget_stack_preview_config(tab)
            assert preview["steam_progress"]["enabled"] is False
            assert preview["steam_progress"]["position"] == "Center"
            tab.steam_enabled.setChecked(True)
            assert build_widget_stack_preview_config(tab)["steam_progress"]["enabled"] is True
            tab.steam_enabled.setChecked(False)

            steam_payload, progress_payload, *_rest = collect_widget_section_save_result(tab, "steam")
            assert steam_payload["enabled"] is False
            assert steam_payload["privacy_mode"] == tab.steam_privacy_mode.currentText()
            assert steam_payload["show_connection_info_icon"] is False
            assert progress_payload["enabled"] is True
            assert progress_payload["position"] == "Center"
            assert progress_payload["font_family"] == "Jost"
            assert "api_key" not in steam_payload
            assert "profile_identifier" not in steam_payload
            achievement_payload = collect_widget_section_save_result(tab, "steam")[2]
            assert achievement_payload["selection_mode"] == "custom"
            assert achievement_payload["custom_appid"] == 367520
            assert achievement_payload["show_artwork"] is False
            assert achievement_payload["artwork_shape"] == "square"
            assert achievement_payload["square_artwork_size"] == 190
            assert achievement_payload["double_capsules"] is False
            assert achievement_payload["capsule_font_size"] == 22
            assert "double_capsule_long_data" not in achievement_payload
            assert achievement_payload["show_latest"] is False
            assert achievement_payload["show_latest_achievement_artwork"] is False
            assert achievement_payload["latest_unlock_count"] == 5
            assert achievement_payload["show_previous"] is False
            assert achievement_payload["show_source"] is False
            assert achievement_payload["capsule_fill_color"] == [12, 34, 56, 78]
            assert achievement_payload["capsule_border_color"] == [90, 87, 65, 43]
        finally:
            tab.deleteLater()
    finally:
        _restore_steam_gate(prior)


def test_achievement_selection_names_are_bracketed_without_changing_saved_mode(qt_app, settings_manager) -> None:
    prior = _with_steam_gate(False)
    try:
        tab = WidgetsTab(settings_manager, lazy_sections=True, initial_view_state={"subtab_id": "steam"})
        try:
            combo = tab.achievement_pulse_selection_mode
            module = _steam_settings_module()
            module._set_achievement_selection_mode(combo, "recent_3")
            spy = QSignalSpy(combo.currentIndexChanged)

            module._apply_achievement_selection_titles(
                tab,
                ("Baldur's Gate 3", "Soulstone Survivors", "Celeste"),
            )

            assert combo.itemText(0) == "Most Recent (Baldur's Gate 3)"
            assert combo.itemText(1) == "Recent #2 (Soulstone Survivors)"
            assert combo.itemText(2) == "Recent #3 (Celeste)"
            assert combo.itemText(3) == "Recent #4"
            assert combo.itemText(5) == "Custom App ID"
            assert combo.currentData() == "recent_3"
            assert spy.count() == 0
        finally:
            tab.deleteLater()
    finally:
        _restore_steam_gate(prior)


def test_steam_settings_section_uses_standard_collapsible_buckets(qt_app, settings_manager) -> None:
    prior = _with_steam_gate(True)
    try:
        tab = WidgetsTab(settings_manager, lazy_sections=True, initial_view_state={"subtab_id": "steam"})
        try:
            checks = (
                ("Connection & Privacy", "steam", "connection"),
                ("Steam Journey", "steam", "steam_progress"),
                ("Achievement Pulse", "steam", "achievement_pulse"),
                ("Abandonment Issues", "steam", "abandonment_issues"),
                ("Friend Pulse", "steam", "friend_pulse"),
            )
            for text, section, bucket in checks:
                toggle = _find_toggle(tab._steam_container, text)
                assert toggle is not None, f"Missing Steam bucket toggle: {text}"
                assert toggle.isChecked() is False
                toggle.click()
                qt_app.processEvents()
                assert tab.get_widget_bucket_state(section, bucket, False) is True
        finally:
            tab.deleteLater()
    finally:
        _restore_steam_gate(prior)


def test_unfinished_steam_card_buckets_are_hidden_without_dev_gate(qt_app, settings_manager) -> None:
    prior = _with_steam_gate(False)
    try:
        tab = WidgetsTab(settings_manager, lazy_sections=True, initial_view_state={"subtab_id": "steam"})
        try:
            achievement = _find_toggle(tab._steam_container, "Achievement Pulse")
            assert achievement is not None and achievement.isHidden() is False
            for label in ("Steam Journey", "Abandonment Issues", "Friend Pulse"):
                toggle = _find_toggle(tab._steam_container, label)
                assert toggle is not None and toggle.isHidden() is True
        finally:
            tab.deleteLater()
    finally:
        _restore_steam_gate(prior)


def test_steam_connection_controls_stay_inert_until_explicit_user_action(
    qt_app,
    settings_manager,
    monkeypatch,
) -> None:
    prior = _with_steam_gate(True)
    checks: list[bool] = []
    try:
        monkeypatch.setattr(
            "ui.tabs.widgets_tab_steam.get_storage_status",
            lambda: checks.append(True) or type(
                "Status",
                (),
                {"storage_available": True, "has_credentials": False, "message": "Steam is not connected."},
            )(),
        )
        tab = WidgetsTab(settings_manager, lazy_sections=True, initial_view_state={"subtab_id": "steam"})
        try:
            assert tab.steam_connect_id_btn.text() == "Connect ID"
            assert tab.steam_connect_api_key_btn.text() == "Connect API KEY"
            assert tab.steam_access_status.text() == "Please Connect Both For Access"
            assert checks == [True]

            tab.steam_check_connection_btn.click()
            assert checks == [True, True]
            assert tab.steam_connection_status.text() == "Steam is not connected."
            assert tab.steam_saved_connection_feedback.text() == "Reconnection Needed"
            assert tab.steam_saved_connection_feedback.isHidden() is False
        finally:
            tab.deleteLater()
    finally:
        _restore_steam_gate(prior)


def test_saved_connection_status_hydrates_green_on_every_settings_open(
    qt_app,
    settings_manager,
    monkeypatch,
) -> None:
    prior = _with_steam_gate(True)
    checks: list[bool] = []
    try:
        monkeypatch.setattr(
            "ui.tabs.widgets_tab_steam.get_storage_status",
            lambda: checks.append(True) or type(
                "Status",
                (),
                {"storage_available": True, "has_credentials": True, "message": "Connected."},
            )(),
        )
        for _index in range(2):
            tab = WidgetsTab(settings_manager, lazy_sections=True, initial_view_state={"subtab_id": "steam"})
            try:
                assert tab.steam_identity_check.text() == "Connected"
                assert tab.steam_api_key_check.text() == "Connected"
                assert tab.steam_access_status.text() == "Steam account access is ready."
                assert tab.steam_connection_status.text() == "Saved Steam identity and API key are available."
                assert tab.steam_saved_connection_feedback.isHidden() is True
            finally:
                tab.deleteLater()
                qt_app.processEvents()
        assert checks == [True, True]
    finally:
        _restore_steam_gate(prior)


def test_saved_connection_check_preserves_pending_openid_identity(qt_app, settings_manager, monkeypatch) -> None:
    prior = _with_steam_gate(True)
    try:
        monkeypatch.setattr(
            "ui.tabs.widgets_tab_steam.get_storage_status",
            lambda: type(
                "Status",
                (),
                {"storage_available": True, "has_credentials": False, "message": "Steam is not connected."},
            )(),
        )
        tab = WidgetsTab(settings_manager, lazy_sections=True, initial_view_state={"subtab_id": "steam"})
        try:
            tab._steam_pending_profile_identifier = "76561197960265728"

            _steam_settings_module()._on_steam_check_saved_connection(tab)

            assert tab._steam_pending_profile_identifier == "76561197960265728"
            assert tab.steam_identity_check.text() == "Connected"
            assert tab.steam_api_key_check.text() == "Not connected"
            assert tab.steam_connection_status.text() == "Steam ID is linked. Add your Web API key to finish connecting."
        finally:
            tab.deleteLater()
    finally:
        _restore_steam_gate(prior)


def test_open_api_key_page_pivots_immediately_to_paste_dialog(qt_app, settings_manager, monkeypatch) -> None:
    prior = _with_steam_gate(True)
    opened: list[tuple[str, bool, str]] = []
    shown: list[bool] = []

    class _OpenPopup:
        result_value = "open"

        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def exec(self) -> int:
            return 0

    try:
        module = _steam_settings_module()
        monkeypatch.setattr(module, "StyledPopup", _OpenPopup)
        monkeypatch.setattr(
            module,
            "open_url",
            lambda url, *, prefer_direct, source: opened.append((url, prefer_direct, source)) or True,
        )
        monkeypatch.setattr(module, "_show_api_key_dialog", lambda _tab: shown.append(True))
        tab = WidgetsTab(settings_manager, lazy_sections=True, initial_view_state={"subtab_id": "steam"})
        try:
            module._on_steam_connect_api_key(tab)

            assert opened == [("https://steamcommunity.com/dev/apikey", True, "steam_settings")]
            assert shown == [True]
        finally:
            tab.deleteLater()
    finally:
        _restore_steam_gate(prior)


def test_steam_api_key_dialog_uses_app_styling_and_visible_input(qt_app, settings_manager) -> None:
    prior = _with_steam_gate(True)
    observed: dict[str, object] = {}
    try:
        tab = WidgetsTab(settings_manager, lazy_sections=True, initial_view_state={"subtab_id": "steam"})
        try:
            def _inspect_and_close() -> None:
                dialog = tab.findChild(QDialog, "steamApiKeyDialog")
                assert dialog is not None
                input_field = dialog.findChild(QLineEdit, "steamApiKeyInput")
                assert input_field is not None
                observed["echo_mode"] = input_field.echoMode()
                observed["style"] = dialog.styleSheet()
                message_label = next(
                    label for label in dialog.findChildren(QLabel) if "localhost" in label.text()
                )
                observed["message"] = message_label.text()
                observed["message_style"] = message_label.styleSheet()
                observed["frameless"] = bool(dialog.windowFlags() & Qt.WindowType.FramelessWindowHint)
                dialog.reject()

            QTimer.singleShot(0, _inspect_and_close)
            _steam_settings_module()._show_api_key_dialog(tab)

            assert observed["echo_mode"] == QLineEdit.EchoMode.Normal
            assert "#steamApiKeyDialogSurface" in observed["style"]
            assert "<b>localhost</b>" in observed["message"]
            assert "font-size: 13px" in observed["message_style"]
            assert observed["frameless"] is True
        finally:
            tab.deleteLater()
    finally:
        _restore_steam_gate(prior)


def test_steam_connection_bucket_opens_from_persisted_target_state(qt_app, settings_manager) -> None:
    prior = _with_steam_gate(True)
    try:
        settings_manager.set("ui.widget_bucket_states", {"steam:connection": True})
        tab = WidgetsTab(settings_manager, lazy_sections=True, initial_view_state={"subtab_id": "steam"})
        try:
            toggle = _find_toggle(tab._steam_container, "Connection & Privacy")
            assert toggle is not None
            assert toggle.isChecked() is True
        finally:
            tab.deleteLater()
    finally:
        _restore_steam_gate(prior)


def test_achievement_factory_is_public_while_unfinished_factories_are_dev_gated(
    qt_app,
    settings_manager,
) -> None:
    prior = _with_steam_gate(False)
    try:
        public_registry = WidgetFactoryRegistry(settings_manager)
        assert public_registry.get_factory("achievement_pulse") is not None
        assert public_registry.get_factory("steam_progress") is None
        assert public_registry.get_factory("abandonment_issues") is None
        assert public_registry.get_factory("friend_pulse") is None
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
            assert getattr(widget, "_view_model").state == "connect_required"
            widget.deleteLater()

            achievement_widget = registry.create_widget(
                "achievement_pulse",
                parent,
                {
                    "enabled": True,
                    "position": "Middle Right",
                    "selection_mode": "custom",
                    "custom_appid": 367520,
                    "show_artwork": True,
                    "artwork_shape": "square",
                    "square_artwork_size": 190,
                    "double_capsule_long_data": False,
                    "capsule_font_size": 22,
                    "latest_unlock_count": 5,
                    "capsule_fill_color": [12, 34, 56, 78],
                    "capsule_border_color": [90, 87, 65, 43],
                },
            )
            assert achievement_widget is not None
            assert getattr(achievement_widget, "_achievement_selection").mode == "custom"
            assert getattr(achievement_widget, "_achievement_selection").custom_appid == 367520
            assert getattr(achievement_widget, "_achievement_show_artwork") is True
            assert getattr(achievement_widget, "_achievement_artwork_shape") == "square"
            assert getattr(achievement_widget, "_achievement_square_artwork_size") == 190
            assert getattr(achievement_widget, "_achievement_double_capsules") is False
            assert getattr(achievement_widget, "_achievement_capsule_font_size") == 22
            assert getattr(achievement_widget, "_achievement_latest_unlock_count") == 5
            assert achievement_widget.minimumHeight() == 318
            assert getattr(achievement_widget, "_achievement_capsule_fill_color").getRgb() == (12, 34, 56, 78)
            assert getattr(achievement_widget, "_achievement_capsule_border_color").getRgb() == (90, 87, 65, 43)
            achievement_widget.deleteLater()
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
            "steam": {"enabled": True, "refresh_minutes": 5},
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
            assert getattr(created["steam_progress_widget"], "_refresh_minutes") == 5
            assert "achievement_pulse_widget" not in created

            created_again = manager.setup_all_widgets(settings, screen_index=0, thread_manager=None)
            assert created_again["steam_progress_widget"] is created["steam_progress_widget"]
        finally:
            parent.deleteLater()
    finally:
        _restore_steam_gate(prior)


def test_steam_master_gate_suppresses_enabled_cards_and_fade_expectations(qt_app) -> None:
    prior = _with_steam_gate(False)
    try:
        parent = QWidget()
        parent.resize(1280, 720)
        manager = WidgetManager(parent, ResourceManager())
        settings = _SteamSetupSettings({
            "steam": {"enabled": False, "refresh_minutes": 10},
            "achievement_pulse": {
                "enabled": True,
                "monitor": "ALL",
                "position": "Middle Right",
            },
            "shadows": {"enabled": True},
        })
        try:
            created = manager.setup_all_widgets(settings, screen_index=0, thread_manager=None)
            assert "achievement_pulse_widget" not in created
            assert "achievement_pulse" not in manager._expected_overlays

            registry = WidgetFactoryRegistry(settings)
            factory = registry.get_factory("achievement_pulse")
            assert factory is not None
            assert factory.create(
                parent,
                {"enabled": True, "position": "Middle Right"},
                steam_settings={"enabled": False},
            ) is None
        finally:
            parent.deleteLater()
    finally:
        _restore_steam_gate(prior)
