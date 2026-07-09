"""Steam widget family settings section.

Phase 3 keeps this dev-gated and provider-inert. Building or loading this
section must not decrypt credentials, scan caches, fetch assets, or submit
provider work.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.resources.manager import ResourceManager
from core.steam.backend import validate_connection
from core.steam.credentials import (
    SteamCredentialPayload,
    disconnect_account,
    get_storage_status,
    normalize_api_key,
    save_credentials,
    validate_credential_input,
)
from core.steam.models import SteamResultStatus
from core.steam.openid import SteamOpenIdLinkSession
from core.threading.manager import ThreadManager
from core.windows.secure_url_launcher import open_url
from rendering.widget_descriptors import get_widget_position_option_labels
from ui.styled_popup import StyledPopup
from ui.tabs.shared_styles import (
    INFO_LABEL_STYLE,
    STATUS_LABEL_STYLE,
    add_aligned_row,
    build_bucket_toggle,
    style_group_box,
)
from ui.widgets import StyledComboBox, StyledFontComboBox

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab


_STEAM_CARD_ORDER: tuple[tuple[str, str, str], ...] = (
    ("steam_progress", "Steam Progress", "Top Right"),
    ("achievement_pulse", "Achievement Pulse", "Middle Right"),
    ("abandonment_issues", "Abandonment Issues", "Bottom Right"),
    ("friend_pulse", "Friend Pulse", "Top Left"),
)
_STEAM_API_KEY_URL = "https://steamcommunity.com/dev/apikey"
_ACHIEVEMENT_SELECTION_OPTIONS: tuple[tuple[str, str], ...] = (
    ("Most Recent", "most_recent"),
    ("Recent #2", "recent_2"),
    ("Recent #3", "recent_3"),
    ("Recent #4", "recent_4"),
    ("Recent #5", "recent_5"),
    ("Custom App ID", "custom"),
)
_ACHIEVEMENT_FIELD_OPTIONS: tuple[tuple[str, str], ...] = (
    ("total", "Show completion"),
    ("playtime", "Show playtime"),
    ("source", "Show source"),
    ("selected", "Show selection"),
)
_ACHIEVEMENT_ARTWORK_SHAPES: tuple[tuple[str, str], ...] = (
    ("Wide", "wide"),
    ("Square", "square"),
)


class _DraggableSteamApiKeyDialog(QDialog):
    """Frameless popup shell that retains normal window drag behavior."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._drag_offset = None

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._drag_offset = None
        super().mouseReleaseEvent(event)


def _set_connection_status(tab: "WidgetsTab", message: str, *, state: str = "pending") -> None:
    """Update only in-memory UI status; normal settings never hold credentials."""
    colors = {
        "connected": "#72d696",
        "warning": "#efad5a",
        "error": "#ed7777",
        "pending": "#d0d0d0",
    }
    label = getattr(tab, "steam_connection_status", None)
    if label is not None:
        label.setText(message)
        label.setStyleSheet(f"{STATUS_LABEL_STYLE} color: {colors.get(state, colors['pending'])};")
    access = getattr(tab, "steam_access_status", None)
    if access is not None:
        ready = state == "connected"
        access.setText("Steam account access is ready." if ready else "Please Connect Both For Access")
        access.setStyleSheet(f"{STATUS_LABEL_STYLE} color: {'#72d696' if ready else '#efad5a'};")


def _set_connection_checks(tab: "WidgetsTab", *, identity_ready: bool, key_ready: bool) -> None:
    for attr, ready in (
        ("steam_identity_check", identity_ready),
        ("steam_api_key_check", key_ready),
    ):
        label = getattr(tab, attr, None)
        if label is not None:
            label.setText("Connected" if ready else "Not connected")
            label.setStyleSheet(f"{STATUS_LABEL_STYLE} color: {'#72d696' if ready else '#efad5a'};")


def _set_saved_connection_feedback(tab: "WidgetsTab", message: str | None, *, success: bool = False) -> None:
    """Show the one-shot result of the explicit saved-connection check."""
    label = getattr(tab, "steam_saved_connection_feedback", None)
    if label is None:
        return
    if not message:
        label.hide()
        return
    label.setText(message)
    label.setStyleSheet(f"{STATUS_LABEL_STYLE} color: {'#72d696' if success else '#efad5a'};")
    label.show()


def _hydrate_saved_connection_status(tab: "WidgetsTab") -> None:
    """Hydrate safe persisted status without decrypting or contacting Steam."""

    if getattr(tab, "_steam_storage_status_hydrated", False):
        return
    tab._steam_storage_status_hydrated = True
    _set_saved_connection_feedback(tab, None)
    status = get_storage_status()
    if status.storage_available and status.has_credentials:
        _set_connection_checks(tab, identity_ready=True, key_ready=True)
        _set_connection_status(tab, "Saved Steam identity and API key are available.", state="connected")
        return
    identity_ready = bool(getattr(tab, "_steam_pending_profile_identifier", None))
    _set_connection_checks(tab, identity_ready=identity_ready, key_ready=False)
    if identity_ready:
        _set_connection_status(tab, "Steam ID is linked. Add your Web API key to finish connecting.")
    else:
        _set_connection_status(tab, status.message, state="warning")


