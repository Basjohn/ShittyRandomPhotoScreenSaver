"""Gmail widget section for widgets tab.

Extracted UI building, settings loading/saving for the Gmail overlay widget.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QGroupBox, QCheckBox, QLineEdit,
    QSlider, QWidget, QPushButton, QGridLayout,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont

from core.logging.logger import get_logger
from core.resources.manager import ResourceManager
from rendering.widget_descriptors import GMAIL_SIGNAL_BLOCK_ATTRS, get_widget_position_option_labels
from core.audio.sound_paths import default_notification_sound_path
from core.threading.manager import ThreadManager
from ui.styled_popup import ColorSwatchButton, StyledPopup
from ui.tabs.shared_styles import (
    STATUS_LABEL_STYLE,
    INFO_LABEL_STYLE,
    add_swatch_label,
    style_group_box,
    add_aligned_row,
    create_inline_label,
    build_bucket_toggle,
)
from ui.widgets import StyledComboBox

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab

logger = get_logger(__name__)

LABEL_WIDTH = 140
_MISSING_DEFAULT = object()


def _set_visible_if_changed(widget: QWidget | None, visible: bool) -> None:
    if widget is not None and (not widget.isHidden()) != bool(visible):
        widget.setVisible(bool(visible))


def _gmail_default(tab: WidgetsTab, key: str):
    value = tab._widget_default('gmail', key, _MISSING_DEFAULT)
    if value is _MISSING_DEFAULT:
        raise KeyError(f"Missing Gmail default: {key}")
    return value


@contextmanager
def _block_gmail_setting_signals(tab: WidgetsTab):
    blockers = []
    for attr_name in GMAIL_SIGNAL_BLOCK_ATTRS:
        widget = getattr(tab, attr_name, None)
        if widget is not None and hasattr(widget, "blockSignals"):
            widget.blockSignals(True)
            blockers.append(widget)
    try:
        yield
    finally:
        for widget in blockers:
            try:
                widget.blockSignals(False)
            except Exception as exc:
                logger.debug("[GMAIL_TAB] Failed to unblock signal: %s", exc)


def _update_gmail_enabled_visibility(tab: WidgetsTab) -> None:
    """Show/hide all Gmail controls based on gmail_enabled checkbox."""
    enabled = getattr(tab, 'gmail_enabled', None) and tab.gmail_enabled.isChecked()
    container = getattr(tab, '_gmail_controls_container', None)
    _set_visible_if_changed(container, bool(enabled))


def _aligned_row(parent: QVBoxLayout, label_text: str) -> QHBoxLayout:
    row, _ = add_aligned_row(parent, label_text, label_width=LABEL_WIDTH, wrap=True)
    return row


def _swatch_row(parent: QVBoxLayout, label_text: str) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setContentsMargins(0, 8, 0, 8)
    row.setSpacing(12)
    add_swatch_label(row, label_text, LABEL_WIDTH)
    content = QHBoxLayout()
    content.setContentsMargins(0, 0, 0, 0)
    content.setSpacing(12)
    row.addLayout(content, 1)
    parent.addLayout(row)
    return content


def _get_gmail_oauth_manager():
    """Lazy-import singleton accessor for GmailOAuthManager (avoids early import cost)."""
    try:
        from core.gmail.gmail_oauth import GmailOAuthManager
        return GmailOAuthManager.instance()
    except Exception as exc:
        logger.error("[GMAIL_TAB] Failed to obtain GmailOAuthManager: %s", exc)
        return None


def _get_gmail_backend():
    """Lazy-import singleton accessor for GmailBackend."""
    try:
        from core.gmail.gmail_backend import GmailBackend
        return GmailBackend.instance()
    except Exception as exc:
        logger.error("[GMAIL_TAB] Failed to obtain GmailBackend: %s", exc)
        return None


def _get_gmail_thread_manager(tab: WidgetsTab) -> ThreadManager:
    manager = getattr(tab, "_gmail_thread_manager", None)
    if manager is None:
        manager = ThreadManager.get_app_shared()
        owns_manager = manager is None
        if manager is None:
            manager = ThreadManager.create_helper_manager(
                resource_manager=ResourceManager.get_app_shared(),
            )
        tab._gmail_thread_manager = manager
        if owns_manager:
            try:
                tab.destroyed.connect(lambda _obj=None, m=manager: m.shutdown(wait=False))
            except Exception as exc:
                logger.debug("[GMAIL_TAB] Failed to attach Gmail ThreadManager cleanup: %s", exc)
    return manager


def _is_imap_selected_in_combo(tab: WidgetsTab) -> bool:
    combo = getattr(tab, "gmail_backend_combo", None)
    if combo is not None and hasattr(combo, "currentText"):
        try:
            return combo.currentText() == "IMAP (App Password)"
        except Exception:
            return True
    return True


def _sync_backend_combo_from_backend(tab: WidgetsTab, backend) -> None:
    combo = getattr(tab, 'gmail_backend_combo', None)
    if backend is None or combo is None:
        return
    try:
        from core.gmail.gmail_backend import GmailBackendMode
        target_index = 0 if backend.mode == GmailBackendMode.IMAP else 1
        if combo.currentIndex() != target_index:
            blocked = combo.blockSignals(True)
            try:
                combo.setCurrentIndex(target_index)
            finally:
                combo.blockSignals(blocked)
    except Exception:
        logger.debug("[GMAIL_TAB] Failed to sync backend combo", exc_info=True)


def _queue_gmail_auth_refresh(tab: WidgetsTab) -> None:
    if getattr(tab, "_gmail_auth_refresh_queued", False):
        return
    tab._gmail_auth_refresh_queued = True

    def _run() -> None:
        tab._gmail_auth_refresh_queued = False
        _refresh_gmail_auth_state(tab)

    QTimer.singleShot(250, _run)


def _finalize_bucket_body(toggle, body: QWidget) -> None:
    expanded = bool(toggle.isChecked())
    if body.isHidden() == expanded:
        body.setVisible(expanded)


def _refresh_gmail_auth_state(tab: WidgetsTab) -> None:
    """Update the auth status label and button visibility based on credential state."""
    status_label = getattr(tab, 'gmail_auth_status', None)
    auth_btn = getattr(tab, 'gmail_authorize_btn', None)
    out_btn = getattr(tab, 'gmail_sign_out_btn', None)
    if status_label is None or auth_btn is None or out_btn is None:
        return

    backend = _get_gmail_backend()
    if backend is None:
        _update_backend_panels(tab, use_backend=False)
        status_label.setText("Gmail unavailable")
        auth_btn.setEnabled(False)
        out_btn.setEnabled(False)
        _set_visible_if_changed(out_btn, False)
        return
    _sync_backend_combo_from_backend(tab, backend)
    imap_email = getattr(tab, "gmail_imap_email", None)
    if imap_email is not None and not imap_email.text() and getattr(backend, "_imap_email", None):
        imap_email.setText(backend._imap_email)

    # Reload OAuth config in case client_secrets was added after start
    mgr = _get_gmail_oauth_manager()
    if mgr is not None:
        try:
            mgr._load_client_config()
        except Exception:
            pass

    # Update mode-specific panel visibility
    _update_backend_panels(tab, use_backend=True)

    status_label.setText(backend.status_text)

    if backend.is_authenticated:
        _set_visible_if_changed(auth_btn, False)
        _set_visible_if_changed(out_btn, True)
        out_btn.setEnabled(True)
    else:
        from core.gmail.gmail_backend import GmailBackendMode
        if backend.mode == GmailBackendMode.IMAP:
            _set_visible_if_changed(auth_btn, False)
        else:
            _set_visible_if_changed(auth_btn, True)
            auth_btn.setEnabled(True)
        _set_visible_if_changed(out_btn, False)


def _update_backend_panels(tab: WidgetsTab, *, use_backend: bool = True) -> None:
    """Show/hide OAuth vs IMAP panels based on current backend mode."""
    backend = _get_gmail_backend() if use_backend else None
    is_imap = _is_imap_selected_in_combo(tab)
    if backend is not None:
        from core.gmail.gmail_backend import GmailBackendMode
        is_imap = backend.mode == GmailBackendMode.IMAP
    oauth_panel = getattr(tab, '_gmail_oauth_panel', None)
    imap_panel = getattr(tab, '_gmail_imap_panel', None)
    _set_visible_if_changed(oauth_panel, not is_imap)
    _set_visible_if_changed(imap_panel, is_imap)


def _on_gmail_authorize_clicked(tab: WidgetsTab) -> None:
    """Start the OAuth flow. Non-blocking — uses internal threaded HTTP server."""
    backend = _get_gmail_backend()
    if backend is None:
        StyledPopup.show_warning(tab, "Gmail", "Gmail backend unavailable.")
        return

    mgr = _get_gmail_oauth_manager()
    if mgr is None:
        StyledPopup.show_warning(tab, "Gmail", "OAuth subsystem unavailable.")
        return

    # Wire signals once per tab instance
    if not getattr(tab, '_gmail_auth_signals_wired', False):
        try:
            backend.auth_state_changed.connect(lambda: _refresh_gmail_auth_state(tab))
            mgr.auth_failed.connect(lambda msg: _on_gmail_auth_failed(tab, msg))
        except Exception as exc:
            logger.warning("[GMAIL_TAB] Signal wiring failed: %s", exc)
        tab._gmail_auth_signals_wired = True

    try:
        mgr._load_client_config()
    except Exception:
        pass

    if not getattr(mgr, '_client_id', None):
        from core.settings.storage_paths import get_app_data_dir
        import webbrowser
        import subprocess

        app_data = get_app_data_dir()
        popup = StyledPopup(
            tab,
            "OAuth Credentials Required",
            "client_secrets.json is missing.\n\n"
            "Google requires you to create OAuth credentials in the Cloud Console, "
            "download the JSON, and place it in your SRPSS app data folder.\n\n"
            f"Step 1 \u2014 Open Google Cloud Console and create OAuth 2.0 credentials.\n"
            f"Step 2 \u2014 Download client_secrets.json.\n"
            f"Step 3 \u2014 Place it here: {app_data}",
            icon_type="warning",
            buttons=[
                ("Open Google Console", "console"),
                ("Open App Data", "folder"),
                ("Retry", "retry"),
                ("Cancel", "cancel"),
            ],
        )
        popup.exec()
        result = popup.result_value
        if result == "console":
            webbrowser.open(
                "https://console.cloud.google.com/apis/credentials", new=1
            )
        elif result == "folder":
            subprocess.run(["explorer", str(app_data)], check=False)
        elif result == "retry":
            try:
                mgr._load_client_config()
            except Exception:
                pass
            _refresh_gmail_auth_state(tab)
        return

    auth_btn = getattr(tab, 'gmail_authorize_btn', None)
    if auth_btn is not None:
        auth_btn.setEnabled(False)
    status_label = getattr(tab, 'gmail_auth_status', None)
    if status_label is not None:
        status_label.setText("Browser opened — complete sign-in...")

    success = backend.start_oauth_flow()
    if not success:
        pass


def _on_gmail_auth_failed(tab: WidgetsTab, message: str) -> None:
    """Handle auth failure — re-enable button and show error."""
    logger.warning("[GMAIL_TAB] Auth failed: %s", message)
    auth_btn = getattr(tab, 'gmail_authorize_btn', None)
    if auth_btn is not None:
        auth_btn.setEnabled(True)
    status_label = getattr(tab, 'gmail_auth_status', None)
    if status_label is not None:
        status_label.setText("Sign-in failed")
    StyledPopup.show_warning(tab, "Gmail Sign-In", message or "Authorization failed.")


def _on_gmail_browse_sound(tab: WidgetsTab) -> None:
    """Open a file dialog to pick the notification sound."""
    from PySide6.QtWidgets import QFileDialog
    current = getattr(tab, 'gmail_sound_file', None)
    start_dir = ""
    if current is not None and current.text():
        from pathlib import Path
        p = Path(current.text())
        if p.exists():
            start_dir = str(p.parent)
    path, _ = QFileDialog.getOpenFileName(
        tab, "Choose Notification Sound", start_dir,
        "Audio Files (*.ogg *.wav *.mp3);;All Files (*.*)",
    )
    if path and current is not None:
        current.setText(path)


def _on_gmail_test_sound(tab: WidgetsTab) -> None:
    """Play the currently-configured sound once for testing."""
    try:
        from core.audio.notification_sound import NotificationSoundPlayer
        player = NotificationSoundPlayer.instance()
        path_widget = getattr(tab, 'gmail_sound_file', None)
        vol_widget = getattr(tab, 'gmail_sound_volume', None)
        if path_widget is not None and path_widget.text():
            player.set_file_path(path_widget.text())
        if vol_widget is not None:
            player.set_volume(int(vol_widget.value()))
        player.play()
    except Exception as exc:
        logger.warning("[GMAIL_TAB] Test sound failed: %s", exc)
        StyledPopup.show_warning(tab, "Gmail", f"Test sound failed: {exc}")


def _on_gmail_sign_out_clicked(tab: WidgetsTab) -> None:
    """Revoke and clear credentials for the active backend."""
    backend = _get_gmail_backend()
    if backend is None:
        return
    if not StyledPopup.question(tab, "Sign Out of Gmail", "Remove Gmail credentials and sign out?"):
        return
    try:
        backend.sign_out()
    except Exception as exc:
        logger.warning("[GMAIL_TAB] Sign-out failed: %s", exc)
    _refresh_gmail_auth_state(tab)


def _on_gmail_backend_changed(tab: WidgetsTab, mode_text: str) -> None:
    """Handle backend mode combo box change."""
    from core.gmail.gmail_backend import GmailBackendMode
    backend = _get_gmail_backend()
    if backend is None:
        return
    backend.mode = GmailBackendMode.IMAP if mode_text == "IMAP (App Password)" else GmailBackendMode.OAUTH
    _refresh_gmail_auth_state(tab)


def _on_gmail_imap_save(tab: WidgetsTab) -> None:
    """Test IMAP credentials off the UI thread, then save them on success."""
    backend = _get_gmail_backend()
    if backend is None:
        return
    email_field = getattr(tab, 'gmail_imap_email', None)
    pw_field = getattr(tab, 'gmail_imap_password', None)
    if email_field is None or pw_field is None:
        return
    email_addr = email_field.text().strip()
    app_pw = pw_field.text().strip()
    if not email_addr or not app_pw:
        StyledPopup.show_warning(tab, "Gmail IMAP", "Email and App Password are both required.")
        return

    status_label = getattr(tab, 'gmail_auth_status', None)
    if status_label:
        status_label.setText("Testing connection...")
    save_btn = getattr(tab, 'gmail_imap_save_btn', None)
    if save_btn is not None:
        save_btn.setEnabled(False)

    generation = int(getattr(tab, "_gmail_imap_save_generation", 0)) + 1
    tab._gmail_imap_save_generation = generation

    def _test_credentials() -> bool:
        return backend.test_imap_credentials(email_addr, app_pw)

    def _finish(result) -> None:
        def _apply_result() -> None:
            if getattr(tab, "_gmail_imap_save_generation", None) != generation:
                return
            if save_btn is not None:
                save_btn.setEnabled(True)
            success = bool(getattr(result, "success", False) and getattr(result, "result", False))
            if success:
                backend.save_imap_credentials(email_addr, app_pw)
                if status_label:
                    status_label.setText(f"Connected (IMAP: {email_addr})")
                StyledPopup.show_success(tab, "Gmail IMAP", "Connection successful!")
            else:
                if status_label:
                    status_label.setText("IMAP login failed")
                StyledPopup.show_warning(
                    tab, "Gmail IMAP",
                    "Login failed. Check your email and app password.\n\n"
                    "Make sure:\n"
                    "  - 2-Step Verification is enabled on your Google account\n"
                    "  - You generated an App Password at myaccount.google.com/apppasswords\n"
                    "  - You entered the 16-character app password (not your regular password)"
                )
            _refresh_gmail_auth_state(tab)

        ThreadManager.run_on_ui_thread(_apply_result)

    try:
        manager = _get_gmail_thread_manager(tab)
        manager.submit_io_task(
            _test_credentials,
            task_id=f"gmail_imap_save_test_{generation}",
            callback=_finish,
        )
    except Exception as exc:
        logger.warning("[GMAIL_TAB] Failed to submit IMAP test task: %s", exc)
        if save_btn is not None:
            save_btn.setEnabled(True)
        if status_label:
            status_label.setText("IMAP test could not start")
        StyledPopup.show_warning(tab, "Gmail IMAP", "Could not start IMAP connection test.")


def build_gmail_ui(tab: WidgetsTab, layout: QVBoxLayout) -> QWidget:
    """Build Gmail section UI and attach widgets to tab instance.

    GUARDRAIL: Only these controls may live outside a bucket:
      - Enable checkbox
    ALL other settings MUST be placed inside a collapsed-by-default bucket.
    The Backend bucket is the only default-open bucket because connection
    state is the first-run task for this widget.
    When adding new interactable settings, create or extend a bucket.

    Returns the Gmail container widget.
    """
    from ui.tabs.widgets_tab import NoWheelSlider

    gmail_group = QGroupBox("Gmail Widget")
    style_group_box(gmail_group)
    gmail_layout = QVBoxLayout(gmail_group)
    gmail_layout.setSpacing(16)

    # Enable checkbox
    tab.gmail_enabled = QCheckBox("Enable Gmail Widget")
    tab.gmail_enabled.setProperty("circleIndicator", True)
    tab.gmail_enabled.setChecked(tab._default_bool('gmail', 'enabled', bool(_gmail_default(tab, 'enabled'))))
    tab.gmail_enabled.stateChanged.connect(tab._save_settings)
    tab.gmail_enabled.stateChanged.connect(tab._update_stack_status)
    gmail_layout.addWidget(tab.gmail_enabled)

    # Controls container
    tab._gmail_controls_container = QWidget()
    _gc = QVBoxLayout(tab._gmail_controls_container)
    _gc.setContentsMargins(0, 0, 0, 12)
    _gc.setSpacing(12)

    backend_toggle, backend_body, backend_inner = build_bucket_toggle(
        _gc, "Backend",
        expanded=tab.get_gmail_bucket_state("backend", default=True),
        on_toggle=lambda checked: tab.set_gmail_bucket_state("backend", checked),
        defer_initial_visibility=True,
    )

    gmail_info = QLabel(
        "Shows recent Gmail messages. Choose a backend below to connect."
    )
    gmail_info.setWordWrap(True)
    gmail_info.setStyleSheet(INFO_LABEL_STYLE)
    backend_inner.addWidget(gmail_info)

    # ------------------------------------------------------------------
    # Backend mode selector
    # ------------------------------------------------------------------
    mode_row = _aligned_row(backend_inner, "Backend:")
    tab.gmail_backend_combo = StyledComboBox()
    tab.gmail_backend_combo.addItems(["IMAP (App Password)", "OAuth (Advanced)"])
    tab.gmail_backend_combo.setMinimumWidth(180)
    tab.gmail_backend_combo.currentTextChanged.connect(
        lambda text: _on_gmail_backend_changed(tab, text)
    )
    mode_row.addWidget(tab.gmail_backend_combo)
    mode_row.addStretch()

    # ------------------------------------------------------------------
    # IMAP panel: email + app password + save/test
    # ------------------------------------------------------------------
    tab._gmail_imap_panel = QWidget()
    imap_layout = QVBoxLayout(tab._gmail_imap_panel)
    imap_layout.setContentsMargins(0, 0, 0, 0)
    imap_layout.setSpacing(8)

    imap_info = QLabel(
        "Enter your Gmail address and an <b>App Password</b>.<br>"
        "Create one at <a href='https://myaccount.google.com/apppasswords'>"
        "myaccount.google.com/apppasswords</a> (requires 2-Step Verification)."
    )
    imap_info.setWordWrap(True)
    imap_info.setOpenExternalLinks(True)
    imap_info.setStyleSheet(INFO_LABEL_STYLE)
    imap_layout.addWidget(imap_info)

    email_row = _aligned_row(imap_layout, "Email:")
    tab.gmail_imap_email = QLineEdit()
    tab.gmail_imap_email.setPlaceholderText("you@gmail.com")
    tab.gmail_imap_email.setMinimumWidth(260)
    email_row.addWidget(tab.gmail_imap_email)
    email_row.addStretch()

    pw_row = _aligned_row(imap_layout, "App Password:")
    tab.gmail_imap_password = QLineEdit()
    tab.gmail_imap_password.setPlaceholderText("xxxx xxxx xxxx xxxx")
    tab.gmail_imap_password.setEchoMode(QLineEdit.EchoMode.Password)
    tab.gmail_imap_password.setMinimumWidth(260)
    pw_row.addWidget(tab.gmail_imap_password)

    tab.gmail_imap_save_btn = QPushButton("Save && Test")
    tab.gmail_imap_save_btn.clicked.connect(lambda: _on_gmail_imap_save(tab))
    pw_row.addWidget(tab.gmail_imap_save_btn)
    pw_row.addStretch()

    backend_inner.addWidget(tab._gmail_imap_panel)

    # ------------------------------------------------------------------
    # OAuth panel (shown when OAuth mode selected)
    # ------------------------------------------------------------------
    tab._gmail_oauth_panel = QWidget()
    oauth_layout = QVBoxLayout(tab._gmail_oauth_panel)
    oauth_layout.setContentsMargins(0, 0, 0, 0)
    oauth_layout.setSpacing(8)

    oauth_info = QLabel(
        "OAuth requires a Google Cloud project with gmail.metadata scope. "
        "This is a <b>restricted</b> scope — in Testing mode, tokens expire every 7 days."
    )
    oauth_info.setWordWrap(True)
    oauth_info.setStyleSheet(INFO_LABEL_STYLE)
    oauth_layout.addWidget(oauth_info)

    backend_inner.addWidget(tab._gmail_oauth_panel)

    # ------------------------------------------------------------------
    # Account status / Authorize / Sign Out (shared between modes)
    # ------------------------------------------------------------------
    auth_row = _aligned_row(backend_inner, "Account:")
    tab.gmail_auth_status = QLabel("")
    tab.gmail_auth_status.setStyleSheet(STATUS_LABEL_STYLE)
    tab.gmail_auth_status.setMinimumWidth(180)
    auth_row.addWidget(tab.gmail_auth_status)

    tab.gmail_authorize_btn = QPushButton("Authorize")
    tab.gmail_sign_out_btn = QPushButton("Sign Out")
    auth_row.addWidget(tab.gmail_authorize_btn)
    auth_row.addWidget(tab.gmail_sign_out_btn)
    auth_row.addStretch()

    tab.gmail_authorize_btn.clicked.connect(lambda: _on_gmail_authorize_clicked(tab))
    tab.gmail_sign_out_btn.clicked.connect(lambda: _on_gmail_sign_out_clicked(tab))

    tab.gmail_auth_status.setText("Gmail status loading...")
    _update_backend_panels(tab, use_backend=False)
    _set_visible_if_changed(tab.gmail_authorize_btn, False)
    _set_visible_if_changed(tab.gmail_sign_out_btn, False)
    _queue_gmail_auth_refresh(tab)

    # Layout bucket
    layout_toggle, layout_body, layout_inner = build_bucket_toggle(
        _gc, "Layout",
        expanded=tab.get_gmail_bucket_state("layout", default=False),
        on_toggle=lambda checked: tab.set_gmail_bucket_state("layout", checked),
        defer_initial_visibility=True,
    )

    # Monitor
    disp_row = _aligned_row(layout_inner, "Display:")
    tab.gmail_monitor_combo = StyledComboBox(size_variant="compact")
    tab.gmail_monitor_combo.addItems(["ALL", "1", "2", "3"])
    tab.gmail_monitor_combo.currentTextChanged.connect(tab._save_settings)
    tab.gmail_monitor_combo.currentTextChanged.connect(tab._update_stack_status)
    tab.gmail_monitor_combo.setMinimumWidth(120)
    disp_row.addWidget(tab.gmail_monitor_combo)
    gmail_monitor_default = _gmail_default(tab, 'monitor')
    tab._set_combo_text(tab.gmail_monitor_combo, str(gmail_monitor_default))
    disp_row.addStretch()

    # Position
    pos_row = _aligned_row(layout_inner, "Position:")
    tab.gmail_position = StyledComboBox()
    tab.gmail_position.addItems(list(get_widget_position_option_labels("gmail")))
    tab.gmail_position.currentTextChanged.connect(tab._save_settings)
    tab.gmail_position.currentTextChanged.connect(tab._update_stack_status)
    tab.gmail_position.setMinimumWidth(150)
    pos_row.addWidget(tab.gmail_position)
    tab._set_combo_text(tab.gmail_position, tab._default_str('gmail', 'position', str(_gmail_default(tab, 'position'))))
    tab.gmail_stack_status = QLabel("")
    tab.gmail_stack_status.setMinimumWidth(100)
    tab.gmail_stack_status.setStyleSheet(STATUS_LABEL_STYLE)
    pos_row.addWidget(tab.gmail_stack_status)
    pos_row.addStretch()

    # Width
    width_row = _aligned_row(layout_inner, "Width:")
    tab.gmail_width = QSpinBox()
    tab.gmail_width.setRange(200, 1200)
    tab.gmail_width.setSingleStep(10)
    tab.gmail_width.setValue(tab._default_int('gmail', 'width', int(_gmail_default(tab, 'width'))))
    tab.gmail_width.setAccelerated(True)
    tab.gmail_width.setSuffix(" px")
    tab.gmail_width.valueChanged.connect(tab._save_settings)
    width_row.addWidget(tab.gmail_width)
    width_row.addStretch()

    # Limit
    limit_row = _aligned_row(layout_inner, "Max Emails:")
    tab.gmail_limit = QSpinBox()
    tab.gmail_limit.setRange(1, 10)
    tab.gmail_limit.setValue(tab._default_int('gmail', 'limit', int(_gmail_default(tab, 'limit'))))
    tab.gmail_limit.setAccelerated(True)
    tab.gmail_limit.valueChanged.connect(tab._save_settings)
    limit_row.addWidget(tab.gmail_limit)
    limit_row.addStretch()

    # Refresh interval
    refresh_row = _aligned_row(layout_inner, "Refresh:")
    tab.gmail_refresh = QSpinBox()
    tab.gmail_refresh.setRange(1, 60)
    tab.gmail_refresh.setValue(tab._default_int('gmail', 'refresh_minutes', int(_gmail_default(tab, 'refresh_minutes'))))
    tab.gmail_refresh.setAccelerated(True)
    tab.gmail_refresh.setSuffix(" min")
    tab.gmail_refresh.valueChanged.connect(tab._save_settings)
    refresh_row.addWidget(tab.gmail_refresh)
    refresh_row.addStretch()

    # Filter label
    filter_row = _aligned_row(layout_inner, "Label Filter:")
    tab.gmail_filter_label = QLineEdit()
    tab.gmail_filter_label.setText(tab._default_str('gmail', 'filter_label', str(_gmail_default(tab, 'filter_label'))))
    tab.gmail_filter_label.setPlaceholderText("e.g. INBOX, CATEGORY_PRIMARY")
    tab.gmail_filter_label.setMinimumWidth(180)
    tab.gmail_filter_label.textChanged.connect(tab._save_settings)
    filter_row.addWidget(tab.gmail_filter_label)
    filter_row.addStretch()

    account_slot_row = _aligned_row(layout_inner, "Account Slot:")
    tab.gmail_account_slot = QSpinBox()
    tab.gmail_account_slot.setRange(0, 9)
    tab.gmail_account_slot.setValue(tab._default_int('gmail', 'account_slot', int(_gmail_default(tab, 'account_slot'))))
    tab.gmail_account_slot.setAccelerated(True)
    tab.gmail_account_slot.valueChanged.connect(tab._save_settings)
    account_slot_row.addWidget(tab.gmail_account_slot)
    account_slot_row.addStretch()

    # Appearance bucket
    appearance_toggle, appearance_body, appearance_inner = build_bucket_toggle(
        _gc, "Appearance",
        expanded=tab.get_gmail_bucket_state("appearance", default=False),
        on_toggle=lambda checked: tab.set_gmail_bucket_state("appearance", checked),
        defer_initial_visibility=True,
    )

    # Font family
    from ui.widgets import StyledFontComboBox
    font_row = _aligned_row(appearance_inner, "Font:")
    tab.gmail_font_combo = StyledFontComboBox(size_variant="hero")
    default_font = tab._default_str('gmail', 'font_family', 'Inter')
    tab.gmail_font_combo.setCurrentFont(QFont(default_font))
    tab.gmail_font_combo.setMinimumWidth(220)
    tab.gmail_font_combo.currentFontChanged.connect(tab._save_settings)
    font_row.addWidget(tab.gmail_font_combo)
    font_row.addStretch()

    # Font size
    fsize_row = _aligned_row(appearance_inner, "Font Size:")
    tab.gmail_font_size = QSpinBox()
    tab.gmail_font_size.setRange(8, 48)
    tab.gmail_font_size.setValue(tab._default_int('gmail', 'font_size', 14))
    tab.gmail_font_size.setAccelerated(True)
    tab.gmail_font_size.valueChanged.connect(tab._save_settings)
    fsize_row.addWidget(tab.gmail_font_size)
    fsize_row.addWidget(create_inline_label("px"))
    fsize_row.addStretch()

    # Margin
    margin_row = _aligned_row(appearance_inner, "Margin:")
    tab.gmail_margin = QSpinBox()
    tab.gmail_margin.setRange(0, 100)
    tab.gmail_margin.setValue(tab._default_int('gmail', 'margin', 30))
    tab.gmail_margin.setAccelerated(True)
    tab.gmail_margin.valueChanged.connect(tab._save_settings)
    margin_row.addWidget(tab.gmail_margin)
    margin_row.addWidget(create_inline_label("px"))
    margin_row.addStretch()

    logo_adjust_row = _aligned_row(appearance_inner, "Header Logo:")
    tab.gmail_header_logo_px_adjust = QSpinBox()
    tab.gmail_header_logo_px_adjust.setRange(-12, 24)
    tab.gmail_header_logo_px_adjust.setSuffix(" px")
    tab.gmail_header_logo_px_adjust.setValue(tab._default_int('gmail', 'header_logo_px_adjust', 0))
    tab.gmail_header_logo_px_adjust.setAccelerated(True)
    tab.gmail_header_logo_px_adjust.valueChanged.connect(tab._save_settings)
    logo_adjust_row.addWidget(tab.gmail_header_logo_px_adjust)
    logo_adjust_row.addStretch()

    # Boolean toggles
    appearance_inner.addSpacing(8)

    tab.gmail_show_sender = QCheckBox("Show Sender Name")
    tab.gmail_show_sender.setProperty("circleIndicator", True)
    tab.gmail_show_sender.setChecked(tab._default_bool('gmail', 'show_sender', True))
    tab.gmail_show_sender.stateChanged.connect(tab._save_settings)
    appearance_inner.addWidget(tab.gmail_show_sender)

    tab.gmail_show_subject = QCheckBox("Show Subject Line")
    tab.gmail_show_subject.setProperty("circleIndicator", True)
    tab.gmail_show_subject.setChecked(tab._default_bool('gmail', 'show_subject', True))
    tab.gmail_show_subject.stateChanged.connect(tab._save_settings)
    appearance_inner.addWidget(tab.gmail_show_subject)

    tab.gmail_show_envelope = QCheckBox("Show Envelope Icon")
    tab.gmail_show_envelope.setProperty("circleIndicator", True)
    tab.gmail_show_envelope.setChecked(tab._default_bool('gmail', 'show_envelope_icon', True))
    tab.gmail_show_envelope.stateChanged.connect(tab._save_settings)
    appearance_inner.addWidget(tab.gmail_show_envelope)

    tab.gmail_show_three_dot = QCheckBox("Show Action Menu (Three-Dot)")
    tab.gmail_show_three_dot.setProperty("circleIndicator", True)
    tab.gmail_show_three_dot.setChecked(tab._default_bool('gmail', 'show_three_dot_menu', True))
    tab.gmail_show_three_dot.stateChanged.connect(tab._save_settings)
    appearance_inner.addWidget(tab.gmail_show_three_dot)

    tab.gmail_show_refresh_spiral = QCheckBox("Show Refresh Spiral")
    tab.gmail_show_refresh_spiral.setProperty("circleIndicator", True)
    tab.gmail_show_refresh_spiral.setChecked(tab._default_bool('gmail', 'show_refresh_spiral', True))
    tab.gmail_show_refresh_spiral.stateChanged.connect(tab._save_settings)
    appearance_inner.addWidget(tab.gmail_show_refresh_spiral)

    tab.gmail_show_unread_count = QCheckBox("Show Unread Count in Header")
    tab.gmail_show_unread_count.setProperty("circleIndicator", True)
    tab.gmail_show_unread_count.setChecked(tab._default_bool('gmail', 'show_unread_count_in_header', True))
    tab.gmail_show_unread_count.stateChanged.connect(tab._save_settings)
    appearance_inner.addWidget(tab.gmail_show_unread_count)

    tab.gmail_show_header_border = QCheckBox("Show Header Border")
    tab.gmail_show_header_border.setProperty("circleIndicator", True)
    tab.gmail_show_header_border.setChecked(tab._default_bool('gmail', 'show_header_border', True))
    tab.gmail_show_header_border.stateChanged.connect(tab._save_settings)
    appearance_inner.addWidget(tab.gmail_show_header_border)

    tab.gmail_show_timestamp = QCheckBox("Show Time Received")
    tab.gmail_show_timestamp.setProperty("circleIndicator", True)
    tab.gmail_show_timestamp.setChecked(tab._default_bool('gmail', 'show_timestamp', True))
    tab.gmail_show_timestamp.stateChanged.connect(tab._save_settings)
    appearance_inner.addWidget(tab.gmail_show_timestamp)

    date_mode_row = _aligned_row(appearance_inner, "Date Style:")
    tab.gmail_date_display_mode = StyledComboBox(size_variant="compact")
    tab.gmail_date_display_mode.addItems(["Relative", "Numerical", "Words"])
    tab.gmail_date_display_mode.currentTextChanged.connect(tab._save_settings)
    tab.gmail_date_display_mode.setMinimumWidth(130)
    tab.gmail_date_display_mode.setEnabled(tab.gmail_show_timestamp.isChecked())
    tab.gmail_show_timestamp.stateChanged.connect(
        lambda state: tab.gmail_date_display_mode.setEnabled(bool(state))
    )
    tab._set_combo_text(
        tab.gmail_date_display_mode,
        {
            "relative": "Relative",
            "numeric": "Numerical",
            "words": "Words",
        }.get(tab._default_str('gmail', 'date_display_mode', str(_gmail_default(tab, 'date_display_mode'))).lower(), "Relative"),
    )
    date_mode_row.addWidget(tab.gmail_date_display_mode)
    date_mode_row.addStretch()

    tab.gmail_group_threads = QCheckBox("Group Similar Email Threads")
    tab.gmail_group_threads.setProperty("circleIndicator", True)
    tab.gmail_group_threads.setChecked(tab._default_bool('gmail', 'group_threads', False))
    tab.gmail_group_threads.stateChanged.connect(tab._save_settings)
    appearance_inner.addWidget(tab.gmail_group_threads)

    tab.gmail_auto_title_case = QCheckBox("Auto Title-Case Subjects")
    tab.gmail_auto_title_case.setProperty("circleIndicator", True)
    tab.gmail_auto_title_case.setChecked(tab._default_bool('gmail', 'auto_title_case', True))
    tab.gmail_auto_title_case.stateChanged.connect(tab._save_settings)
    appearance_inner.addWidget(tab.gmail_auto_title_case)

    tab.gmail_clean_sender_names = QCheckBox("Clean Up Sender Names")
    tab.gmail_clean_sender_names.setProperty("circleIndicator", True)
    tab.gmail_clean_sender_names.setChecked(tab._default_bool('gmail', 'clean_sender_names', True))
    tab.gmail_clean_sender_names.stateChanged.connect(tab._save_settings)
    appearance_inner.addWidget(tab.gmail_clean_sender_names)

    text_limit_row = _aligned_row(appearance_inner, "Text Limits:")
    text_limit_grid = QGridLayout()
    text_limit_grid.setContentsMargins(0, 0, 0, 0)
    text_limit_grid.setHorizontalSpacing(20)
    text_limit_grid.setVerticalSpacing(10)
    text_limit_grid.setColumnMinimumWidth(0, 112)
    text_limit_grid.setColumnMinimumWidth(2, 136)
    tab.gmail_max_sender_words = QSpinBox()
    tab.gmail_max_sender_words.setRange(0, 20)
    tab.gmail_max_sender_words.setSpecialValueText("Off")
    tab.gmail_max_sender_words.setValue(tab._default_int('gmail', 'max_sender_words', 3))
    tab.gmail_max_sender_words.setAccelerated(True)
    tab.gmail_max_sender_words.valueChanged.connect(tab._save_settings)
    text_limit_grid.addWidget(create_inline_label("Sender words"), 0, 0)
    text_limit_grid.addWidget(tab.gmail_max_sender_words, 0, 1)

    tab.gmail_sender_column_width = QSpinBox()
    tab.gmail_sender_column_width.setRange(40, 360)
    tab.gmail_sender_column_width.setValue(tab._default_int('gmail', 'sender_column_width', 180))
    tab.gmail_sender_column_width.setAccelerated(True)
    tab.gmail_sender_column_width.setSuffix(" px")
    tab.gmail_sender_column_width.valueChanged.connect(tab._save_settings)
    text_limit_grid.addWidget(create_inline_label("Sender column"), 0, 2)
    text_limit_grid.addWidget(tab.gmail_sender_column_width, 0, 3)

    tab.gmail_max_subject_words = QSpinBox()
    tab.gmail_max_subject_words.setRange(0, 30)
    tab.gmail_max_subject_words.setSpecialValueText("Off")
    tab.gmail_max_subject_words.setValue(tab._default_int('gmail', 'max_subject_words', 4))
    tab.gmail_max_subject_words.setAccelerated(True)
    tab.gmail_max_subject_words.valueChanged.connect(tab._save_settings)
    text_limit_grid.addWidget(create_inline_label("Subject words"), 1, 0)
    text_limit_grid.addWidget(tab.gmail_max_subject_words, 1, 1)

    tab.gmail_max_subject_chars = QSpinBox()
    tab.gmail_max_subject_chars.setRange(0, 200)
    tab.gmail_max_subject_chars.setSpecialValueText("Off")
    tab.gmail_max_subject_chars.setValue(tab._default_int('gmail', 'max_subject_chars', 0))
    tab.gmail_max_subject_chars.setAccelerated(True)
    tab.gmail_max_subject_chars.valueChanged.connect(tab._save_settings)
    text_limit_grid.addWidget(create_inline_label("Subject chars"), 1, 2)
    text_limit_grid.addWidget(tab.gmail_max_subject_chars, 1, 3)
    text_limit_grid.setColumnStretch(4, 1)
    text_limit_row.addLayout(text_limit_grid)
    text_limit_row.addStretch()

    tab.gmail_desaturate = QCheckBox("Desaturate Logo When No Unread")
    tab.gmail_desaturate.setProperty("circleIndicator", True)
    tab.gmail_desaturate.setChecked(tab._default_bool('gmail', 'desaturate_when_no_unread', True))
    tab.gmail_desaturate.stateChanged.connect(tab._save_settings)
    appearance_inner.addWidget(tab.gmail_desaturate)

    appearance_inner.addSpacing(8)

    # Background frame
    tab.gmail_show_background = QCheckBox("Show Background Frame")
    tab.gmail_show_background.setProperty("circleIndicator", True)
    tab.gmail_show_background.setChecked(tab._default_bool('gmail', 'show_background', True))
    tab.gmail_show_background.stateChanged.connect(tab._save_settings)
    appearance_inner.addWidget(tab.gmail_show_background)

    appearance_inner.addSpacing(8)

    # Background opacity
    opacity_row = _aligned_row(appearance_inner, "Background Opacity:")
    tab.gmail_bg_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.gmail_bg_opacity.setMinimum(0)
    tab.gmail_bg_opacity.setMaximum(100)
    gmail_bg_opacity_pct = int(tab._default_float('gmail', 'bg_opacity', 0.6) * 100)
    tab.gmail_bg_opacity.setValue(gmail_bg_opacity_pct)
    tab.gmail_bg_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.gmail_bg_opacity.setTickInterval(10)
    tab.gmail_bg_opacity.valueChanged.connect(tab._save_settings)
    opacity_row.addWidget(tab.gmail_bg_opacity)
    tab.gmail_bg_opacity_label = QLabel(f"{gmail_bg_opacity_pct}%")
    tab.gmail_bg_opacity.valueChanged.connect(
        lambda v: tab.gmail_bg_opacity_label.setText(f"{v}%")
    )
    tab.gmail_bg_opacity_label.setMinimumWidth(50)
    opacity_row.addWidget(tab.gmail_bg_opacity_label)

    # Text color
    color_row = _swatch_row(appearance_inner, "Text Color:")
    tab.gmail_color_btn = ColorSwatchButton(title="Choose Gmail Text Color")
    tab.gmail_color_btn.set_color(tab._gmail_color)
    tab.gmail_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_gmail_color', c), tab._save_settings())
    )
    color_row.addWidget(tab.gmail_color_btn)
    color_row.addStretch()

    # Background color
    bg_color_row = _swatch_row(appearance_inner, "Background Color:")
    tab.gmail_bg_color_btn = ColorSwatchButton(title="Choose Gmail Background Color")
    tab.gmail_bg_color_btn.set_color(tab._gmail_bg_color)
    tab.gmail_bg_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_gmail_bg_color', c), tab._save_settings())
    )
    bg_color_row.addWidget(tab.gmail_bg_color_btn)
    bg_color_row.addStretch()

    # Border color
    border_color_row = _swatch_row(appearance_inner, "Border Color:")
    tab.gmail_border_color_btn = ColorSwatchButton(title="Choose Gmail Border Color")
    tab.gmail_border_color_btn.set_color(tab._gmail_border_color)
    tab.gmail_border_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_gmail_border_color', c), tab._save_settings())
    )
    border_color_row.addWidget(tab.gmail_border_color_btn)
    border_color_row.addStretch()

    # Border opacity
    border_opacity_row = _aligned_row(appearance_inner, "Border Opacity:")
    tab.gmail_border_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.gmail_border_opacity.setMinimum(0)
    tab.gmail_border_opacity.setMaximum(100)
    gmail_border_opacity_pct = int(tab._default_float('gmail', 'border_opacity', 1.0) * 100)
    tab.gmail_border_opacity.setValue(gmail_border_opacity_pct)
    tab.gmail_border_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.gmail_border_opacity.setTickInterval(10)
    tab.gmail_border_opacity.valueChanged.connect(tab._save_settings)
    border_opacity_row.addWidget(tab.gmail_border_opacity)
    tab.gmail_border_opacity_label = QLabel(f"{gmail_border_opacity_pct}%")
    tab.gmail_border_opacity.valueChanged.connect(
        lambda v: tab.gmail_border_opacity_label.setText(f"{v}%")
    )
    tab.gmail_border_opacity_label.setMinimumWidth(50)
    border_opacity_row.addWidget(tab.gmail_border_opacity_label)

    # Separators bucket
    sep_toggle, sep_body, sep_inner = build_bucket_toggle(
        _gc, "Separators",
        expanded=tab.get_gmail_bucket_state("separators", default=False),
        on_toggle=lambda checked: tab.set_gmail_bucket_state("separators", checked),
        defer_initial_visibility=True,
    )

    tab.gmail_show_separators = QCheckBox("Show Separator Lines")
    tab.gmail_show_separators.setProperty("circleIndicator", True)
    tab.gmail_show_separators.setChecked(tab._default_bool('gmail', 'show_separators', True))
    tab.gmail_show_separators.stateChanged.connect(tab._save_settings)
    sep_inner.addWidget(tab.gmail_show_separators)

    sep_color_row = _swatch_row(sep_inner, "Separator Color:")
    tab.gmail_separator_color_btn = ColorSwatchButton(title="Choose Separator Color")
    tab.gmail_separator_color_btn.set_color(tab._gmail_separator_color)
    tab.gmail_separator_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_gmail_separator_color', c), tab._save_settings())
    )
    sep_color_row.addWidget(tab.gmail_separator_color_btn)
    sep_color_row.addStretch()

    sep_thick_row = _aligned_row(sep_inner, "Separator Thickness:")
    tab.gmail_separator_thickness = QSpinBox()
    tab.gmail_separator_thickness.setRange(1, 4)
    tab.gmail_separator_thickness.setValue(tab._default_int('gmail', 'separator_thickness', 1))
    tab.gmail_separator_thickness.setAccelerated(True)
    tab.gmail_separator_thickness.valueChanged.connect(tab._save_settings)
    sep_thick_row.addWidget(tab.gmail_separator_thickness)
    sep_thick_row.addWidget(create_inline_label("px"))
    sep_thick_row.addStretch()

    bsep_color_row = _swatch_row(sep_inner, "Boundary Color:")
    tab.gmail_boundary_separator_color_btn = ColorSwatchButton(title="Choose Boundary Separator Color")
    tab.gmail_boundary_separator_color_btn.set_color(tab._gmail_boundary_separator_color)
    tab.gmail_boundary_separator_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_gmail_boundary_separator_color', c), tab._save_settings())
    )
    bsep_color_row.addWidget(tab.gmail_boundary_separator_color_btn)
    bsep_color_row.addStretch()

    bsep_thick_row = _aligned_row(sep_inner, "Boundary Thickness:")
    tab.gmail_boundary_separator_thickness = QSpinBox()
    tab.gmail_boundary_separator_thickness.setRange(1, 6)
    tab.gmail_boundary_separator_thickness.setValue(tab._default_int('gmail', 'boundary_separator_thickness', 2))
    tab.gmail_boundary_separator_thickness.setAccelerated(True)
    tab.gmail_boundary_separator_thickness.valueChanged.connect(tab._save_settings)
    bsep_thick_row.addWidget(tab.gmail_boundary_separator_thickness)
    bsep_thick_row.addWidget(create_inline_label("px"))
    bsep_thick_row.addStretch()

    # Sound bucket
    sound_toggle, sound_body, sound_inner = build_bucket_toggle(
        _gc, "Notification Sound",
        expanded=tab.get_gmail_bucket_state("sound", default=False),
        on_toggle=lambda checked: tab.set_gmail_bucket_state("sound", checked),
        defer_initial_visibility=True,
    )

    tab.gmail_play_sound = QCheckBox("Play Sound on New Mail")
    tab.gmail_play_sound.setProperty("circleIndicator", True)
    tab.gmail_play_sound.setChecked(tab._default_bool('gmail', 'play_sound_on_new_mail', False))
    tab.gmail_play_sound.stateChanged.connect(tab._save_settings)
    sound_inner.addWidget(tab.gmail_play_sound)

    # Sound file path
    sound_path_row = _aligned_row(sound_inner, "Sound File:")
    tab.gmail_sound_file = QLineEdit()
    tab.gmail_sound_file.setText(tab._default_str('gmail', 'sound_file_path', default_notification_sound_path()))
    tab.gmail_sound_file.setPlaceholderText("Path to .ogg/.wav/.mp3")
    tab.gmail_sound_file.setMinimumWidth(220)
    tab.gmail_sound_file.textChanged.connect(tab._save_settings)
    sound_path_row.addWidget(tab.gmail_sound_file)

    tab.gmail_sound_browse_btn = QPushButton("Browse...")
    tab.gmail_sound_browse_btn.clicked.connect(lambda: _on_gmail_browse_sound(tab))
    sound_path_row.addWidget(tab.gmail_sound_browse_btn)

    tab.gmail_sound_test_btn = QPushButton("Test")
    tab.gmail_sound_test_btn.clicked.connect(lambda: _on_gmail_test_sound(tab))
    sound_path_row.addWidget(tab.gmail_sound_test_btn)
    sound_path_row.addStretch()

    # Sound volume
    sound_vol_row = _aligned_row(sound_inner, "Sound Volume:")
    tab.gmail_sound_volume = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.gmail_sound_volume.setMinimum(0)
    tab.gmail_sound_volume.setMaximum(100)
    tab.gmail_sound_volume.setValue(tab._default_int('gmail', 'sound_volume_percent', 50))
    tab.gmail_sound_volume.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.gmail_sound_volume.setTickInterval(10)
    tab.gmail_sound_volume.valueChanged.connect(tab._save_settings)
    sound_vol_row.addWidget(tab.gmail_sound_volume)
    tab.gmail_sound_volume_label = QLabel(f"{tab.gmail_sound_volume.value()}%")
    tab.gmail_sound_volume.valueChanged.connect(
        lambda v: tab.gmail_sound_volume_label.setText(f"{v}%")
    )
    tab.gmail_sound_volume_label.setMinimumWidth(50)
    sound_vol_row.addWidget(tab.gmail_sound_volume_label)

    for toggle, body in (
        (backend_toggle, backend_body),
        (layout_toggle, layout_body),
        (appearance_toggle, appearance_body),
        (sep_toggle, sep_body),
        (sound_toggle, sound_body),
    ):
        _finalize_bucket_body(toggle, body)

    gmail_layout.addWidget(tab._gmail_controls_container)
    tab.gmail_enabled.stateChanged.connect(lambda: _update_gmail_enabled_visibility(tab))
    _update_gmail_enabled_visibility(tab)

    container = QWidget()
    container_layout = QVBoxLayout(container)
    container_layout.setContentsMargins(0, 20, 0, 0)
    container_layout.addWidget(gmail_group)
    return container


def load_gmail_settings(tab: WidgetsTab, widgets: dict) -> None:
    """Load gmail settings from widgets config dict."""
    def _apply_color(btn_attr: str, color_attr: str) -> None:
        btn = getattr(tab, btn_attr, None)
        color = getattr(tab, color_attr, None)
        if btn is not None and color is not None and hasattr(btn, "set_color"):
            try:
                btn.set_color(color)
            except Exception:
                logger.debug("[GMAIL_TAB] Failed to sync %s", btn_attr, exc_info=True)

    gmail_config = widgets.get('gmail', {})
    if not isinstance(gmail_config, dict):
        gmail_config = {}
    gmail_defaults = {
        key: _gmail_default(tab, key)
        for key in (
            'enabled', 'position', 'monitor', 'limit', 'refresh_minutes',
            'filter_label', 'account_slot', 'width', 'font_family',
            'font_size', 'header_logo_px_adjust', 'margin', 'show_sender', 'show_subject',
            'show_envelope_icon', 'show_three_dot_menu', 'show_refresh_spiral',
            'show_unread_count_in_header', 'show_header_border',
            'show_separators', 'show_timestamp', 'date_display_mode',
            'group_threads', 'auto_title_case', 'clean_sender_names',
            'max_sender_words', 'sender_column_width', 'max_subject_words',
            'max_subject_chars', 'desaturate_when_no_unread',
            'show_background', 'bg_opacity',
            'border_opacity', 'separator_thickness',
            'boundary_separator_thickness', 'play_sound_on_new_mail',
            'sound_file_path', 'sound_volume_percent', 'color',
            'bg_color', 'border_color', 'separator_color',
            'boundary_separator_color',
        )
    }

    with _block_gmail_setting_signals(tab):
        tab.gmail_enabled.setChecked(tab._config_bool('gmail', gmail_config, 'enabled', bool(gmail_defaults['enabled'])))

        gmail_pos = tab._config_str('gmail', gmail_config, 'position', str(gmail_defaults['position']))
        idx = tab.gmail_position.findText(gmail_pos)
        if idx >= 0:
            tab.gmail_position.setCurrentIndex(idx)

        mon_sel = gmail_config.get('monitor', gmail_defaults['monitor'])
        mon_text = str(mon_sel) if isinstance(mon_sel, (int, str)) else str(gmail_defaults['monitor'])
        mon_idx = tab.gmail_monitor_combo.findText(mon_text)
        if mon_idx >= 0:
            tab.gmail_monitor_combo.setCurrentIndex(mon_idx)

        tab.gmail_limit.setValue(tab._config_int('gmail', gmail_config, 'limit', int(gmail_defaults['limit'])))
        tab.gmail_refresh.setValue(tab._config_int('gmail', gmail_config, 'refresh_minutes', int(gmail_defaults['refresh_minutes'])))
        tab.gmail_filter_label.setText(tab._config_str('gmail', gmail_config, 'filter_label', str(gmail_defaults['filter_label'])))
        tab.gmail_account_slot.setValue(tab._config_int('gmail', gmail_config, 'account_slot', int(gmail_defaults['account_slot'])))
        width_default = gmail_defaults['width']
        width_value = gmail_config.get('width', gmail_config.get('min_width', width_default))
        try:
            tab.gmail_width.setValue(int(width_value))
        except (TypeError, ValueError):
            tab.gmail_width.setValue(int(width_default))
        tab.gmail_font_combo.setCurrentFont(QFont(tab._config_str('gmail', gmail_config, 'font_family', str(gmail_defaults['font_family']))))
        tab.gmail_font_size.setValue(tab._config_int('gmail', gmail_config, 'font_size', int(gmail_defaults['font_size'])))
        tab.gmail_header_logo_px_adjust.setValue(tab._config_int('gmail', gmail_config, 'header_logo_px_adjust', int(gmail_defaults['header_logo_px_adjust'])))
        tab.gmail_margin.setValue(tab._config_int('gmail', gmail_config, 'margin', int(gmail_defaults['margin'])))

        tab.gmail_show_sender.setChecked(tab._config_bool('gmail', gmail_config, 'show_sender', bool(gmail_defaults['show_sender'])))
        tab.gmail_show_subject.setChecked(tab._config_bool('gmail', gmail_config, 'show_subject', bool(gmail_defaults['show_subject'])))
        tab.gmail_show_envelope.setChecked(tab._config_bool('gmail', gmail_config, 'show_envelope_icon', bool(gmail_defaults['show_envelope_icon'])))
        tab.gmail_show_three_dot.setChecked(tab._config_bool('gmail', gmail_config, 'show_three_dot_menu', bool(gmail_defaults['show_three_dot_menu'])))
        tab.gmail_show_refresh_spiral.setChecked(tab._config_bool('gmail', gmail_config, 'show_refresh_spiral', bool(gmail_defaults['show_refresh_spiral'])))
        tab.gmail_show_unread_count.setChecked(tab._config_bool('gmail', gmail_config, 'show_unread_count_in_header', bool(gmail_defaults['show_unread_count_in_header'])))
        tab.gmail_show_header_border.setChecked(tab._config_bool('gmail', gmail_config, 'show_header_border', bool(gmail_defaults['show_header_border'])))
        tab.gmail_show_separators.setChecked(tab._config_bool('gmail', gmail_config, 'show_separators', bool(gmail_defaults['show_separators'])))
        tab.gmail_show_timestamp.setChecked(tab._config_bool('gmail', gmail_config, 'show_timestamp', bool(gmail_defaults['show_timestamp'])))
        tab._set_combo_text(
            tab.gmail_date_display_mode,
            {
                "relative": "Relative",
                "numeric": "Numerical",
                "numerical": "Numerical",
                "words": "Words",
            }.get(str(gmail_config.get('date_display_mode', gmail_defaults['date_display_mode'])).lower(), "Relative"),
        )
        tab.gmail_date_display_mode.setEnabled(tab.gmail_show_timestamp.isChecked())
        tab.gmail_group_threads.setChecked(tab._config_bool('gmail', gmail_config, 'group_threads', bool(gmail_defaults['group_threads'])))
        tab.gmail_auto_title_case.setChecked(tab._config_bool('gmail', gmail_config, 'auto_title_case', bool(gmail_defaults['auto_title_case'])))
        tab.gmail_clean_sender_names.setChecked(tab._config_bool('gmail', gmail_config, 'clean_sender_names', bool(gmail_defaults['clean_sender_names'])))
        tab.gmail_max_sender_words.setValue(tab._config_int('gmail', gmail_config, 'max_sender_words', int(gmail_defaults['max_sender_words'])))
        tab.gmail_sender_column_width.setValue(tab._config_int('gmail', gmail_config, 'sender_column_width', int(gmail_defaults['sender_column_width'])))
        tab.gmail_max_subject_words.setValue(tab._config_int('gmail', gmail_config, 'max_subject_words', int(gmail_defaults['max_subject_words'])))
        tab.gmail_max_subject_chars.setValue(tab._config_int('gmail', gmail_config, 'max_subject_chars', int(gmail_defaults['max_subject_chars'])))
        tab.gmail_desaturate.setChecked(tab._config_bool('gmail', gmail_config, 'desaturate_when_no_unread', bool(gmail_defaults['desaturate_when_no_unread'])))

        tab.gmail_show_background.setChecked(tab._config_bool('gmail', gmail_config, 'show_background', bool(gmail_defaults['show_background'])))
        opacity_pct = int(tab._config_float('gmail', gmail_config, 'bg_opacity', float(gmail_defaults['bg_opacity'])) * 100)
        tab.gmail_bg_opacity.setValue(opacity_pct)
        tab.gmail_bg_opacity_label.setText(f"{opacity_pct}%")

        border_opacity_pct = int(tab._config_float('gmail', gmail_config, 'border_opacity', float(gmail_defaults['border_opacity'])) * 100)
        tab.gmail_border_opacity.setValue(border_opacity_pct)
        tab.gmail_border_opacity_label.setText(f"{border_opacity_pct}%")

        tab.gmail_separator_thickness.setValue(tab._config_int('gmail', gmail_config, 'separator_thickness', int(gmail_defaults['separator_thickness'])))
        tab.gmail_boundary_separator_thickness.setValue(tab._config_int('gmail', gmail_config, 'boundary_separator_thickness', int(gmail_defaults['boundary_separator_thickness'])))

        # Sound settings
        tab.gmail_play_sound.setChecked(tab._config_bool('gmail', gmail_config, 'play_sound_on_new_mail', bool(gmail_defaults['play_sound_on_new_mail'])))
        tab.gmail_sound_file.setText(tab._config_str('gmail', gmail_config, 'sound_file_path', str(gmail_defaults['sound_file_path'])))
        tab.gmail_sound_volume.setValue(tab._config_int('gmail', gmail_config, 'sound_volume_percent', int(gmail_defaults['sound_volume_percent'])))
        tab.gmail_sound_volume_label.setText(f"{tab.gmail_sound_volume.value()}%")

        # Colors
        color_data = gmail_config.get('color', gmail_defaults['color'])
        tab._gmail_color = QColor(*color_data)
        bg_color_data = gmail_config.get('bg_color', gmail_defaults['bg_color'])
        try:
            tab._gmail_bg_color = QColor(*bg_color_data)
        except Exception:
            tab._gmail_bg_color = QColor(35, 35, 35, 255)
        border_color_data = gmail_config.get('border_color', gmail_defaults['border_color'])
        try:
            tab._gmail_border_color = QColor(*border_color_data)
        except Exception:
            tab._gmail_border_color = QColor(255, 255, 255, 255)
        sep_color_data = gmail_config.get('separator_color', gmail_defaults['separator_color'])
        tab._gmail_separator_color = QColor(*sep_color_data)
        bsep_color_data = gmail_config.get('boundary_separator_color', gmail_defaults['boundary_separator_color'])
        tab._gmail_boundary_separator_color = QColor(*bsep_color_data)
        _apply_color('gmail_color_btn', '_gmail_color')
        _apply_color('gmail_separator_color_btn', '_gmail_separator_color')
        _apply_color('gmail_boundary_separator_color_btn', '_gmail_boundary_separator_color')
        _apply_color('gmail_bg_color_btn', '_gmail_bg_color')
        _apply_color('gmail_border_color_btn', '_gmail_border_color')

    _update_gmail_enabled_visibility(tab)
    _update_backend_panels(tab, use_backend=False)
    _queue_gmail_auth_refresh(tab)


def save_gmail_settings(tab: WidgetsTab) -> dict:
    """Return gmail_config dict from current UI state."""
    filter_default = str(_gmail_default(tab, 'filter_label'))
    sound_default = str(_gmail_default(tab, 'sound_file_path'))
    gmail_config = {
        'enabled': tab.gmail_enabled.isChecked(),
        'position': tab.gmail_position.currentText(),
        'limit': tab.gmail_limit.value(),
        'refresh_minutes': tab.gmail_refresh.value(),
        'filter_label': tab.gmail_filter_label.text().strip() or filter_default,
        'account_slot': str(tab.gmail_account_slot.value()),
        'width': tab.gmail_width.value(),
        'font_family': tab.gmail_font_combo.currentFont().family(),
        'font_size': tab.gmail_font_size.value(),
        'header_logo_px_adjust': tab.gmail_header_logo_px_adjust.value(),
        'margin': tab.gmail_margin.value(),
        'show_sender': tab.gmail_show_sender.isChecked(),
        'show_subject': tab.gmail_show_subject.isChecked(),
        'show_envelope_icon': tab.gmail_show_envelope.isChecked(),
        'show_three_dot_menu': tab.gmail_show_three_dot.isChecked(),
        'show_refresh_spiral': tab.gmail_show_refresh_spiral.isChecked(),
        'show_unread_count_in_header': tab.gmail_show_unread_count.isChecked(),
        'show_header_border': tab.gmail_show_header_border.isChecked(),
        'show_separators': tab.gmail_show_separators.isChecked(),
        'show_timestamp': tab.gmail_show_timestamp.isChecked(),
        'date_display_mode': {
            "Relative": "relative",
            "Numerical": "numeric",
            "Words": "words",
        }.get(tab.gmail_date_display_mode.currentText(), "relative"),
        'group_threads': tab.gmail_group_threads.isChecked(),
        'auto_title_case': tab.gmail_auto_title_case.isChecked(),
        'clean_sender_names': tab.gmail_clean_sender_names.isChecked(),
        'max_sender_words': tab.gmail_max_sender_words.value(),
        'sender_column_width': tab.gmail_sender_column_width.value(),
        'max_subject_words': tab.gmail_max_subject_words.value(),
        'max_subject_chars': tab.gmail_max_subject_chars.value(),
        'desaturate_when_no_unread': tab.gmail_desaturate.isChecked(),
        'show_background': tab.gmail_show_background.isChecked(),
        'bg_opacity': tab.gmail_bg_opacity.value() / 100.0,
        'color': [tab._gmail_color.red(), tab._gmail_color.green(),
                  tab._gmail_color.blue(), tab._gmail_color.alpha()],
        'bg_color': [tab._gmail_bg_color.red(), tab._gmail_bg_color.green(),
                     tab._gmail_bg_color.blue(), tab._gmail_bg_color.alpha()],
        'border_color': [tab._gmail_border_color.red(), tab._gmail_border_color.green(),
                         tab._gmail_border_color.blue(), tab._gmail_border_color.alpha()],
        'border_opacity': tab.gmail_border_opacity.value() / 100.0,
        'separator_thickness': tab.gmail_separator_thickness.value(),
        'boundary_separator_thickness': tab.gmail_boundary_separator_thickness.value(),
        'separator_color': [tab._gmail_separator_color.red(), tab._gmail_separator_color.green(),
                            tab._gmail_separator_color.blue(), tab._gmail_separator_color.alpha()],
        'boundary_separator_color': [tab._gmail_boundary_separator_color.red(), tab._gmail_boundary_separator_color.green(),
                                     tab._gmail_boundary_separator_color.blue(), tab._gmail_boundary_separator_color.alpha()],
        'play_sound_on_new_mail': tab.gmail_play_sound.isChecked(),
        'sound_file_path': tab.gmail_sound_file.text().strip() or sound_default,
        'sound_volume_percent': tab.gmail_sound_volume.value(),
    }
    mon_text = tab.gmail_monitor_combo.currentText()
    gmail_config['monitor'] = mon_text if mon_text == 'ALL' else int(mon_text)

    return gmail_config
