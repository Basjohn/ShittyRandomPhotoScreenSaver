"""Shared Visualizer appearance controls (V6a).

Bar Fill colour, Bar Border colour and Border Opacity are owned by the shared
visualizer save/load path even though the authored Settings presentation has
historically exposed them with Spectrum. Their stored keys remain mode-qualified.
Historically their *widgets* were created inside the Spectrum builder, which
forced Spectrum to stay eagerly constructed. V6a extracted their logical owner;
V7 keeps them permanently under the stable top-level Visualizers mode page. They
are never descendants of a retireable mode body.

The row widgets are created exactly once. Mode builders must not recreate or
reparent them. V7 shows this stable group only with Spectrum, preserving the old
user-facing scope while keeping the lifecycle ownership invisible.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel, QSlider, QVBoxLayout

from ui.styled_popup import ColorSwatchButton
from ui.tabs.media.builder_scaffold import (
    add_builder_swatch_row,
    bind_color_button,
    bind_setting_signal,
)
from ui.tabs.shared_styles import NoWheelSlider, add_aligned_row_widget

if TYPE_CHECKING:
    from ui.tabs.visualizer_settings_context import VisualizerSettingsContextMixin

_LABEL_WIDTH = 150


def build_shared_visualizer_appearance_controls(
    tab: "VisualizerSettingsContextMixin", target_layout: QVBoxLayout
) -> None:
    """Create the shared Bar Fill/Border colour + Border Opacity rows eagerly.

    Sets on ``tab``: the row widgets ``_shared_vis_fill_row`` /
    ``_shared_vis_border_row`` / ``_shared_vis_border_opacity_row``, plus the
    control attributes ``vis_fill_color_btn`` /
    ``vis_border_color_btn`` / ``vis_border_opacity`` / ``vis_border_opacity_label``
    and the shared colour state ``_spotify_vis_fill_color`` /
    ``_spotify_vis_border_color`` (matching the load fallbacks; load overrides).
    """
    if not hasattr(tab, "_spotify_vis_fill_color"):
        tab._spotify_vis_fill_color = QColor(0, 255, 128, 230)
    if not hasattr(tab, "_spotify_vis_border_color"):
        tab._spotify_vis_border_color = QColor(255, 255, 255, 230)

    fill_row, fill_content, _ = add_builder_swatch_row(
        target_layout, "Bar Fill Color:", label_width=_LABEL_WIDTH
    )
    tab.vis_fill_color_btn = ColorSwatchButton(title="Choose Spectrum Bar Fill Color")
    bind_color_button(
        tab,
        tab.vis_fill_color_btn,
        "_spotify_vis_fill_color",
        initial_color=tab._spotify_vis_fill_color,
    )
    fill_content.addWidget(tab.vis_fill_color_btn)
    fill_content.addStretch()
    tab._shared_vis_fill_row = fill_row

    border_row, border_content, _ = add_builder_swatch_row(
        target_layout, "Bar Border Color:", label_width=_LABEL_WIDTH
    )
    tab.vis_border_color_btn = ColorSwatchButton(title="Choose Spectrum Bar Border Color")
    bind_color_button(
        tab,
        tab.vis_border_color_btn,
        "_spotify_vis_border_color",
        initial_color=tab._spotify_vis_border_color,
    )
    border_content.addWidget(tab.vis_border_color_btn)
    border_content.addStretch()
    tab._shared_vis_border_row = border_row

    opacity_row, opacity_content, _ = add_aligned_row_widget(
        target_layout, "Bar Border Opacity:", label_width=_LABEL_WIDTH
    )
    tab.vis_border_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.vis_border_opacity.setMinimum(0)
    tab.vis_border_opacity.setMaximum(100)
    _pct = int(
        tab._default_float("spotify_visualizer", "spectrum_bar_border_opacity", 0.85) * 100
    )
    tab.vis_border_opacity.setValue(_pct)
    tab.vis_border_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.vis_border_opacity.setTickInterval(5)
    bind_setting_signal(
        tab,
        tab.vis_border_opacity.valueChanged,
        updater=lambda v: tab.vis_border_opacity_label.setText(f"{v}%"),
    )
    opacity_content.addWidget(tab.vis_border_opacity)
    tab.vis_border_opacity_label = QLabel(f"{_pct}%")
    opacity_content.addWidget(tab.vis_border_opacity_label)
    tab._shared_vis_border_opacity_row = opacity_row
