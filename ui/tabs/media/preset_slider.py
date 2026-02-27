"""Reusable preset slider for per-visualizer-mode presets.

Provides a compact slider spanning however many named presets a mode
exposes plus the trailing Custom slot. When Custom is selected, emits a
signal so the parent can show the Advanced settings container.

Usage:
    slider = VisualizerPresetSlider("spectrum")
    slider.preset_changed.connect(on_preset_changed)
    slider.set_advanced_container(my_settings_widget)
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QSlider
from PySide6.QtCore import Qt, Signal
from ui.tabs.shared_styles import NoWheelSlider

from core.logging.logger import get_logger
from core.settings.visualizer_presets import (
    get_custom_preset_index,
    get_preset_count,
    get_preset_names,
)

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class VisualizerPresetSlider(QWidget):
    """Compact preset slider for a single visualizer mode.

    Signals:
        preset_changed(int): emitted when the user moves the slider.
            Index 0..2 = named presets, 3 = Custom.
        advanced_toggled(bool): emitted when Advanced (Custom) is
            selected (True) or deselected (False).
    """

    preset_changed = Signal(int)
    advanced_toggled = Signal(bool)

    def __init__(self, mode: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._mode = mode
        self._advanced_container: Optional[QWidget] = None
        self._preset_names = get_preset_names(mode)
        self._preset_count = get_preset_count(mode)
        self._custom_index = get_custom_preset_index(mode)

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(2)

        # Row: label + slider column
        row = QHBoxLayout()
        row.setSpacing(6)

        lbl = QLabel("Preset:")
        lbl.setFixedWidth(48)
        row.addWidget(lbl)

        slider_column = QVBoxLayout()
        slider_column.setContentsMargins(0, 0, 0, 0)
        slider_column.setSpacing(2)

        self._slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self._slider.setMinimum(0)
        self._slider.setMaximum(self._preset_count - 1)
        self._slider.setValue(0)
        self._slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._slider.setTickInterval(1)
        self._slider.setPageStep(1)
        self._slider.setSingleStep(1)
        self._slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid rgba(68, 68, 68, 1.0);
                height: 6px;
                background: rgba(35, 35, 35, 1.0);
                margin: 2px 0;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: rgba(255, 255, 255, 0.95);
                border: 1px solid rgba(200, 200, 200, 1.0);
                width: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: rgba(255, 255, 255, 1.0);
                border: 1px solid rgba(153, 153, 153, 1.0);
            }
            QSlider::sub-page:horizontal {
                background: rgba(58, 58, 58, 1.0);
                border: 1px solid rgba(102, 102, 102, 1.0);
                height: 6px;
                border-radius: 3px;
            }
        """)
        self._slider.setToolTip(
            "Choose a visualizer preset. Custom (rightmost) shows all settings."
        )
        self._slider.valueChanged.connect(self._on_slider_changed)
        slider_column.addWidget(self._slider)

        self._value_label = QLabel(self._preset_names[0])
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._value_label.setWordWrap(True)
        slider_column.addWidget(self._value_label)

        row.addLayout(slider_column, 1)

        layout.addLayout(row)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_advanced_container(self, container: QWidget) -> None:
        """Register the widget that should show/hide based on preset."""
        self._advanced_container = container
        self._update_advanced_visibility()

    def set_preset_index(self, index: int) -> None:
        """Programmatically set the slider without triggering save."""
        idx = max(0, min(self._preset_count - 1, index))
        self._slider.blockSignals(True)
        self._slider.setValue(idx)
        self._slider.blockSignals(False)
        self._value_label.setText(self._preset_names[idx])
        self._update_advanced_visibility()

    def preset_index(self) -> int:
        return self._slider.value()

    @property
    def mode(self) -> str:
        return self._mode

    def custom_index(self) -> int:
        return self._custom_index

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_slider_changed(self, value: int) -> None:
        idx = max(0, min(self._preset_count - 1, value))
        self._value_label.setText(self._preset_names[idx])
        self._update_advanced_visibility()
        # Guard: tell the parent tab this change came from the preset slider
        # so _auto_switch_preset_to_custom doesn't re-trigger.
        tab = self._find_tab()
        if tab is not None:
            tab._preset_slider_changing = True
        self.preset_changed.emit(idx)
        self.advanced_toggled.emit(idx == self._custom_index)
        if tab is not None:
            tab._preset_slider_changing = False

    def _find_tab(self):
        """Walk up the parent chain to find the WidgetsTab instance."""
        w = self.parent()
        while w is not None:
            if hasattr(w, '_preset_slider_changing'):
                return w
            # WidgetsTab is the top-level tab widget with _save_settings
            if hasattr(w, '_save_settings') and hasattr(w, 'spotify_vis_type_combo'):
                return w
            w = w.parent()
        return None

    def _update_advanced_visibility(self) -> None:
        if self._advanced_container is not None:
            is_custom = self._slider.value() == self._custom_index
            self._advanced_container.setVisible(is_custom)