def _get_steam_thread_manager(tab: "WidgetsTab") -> ThreadManager:
    """Use the app shared manager, with the same narrow fallback as Gmail auth."""
    manager = getattr(tab, "_steam_thread_manager", None)
    if manager is not None:
        return manager
    manager = ThreadManager.get_app_shared()
    owns_manager = manager is None
    if manager is None:
        manager = ThreadManager.create_helper_manager(
            resource_manager=ResourceManager.get_app_shared(),
        )
    tab._steam_thread_manager = manager
    if owns_manager:
        try:
            tab.destroyed.connect(lambda _obj=None, owned=manager: owned.shutdown(wait=False))
        except Exception:
            pass
    return manager


def _on_steam_check_saved_connection(tab: "WidgetsTab") -> None:
    """Explicitly inspect non-secret DPAPI storage status without decrypting it."""
    status = get_storage_status()
    if status.storage_available and status.has_credentials:
        _set_connection_checks(tab, identity_ready=True, key_ready=True)
        _set_connection_status(tab, "Saved Steam identity and API key are available.", state="connected")
        _set_saved_connection_feedback(tab, "Connected Successfully", success=True)
        return
    identity_ready = bool(getattr(tab, "_steam_pending_profile_identifier", None))
    _set_connection_checks(tab, identity_ready=identity_ready, key_ready=False)
    if identity_ready:
        _set_connection_status(tab, "Steam ID is linked. Add your Web API key to finish connecting.", state="pending")
        _set_saved_connection_feedback(tab, "Reconnection Needed")
        return
    _set_connection_status(tab, status.message, state="warning")
    _set_saved_connection_feedback(tab, "Reconnection Needed")


def _on_steam_connect_id(tab: "WidgetsTab") -> None:
    _set_saved_connection_feedback(tab, None)
    popup = StyledPopup(
        tab,
        "Connect Steam ID",
        "SRPSS opens Steam's official sign-in page. Your password never enters SRPSS. "
        "A Steam Guard check is normal, then Steam returns to a temporary local SRPSS callback. "
        "If Steam asks for a website or domain, use <b>localhost</b>.",
        icon_type="info",
        buttons=[("Open Steam", "open"), ("Cancel", "cancel")],
    )
    popup.exec()
    if popup.result_value != "open":
        return
    try:
        session = SteamOpenIdLinkSession()
        login_url = session.start()
        tab._steam_openid_session = session
        generation = int(getattr(tab, "_steam_connection_generation", 0)) + 1
        tab._steam_connection_generation = generation
        _set_connection_status(tab, "Waiting for Steam identity confirmation in your browser.")
        if not open_url(login_url, prefer_direct=True, source="steam_settings"):
            session.close()
            _set_connection_status(tab, "Could not open the Steam identity page.", state="error")
            return

        def _wait_for_identity():
            return session.wait_for_result()

        def _finished(task_result) -> None:
            def _apply_result() -> None:
                if getattr(tab, "_steam_connection_generation", None) != generation:
                    return
                result = task_result.result if task_result.success else None
                if result is not None and result.success:
                    tab._steam_pending_profile_identifier = result.steam_id64
                    _set_connection_checks(tab, identity_ready=True, key_ready=False)
                    _set_connection_status(tab, result.message, state="pending")
                else:
                    _set_connection_checks(tab, identity_ready=False, key_ready=False)
                    message = getattr(result, "message", "Steam identity connection failed. Please try again.")
                    _set_connection_status(tab, message, state="error")
            ThreadManager.run_on_ui_thread(_apply_result)

        _get_steam_thread_manager(tab).submit_io_task(
            _wait_for_identity,
            task_id=f"steam_openid_link_{generation}",
            callback=_finished,
        )
    except Exception:
        _set_connection_status(tab, "Could not start Steam identity linking. Please try again.", state="error")


def _on_steam_connect_api_key(tab: "WidgetsTab") -> None:
    _set_saved_connection_feedback(tab, None)
    popup = StyledPopup(
        tab,
        "Connect Steam API Key",
        "Steam opens its official Web API key page. A Steam Guard check is normal. "
        "If Steam asks for a website or domain, use <b>localhost</b>.",
        icon_type="info",
        buttons=[("Open Key Page", "open"), ("Paste Key", "paste"), ("Cancel", "cancel")],
    )
    popup.exec()
    if popup.result_value == "open":
        if not open_url(_STEAM_API_KEY_URL, prefer_direct=True, source="steam_settings"):
            _set_connection_status(tab, "Could not open Steam's API key page.", state="error")
            return
        _show_api_key_dialog(tab)
    elif popup.result_value == "paste":
        _show_api_key_dialog(tab)


