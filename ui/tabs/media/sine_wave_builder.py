"""Lazy Settings body for the Sine Waves visualizer, built from its spec
(``core/settings/visualizer_mode_settings.py``). Only the extra lines' section is hand-built here:
each line's colour, glow colour and travel sit side by side, and the rows appear with the line count."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget

from ui.styled_popup import ColorSwatchButton
from ui.tabs.media.builder_scaffold import add_builder_swatch_row, bind_color_button, bind_setting_signal
from ui.tabs.media.spec_mode_builder import build_spec_mode_ui
from ui.tabs.shared_styles import NoWheelSlider, add_aligned_row_widget
from ui.widgets import StyledComboBox

LINES = range(2, 7)
_LABEL_WIDTH = 150


def build_sine_wave_ui(tab, parent_layout) -> None:
    """Build Sine Waves' body and its consumed technical profile."""

    build_spec_mode_ui(tab, parent_layout, "sine_wave")


def update_line_visibility(tab) -> None:
    """Show the extra lines' controls only in multi-line mode, each line's only within the count."""
    multi = getattr(tab, "sine_multi_line", None)
    enabled = bool(multi is not None and multi.isChecked())
    container = getattr(tab, "_sine_multi_container", None)
    if container is not None:
        container.setVisible(enabled)
    count_slider = getattr(tab, "sine_line_count_slider", None)
    count = count_slider.value() if count_slider is not None else 0
    for line in LINES:
        shown = enabled and count >= line
        for name in (f"_sine_l{line}_row_widget", f"_sine_line{line}_ghost_row_widget", f"_sine_l{line}_shift_row_widget"):
            widget = getattr(tab, name, None)
            if widget is not None:
                widget.setVisible(shown)


def shift_text(position: int) -> str:
    return f"{position / 100.0:.2f} cycles"


def _column(content: QHBoxLayout, title: str) -> QVBoxLayout:
    column = QVBoxLayout()
    label = QLabel(title)
    label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    column.addWidget(label)
    content.addLayout(column)
    return column


def _row(layout, label: str) -> tuple[QWidget, QHBoxLayout]:
    widget, content, _ = add_aligned_row_widget(layout, label, label_width=_LABEL_WIDTH)
    return widget, content


def build_lines_section(tab, layout) -> None:
    """Multi-line mode, the line count, and lines 2-6: colour, glow colour, travel, ghost and shift."""
    default_count = int(tab._widget_default("spotify_visualizer", "sine_line_count"))
    tab.sine_multi_line = QCheckBox("Multi-Line Mode")
    tab.sine_multi_line.setProperty("circleIndicator", True)
    tab.sine_multi_line.setChecked(default_count > 1)
    tab.sine_multi_line.setToolTip("Enable additional sine waves with different frequency distributions.")
    tab.sine_multi_line.toggled.connect(lambda _on: update_line_visibility(tab))
    bind_setting_signal(tab, tab.sine_multi_line.toggled, auto_switch=True)
    layout.addWidget(tab.sine_multi_line)

    tab._sine_multi_container = QWidget()
    lines_layout = QVBoxLayout(tab._sine_multi_container)
    lines_layout.setContentsMargins(0, 0, 0, 0)

    _widget, count_row = _row(lines_layout, "Line Count:")
    tab.sine_line_count_slider = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_line_count_slider.setRange(2, 6)
    tab.sine_line_count_slider.setValue(max(2, min(6, default_count)))
    tab.sine_line_count_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_line_count_slider.setTickInterval(1)
    tab.sine_line_count_label = QLabel(str(tab.sine_line_count_slider.value()))
    tab.sine_line_count_slider.valueChanged.connect(lambda v: tab.sine_line_count_label.setText(str(v)))
    tab.sine_line_count_slider.valueChanged.connect(lambda _v: update_line_visibility(tab))
    bind_setting_signal(tab, tab.sine_line_count_slider.valueChanged, auto_switch=True)
    count_row.addWidget(tab.sine_line_count_slider)
    count_row.addWidget(tab.sine_line_count_label)

    for line in LINES:
        row_widget, content, label = add_builder_swatch_row(lines_layout, f"Line {line}:", label_width=_LABEL_WIDTH)
        setattr(tab, f"_sine_l{line}_row_widget", row_widget)
        setattr(tab, f"_sine_line{line}_label", label)
        for kind, title, tip in (("color", "Line Color", "colour"), ("glow_color", "Glow Color", "glow colour")):
            key = f"sine_line{line}_{kind}"
            colour = QColor(*tab._widget_default("spotify_visualizer", key))
            setattr(tab, f"_{key}", colour)
            button = ColorSwatchButton(title=f"Line {line} {title}")
            button.setToolTip(f"Sine wave line {line} {tip}")
            bind_color_button(tab, button, f"_{key}", auto_switch=True, initial_color=colour)
            setattr(tab, f"sine_line{line}_{'glow' if kind == 'glow_color' else 'color'}_btn", button)
            _column(content, title).addWidget(button)
        travel = StyledComboBox(size_variant="mini")
        travel.addItems(["None", "Left", "Right"])
        travel.setCurrentIndex(max(0, min(2, int(tab._widget_default("spotify_visualizer", f"sine_travel_line{line}")))))
        bind_setting_signal(tab, travel.currentIndexChanged, auto_switch=True)
        setattr(tab, f"sine_travel_line{line}", travel)
        align = QHBoxLayout()
        align.addStretch()
        align.addWidget(travel)
        _column(content, "Travel").addLayout(align)
        content.addStretch()

        ghost_row, ghost_content = _row(lines_layout, f"Line {line} Ghost:")
        setattr(tab, f"_sine_line{line}_ghost_row_widget", ghost_row)
        ghost = QCheckBox("Draw Ghost")
        ghost.setProperty("circleIndicator", True)
        ghost.setChecked(bool(tab._widget_default("spotify_visualizer", f"sine_ghost_line{line}_enabled")))
        ghost.setToolTip(f"Allow the ghost trail to render for sine wave line {line}.")
        bind_setting_signal(tab, ghost.toggled, auto_switch=True)
        setattr(tab, f"sine_ghost_line{line}_enabled", ghost)
        ghost_content.addWidget(ghost)
        ghost_content.addStretch()

        shift_row, shift_content = _row(lines_layout, f"Line {line} Horizontal Shift:")
        setattr(tab, f"_sine_l{line}_shift_row_widget", shift_row)
        shift = NoWheelSlider(Qt.Orientation.Horizontal)
        shift.setRange(-100, 100)
        shift.setValue(max(-100, min(100, round(float(tab._widget_default("spotify_visualizer", f"sine_line{line}_shift")) * 100))))
        shift.setTickPosition(QSlider.TickPosition.TicksBelow)
        shift.setTickInterval(10)
        shift.setToolTip(f"Phase offset for line {line} relative to card width (negative = lead, positive = lag).")
        shift_label = QLabel(shift_text(shift.value()))
        shift.valueChanged.connect(lambda v, label=shift_label: label.setText(shift_text(v)))
        bind_setting_signal(tab, shift.valueChanged, auto_switch=True)
        setattr(tab, f"sine_line{line}_shift", shift)
        setattr(tab, f"sine_line{line}_shift_label", shift_label)
        shift_content.addWidget(shift)
        shift_content.addWidget(shift_label)

    layout.addWidget(tab._sine_multi_container)
    update_line_visibility(tab)
