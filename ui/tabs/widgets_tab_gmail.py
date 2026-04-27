"""Gmail widget section for widgets tab.

Extracted UI building, settings loading/saving for the Gmail overlay widget.
Gated by ``core.dev_gates.is_gmail_enabled()``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QGroupBox, QCheckBox, QLineEdit,
    QSlider, QWidget, QPushButton,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

from core.logging.logger import get_logger
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


def _update_gmail_enabled_visibility(tab: WidgetsTab) -> None:
    """Show/hide all Gmail controls based on gmail_enabled checkbox."""
    enabled = getattr(tab, 'gmail_enabled', None) and tab.gmail_enabled.isChecked()
    container = getattr(tab, '_gmail_controls_container', None)
    if container is not None:
        container.setVisible(bool(enabled))


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


def _refresh_gmail_auth_state(tab: WidgetsTab) -> None:
    """Update the auth status label and button visibility based on credential state."""
    status_label = getattr(tab, 'gmail_auth_status', None)
    auth_btn = getattr(tab, 'gmail_authorize_btn', None)
    out_btn = getattr(tab, 'gmail_sign_out_btn', None)
    if status_label is None or auth_btn is None or out_btn is None:
        return

    backend = _get_gmail_backend()
    if backend is None:
        status_label.setText("Gmail unavailable")
        auth_btn.setEnabled(False)
        out_btn.setEnabled(False)
        out_btn.setVisible(False)
        return

    # Reload OAuth config in case client_secrets was added after start
    mgr = _get_gmail_oauth_manager()
    if mgr is not None:
        try:
            mgr._load_client_config()
        except Exception:
            pass

    # Update mode-specific panel visibility
    _update_backend_panels(tab)

    status_label.setText(backend.status_text)

    if backend.is_authenticated:
        auth_btn.setVisible(False)
        out_btn.setVisible(True)
        out_btn.setEnabled(True)
    else:
        from core.gmail.gmail_backend import GmailBackendMode
        if backend.mode == GmailBackendMode.IMAP:
            auth_btn.setVisible(False)
        else:
            auth_btn.setVisible(True)
            auth_btn.setEnabled(True)
        out_btn.setVisible(False)


def _update_backend_panels(tab: WidgetsTab) -> None:
    """Show/hide OAuth vs IMAP panels based on current backend mode."""
    backend = _get_gmail_backend()
    if backend is None:
        return
    from core.gmail.gmail_backend import GmailBackendMode
    is_imap = backend.mode == GmailBackendMode.IMAP
    oauth_panel = getattr(tab, '_gmail_oauth_panel', None)
    imap_panel = getattr(tab, '_gmail_imap_panel', None)
    if oauth_panel is not None:
        oauth_panel.setVisible(not is_imap)
    if imap_panel is not None:
        imap_panel.setVisible(is_imap)


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
    """Save IMAP credentials and test connection."""
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

    backend.save_imap_credentials(email_addr, app_pw)
    success = backend.test_imap_connection()
    if success:
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


def build_gmail_ui(tab: WidgetsTab, layout: QVBoxLayout) -> QWidget:
    """Build Gmail section UI and attach widgets to tab instance.

    GUARDRAIL: Only these controls may live outside a bucket:
      - Enable checkbox
      - Backend mode selector (+ IMAP/OAuth panels)
      - Email + App Password fields (IMAP panel)
      - Account status row
    ALL other settings MUST be placed inside a collapsed-by-default bucket.
    When adding new interactable settings, create or extend a bucket.

    Returns the Gmail container widget.
    """
    from core.dev_gates import is_gmail_enabled
    from ui.tabs.widgets_tab import NoWheelSlider

    gmail_gated = not is_gmail_enabled()

    gmail_group = QGroupBox("Gmail Widget")
    style_group_box(gmail_group)
    gmail_layout = QVBoxLayout(gmail_group)
    gmail_layout.setSpacing(16)

    # Enable checkbox
    tab.gmail_enabled = QCheckBox("Enable Gmail Widget")
    tab.gmail_enabled.setProperty("circleIndicator", True)
    tab.gmail_enabled.setChecked(tab._default_bool('gmail', 'enabled', False))
    tab.gmail_enabled.stateChanged.connect(tab._save_settings)
    tab.gmail_enabled.stateChanged.connect(tab._update_stack_status)
    gmail_layout.addWidget(tab.gmail_enabled)

    if gmail_gated:
        tab.gmail_enabled.setEnabled(False)
        tab.gmail_enabled.setChecked(False)
        gate_label = QLabel("Requires --devgmail flag to enable.")
        gate_label.setStyleSheet(INFO_LABEL_STYLE)
        gmail_layout.addWidget(gate_label)

    # Controls container
    tab._gmail_controls_container = QWidget()
    _gc = QVBoxLayout(tab._gmail_controls_container)
    _gc.setContentsMargins(0, 0, 0, 12)
    _gc.setSpacing(12)

    gmail_info = QLabel(
        "Shows recent Gmail messages. Choose a backend below to connect."
    )
    gmail_info.setWordWrap(True)
    gmail_info.setStyleSheet(INFO_LABEL_STYLE)
    _gc.addWidget(gmail_info)

    # ------------------------------------------------------------------
    # Backend mode selector
    # ------------------------------------------------------------------
    mode_row = _aligned_row(_gc, "Backend:")
    tab.gmail_backend_combo = StyledComboBox()
    tab.gmail_backend_combo.addItems(["IMAP (App Password)", "OAuth (Advanced)"])
    tab.gmail_backend_combo.setMinimumWidth(180)
    backend = _get_gmail_backend()
    if backend is not None:
        from core.gmail.gmail_backend import GmailBackendMode
        if backend.mode == GmailBackendMode.IMAP:
            tab.gmail_backend_combo.setCurrentIndex(0)
        else:
            tab.gmail_backend_combo.setCurrentIndex(1)
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
    if backend is not None and getattr(backend, '_imap_email', None):
        tab.gmail_imap_email.setText(backend._imap_email)
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

    _gc.addWidget(tab._gmail_imap_panel)

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

    _gc.addWidget(tab._gmail_oauth_panel)

    # ------------------------------------------------------------------
    # Account status / Authorize / Sign Out (shared between modes)
    # ------------------------------------------------------------------
    auth_row = _aligned_row(_gc, "Account:")
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

    _refresh_gmail_auth_state(tab)

    # Layout bucket
    _, _, layout_inner = build_bucket_toggle(
        _gc, "Layout",
        expanded=tab.get_gmail_bucket_state("layout", default=False),
        on_toggle=lambda checked: tab.set_gmail_bucket_state("layout", checked),
    )

    # Position
    pos_row = _aligned_row(layout_inner, "Position:")
    tab.gmail_position = StyledComboBox()
    tab.gmail_position.addItems([
        "Top Left", "Top Center", "Top Right",
        "Middle Left", "Center", "Middle Right",
        "Bottom Left", "Bottom Center", "Bottom Right",
    ])
    tab.gmail_position.currentTextChanged.connect(tab._save_settings)
    tab.gmail_position.currentTextChanged.connect(tab._update_stack_status)
    tab.gmail_position.setMinimumWidth(150)
    pos_row.addWidget(tab.gmail_position)
    tab._set_combo_text(tab.gmail_position, tab._default_str('gmail', 'position', 'Top Left'))
    tab.gmail_stack_status = QLabel("")
    tab.gmail_stack_status.setMinimumWidth(100)
    tab.gmail_stack_status.setStyleSheet(STATUS_LABEL_STYLE)
    pos_row.addWidget(tab.gmail_stack_status)
    pos_row.addStretch()

    # Monitor
    disp_row = _aligned_row(layout_inner, "Display:")
    tab.gmail_monitor_combo = StyledComboBox(size_variant="compact")
    tab.gmail_monitor_combo.addItems(["ALL", "1", "2", "3"])
    tab.gmail_monitor_combo.currentTextChanged.connect(tab._save_settings)
    tab.gmail_monitor_combo.currentTextChanged.connect(tab._update_stack_status)
    tab.gmail_monitor_combo.setMinimumWidth(120)
    disp_row.addWidget(tab.gmail_monitor_combo)
    gmail_monitor_default = tab._widget_default('gmail', 'monitor', 'ALL')
    tab._set_combo_text(tab.gmail_monitor_combo, str(gmail_monitor_default))
    disp_row.addStretch()

    # Limit
    limit_row = _aligned_row(layout_inner, "Max Emails:")
    tab.gmail_limit = QSpinBox()
    tab.gmail_limit.setRange(1, 10)
    tab.gmail_limit.setValue(tab._default_int('gmail', 'limit', 5))
    tab.gmail_limit.setAccelerated(True)
    tab.gmail_limit.valueChanged.connect(tab._save_settings)
    limit_row.addWidget(tab.gmail_limit)
    limit_row.addStretch()

    # Refresh interval
    refresh_row = _aligned_row(layout_inner, "Refresh:")
    tab.gmail_refresh = QSpinBox()
    tab.gmail_refresh.setRange(1, 60)
    tab.gmail_refresh.setValue(tab._default_int('gmail', 'refresh_minutes', 5))
    tab.gmail_refresh.setAccelerated(True)
    tab.gmail_refresh.setSuffix(" min")
    tab.gmail_refresh.valueChanged.connect(tab._save_settings)
    refresh_row.addWidget(tab.gmail_refresh)
    refresh_row.addStretch()

    # Filter label
    filter_row = _aligned_row(layout_inner, "Label Filter:")
    tab.gmail_filter_label = QLineEdit()
    tab.gmail_filter_label.setText(tab._default_str('gmail', 'filter_label', 'INBOX'))
    tab.gmail_filter_label.setPlaceholderText("e.g. INBOX, CATEGORY_PRIMARY")
    tab.gmail_filter_label.setMinimumWidth(180)
    tab.gmail_filter_label.textChanged.connect(tab._save_settings)
    filter_row.addWidget(tab.gmail_filter_label)
    filter_row.addStretch()

    # Appearance bucket
    _, _, appearance_inner = build_bucket_toggle(
        _gc, "Appearance",
        expanded=tab.get_gmail_bucket_state("appearance", default=False),
        on_toggle=lambda checked: tab.set_gmail_bucket_state("appearance", checked),
    )

    # Font family
    from ui.widgets import StyledFontComboBox
    font_row = _aligned_row(appearance_inner, "Font:")
    tab.gmail_font_combo = StyledFontComboBox(size_variant="hero")
    default_font = tab._default_str('gmail', 'font_family', 'Segoe UI')
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

    # Boolean toggles
    appearance_inner.addSpacing(8)

    tab.gmail_show_sender = QCheckBox("Show sender name")
    tab.gmail_show_sender.setProperty("circleIndicator", True)
    tab.gmail_show_sender.setChecked(tab._default_bool('gmail', 'show_sender', True))
    tab.gmail_show_sender.stateChanged.connect(tab._save_settings)
    appearance_inner.addWidget(tab.gmail_show_sender)

    tab.gmail_show_subject = QCheckBox("Show subject line")
    tab.gmail_show_subject.setProperty("circleIndicator", True)
    tab.gmail_show_subject.setChecked(tab._default_bool('gmail', 'show_subject', True))
    tab.gmail_show_subject.stateChanged.connect(tab._save_settings)
    appearance_inner.addWidget(tab.gmail_show_subject)

    tab.gmail_show_envelope = QCheckBox("Show envelope icon")
    tab.gmail_show_envelope.setProperty("circleIndicator", True)
    tab.gmail_show_envelope.setChecked(tab._default_bool('gmail', 'show_envelope_icon', True))
    tab.gmail_show_envelope.stateChanged.connect(tab._save_settings)
    appearance_inner.addWidget(tab.gmail_show_envelope)

    tab.gmail_show_three_dot = QCheckBox("Show action menu (three-dot)")
    tab.gmail_show_three_dot.setProperty("circleIndicator", True)
    tab.gmail_show_three_dot.setChecked(tab._default_bool('gmail', 'show_three_dot_menu', True))
    tab.gmail_show_three_dot.stateChanged.connect(tab._save_settings)
    appearance_inner.addWidget(tab.gmail_show_three_dot)

    tab.gmail_show_unread_count = QCheckBox("Show unread count in header")
    tab.gmail_show_unread_count.setProperty("circleIndicator", True)
    tab.gmail_show_unread_count.setChecked(tab._default_bool('gmail', 'show_unread_count_in_header', True))
    tab.gmail_show_unread_count.stateChanged.connect(tab._save_settings)
    appearance_inner.addWidget(tab.gmail_show_unread_count)

    tab.gmail_show_timestamp = QCheckBox("Show time received")
    tab.gmail_show_timestamp.setProperty("circleIndicator", True)
    tab.gmail_show_timestamp.setChecked(tab._default_bool('gmail', 'show_timestamp', True))
    tab.gmail_show_timestamp.stateChanged.connect(tab._save_settings)
    appearance_inner.addWidget(tab.gmail_show_timestamp)

    tab.gmail_auto_title_case = QCheckBox("Auto title-case subjects")
    tab.gmail_auto_title_case.setProperty("circleIndicator", True)
    tab.gmail_auto_title_case.setChecked(tab._default_bool('gmail', 'auto_title_case', True))
    tab.gmail_auto_title_case.stateChanged.connect(tab._save_settings)
    appearance_inner.addWidget(tab.gmail_auto_title_case)

    tab.gmail_desaturate = QCheckBox("Desaturate logo when no unread")
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

    # Intense shadow
    tab.gmail_intense_shadow = QCheckBox("Intense Shadows")
    tab.gmail_intense_shadow.setProperty("circleIndicator", True)
    tab.gmail_intense_shadow.setChecked(tab._default_bool('gmail', 'intense_shadow', True))
    tab.gmail_intense_shadow.stateChanged.connect(tab._save_settings)
    appearance_inner.addWidget(tab.gmail_intense_shadow)

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
    _, _, sep_inner = build_bucket_toggle(
        _gc, "Separators",
        expanded=tab.get_gmail_bucket_state("separators", default=False),
        on_toggle=lambda checked: tab.set_gmail_bucket_state("separators", checked),
    )

    tab.gmail_show_separators = QCheckBox("Show separator lines")
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
    _, _, sound_inner = build_bucket_toggle(
        _gc, "Notification Sound",
        expanded=tab.get_gmail_bucket_state("sound", default=False),
        on_toggle=lambda checked: tab.set_gmail_bucket_state("sound", checked),
    )

    tab.gmail_play_sound = QCheckBox("Play Sound on New Mail")
    tab.gmail_play_sound.setProperty("circleIndicator", True)
    tab.gmail_play_sound.setChecked(tab._default_bool('gmail', 'play_sound_on_new_mail', False))
    tab.gmail_play_sound.stateChanged.connect(tab._save_settings)
    sound_inner.addWidget(tab.gmail_play_sound)

    # Sound file path
    sound_path_row = _aligned_row(sound_inner, "Sound File:")
    tab.gmail_sound_file = QLineEdit()
    tab.gmail_sound_file.setText(tab._default_str('gmail', 'sound_file_path', 'resources/tutuogg.ogg'))
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

    # Disable all controls if gated
    if gmail_gated:
        tab._gmail_controls_container.setEnabled(False)

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

    tab.gmail_enabled.setChecked(tab._config_bool('gmail', gmail_config, 'enabled', False))

    gmail_pos = tab._config_str('gmail', gmail_config, 'position', 'Top Left')
    idx = tab.gmail_position.findText(gmail_pos)
    if idx >= 0:
        tab.gmail_position.setCurrentIndex(idx)

    mon_sel = gmail_config.get('monitor', tab._widget_default('gmail', 'monitor', 'ALL'))
    mon_text = str(mon_sel) if isinstance(mon_sel, (int, str)) else 'ALL'
    mon_idx = tab.gmail_monitor_combo.findText(mon_text)
    if mon_idx >= 0:
        tab.gmail_monitor_combo.setCurrentIndex(mon_idx)

    tab.gmail_limit.setValue(tab._config_int('gmail', gmail_config, 'limit', 5))
    tab.gmail_refresh.setValue(tab._config_int('gmail', gmail_config, 'refresh_minutes', 5))
    tab.gmail_filter_label.setText(tab._config_str('gmail', gmail_config, 'filter_label', 'INBOX'))
    tab.gmail_font_combo.setCurrentFont(QFont(tab._config_str('gmail', gmail_config, 'font_family', 'Segoe UI')))
    tab.gmail_font_size.setValue(tab._config_int('gmail', gmail_config, 'font_size', 14))
    tab.gmail_margin.setValue(tab._config_int('gmail', gmail_config, 'margin', 30))

    tab.gmail_show_sender.setChecked(tab._config_bool('gmail', gmail_config, 'show_sender', True))
    tab.gmail_show_subject.setChecked(tab._config_bool('gmail', gmail_config, 'show_subject', True))
    tab.gmail_show_envelope.setChecked(tab._config_bool('gmail', gmail_config, 'show_envelope_icon', True))
    tab.gmail_show_three_dot.setChecked(tab._config_bool('gmail', gmail_config, 'show_three_dot_menu', True))
    tab.gmail_show_unread_count.setChecked(tab._config_bool('gmail', gmail_config, 'show_unread_count_in_header', True))
    tab.gmail_show_separators.setChecked(tab._config_bool('gmail', gmail_config, 'show_separators', True))
    tab.gmail_show_timestamp.setChecked(tab._config_bool('gmail', gmail_config, 'show_timestamp', True))
    tab.gmail_auto_title_case.setChecked(tab._config_bool('gmail', gmail_config, 'auto_title_case', True))
    tab.gmail_desaturate.setChecked(tab._config_bool('gmail', gmail_config, 'desaturate_when_no_unread', True))

    tab.gmail_show_background.setChecked(tab._config_bool('gmail', gmail_config, 'show_background', True))
    tab.gmail_intense_shadow.setChecked(tab._config_bool('gmail', gmail_config, 'intense_shadow', True))

    opacity_pct = int(tab._config_float('gmail', gmail_config, 'bg_opacity', 0.6) * 100)
    tab.gmail_bg_opacity.setValue(opacity_pct)
    tab.gmail_bg_opacity_label.setText(f"{opacity_pct}%")

    border_opacity_pct = int(tab._config_float('gmail', gmail_config, 'border_opacity', 1.0) * 100)
    tab.gmail_border_opacity.setValue(border_opacity_pct)
    tab.gmail_border_opacity_label.setText(f"{border_opacity_pct}%")

    tab.gmail_separator_thickness.setValue(tab._config_int('gmail', gmail_config, 'separator_thickness', 1))
    tab.gmail_boundary_separator_thickness.setValue(tab._config_int('gmail', gmail_config, 'boundary_separator_thickness', 2))

    # Sound settings
    tab.gmail_play_sound.setChecked(tab._config_bool('gmail', gmail_config, 'play_sound_on_new_mail', False))
    tab.gmail_sound_file.setText(tab._config_str('gmail', gmail_config, 'sound_file_path', 'resources/tutuogg.ogg'))
    tab.gmail_sound_volume.setValue(tab._config_int('gmail', gmail_config, 'sound_volume_percent', 50))
    tab.gmail_sound_volume_label.setText(f"{tab.gmail_sound_volume.value()}%")

    # Colors
    color_data = gmail_config.get('color', tab._widget_default('gmail', 'color', [255, 255, 255, 230]))
    tab._gmail_color = QColor(*color_data)
    bg_color_data = gmail_config.get('bg_color', tab._widget_default('gmail', 'bg_color', [35, 35, 35, 255]))
    try:
        tab._gmail_bg_color = QColor(*bg_color_data)
    except Exception:
        tab._gmail_bg_color = QColor(35, 35, 35, 255)
    border_color_data = gmail_config.get('border_color', tab._widget_default('gmail', 'border_color', [255, 255, 255, 255]))
    try:
        tab._gmail_border_color = QColor(*border_color_data)
    except Exception:
        tab._gmail_border_color = QColor(255, 255, 255, 255)
    sep_color_data = gmail_config.get('separator_color', tab._widget_default('gmail', 'separator_color', [200, 200, 200, 40]))
    tab._gmail_separator_color = QColor(*sep_color_data)
    bsep_color_data = gmail_config.get('boundary_separator_color', tab._widget_default('gmail', 'boundary_separator_color', [180, 180, 180, 80]))
    tab._gmail_boundary_separator_color = QColor(*bsep_color_data)
    _apply_color('gmail_color_btn', '_gmail_color')
    _apply_color('gmail_separator_color_btn', '_gmail_separator_color')
    _apply_color('gmail_boundary_separator_color_btn', '_gmail_boundary_separator_color')
    _apply_color('gmail_bg_color_btn', '_gmail_bg_color')
    _apply_color('gmail_border_color_btn', '_gmail_border_color')

    # Sync backend combo from persisted GmailBackend config
    backend = _get_gmail_backend()
    combo = getattr(tab, 'gmail_backend_combo', None)
    if backend is not None and combo is not None:
        from core.gmail.gmail_backend import GmailBackendMode
        combo.setCurrentIndex(0 if backend.mode == GmailBackendMode.IMAP else 1)

    _update_gmail_enabled_visibility(tab)
    _refresh_gmail_auth_state(tab)


def save_gmail_settings(tab: WidgetsTab) -> dict:
    """Return gmail_config dict from current UI state."""
    gmail_config = {
        'enabled': tab.gmail_enabled.isChecked(),
        'position': tab.gmail_position.currentText(),
        'limit': tab.gmail_limit.value(),
        'refresh_minutes': tab.gmail_refresh.value(),
        'filter_label': tab.gmail_filter_label.text().strip() or 'INBOX',
        'font_family': tab.gmail_font_combo.currentFont().family(),
        'font_size': tab.gmail_font_size.value(),
        'margin': tab.gmail_margin.value(),
        'show_sender': tab.gmail_show_sender.isChecked(),
        'show_subject': tab.gmail_show_subject.isChecked(),
        'show_envelope_icon': tab.gmail_show_envelope.isChecked(),
        'show_three_dot_menu': tab.gmail_show_three_dot.isChecked(),
        'show_unread_count_in_header': tab.gmail_show_unread_count.isChecked(),
        'show_separators': tab.gmail_show_separators.isChecked(),
        'show_timestamp': tab.gmail_show_timestamp.isChecked(),
        'auto_title_case': tab.gmail_auto_title_case.isChecked(),
        'desaturate_when_no_unread': tab.gmail_desaturate.isChecked(),
        'show_background': tab.gmail_show_background.isChecked(),
        'intense_shadow': tab.gmail_intense_shadow.isChecked(),
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
        'sound_file_path': tab.gmail_sound_file.text().strip() or 'resources/tutuogg.ogg',
        'sound_volume_percent': tab.gmail_sound_volume.value(),
    }
    mon_text = tab.gmail_monitor_combo.currentText()
    gmail_config['monitor'] = mon_text if mon_text == 'ALL' else int(mon_text)

    return gmail_config