def _show_api_key_dialog(tab: "WidgetsTab") -> None:
    """Show a user-triggered paste surface; never prefill from saved credentials."""
    dialog = _DraggableSteamApiKeyDialog(tab)
    dialog.setObjectName("steamApiKeyDialog")
    dialog.setWindowTitle("Paste Steam API Key")
    dialog.setModal(True)
    dialog.setWindowFlags(
        Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.Dialog
        | Qt.WindowType.WindowStaysOnTopHint
    )
    dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    dialog.setMinimumWidth(430)
    dialog.setStyleSheet(
        """
        #steamApiKeyDialogSurface {
            background-color: rgba(30, 30, 36, 248);
            border: 1px solid rgba(255, 255, 255, 38);
            border-radius: 10px;
        }
        #steamApiKeyDialogSurface QLabel {
            color: #eeeeee;
        }
        #steamApiKeyDialogSurface QLineEdit#steamApiKeyInput {
            background-color: rgba(14, 14, 18, 220);
            border: 1px solid rgba(255, 255, 255, 55);
            border-radius: 6px;
            color: #ffffff;
            padding: 8px 10px;
        }
        #steamApiKeyDialogSurface QLineEdit#steamApiKeyInput:focus {
            border-color: #6aa9d9;
        }
        #steamApiKeyDialogSurface QPushButton {
            background-color: rgba(77, 119, 153, 210);
            border: 1px solid rgba(255, 255, 255, 45);
            border-radius: 6px;
            color: #ffffff;
            min-height: 30px;
            padding: 3px 12px;
        }
        #steamApiKeyDialogSurface QPushButton:hover {
            background-color: rgba(96, 145, 183, 235);
        }
        #steamApiKeyDialogSurface QPushButton:pressed {
            background-color: rgba(57, 89, 117, 235);
        }
        """
    )
    dialog_layout = QVBoxLayout(dialog)
    dialog_layout.setContentsMargins(0, 0, 0, 0)

    surface = QFrame(dialog)
    surface.setObjectName("steamApiKeyDialogSurface")
    shadow = QGraphicsDropShadowEffect(dialog)
    shadow.setBlurRadius(20)
    shadow.setColor(QColor(0, 0, 0, 150))
    shadow.setOffset(0, 4)
    surface.setGraphicsEffect(shadow)
    dialog_layout.addWidget(surface)

    layout = QVBoxLayout(surface)
    layout.setContentsMargins(22, 22, 22, 20)
    layout.setSpacing(12)

    heading = QLabel("Steam Web API Key")
    heading.setStyleSheet("font-size: 16px; font-weight: 700; color: #ffffff;")
    layout.addWidget(heading)

    message = QLabel(
        "Paste the key from Steam's official page. A Steam Guard check is normal. "
        "If Steam asks for a website or domain, use <b>localhost</b>."
    )
    message.setTextFormat(Qt.TextFormat.RichText)
    message.setStyleSheet(f"{INFO_LABEL_STYLE} font-size: 13px;")
    message.setWordWrap(True)
    layout.addWidget(message)

    key_field = QLineEdit()
    key_field.setObjectName("steamApiKeyInput")
    key_field.setEchoMode(QLineEdit.EchoMode.Normal)
    key_field.setPlaceholderText("Steam Web API key")
    key_field.setMinimumWidth(340)
    layout.addWidget(key_field)

    button_row = QHBoxLayout()
    paste_button = QPushButton("Paste Key")
    save_button = QPushButton("Save && Test")
    cancel_button = QPushButton("Cancel")
    button_row.addWidget(paste_button)
    button_row.addStretch()
    button_row.addWidget(save_button)
    button_row.addWidget(cancel_button)
    layout.addLayout(button_row)

    def _paste_key() -> None:
        key_field.setText(normalize_api_key(QApplication.clipboard().text()))

    def _save_key() -> None:
        normalized_key = normalize_api_key(key_field.text())
        key_field.setText(normalized_key)
        if _submit_steam_credentials(tab, normalized_key):
            dialog.accept()

    paste_button.clicked.connect(_paste_key)
    save_button.clicked.connect(_save_key)
    cancel_button.clicked.connect(dialog.reject)
    dialog.exec()


