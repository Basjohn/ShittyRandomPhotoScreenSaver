"""Defaults widget section for WidgetsTab."""
from __future__ import annotations

from typing import TYPE_CHECKING, Mapping

from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QGroupBox, QCheckBox, QWidget

from ui.tabs.shared_styles import FORM_ROW_LABEL_STYLE, add_aligned_row, style_group_box

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab


def build_defaults_ui(tab: WidgetsTab, layout: QVBoxLayout) -> QWidget:
    """Build the Defaults section UI and attach controls to the tab instance."""

    label_width = 150

    group = QGroupBox("Global Widget Defaults")
    style_group_box(group)
    content_layout = QVBoxLayout(group)
    content_layout.setContentsMargins(18, 16, 18, 16)
    content_layout.setSpacing(12)

    row = QHBoxLayout()
    row.setContentsMargins(0, 8, 0, 8)
    row.setSpacing(12)
    tab.widget_shadows_enabled = QCheckBox("Enable Widget Drop Shadows")
    tab.widget_shadows_enabled.setProperty("circleIndicator", True)
    tab.widget_shadows_enabled.setToolTip(
        "Applies a subtle drop shadow to every widget card when enabled."
    )
    tab.widget_shadows_enabled.setChecked(tab._default_bool("shadows", "enabled", True))
    tab.widget_shadows_enabled.stateChanged.connect(tab._save_settings)
    row.addWidget(tab.widget_shadows_enabled)
    row.addStretch()
    content_layout.addLayout(row)

    row = QHBoxLayout()
    row.setContentsMargins(0, 8, 0, 8)
    row.setSpacing(12)
    tab.widget_text_shadows_enabled = QCheckBox("Enable Widget Text Shadows")
    tab.widget_text_shadows_enabled.setProperty("circleIndicator", True)
    tab.widget_text_shadows_enabled.setToolTip(
        "Paints widget text shadows without Qt graphics effects."
    )
    tab.widget_text_shadows_enabled.setChecked(tab._default_bool("shadows", "text_enabled", True))
    tab.widget_text_shadows_enabled.stateChanged.connect(tab._save_settings)
    row.addWidget(tab.widget_text_shadows_enabled)
    row.addStretch()
    content_layout.addLayout(row)

    row = QHBoxLayout()
    row.setContentsMargins(0, 8, 0, 8)
    row.setSpacing(12)
    tab.widget_header_shadows_enabled = QCheckBox("Enable Widget Header Drop Shadows")
    tab.widget_header_shadows_enabled.setProperty("circleIndicator", True)
    tab.widget_header_shadows_enabled.setToolTip(
        "Paints header-frame drop shadows without Qt graphics effects."
    )
    tab.widget_header_shadows_enabled.setChecked(tab._default_bool("shadows", "header_enabled", True))
    tab.widget_header_shadows_enabled.stateChanged.connect(tab._save_settings)
    row.addWidget(tab.widget_header_shadows_enabled)
    row.addStretch()
    content_layout.addLayout(row)

    row = QHBoxLayout()
    row.setContentsMargins(0, 8, 0, 8)
    row.setSpacing(12)
    tab.widget_stacking_enabled = QCheckBox("Enable Authored Widget Stacking")
    tab.widget_stacking_enabled.setProperty("circleIndicator", True)
    tab.widget_stacking_enabled.setToolTip(
        "Opt-in only. When enabled, non-Custom authored widgets may be packed to reduce overlap, "
        "but this can shift them away from their exact authored spacing."
    )
    tab.widget_stacking_enabled.setChecked(tab._default_bool("global", "stacking_enabled", False))
    tab.widget_stacking_enabled.stateChanged.connect(tab._save_settings)
    tab.widget_stacking_enabled.stateChanged.connect(tab._update_stack_status)
    row.addWidget(tab.widget_stacking_enabled)
    row.addStretch()
    content_layout.addLayout(row)

    border_row, _ = add_aligned_row(
        content_layout,
        "Card Border Width:",
        label_width=label_width,
        wrap=False,
    )
    tab.card_border_width_spin = QSpinBox()
    tab.card_border_width_spin.setRange(0, 12)
    tab.card_border_width_spin.setValue(tab._global_card_border_width)
    tab.card_border_width_spin.valueChanged.connect(tab._on_global_border_width_changed)
    border_row.addWidget(tab.card_border_width_spin)

    px_label = QLabel("px")
    px_label.setStyleSheet(FORM_ROW_LABEL_STYLE)
    px_label.setMinimumWidth(24)
    border_row.addWidget(px_label)
    border_row.addStretch()

    return group


def load_defaults_settings(tab: WidgetsTab, widgets_config: Mapping[str, object]) -> None:
    """Load Defaults-section controls from the widgets config mapping."""

    shadows_config = widgets_config.get("shadows", {}) if isinstance(widgets_config, Mapping) else {}
    if isinstance(shadows_config, Mapping):
        tab.widget_shadows_enabled.setChecked(tab._config_bool("shadows", shadows_config, "enabled", True))
        tab.widget_text_shadows_enabled.setChecked(tab._config_bool("shadows", shadows_config, "text_enabled", True))
        tab.widget_header_shadows_enabled.setChecked(tab._config_bool("shadows", shadows_config, "header_enabled", True))
    else:
        tab.widget_shadows_enabled.setChecked(True)
        tab.widget_text_shadows_enabled.setChecked(True)
        tab.widget_header_shadows_enabled.setChecked(True)

    global_cfg = widgets_config.get("global", {}) if isinstance(widgets_config, Mapping) else {}
    border_width = tab._config_int("global", global_cfg, "card_border_width_px", 3)
    border_width = max(0, min(12, border_width))
    stacking_enabled = tab._config_bool("global", global_cfg, "stacking_enabled", False)
    tab._global_card_border_width = border_width
    tab.widget_stacking_enabled.setChecked(stacking_enabled)
    if hasattr(tab, "card_border_width_spin"):
        tab.card_border_width_spin.setValue(border_width)


def save_defaults_settings(tab: WidgetsTab) -> tuple[dict[str, object], dict[str, object]]:
    """Build Defaults-section persistence payloads for shadows/global settings."""

    shadows_config = {
        "enabled": tab.widget_shadows_enabled.isChecked(),
        "text_enabled": tab.widget_text_shadows_enabled.isChecked(),
        "header_enabled": tab.widget_header_shadows_enabled.isChecked(),
    }
    border_width = getattr(tab, "_global_card_border_width", tab._widget_default("global", "card_border_width_px", 3))
    global_config = {
        "card_border_width_px": int(border_width),
        "stacking_enabled": tab.widget_stacking_enabled.isChecked(),
    }
    return shadows_config, global_config
