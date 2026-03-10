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

from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QSlider, QPushButton
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from ui.tabs.shared_styles import NoWheelSlider

from core.logging.logger import get_logger
from core.settings.visualizer_presets import (
    get_custom_preset_index,
    get_preset_count,
    get_preset_names,
    get_preset_file_path,
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
        self._slider.setToolTip(
            "Choose a visualizer preset. Custom (rightmost) shows all settings."
        )
        self._slider.valueChanged.connect(self._on_slider_changed)
        slider_column.addWidget(self._slider)

        # Label row: preset name + EDIT PRESET button
        label_row = QHBoxLayout()
        label_row.setContentsMargins(0, 0, 0, 0)
        label_row.setSpacing(6)

        self._value_label = QLabel(self._preset_names[0])
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._value_label.setWordWrap(True)
        label_row.addWidget(self._value_label, 1)

        self._edit_btn = QPushButton("Edit Preset")
        self._edit_btn.setToolTip("Open this preset's JSON file in your default editor.")
        self._edit_btn.setFixedHeight(22)
        self._edit_btn.setStyleSheet(
            "QPushButton { font-size: 9pt; padding: 2px 8px; }"
        )
        self._edit_btn.clicked.connect(self._open_preset_json)
        self._edit_btn.setVisible(False)
        label_row.addWidget(self._edit_btn)

        slider_column.addLayout(label_row)

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
            if hasattr(w, '_save_settings') and hasattr(w, 'vis_mode_combo'):
                return w
            w = w.parent()
        return None

    def _update_advanced_visibility(self) -> None:
        idx = self._slider.value()
        is_custom = idx == self._custom_index
        if self._advanced_container is not None:
            self._advanced_container.setVisible(is_custom)
        # Show EDIT PRESET only for non-Custom presets that have a JSON file
        if is_custom:
            self._edit_btn.setVisible(False)
        else:
            path = get_preset_file_path(self._mode, idx)
            self._edit_btn.setVisible(path is not None)

    def _open_preset_json(self) -> None:
        """Open the current preset's JSON file in the OS default editor."""
        idx = self._slider.value()
        path = get_preset_file_path(self._mode, idx)
        if path is None or not path.is_file():
            logger.warning("[VIS_PRESETS] No JSON file for %s preset %d", self._mode, idx)
            return
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        except Exception:
            logger.debug("[VIS_PRESETS] Failed to open preset file", exc_info=True)