def _submit_steam_credentials(tab: "WidgetsTab", api_key: str) -> bool:
    """Start validation for a normalized user-entered key and report acceptance."""
    api_key = normalize_api_key(api_key)
    profile_identifier = getattr(tab, "_steam_pending_profile_identifier", None)
    validation = validate_credential_input(api_key, profile_identifier)
    if not validation.can_test:
        _set_connection_status(tab, validation.message, state="warning")
        return False
    generation = int(getattr(tab, "_steam_connection_generation", 0)) + 1
    tab._steam_connection_generation = generation
    _set_connection_status(tab, "Testing Steam API key before encrypted storage.")

    def _test_and_save() -> tuple[bool, str]:
        result = validate_connection(api_key=api_key, steamid=profile_identifier)
        if result.status != SteamResultStatus.SUCCESS:
            return False, "Steam did not accept this API key and identity pair. Your saved connection was left unchanged."
        save_credentials(SteamCredentialPayload(api_key=api_key, profile_identifier=profile_identifier))
        return True, "Steam identity and API key were verified and stored securely."

    def _finished(task_result) -> None:
        def _apply_result() -> None:
            if getattr(tab, "_steam_connection_generation", None) != generation:
                return
            success = bool(task_result.success and task_result.result and task_result.result[0])
            if success:
                _set_connection_checks(tab, identity_ready=True, key_ready=True)
                _set_connection_status(tab, task_result.result[1], state="connected")
                return
            _set_connection_checks(tab, identity_ready=True, key_ready=False)
            message = task_result.result[1] if task_result.success and task_result.result else "Steam credential test failed. Your saved connection was left unchanged."
            _set_connection_status(tab, message, state="error")
        ThreadManager.run_on_ui_thread(_apply_result)

    try:
        _get_steam_thread_manager(tab).submit_io_task(
            _test_and_save,
            task_id=f"steam_credential_test_{generation}",
            callback=_finished,
        )
    except Exception:
        _set_connection_status(tab, "Could not start the Steam credential test.", state="error")
        return False
    return True


def _on_steam_disconnect(tab: "WidgetsTab") -> None:
    _set_saved_connection_feedback(tab, None)
    if not StyledPopup.question(
        tab,
        "Disconnect Steam",
        "Remove the encrypted Steam key, linked identity, and account-private Steam cache for this Windows user?",
        yes_text="Disconnect",
        no_text="Cancel",
        default_to_yes=False,
    ):
        return
    generation = int(getattr(tab, "_steam_connection_generation", 0)) + 1
    tab._steam_connection_generation = generation
    _set_connection_status(tab, "Disconnecting Steam and clearing account-private cache.")

    def _finished(task_result) -> None:
        def _apply_result() -> None:
            if getattr(tab, "_steam_connection_generation", None) != generation:
                return
            if task_result.success:
                tab._steam_pending_profile_identifier = None
                _set_connection_checks(tab, identity_ready=False, key_ready=False)
                _set_connection_status(tab, "Steam is disconnected.", state="warning")
            else:
                _set_connection_status(tab, "Steam disconnect did not complete. Please try again.", state="error")
        ThreadManager.run_on_ui_thread(_apply_result)

    try:
        _get_steam_thread_manager(tab).submit_io_task(
            disconnect_account,
            task_id=f"steam_disconnect_{generation}",
            callback=_finished,
        )
    except Exception:
        _set_connection_status(tab, "Could not start Steam disconnect.", state="error")


def _aligned_row(parent: QVBoxLayout, label_text: str) -> QHBoxLayout:
    row, _label = add_aligned_row(parent, label_text, label_width=145, wrap=False)
    return row


def _section_config(
    widgets_config: Mapping[str, Any],
    section: str,
) -> Mapping[str, Any]:
    candidate = widgets_config.get(section, {})
    return candidate if isinstance(candidate, Mapping) else {}


def _finalize_bucket_body(toggle, body: QWidget) -> None:
    expanded = bool(toggle.isChecked())
    if body.isHidden() == expanded:
        body.setVisible(expanded)


def _set_achievement_selection_mode(combo: StyledComboBox, mode: str) -> None:
    for index in range(combo.count()):
        if combo.itemData(index) == mode:
            combo.setCurrentIndex(index)
            return
    combo.setCurrentIndex(0)


def _set_combo_data(combo: StyledComboBox, value: str) -> None:
    for index in range(combo.count()):
        if combo.itemData(index) == value:
            combo.setCurrentIndex(index)
            return
    combo.setCurrentIndex(0)


def _update_achievement_artwork_controls(tab: "WidgetsTab") -> None:
    shape = getattr(tab, "achievement_pulse_artwork_shape", None)
    visible = getattr(tab, "achievement_pulse_show_artwork", None)
    if shape is not None and visible is not None:
        shape.setEnabled(visible.isChecked())


def _update_achievement_latest_controls(tab: "WidgetsTab") -> None:
    count = getattr(tab, "achievement_pulse_latest_unlock_count", None)
    visible = getattr(tab, "achievement_pulse_show_latest", None)
    if count is not None and visible is not None:
        count.setEnabled(visible.isChecked())


def _update_steam_enabled_visibility(tab: "WidgetsTab") -> None:
    enabled = getattr(tab, "steam_enabled", None) and tab.steam_enabled.isChecked()
    container = getattr(tab, "_steam_controls_container", None)
    if container is not None:
        container.setVisible(bool(enabled))


