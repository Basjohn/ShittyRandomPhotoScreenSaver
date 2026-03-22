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

import json
import re
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QSlider,
    QPushButton,
    QSizePolicy,
    QDialog,
    QFileDialog,
)
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QPainter, QPen, QPalette
from ui.tabs.shared_styles import (
    NoWheelSlider,
    add_section_label,
    apply_section_heading_style,
    FORM_LABEL_HEIGHT,
)

from core.logging.logger import get_logger
from core.settings.visualizer_presets import (
    get_custom_preset_index,
    get_preset_count,
    get_preset_names,
    get_preset_file_path,
    get_visualizer_presets_dir,
    reload_presets,
)
from ui.styled_popup import StyledPopup

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class _PresetNotchBar(QWidget):
    """Lightweight notch renderer that mirrors the preset slider span."""

    _H_MARGIN = 14

    def __init__(self, notch_count: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._notch_count = max(0, notch_count)
        self.setFixedHeight(10)
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setSizePolicy(policy)

    def set_notch_count(self, count: int) -> None:
        if count != self._notch_count:
            self._notch_count = max(0, count)
            self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        if self._notch_count <= 1:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        palette = self.palette()
        color = palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text)
        pen = QPen(color)
        pen.setWidth(2)
        painter.setPen(pen)
        total_width = max(1, self.width() - 1)
        height = self.height()
        span = self._notch_count - 1
        usable = max(0, total_width - 2 * self._H_MARGIN)
        for i in range(self._notch_count):
            if span <= 0:
                x = self._H_MARGIN
            else:
                x = self._H_MARGIN + round((i / span) * usable)
            painter.drawLine(x, 0, x, height)
        painter.end()


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
        self._technical_container: Optional[QWidget] = None
        self._preset_names = get_preset_names(mode)
        self._preset_count = get_preset_count(mode)
        self._custom_index = get_custom_preset_index(mode)

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(2)

        # Single row: "Preset:" label | preset name | slider | Edit button
        row = QHBoxLayout()
        row.setSpacing(6)
        row.setContentsMargins(0, 0, 0, 0)
        row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        add_section_label(row, "Preset:", 48)

        self._value_label = QLabel(self._preset_names[0])
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._value_label.setMinimumWidth(140)
        apply_section_heading_style(self._value_label)
        self._value_label.setMinimumHeight(FORM_LABEL_HEIGHT)
        row.addWidget(self._value_label)

        slider_column = QVBoxLayout()
        slider_column.setSpacing(2)
        slider_column.setContentsMargins(0, 3, 0, 0)

        self._slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self._slider.setObjectName("presetModeSlider")
        self._slider.setMinimum(0)
        self._slider.setMaximum(self._preset_count - 1)
        self._slider.setValue(0)
        self._slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._slider.setTickInterval(1)
        self._slider.setPageStep(1)
        self._slider.setSingleStep(1)
        self._slider.setMinimumHeight(FORM_LABEL_HEIGHT)
        self._slider.setToolTip(
            "Choose a visualizer preset. Custom (rightmost) shows all settings."
        )
        self._slider.valueChanged.connect(self._on_slider_changed)
        slider_column.addWidget(self._slider)

        self._notch_bar = _PresetNotchBar(self._preset_count)
        slider_column.addWidget(self._notch_bar)
        row.addLayout(slider_column, 1)

        self._edit_btn = QPushButton("Edit Preset")
        self._edit_btn.setToolTip("Open this preset's JSON file in your default editor.")
        self._edit_btn.setFixedHeight(22)
        self._edit_btn.setFixedWidth(90)
        self._edit_btn.setStyleSheet(
            "QPushButton { font-size: 9pt; padding: 2px 8px; }"
        )
        self._edit_btn.clicked.connect(self._open_preset_json)
        self._edit_btn.setVisible(True)
        row.addWidget(self._edit_btn)

        self._custom_action_btn = QPushButton("Move To Custom")
        self._custom_action_btn.setFixedHeight(22)
        self._custom_action_btn.setFixedWidth(130)
        self._custom_action_btn.setStyleSheet(
            "QPushButton { font-size: 9pt; padding: 2px 8px; }"
        )
        self._custom_action_btn.clicked.connect(self._on_custom_action_clicked)
        row.addWidget(self._custom_action_btn)

        layout.addLayout(row)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_advanced_container(self, container: QWidget) -> None:
        """Register the widget that should show/hide based on preset."""
        self._advanced_container = container
        self._update_advanced_visibility()

    def set_technical_container(self, container: QWidget) -> None:
        """Register the Technical group widget for auto-hide on non-Custom presets."""
        self._technical_container = container
        container.setVisible(self._slider.value() == self._custom_index)

    def set_preset_index(self, index: int) -> None:
        """Programmatically set the slider without triggering save."""
        idx = max(0, min(self._preset_count - 1, index))
        self._slider.blockSignals(True)
        self._slider.setValue(idx)
        self._slider.blockSignals(False)
        self._value_label.setText(self._preset_names[idx])
        self._update_advanced_visibility()
        self.advanced_toggled.emit(idx == self._custom_index)

    def preset_index(self) -> int:
        return self._slider.value()

    @property
    def mode(self) -> str:
        return self._mode

    def custom_index(self) -> int:
        return self._custom_index

    def cycle_next(self) -> None:
        """Advance to the next preset slot (wraps at Custom)."""
        self._cycle_by(1)

    def cycle_previous(self) -> None:
        """Move to the previous preset slot (wraps to last slot)."""
        self._cycle_by(-1)

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

    def _cycle_by(self, delta: int) -> None:
        if self._preset_count <= 0 or not delta:
            return
        current = self._slider.value()
        next_idx = (current + delta) % self._preset_count
        self._slider.setValue(next_idx)

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
        if self._technical_container is not None:
            self._technical_container.setVisible(is_custom)
        # Keep Edit button footprint stable to avoid slider flicker. Disable
        # it when Custom is selected or when no backing file exists.
        path = get_preset_file_path(self._mode, idx)
        has_file = path is not None
        self._edit_btn.setEnabled((not is_custom) and has_file)
        if not has_file:
            self._edit_btn.setToolTip("Preset JSON not found on disk.")
        elif is_custom:
            self._edit_btn.setToolTip("Switch to a curated preset to edit its JSON.")
        else:
            self._edit_btn.setToolTip("Open this preset's JSON file in your default editor.")
        # Move To Custom: only enabled when on a non-custom preset
        if self._custom_action_btn is not None:
            if is_custom:
                self._custom_action_btn.setText("Save Preset As…")
                self._custom_action_btn.setToolTip(
                    "Save the current Custom settings as a curated preset JSON file."
                )
            else:
                self._custom_action_btn.setText("Move To Custom")
                self._custom_action_btn.setToolTip(
                    "Copy this preset's current settings into Custom mode and switch to it."
                )
            self._custom_action_btn.setEnabled(True)

    def _on_custom_action_clicked(self) -> None:
        if self._slider.value() == self._custom_index:
            self._save_custom_preset_as()
        else:
            self._move_to_custom()

    def _move_to_custom(self) -> None:
        """Switch to Custom preset, keeping the current UI values as custom settings.

        The UI widgets already hold the current preset's values (loaded when the
        preset was selected). Switching the slider to Custom and triggering a save
        will persist those values as the user's custom configuration.
        """
        idx = self._slider.value()
        if idx == self._custom_index:
            return

        logger.debug(
            "[VIS_PRESETS] Move To Custom: %s preset %d → Custom (%d)",
            self._mode, idx, self._custom_index,
        )

        setattr(self, "_pending_move_to_custom", True)

        # Switch slider to Custom — this triggers _on_slider_changed which
        # emits preset_changed and advanced_toggled, shows Advanced container,
        # and saves settings. The UI widgets retain the preset values so the
        # save captures them as custom.
        self._slider.setValue(self._custom_index)

    def _save_custom_preset_as(self) -> None:
        tab = self._find_tab()
        if tab is None or not hasattr(tab, "build_visualizer_preset_payload"):
            return

        payload = tab.build_visualizer_preset_payload(self._mode)
        if not payload:
            StyledPopup(
                tab,
                "Unable To Save",
                "No Custom settings detected for this mode.",
                icon_type="error",
                buttons=[("OK", "ok")],
            ).exec()
            return

        presets_dir = get_visualizer_presets_dir(self._mode)
        try:
            presets_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            logger.debug("[VIS_PRESETS] Failed to create presets dir %s", presets_dir, exc_info=True)

        default_path = self._default_save_path(presets_dir)
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Visualizer Preset",
            str(default_path),
            "Visualizer Preset (*.json)",
        )
        if not file_path:
            return

        path = Path(file_path)
        if path.suffix.lower() != ".json":
            path = path.with_suffix(".json")

        self._apply_filename_metadata(path, payload)
        payload.setdefault("description", "Saved from Custom preset in Settings.")

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
        except Exception:
            logger.debug("[VIS_PRESETS] Failed to save preset %s", path, exc_info=True)
            StyledPopup(
                tab,
                "Save Failed",
                f"Could not write {path}.",
                icon_type="error",
                buttons=[("OK", "ok")],
            ).exec()
            return

        StyledPopup(
            tab,
            "Preset Saved",
            f"Curated preset saved to\n{path}",
            icon_type="success",
            buttons=[("OK", "ok")],
        ).exec()
        self._reload_and_reapply_current_preset(self._slider.value(), force_custom=True)

    def _default_save_path(self, presets_dir: Path) -> Path:
        base_stem = f"preset_{self._custom_index}_custom"
        candidate = presets_dir / f"{base_stem}.json"
        counter = 1
        while candidate.exists():
            candidate = presets_dir / f"{base_stem}_{counter}.json"
            counter += 1
        return candidate

    _FILENAME_RE = re.compile(r"preset[_-]*(\d+)(?:[_-]*(.+))?", re.IGNORECASE)

    def _apply_filename_metadata(self, path: Path, payload: dict) -> None:
        match = self._FILENAME_RE.match(path.stem)
        if match:
            try:
                ordinal = int(match.group(1))
                payload["preset_index"] = max(0, ordinal - 1)
            except (TypeError, ValueError):
                pass
            suffix = match.group(2)
            if suffix:
                friendly_suffix = re.sub(r"[_-]+", " ", suffix).strip()
            else:
                friendly_suffix = ""
            base = f"Preset {match.group(1)}"
            if friendly_suffix:
                payload["name"] = f"{base} ({friendly_suffix.title()})"
            else:
                payload["name"] = base
        if not payload.get("name"):
            payload["name"] = path.stem.replace("_", " ").title()

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
            return

        popup = StyledPopup(
            self._find_tab(),
            "Edit Preset",
            "Do your weird shit and click OK when done.",
            icon_type="info",
            buttons=[("OK", "ok")],
        )
        if popup.exec() == QDialog.DialogCode.Accepted:
            self._reload_and_reapply_current_preset(idx)

    def _reload_and_reapply_current_preset(self, desired_index: int, *, force_custom: bool = False) -> None:
        """Reload preset definitions from disk and reapply the current slot."""

        try:
            reload_presets(self._mode)
            self._preset_names = get_preset_names(self._mode)
            self._preset_count = get_preset_count(self._mode)
            self._custom_index = get_custom_preset_index(self._mode)
        except Exception:
            logger.debug(
                "[VIS_PRESETS] Failed to reload presets for %s", self._mode, exc_info=True
            )
            return

        self._slider.blockSignals(True)
        self._slider.setMaximum(max(0, self._preset_count - 1))
        if force_custom:
            target_index = self._custom_index
        else:
            target_index = max(0, min(self._preset_count - 1, desired_index))
        self._slider.setValue(target_index)
        self._slider.blockSignals(False)
        self._value_label.setText(self._preset_names[target_index])
        self._notch_bar.set_notch_count(self._preset_count)
        self._update_advanced_visibility()

        tab = self._find_tab()
        if tab is not None and hasattr(tab, "_on_visualizer_preset_changed"):
            previous_flag = getattr(tab, "_preset_slider_changing", False)
            try:
                tab._preset_slider_changing = True
                tab._on_visualizer_preset_changed(self._mode, target_index)
            finally:
                tab._preset_slider_changing = previous_flag
