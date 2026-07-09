"""Steam widget family settings section.

Phase 3 keeps this dev-gated and provider-inert. Building or loading this
section must not decrypt credentials, scan caches, fetch assets, or submit
provider work.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

from PySide6.QtWidgets import QCheckBox, QGroupBox, QHBoxLayout, QLabel, QSpinBox, QVBoxLayout, QWidget

from rendering.widget_descriptors import get_widget_position_option_labels
from ui.tabs.shared_styles import (
    INFO_LABEL_STYLE,
    STATUS_LABEL_STYLE,
    add_aligned_row,
    build_bucket_toggle,
    style_group_box,
)
from ui.widgets import StyledComboBox

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab


_STEAM_CARD_ORDER: tuple[tuple[str, str, str], ...] = (
    ("steam_progress", "Steam Progress", "Top Right"),
    ("achievement_pulse", "Achievement Pulse", "Middle Right"),
    ("abandonment_issues", "Abandonment Issues", "Bottom Right"),
    ("friend_pulse", "Friend Pulse", "Top Left"),
)


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

    font_row = _aligned_row(layout, "Font Size:")
    font_size = QSpinBox()
    font_size.setRange(8, 40)
    font_size.setValue(tab._default_int(key, "font_size", 14))
    font_size.valueChanged.connect(tab._save_settings)
    setattr(tab, font_attr, font_size)
    font_row.addWidget(font_size)
    font_row.addWidget(QLabel("px"))
    font_row.addStretch()

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
        "Steam is currently development-gated. Opening this section does not check credentials, "
        "scan caches, fetch assets, or contact Steam."
    )
    info.setWordWrap(True)
    info.setStyleSheet(INFO_LABEL_STYLE)
    connection_layout.addWidget(info)

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
    tab.steam_refresh_minutes.setRange(15, 240)
    tab.steam_refresh_minutes.setSuffix(" min")
    tab.steam_refresh_minutes.setValue(tab._default_int("steam", "refresh_minutes", 30))
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

    tab.steam_connection_status = QLabel("Connection not checked this session.")
    tab.steam_connection_status.setStyleSheet(STATUS_LABEL_STYLE)
    connection_layout.addWidget(tab.steam_connection_status)

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
            int(steam_config.get("refresh_minutes", tab._default_int("steam", "refresh_minutes", 30)))
        )
    except Exception:
        tab.steam_refresh_minutes.setValue(tab._default_int("steam", "refresh_minutes", 30))
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
        try:
            getattr(tab, f"{key}_font_size").setValue(
                int(config.get("font_size", tab._default_int(key, "font_size", 14)))
            )
        except Exception:
            getattr(tab, f"{key}_font_size").setValue(tab._default_int(key, "font_size", 14))


def _save_card(tab: "WidgetsTab", key: str) -> dict[str, Any]:
    defaults = tab._widget_defaults.get(key, {})
    if not isinstance(defaults, dict):
        defaults = {}
    payload = dict(defaults)
    payload.update({
        "enabled": getattr(tab, f"{key}_enabled").isChecked(),
        "position": getattr(tab, f"{key}_position").currentText(),
        "monitor": getattr(tab, f"{key}_monitor_combo").currentText(),
        "font_size": int(getattr(tab, f"{key}_font_size").value()),
    })
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