def _build_card_group(tab: "WidgetsTab", parent_layout: QVBoxLayout, key: str, label: str, fallback_position: str) -> None:
    toggle, body, layout = build_bucket_toggle(
        parent_layout,
        label,
        expanded=tab.get_widget_bucket_state("steam", key, default=False),
        on_toggle=lambda checked, bucket=key: tab.set_widget_bucket_state("steam", bucket, checked),
        defer_initial_visibility=True,
    )
    layout.setSpacing(12)

    enabled_attr = f"{key}_enabled"
    position_attr = f"{key}_position"
    monitor_attr = f"{key}_monitor_combo"
    font_family_attr = f"{key}_font_family"
    font_attr = f"{key}_font_size"
    status_attr = f"{key}_stack_status"

    enabled = QCheckBox(f"Enable {label}")
    enabled.setProperty("circleIndicator", True)
    enabled.setToolTip(f"Show the dev-gated {label} mock card.")
    enabled.setChecked(tab._default_bool(key, "enabled", False))
    enabled.stateChanged.connect(tab._save_settings)
    setattr(tab, enabled_attr, enabled)
    layout.addWidget(enabled)

    position_row = _aligned_row(layout, "Position:")
    position = StyledComboBox()
    position.addItems(list(get_widget_position_option_labels(key)))
    position.setMinimumWidth(150)
    position.currentTextChanged.connect(tab._save_settings)
    tab._set_combo_text(position, tab._default_str(key, "position", fallback_position))
    setattr(tab, position_attr, position)
    position_row.addWidget(position)
    position_row.addStretch()

    display_row = _aligned_row(layout, "Display:")
    monitor = StyledComboBox(size_variant="compact")
    monitor.addItems(["ALL", "1", "2", "3"])
    monitor.setMinimumWidth(120)
    monitor.currentTextChanged.connect(tab._save_settings)
    tab._set_combo_text(monitor, str(tab._widget_default(key, "monitor", "ALL")))
    setattr(tab, monitor_attr, monitor)
    display_row.addWidget(monitor)
    display_row.addStretch()

    font_family_row = _aligned_row(layout, "Font:")
    font_family = StyledFontComboBox(size_variant="hero")
    font_family.setCurrentFont(QFont(tab._default_str(key, "font_family", "Inter")))
    font_family.setMinimumWidth(220)
    font_family.currentFontChanged.connect(tab._save_settings)
    setattr(tab, font_family_attr, font_family)
    font_family_row.addWidget(font_family)
    font_family_row.addStretch()

    font_row = _aligned_row(layout, "Font Size:")
    font_size = QSpinBox()
    font_size.setRange(8, 40)
    font_size.setValue(tab._default_int(key, "font_size", 14))
    font_size.valueChanged.connect(tab._save_settings)
    setattr(tab, font_attr, font_size)
    font_row.addWidget(font_size)
    font_row.addWidget(QLabel("px"))
    font_row.addStretch()

    if key == "achievement_pulse":
        selection_row = _aligned_row(layout, "Game Selection:")
        selection_mode = StyledComboBox()
        for label_text, mode in _ACHIEVEMENT_SELECTION_OPTIONS:
            selection_mode.addItem(label_text, mode)
        selection_mode.currentIndexChanged.connect(tab._save_settings)
        _set_achievement_selection_mode(
            selection_mode,
            str(tab._widget_default(key, "selection_mode", "most_recent")),
        )
        tab.achievement_pulse_selection_mode = selection_mode
        selection_row.addWidget(selection_mode)
        selection_row.addStretch()

        appid_row = _aligned_row(layout, "Custom App ID:")
        custom_appid = QSpinBox()
        custom_appid.setRange(0, 2_147_483_647)
        custom_appid.setSpecialValueText("Not set")
        custom_appid.valueChanged.connect(tab._save_settings)
        try:
            custom_appid.setValue(int(tab._widget_default(key, "custom_appid", 0) or 0))
        except Exception:
            custom_appid.setValue(0)
        tab.achievement_pulse_custom_appid = custom_appid
        appid_row.addWidget(custom_appid)
        appid_row.addStretch()

        artwork_row = _aligned_row(layout, "Artwork:")
        show_artwork = QCheckBox("Show Artwork")
        show_artwork.setProperty("circleIndicator", True)
        show_artwork.setChecked(tab._default_bool(key, "show_artwork", True))
        show_artwork.stateChanged.connect(tab._save_settings)
        show_artwork.stateChanged.connect(lambda _state: _update_achievement_artwork_controls(tab))
        tab.achievement_pulse_show_artwork = show_artwork
        artwork_row.addWidget(show_artwork)
        artwork_row.addStretch()

        artwork_shape_row = _aligned_row(layout, "Artwork Shape:")
        artwork_shape = StyledComboBox()
        for shape_label, shape_value in _ACHIEVEMENT_ARTWORK_SHAPES:
            artwork_shape.addItem(shape_label, shape_value)
        _set_combo_data(artwork_shape, str(tab._widget_default(key, "artwork_shape", "wide")))
        artwork_shape.currentIndexChanged.connect(tab._save_settings)
        tab.achievement_pulse_artwork_shape = artwork_shape
        artwork_shape_row.addWidget(artwork_shape)
        artwork_shape_row.addStretch()
        _update_achievement_artwork_controls(tab)

        latest_row = _aligned_row(layout, "Latest Unlocks:")
        show_latest = QCheckBox("Show Latest Unlocks")
        show_latest.setProperty("circleIndicator", True)
        show_latest.setChecked(tab._default_bool(key, "show_latest", True))
        show_latest.stateChanged.connect(tab._save_settings)
        show_latest.stateChanged.connect(lambda _state: _update_achievement_latest_controls(tab))
        tab.achievement_pulse_show_latest = show_latest
        latest_row.addWidget(show_latest)
        latest_count = QSpinBox()
        latest_count.setRange(1, 3)
        latest_count.setValue(tab._default_int(key, "latest_unlock_count", 1))
        latest_count.valueChanged.connect(tab._save_settings)
        tab.achievement_pulse_latest_unlock_count = latest_count
        latest_row.addWidget(latest_count)
        latest_row.addStretch()
        _update_achievement_latest_controls(tab)

        fields_label = QLabel("Displayed Fields:")
        fields_label.setStyleSheet(INFO_LABEL_STYLE)
        layout.addWidget(fields_label)
        for field_id, label_text in _ACHIEVEMENT_FIELD_OPTIONS:
            field_toggle = QCheckBox(label_text)
            field_toggle.setProperty("circleIndicator", True)
            fallback = False if field_id == "selected" else True
            field_toggle.setChecked(tab._default_bool(key, f"show_{field_id}", fallback))
            field_toggle.stateChanged.connect(tab._save_settings)
            setattr(tab, f"achievement_pulse_show_{field_id}", field_toggle)
            layout.addWidget(field_toggle)

    status = QLabel("")
    status.setStyleSheet(STATUS_LABEL_STYLE)
    status.setWordWrap(True)
    setattr(tab, status_attr, status)
    layout.addWidget(status)

    _finalize_bucket_body(toggle, body)


