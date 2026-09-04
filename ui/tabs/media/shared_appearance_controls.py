"""Shared Visualizer appearance controls (V6a).

Bar Fill colour, Bar Border colour and Border Opacity are genuinely shared
across every Visualizer mode: their state is per-active-mode and their save/load
is already owned by the shared visualizer settings path, not by any mode binding.
Historically their *widgets* were created inside the Spectrum builder, which
forced Spectrum to stay eagerly constructed. This module owns the widgets so they
exist independently of any mode body (including an unbuilt Spectrum).

The row widgets are created once, parented to a hidden holder. A mode builder
that shows them (Spectrum) places the exact same row widgets into its own layout
via :func:`place_shared_visualizer_appearance_controls` — it must not recreate or
duplicate them. This keeps their visible presentation, order and pixels unchanged
while making ownership shared.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel, QSlider, QVBoxLayout, QWidget

from ui.styled_popup import ColorSwatchButton
from ui.tabs.media.builder_scaffold import (
    add_builder_swatch_row,
    bind_color_button,
    bind_setting_signal,
)
from ui.tabs.shared_styles import NoWheelSlider, add_aligned_row_widget

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab

_LABEL_WIDTH = 150


def build_shared_visualizer_appearance_controls(tab: "WidgetsTab") -> None:
    """Create the shared Bar Fill/Border colour + Border Opacity rows eagerly.

    Sets on ``tab``: the row widgets ``_shared_vis_fill_row`` /
    ``_shared_vis_border_row`` / ``_shared_vis_border_opacity_row`` (parented to a
    hidden holder), plus the control attributes ``vis_fill_color_btn`` /
    ``vis_border_color_btn`` / ``vis_border_opacity`` / ``vis_border_opacity_label``
    and the shared colour state ``_spotify_vis_fill_color`` /
    ``_spotify_vis_border_color`` (matching the load fallbacks; load overrides).
    """
    if not hasattr(tab, "_spotify_vis_fill_color"):
        tab._spotify_vis_fill_color = QColor(0, 255, 128, 230)
    if not hasattr(tab, "_spotify_vis_border_color"):
        tab._spotify_vis_border_color = QColor(255, 255, 255, 230)

    holder = QWidget()
    holder_layout = QVBoxLayout(holder)
    holder_layout.setContentsMargins(0, 0, 0, 0)
    # Keeps the rows alive while no mode body hosts them; never shown itself.
    tab._shared_vis_appearance_holder = holder

    fill_row, fill_content, _ = add_builder_swatch_row(
        holder_layout, "Bar Fill Color:", label_width=_LABEL_WIDTH
    )
    tab.vis_fill_color_btn = ColorSwatchButton(title="Choose Beat Bar Fill Color")
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
        holder_layout, "Bar Border Color:", label_width=_LABEL_WIDTH
    )
    tab.vis_border_color_btn = ColorSwatchButton(title="Choose Beat Bar Border Color")
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
        holder_layout, "Bar Border Opacity:", label_width=_LABEL_WIDTH
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


def place_shared_appearance_fill_border(tab: "WidgetsTab", target_layout: QVBoxLayout) -> None:
    """Place the shared Fill + Border colour rows into *target_layout* in order."""
    target_layout.addWidget(tab._shared_vis_fill_row)
    target_layout.addWidget(tab._shared_vis_border_row)


def place_shared_appearance_border_opacity(tab: "WidgetsTab", target_layout: QVBoxLayout) -> None:
    """Place the shared Border Opacity row into *target_layout*."""
    target_layout.addWidget(tab._shared_vis_border_opacity_row)
