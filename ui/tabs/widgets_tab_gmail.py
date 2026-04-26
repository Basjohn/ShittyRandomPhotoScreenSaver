"""Gmail widget section for widgets tab.

Extracted UI building, settings loading/saving for the Gmail overlay widget.
Gated by ``core.dev_gates.is_gmail_enabled()``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QGroupBox, QCheckBox, QLineEdit,
    QSlider, QWidget, QPushButton, QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

from core.logging.logger import get_logger
from ui.styled_popup import ColorSwatchButton
from ui.tabs.shared_styles import (
    STATUS_LABEL_STYLE,
    INFO_LABEL_STYLE,
    add_swatch_label,
    style_group_box,
    add_aligned_row,
    create_inline_label,
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


def _refresh_gmail_auth_state(tab: WidgetsTab) -> None:
    """Update the auth status label and button visibility based on credential state."""
    status_label = getattr(tab, 'gmail_auth_status', None)
    auth_btn = getattr(tab, 'gmail_authorize_btn', None)
    out_btn = getattr(tab, 'gmail_sign_out_btn', None)
    if status_label is None or auth_btn is None or out_btn is None:
        return

    mgr = _get_gmail_oauth_manager()
    if mgr is None:
        status_label.setText("OAuth unavailable")
        auth_btn.setEnabled(False)
        out_btn.setEnabled(False)
        out_btn.setVisible(False)
        return

    if mgr.is_authenticated:
        status_label.setText("Signed in")
        auth_btn.setVisible(False)
        out_btn.setVisible(True)
        out_btn.setEnabled(True)
    else:
        # Detect missing client_secrets.json
        client_id = getattr(mgr, '_client_id', None)
        if not client_id:
            status_label.setText("Missing client_secrets.json")
            auth_btn.setEnabled(False)
        else:
            status_label.setText("Not signed in")
            auth_btn.setEnabled(True)
        auth_btn.setVisible(True)
        out_btn.setVisible(False)


def _on_gmail_authorize_clicked(tab: WidgetsTab) -> None:
    """Start the OAuth flow. Non-blocking — uses internal threaded HTTP server."""
    mgr = _get_gmail_oauth_manager()
    if mgr is None:
        QMessageBox.warning(tab, "Gmail", "OAuth subsystem unavailable.")
        return

    # Wire signals once per tab instance
    if not getattr(tab, '_gmail_auth_signals_wired', False):
        try:
            mgr.auth_completed.connect(lambda _creds: _refresh_gmail_auth_state(tab))
            mgr.auth_revoked.connect(lambda: _refresh_gmail_auth_state(tab))
            mgr.auth_failed.connect(lambda msg: _on_gmail_auth_failed(tab, msg))
        except Exception as exc:
            logger.warning("[GMAIL_TAB] Signal wiring failed: %s", exc)
        tab._gmail_auth_signals_wired = True

    auth_btn = getattr(tab, 'gmail_authorize_btn', None)
    if auth_btn is not None:
        auth_btn.setEnabled(False)
    status_label = getattr(tab, 'gmail_auth_status', None)
    if status_label is not None:
        status_label.setText("Browser opened — complete sign-in...")

    started = mgr.start_auth_flow()
    if not started and auth_btn is not None:
        auth_btn.setEnabled(True)


def _on_gmail_auth_failed(tab: WidgetsTab, message: str) -> None:
    """Handle auth failure — re-enable button and show error."""
    logger.warning("[GMAIL_TAB] Auth failed: %s", message)
    auth_btn = getattr(tab, 'gmail_authorize_btn', None)
    if auth_btn is not None:
        auth_btn.setEnabled(True)
    status_label = getattr(tab, 'gmail_auth_status', None)
    if status_label is not None:
        status_label.setText("Sign-in failed")
    try:
        QMessageBox.warning(tab, "Gmail Sign-In", message or "Authorization failed.")
    except Exception:
        pass


def _on_gmail_sign_out_clicked(tab: WidgetsTab) -> None:
    """Revoke and clear local credentials."""
    mgr = _get_gmail_oauth_manager()
    if mgr is None:
        return
    confirm = QMessageBox.question(
        tab, "Sign Out of Gmail",
        "Revoke Gmail access and delete the local token?",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )
    if confirm != QMessageBox.Yes:
        return
    try:
        if mgr.is_authenticated:
            mgr.revoke_credentials()
        else:
            mgr.clear_local_credentials()
    except Exception as exc:
        logger.warning("[GMAIL_TAB] Sign-out failed: %s", exc)
    _refresh_gmail_auth_state(tab)


def build_gmail_ui(tab: WidgetsTab, layout: QVBoxLayout) -> QWidget:
    """Build Gmail section UI and attach widgets to tab instance.

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
        "Shows recent Gmail messages. Requires OAuth credentials "
        "(client_secrets.json) in your SRPSS app data folder."
    )
    gmail_info.setWordWrap(True)
    gmail_info.setStyleSheet(INFO_LABEL_STYLE)
    _gc.addWidget(gmail_info)

    # ------------------------------------------------------------------
    # OAuth: Authorize / Sign Out
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

    # Position
    pos_row = _aligned_row(_gc, "Position:")
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
    disp_row = _aligned_row(_gc, "Display:")
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
    limit_row = _aligned_row(_gc, "Max Emails:")
    tab.gmail_limit = QSpinBox()
    tab.gmail_limit.setRange(1, 10)
    tab.gmail_limit.setValue(tab._default_int('gmail', 'limit', 5))
    tab.gmail_limit.setAccelerated(True)
    tab.gmail_limit.valueChanged.connect(tab._save_settings)
    limit_row.addWidget(tab.gmail_limit)
    limit_row.addStretch()

    # Refresh interval
    refresh_row = _aligned_row(_gc, "Refresh:")
    tab.gmail_refresh = QSpinBox()
    tab.gmail_refresh.setRange(1, 60)
    tab.gmail_refresh.setValue(tab._default_int('gmail', 'refresh_minutes', 5))
    tab.gmail_refresh.setAccelerated(True)
    tab.gmail_refresh.setSuffix(" min")
    tab.gmail_refresh.valueChanged.connect(tab._save_settings)
    refresh_row.addWidget(tab.gmail_refresh)
    refresh_row.addStretch()

    # Filter label
    filter_row = _aligned_row(_gc, "Label Filter:")
    tab.gmail_filter_label = QLineEdit()
    tab.gmail_filter_label.setText(tab._default_str('gmail', 'filter_label', 'INBOX'))
    tab.gmail_filter_label.setPlaceholderText("e.g. INBOX, CATEGORY_PRIMARY")
    tab.gmail_filter_label.setMinimumWidth(180)
    tab.gmail_filter_label.textChanged.connect(tab._save_settings)
    filter_row.addWidget(tab.gmail_filter_label)
    filter_row.addStretch()

    # Font family
    from ui.widgets import StyledFontComboBox
    font_row = _aligned_row(_gc, "Font:")
    tab.gmail_font_combo = StyledFontComboBox(size_variant="hero")
    default_font = tab._default_str('gmail', 'font_family', 'Segoe UI')
    tab.gmail_font_combo.setCurrentFont(QFont(default_font))
    tab.gmail_font_combo.setMinimumWidth(220)
    tab.gmail_font_combo.currentFontChanged.connect(tab._save_settings)
    font_row.addWidget(tab.gmail_font_combo)
    font_row.addStretch()

    # Font size
    fsize_row = _aligned_row(_gc, "Font Size:")
    tab.gmail_font_size = QSpinBox()
    tab.gmail_font_size.setRange(8, 48)
    tab.gmail_font_size.setValue(tab._default_int('gmail', 'font_size', 14))
    tab.gmail_font_size.setAccelerated(True)
    tab.gmail_font_size.valueChanged.connect(tab._save_settings)
    fsize_row.addWidget(tab.gmail_font_size)
    fsize_row.addWidget(create_inline_label("px"))
    fsize_row.addStretch()

    # Margin
    margin_row = _aligned_row(_gc, "Margin:")
    tab.gmail_margin = QSpinBox()
    tab.gmail_margin.setRange(0, 100)
    tab.gmail_margin.setValue(tab._default_int('gmail', 'margin', 30))
    tab.gmail_margin.setAccelerated(True)
    tab.gmail_margin.valueChanged.connect(tab._save_settings)
    margin_row.addWidget(tab.gmail_margin)
    margin_row.addWidget(create_inline_label("px"))
    margin_row.addStretch()

    # Boolean toggles
    _gc.addSpacing(8)

    tab.gmail_show_sender = QCheckBox("Show sender name")
    tab.gmail_show_sender.setProperty("circleIndicator", True)
    tab.gmail_show_sender.setChecked(tab._default_bool('gmail', 'show_sender', True))
    tab.gmail_show_sender.stateChanged.connect(tab._save_settings)
    _gc.addWidget(tab.gmail_show_sender)

    tab.gmail_show_subject = QCheckBox("Show subject line")
    tab.gmail_show_subject.setProperty("circleIndicator", True)
    tab.gmail_show_subject.setChecked(tab._default_bool('gmail', 'show_subject', True))
    tab.gmail_show_subject.stateChanged.connect(tab._save_settings)
    _gc.addWidget(tab.gmail_show_subject)

    tab.gmail_show_envelope = QCheckBox("Show envelope icon")
    tab.gmail_show_envelope.setProperty("circleIndicator", True)
    tab.gmail_show_envelope.setChecked(tab._default_bool('gmail', 'show_envelope_icon', True))
    tab.gmail_show_envelope.stateChanged.connect(tab._save_settings)
    _gc.addWidget(tab.gmail_show_envelope)

    tab.gmail_show_three_dot = QCheckBox("Show action menu (three-dot)")
    tab.gmail_show_three_dot.setProperty("circleIndicator", True)
    tab.gmail_show_three_dot.setChecked(tab._default_bool('gmail', 'show_three_dot_menu', True))
    tab.gmail_show_three_dot.stateChanged.connect(tab._save_settings)
    _gc.addWidget(tab.gmail_show_three_dot)

    tab.gmail_show_unread_count = QCheckBox("Show unread count in header")
    tab.gmail_show_unread_count.setProperty("circleIndicator", True)
    tab.gmail_show_unread_count.setChecked(tab._default_bool('gmail', 'show_unread_count_in_header', True))
    tab.gmail_show_unread_count.stateChanged.connect(tab._save_settings)
    _gc.addWidget(tab.gmail_show_unread_count)

    tab.gmail_show_separators = QCheckBox("Show separator lines")
    tab.gmail_show_separators.setProperty("circleIndicator", True)
    tab.gmail_show_separators.setChecked(tab._default_bool('gmail', 'show_separators', True))
    tab.gmail_show_separators.stateChanged.connect(tab._save_settings)
    _gc.addWidget(tab.gmail_show_separators)

    tab.gmail_show_timestamp = QCheckBox("Show time received")
    tab.gmail_show_timestamp.setProperty("circleIndicator", True)
    tab.gmail_show_timestamp.setChecked(tab._default_bool('gmail', 'show_timestamp', True))
    tab.gmail_show_timestamp.stateChanged.connect(tab._save_settings)
    _gc.addWidget(tab.gmail_show_timestamp)

    tab.gmail_auto_title_case = QCheckBox("Auto title-case subjects")
    tab.gmail_auto_title_case.setProperty("circleIndicator", True)
    tab.gmail_auto_title_case.setChecked(tab._default_bool('gmail', 'auto_title_case', True))
    tab.gmail_auto_title_case.stateChanged.connect(tab._save_settings)
    _gc.addWidget(tab.gmail_auto_title_case)

    tab.gmail_desaturate = QCheckBox("Desaturate logo when no unread")
    tab.gmail_desaturate.setProperty("circleIndicator", True)
    tab.gmail_desaturate.setChecked(tab._default_bool('gmail', 'desaturate_when_no_unread', True))
    tab.gmail_desaturate.stateChanged.connect(tab._save_settings)
    _gc.addWidget(tab.gmail_desaturate)

    _gc.addSpacing(8)

    # Background frame
    tab.gmail_show_background = QCheckBox("Show Background Frame")
    tab.gmail_show_background.setProperty("circleIndicator", True)
    tab.gmail_show_background.setChecked(tab._default_bool('gmail', 'show_background', True))
    tab.gmail_show_background.stateChanged.connect(tab._save_settings)
    _gc.addWidget(tab.gmail_show_background)

    # Intense shadow
    tab.gmail_intense_shadow = QCheckBox("Intense Shadows")
    tab.gmail_intense_shadow.setProperty("circleIndicator", True)
    tab.gmail_intense_shadow.setChecked(tab._default_bool('gmail', 'intense_shadow', True))
    tab.gmail_intense_shadow.stateChanged.connect(tab._save_settings)
    _gc.addWidget(tab.gmail_intense_shadow)

    _gc.addSpacing(8)

    # Background opacity
    opacity_row = _aligned_row(_gc, "Background Opacity:")
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
    color_row = _swatch_row(_gc, "Text Color:")
    tab.gmail_color_btn = ColorSwatchButton(title="Choose Gmail Text Color")
    tab.gmail_color_btn.set_color(tab._gmail_color)
    tab.gmail_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_gmail_color', c), tab._save_settings())
    )
    color_row.addWidget(tab.gmail_color_btn)
    color_row.addStretch()

    # Background color
    bg_color_row = _swatch_row(_gc, "Background Color:")
    tab.gmail_bg_color_btn = ColorSwatchButton(title="Choose Gmail Background Color")
    tab.gmail_bg_color_btn.set_color(tab._gmail_bg_color)
    tab.gmail_bg_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_gmail_bg_color', c), tab._save_settings())
    )
    bg_color_row.addWidget(tab.gmail_bg_color_btn)
    bg_color_row.addStretch()

    # Border color
    border_color_row = _swatch_row(_gc, "Border Color:")
    tab.gmail_border_color_btn = ColorSwatchButton(title="Choose Gmail Border Color")
    tab.gmail_border_color_btn.set_color(tab._gmail_border_color)
    tab.gmail_border_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_gmail_border_color', c), tab._save_settings())
    )
    border_color_row.addWidget(tab.gmail_border_color_btn)
    border_color_row.addStretch()

    # Border opacity
    border_opacity_row = _aligned_row(_gc, "Border Opacity:")
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
    _apply_color('gmail_color_btn', '_gmail_color')
    _apply_color('gmail_bg_color_btn', '_gmail_bg_color')
    _apply_color('gmail_border_color_btn', '_gmail_border_color')

    _update_gmail_enabled_visibility(tab)


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
    }
    mon_text = tab.gmail_monitor_combo.currentText()
    gmail_config['monitor'] = mon_text if mon_text == 'ALL' else int(mon_text)

    return gmail_config