def build_steam_ui(tab: "WidgetsTab", layout: QVBoxLayout) -> QWidget:
    """Build the lazy Steam Settings section."""
    steam_group = QGroupBox("Steam Widget")
    style_group_box(steam_group)
    root = QVBoxLayout(steam_group)
    root.setContentsMargins(16, 18, 16, 16)
    root.setSpacing(16)

    tab.steam_enabled = QCheckBox("Enable Steam Widget")
    tab.steam_enabled.setProperty("circleIndicator", True)
    tab.steam_enabled.setToolTip(
        "Shows the Steam family shell and its card buckets in the settings dialog."
    )
    tab.steam_enabled.setChecked(tab._default_bool("steam", "enabled", True))
    tab.steam_enabled.stateChanged.connect(tab._save_settings)
    root.addWidget(tab.steam_enabled)

    tab._steam_controls_container = QWidget()
    _steam_controls_layout = QVBoxLayout(tab._steam_controls_container)
    _steam_controls_layout.setContentsMargins(0, 0, 0, 12)
    _steam_controls_layout.setSpacing(12)

    connection_toggle, connection_body, connection_layout = build_bucket_toggle(
        _steam_controls_layout,
        "Connection & Privacy",
        expanded=tab.get_widget_bucket_state("steam", "connection", default=False),
        on_toggle=lambda checked: tab.set_widget_bucket_state("steam", "connection", checked),
        defer_initial_visibility=True,
    )
    connection_layout.setSpacing(12)

    info = QLabel(
        "Steam is currently development-gated. Opening this section reads only encrypted-storage "
        "availability; it does not decrypt credentials, scan caches, fetch assets, or contact Steam."
    )
    info.setWordWrap(True)
    info.setStyleSheet(INFO_LABEL_STYLE)
    connection_layout.addWidget(info)

    identity_row = _aligned_row(connection_layout, "Steam Identity:")
    tab.steam_connect_id_btn = QPushButton("Connect ID")
    tab.steam_connect_id_btn.setToolTip("Link SteamID64 through Steam's official OpenID page.")
    tab.steam_connect_id_btn.clicked.connect(lambda: _on_steam_connect_id(tab))
    tab.steam_identity_check = QLabel("Not connected")
    identity_row.addWidget(tab.steam_connect_id_btn)
    identity_row.addWidget(tab.steam_identity_check)
    identity_row.addStretch()

    key_row = _aligned_row(connection_layout, "Steam API Key:")
    tab.steam_connect_api_key_btn = QPushButton("Connect API KEY")
    tab.steam_connect_api_key_btn.setToolTip("Open Steam's key page or explicitly paste a key to Save & Test.")
    tab.steam_connect_api_key_btn.clicked.connect(lambda: _on_steam_connect_api_key(tab))
    tab.steam_api_key_check = QLabel("Not connected")
    key_row.addWidget(tab.steam_connect_api_key_btn)
    key_row.addWidget(tab.steam_api_key_check)
    key_row.addStretch()

    connection_actions = QHBoxLayout()
    tab.steam_check_connection_btn = QPushButton("Check Saved Connection")
    tab.steam_check_connection_btn.setToolTip("Check DPAPI storage state without decrypting credentials or contacting Steam.")
    tab.steam_check_connection_btn.clicked.connect(lambda: _on_steam_check_saved_connection(tab))
    tab.steam_disconnect_btn = QPushButton("Disconnect")
    tab.steam_disconnect_btn.clicked.connect(lambda: _on_steam_disconnect(tab))
    tab.steam_saved_connection_feedback = QLabel()
    tab.steam_saved_connection_feedback.setObjectName("steamSavedConnectionFeedback")
    tab.steam_saved_connection_feedback.hide()
    connection_actions.addWidget(tab.steam_check_connection_btn)
    connection_actions.addWidget(tab.steam_disconnect_btn)
    connection_actions.addWidget(tab.steam_saved_connection_feedback)
    connection_actions.addStretch()
    connection_layout.addLayout(connection_actions)

    privacy_row = _aligned_row(connection_layout, "Privacy Mode:")
    tab.steam_privacy_mode = StyledComboBox()
    tab.steam_privacy_mode.addItems(["Strict", "Balanced", "Rich"])
    tab.steam_privacy_mode.setMinimumWidth(150)
    tab.steam_privacy_mode.currentTextChanged.connect(tab._save_settings)
    tab._set_combo_text(tab.steam_privacy_mode, tab._default_str("steam", "privacy_mode", "Strict"))
    privacy_row.addWidget(tab.steam_privacy_mode)
    privacy_row.addStretch()

    refresh_row = _aligned_row(connection_layout, "Refresh Window:")
    tab.steam_refresh_minutes = QSpinBox()
    tab.steam_refresh_minutes.setRange(5, 240)
    tab.steam_refresh_minutes.setSuffix(" min")
    tab.steam_refresh_minutes.setValue(tab._default_int("steam", "refresh_minutes", 10))
    tab.steam_refresh_minutes.valueChanged.connect(tab._save_settings)
    refresh_row.addWidget(tab.steam_refresh_minutes)
    refresh_row.addStretch()

    tab.steam_show_connection_info_icon = QCheckBox("Show stale connection info icon")
    tab.steam_show_connection_info_icon.setProperty("circleIndicator", True)
    tab.steam_show_connection_info_icon.setToolTip(
        "Show a small orange info icon when cached Steam data is at least one day stale and the connection needs attention."
    )
    tab.steam_show_connection_info_icon.setChecked(tab._default_bool("steam", "show_connection_info_icon", True))
    tab.steam_show_connection_info_icon.stateChanged.connect(tab._save_settings)
    connection_layout.addWidget(tab.steam_show_connection_info_icon)

    tab.steam_access_status = QLabel()
    connection_layout.addWidget(tab.steam_access_status)

    tab.steam_connection_status = QLabel()
    connection_layout.addWidget(tab.steam_connection_status)
    _hydrate_saved_connection_status(tab)

    _finalize_bucket_body(connection_toggle, connection_body)

    for key, label, fallback_position in _STEAM_CARD_ORDER:
        _build_card_group(tab, _steam_controls_layout, key, label, fallback_position)

    root.addWidget(tab._steam_controls_container)
    tab.steam_enabled.stateChanged.connect(lambda _state: _update_steam_enabled_visibility(tab))
    _update_steam_enabled_visibility(tab)

    layout.addWidget(steam_group)
    return steam_group


def load_steam_settings(tab: "WidgetsTab", widgets_config: Mapping[str, Any]) -> None:
    """Load saved non-secret Steam settings into the lazy section controls."""
    steam_config = _section_config(widgets_config, "steam")
    tab.steam_enabled.setChecked(
        bool(steam_config.get("enabled", tab._default_bool("steam", "enabled", True)))
    )
    tab._set_combo_text(
        tab.steam_privacy_mode,
        str(steam_config.get("privacy_mode", tab._default_str("steam", "privacy_mode", "Strict"))),
    )
    try:
        tab.steam_refresh_minutes.setValue(
            int(steam_config.get("refresh_minutes", tab._default_int("steam", "refresh_minutes", 10)))
        )
    except Exception:
        tab.steam_refresh_minutes.setValue(tab._default_int("steam", "refresh_minutes", 10))
    tab.steam_show_connection_info_icon.setChecked(
        bool(steam_config.get("show_connection_info_icon", tab._default_bool("steam", "show_connection_info_icon", True)))
    )

    for key, _label, fallback_position in _STEAM_CARD_ORDER:
        config = _section_config(widgets_config, key)
        getattr(tab, f"{key}_enabled").setChecked(
            bool(config.get("enabled", tab._default_bool(key, "enabled", False)))
        )
        tab._set_combo_text(
            getattr(tab, f"{key}_position"),
            str(config.get("position", tab._default_str(key, "position", fallback_position))),
        )
        tab._set_combo_text(
            getattr(tab, f"{key}_monitor_combo"),
            str(config.get("monitor", tab._widget_default(key, "monitor", "ALL"))),
        )
        getattr(tab, f"{key}_font_family").setCurrentFont(
            QFont(str(config.get("font_family", tab._default_str(key, "font_family", "Inter"))))
        )
        try:
            getattr(tab, f"{key}_font_size").setValue(
                int(config.get("font_size", tab._default_int(key, "font_size", 14)))
            )
        except Exception:
            getattr(tab, f"{key}_font_size").setValue(tab._default_int(key, "font_size", 14))
        if key == "achievement_pulse":
            _set_achievement_selection_mode(
                tab.achievement_pulse_selection_mode,
                str(config.get("selection_mode", tab._widget_default(key, "selection_mode", "most_recent"))),
            )
            try:
                tab.achievement_pulse_custom_appid.setValue(
                    int(config.get("custom_appid", tab._widget_default(key, "custom_appid", 0)) or 0)
                )
            except Exception:
                tab.achievement_pulse_custom_appid.setValue(0)
            tab.achievement_pulse_show_artwork.setChecked(
                bool(config.get("show_artwork", tab._default_bool(key, "show_artwork", True)))
            )
            _set_combo_data(
                tab.achievement_pulse_artwork_shape,
                str(config.get("artwork_shape", tab._default_str(key, "artwork_shape", "wide"))),
            )
            tab.achievement_pulse_show_latest.setChecked(
                bool(config.get("show_latest", tab._default_bool(key, "show_latest", True)))
            )
            try:
                tab.achievement_pulse_latest_unlock_count.setValue(
                    int(config.get("latest_unlock_count", tab._default_int(key, "latest_unlock_count", 1)))
                )
            except Exception:
                tab.achievement_pulse_latest_unlock_count.setValue(1)
            for field_id, _label_text in _ACHIEVEMENT_FIELD_OPTIONS:
                fallback = False if field_id == "selected" else True
                getattr(tab, f"achievement_pulse_show_{field_id}").setChecked(
                    bool(config.get(f"show_{field_id}", tab._default_bool(key, f"show_{field_id}", fallback)))
                )
            _update_achievement_artwork_controls(tab)
            _update_achievement_latest_controls(tab)

    _hydrate_saved_connection_status(tab)


def _save_card(tab: "WidgetsTab", key: str) -> dict[str, Any]:
    defaults = tab._widget_defaults.get(key, {})
    if not isinstance(defaults, dict):
        defaults = {}
    payload = dict(defaults)
    payload.update({
        "enabled": getattr(tab, f"{key}_enabled").isChecked(),
        "position": getattr(tab, f"{key}_position").currentText(),
        "monitor": getattr(tab, f"{key}_monitor_combo").currentText(),
        "font_family": getattr(tab, f"{key}_font_family").currentFont().family(),
        "font_size": int(getattr(tab, f"{key}_font_size").value()),
    })
    if key == "achievement_pulse":
        payload["selection_mode"] = str(tab.achievement_pulse_selection_mode.currentData() or "most_recent")
        custom_appid = int(tab.achievement_pulse_custom_appid.value())
        payload["custom_appid"] = custom_appid or None
        payload["show_artwork"] = bool(tab.achievement_pulse_show_artwork.isChecked())
        payload["artwork_shape"] = str(tab.achievement_pulse_artwork_shape.currentData() or "wide")
        payload["show_latest"] = bool(tab.achievement_pulse_show_latest.isChecked())
        payload["latest_unlock_count"] = int(tab.achievement_pulse_latest_unlock_count.value())
        for field_id, _label_text in _ACHIEVEMENT_FIELD_OPTIONS:
            payload[f"show_{field_id}"] = bool(getattr(tab, f"achievement_pulse_show_{field_id}").isChecked())
    return payload


def save_steam_settings(tab: "WidgetsTab") -> tuple[dict[str, Any], ...]:
    """Return shared Steam settings plus all four card payloads."""
    steam_payload = {
        "enabled": bool(tab.steam_enabled.isChecked()),
        "privacy_mode": tab.steam_privacy_mode.currentText(),
        "refresh_minutes": int(tab.steam_refresh_minutes.value()),
        "show_connection_info_icon": bool(tab.steam_show_connection_info_icon.isChecked()),
    }
    return (
        steam_payload,
        _save_card(tab, "steam_progress"),
        _save_card(tab, "achievement_pulse"),
        _save_card(tab, "abandonment_issues"),
        _save_card(tab, "friend_pulse"),
    )
