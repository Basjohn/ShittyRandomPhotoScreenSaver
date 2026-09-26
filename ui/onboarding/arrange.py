"""Lightweight QWidget projection of the canonical CUSTOM layout draft."""
from __future__ import annotations

import weakref

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QListWidget, QListWidgetItem, QSizePolicy, QVBoxLayout, QWidget
from PySide6.QtGui import QGuiApplication

from rendering.custom_layout_contract import get_screen_signature, get_screen_signature_aliases
from rendering.quick.custom_layout_size import CUSTOM_LAYOUT_MIN_RESIZE_SCALE
from core.settings.default_contract import require_canonical_default
from core.settings.layout_slots import get_layout_slot_payload
from ui.onboarding.arrange_model import ArrangeDisplay, ArrangeModel
from ui.onboarding.common import Page, action, checkbox, text_label
from ui.styled_popup import StyledPopup
from ui.settings_theme_runtime import get_active_settings_theme, subscribe_settings_theme
from ui.tabs.shared_styles import NoWheelSlider
from ui.widgets import StyledComboBox


class _ArrangeCanvas(QWidget):
    """A scaled, event-owned projection; it never represents persisted coordinates."""

    changed = Signal()
    selectionChanged = Signal()
    dragFinished = Signal()

    _MIN_HEIGHT = 260
    _MAX_HEIGHT = 560
    _PAD = 10
    _LABEL_BAND = 24  # display names sit below their rectangles, never under widgets

    def __init__(self, model: ArrangeModel, parent=None) -> None:
        super().__init__(parent)
        self.model = model
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.setMinimumHeight(self._MIN_HEIGHT)
        self._selected = None
        self._drag_origin: QPoint | None = None
        self._original_rect: QRect | None = None
        self.setMouseTracking(True)

    def _bounds(self) -> QRect:
        rectangles = [display.geometry for display in self.model.displays]
        if not rectangles:
            return QRect(0, 0, 1, 1)
        result = QRect(rectangles[0])
        for rect in rectangles[1:]: result = result.united(rect)
        return result

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        """Follow the combined display aspect so the canvas uses its width."""
        bounds = self._bounds()
        height = round((width - 2 * self._PAD) * bounds.height() / max(1, bounds.width())) + 2 * self._PAD + self._LABEL_BAND
        return max(self._MIN_HEIGHT, min(self._MAX_HEIGHT, height))

    def sizeHint(self) -> QSize:
        return QSize(640, self.heightForWidth(640))

    def _scale(self) -> float:
        bounds = self._bounds()
        usable_w = self.width() - 2 * self._PAD
        usable_h = self.height() - 2 * self._PAD - self._LABEL_BAND
        return min(max(0.05, usable_w / max(1, bounds.width())), max(0.05, usable_h / max(1, bounds.height())))

    def _origin(self) -> QPoint:
        """Centre the scaled displays inside the canvas."""
        bounds, scale = self._bounds(), self._scale()
        return QPoint(round((self.width() - bounds.width() * scale) / 2),
                      round((self.height() - self._LABEL_BAND - bounds.height() * scale) / 2))

    def _project(self, rect: QRect) -> QRect:
        bounds, scale, origin = self._bounds(), self._scale(), self._origin()
        return QRect(origin.x() + round((rect.x() - bounds.x()) * scale), origin.y() + round((rect.y() - bounds.y()) * scale), max(2, round(rect.width() * scale)), max(2, round(rect.height() * scale)))

    def _unproject_delta(self, delta: QPoint) -> QPoint:
        scale = self._scale()
        return QPoint(round(delta.x() / scale), round(delta.y() / scale))

    def _unproject_point(self, point: QPoint) -> QPoint:
        bounds, scale, origin = self._bounds(), self._scale(), self._origin()
        return QPoint(bounds.x() + round((point.x() - origin.x()) / scale), bounds.y() + round((point.y() - origin.y()) / scale))

    def paintEvent(self, _event) -> None:
        theme = get_active_settings_theme()
        color = lambda token: QColor(*theme.color(token).as_tuple())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color("panel.group.surface"))
        painter.drawRoundedRect(QRectF(self.rect()), 8.0, 8.0)
        small = self.font(); small.setPointSizeF(max(7.0, small.pointSizeF() - 1.0))
        for display in self.model.displays:
            rect = QRectF(self._project(display.geometry)).adjusted(1, 1, -1, -1)
            painter.setPen(QPen(color("panel.border"), 2.0))
            painter.setBrush(color("panel.subsection.surface"))
            painter.drawRoundedRect(rect, 4.0, 4.0)
        items = list(self.model.session.active_items())
        items.sort(key=lambda item: item is self._selected)  # selected paints last
        for item in items:
            rect = QRectF(self._project(item.current_global_rect))
            selected = item is self._selected
            fill = color("control.button.surface"); fill.setAlpha(235 if selected else 205)
            painter.setPen(QPen(color("control.button.pressed_border") if selected else color("control.button.border"), 2.5 if selected else 1.75))
            painter.setBrush(fill)
            painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 3.0, 3.0)
            if rect.width() < 28 or rect.height() < 14:
                continue
            painter.setFont(small)
            painter.setPen(color("control.button.text"))
            metrics = painter.fontMetrics()
            name = metrics.elidedText(self.model.item_label(item.source_key), Qt.TextElideMode.ElideRight, int(rect.width() - 8))
            painter.drawText(rect.adjusted(4, 2, -4, -2), Qt.AlignmentFlag.AlignCenter, name)
        # Display names in the reserved band under each display.
        painter.setFont(small)
        painter.setPen(color("panel.group.text"))
        for display in self.model.displays:
            rect = QRectF(self._project(display.geometry))
            label = f"Display {display.monitor_route}  ·  {display.geometry.width()}×{display.geometry.height()}"
            painter.drawText(QRectF(rect.left(), rect.bottom() + 4, rect.width(), self._LABEL_BAND - 6),
                             Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, label)

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton: return
        self._selected = next((item for item in reversed(self.model.session.active_items()) if self._project(item.current_global_rect).contains(event.position().toPoint())), None)
        if self._selected is not None:
            self._drag_origin = event.position().toPoint(); self._original_rect = QRect(self._selected.current_global_rect)
            self.model.session.select_item(self._selected)
        self.selectionChanged.emit()
        self.changed.emit(); self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._selected is None or self._drag_origin is None or self._original_rect is None: return
        delta = self._unproject_delta(event.position().toPoint() - self._drag_origin)
        rect = QRect(self._original_rect); rect.translate(delta)
        self.model.move(self._selected.source_key, rect, cursor_global=self._unproject_point(event.position().toPoint())); self.changed.emit(); self.update()

    def mouseReleaseEvent(self, _event) -> None:
        self._drag_origin = None; self._original_rect = None
        self.dragFinished.emit()


class ArrangePage(Page):
    """Shared Guided Setup/Quick Start draft editor; writes only on Apply/leave."""

    pendingChanged = Signal(bool)

    def __init__(self, settings, parent=None, *, show_slots: bool = True) -> None:
        super().__init__(settings, parent)
        self.model: ArrangeModel | None = None
        self.body.addWidget(text_label("Arrange widgets freely. Changes stay in this draft until you apply them.", heading=True))
        self.canvas_holder = QVBoxLayout(); self.body.addLayout(self.canvas_holder)
        chooser = QHBoxLayout()
        self.item_list = QListWidget()
        self.item_list.setMaximumHeight(118)
        self.item_list.setToolTip("Choose a widget and display when boxes overlap or are too small to select on the canvas.")
        self.item_list.currentItemChanged.connect(self._select_list_item)
        chooser.addWidget(self.item_list, 1)
        selection_panel = QVBoxLayout()
        self.selection_hint = text_label("Select a widget to arrange it.")
        selection_panel.addWidget(self.selection_hint)
        self.free_check = checkbox("Free placement")
        self.free_check.setToolTip("Derive a content-sized CUSTOM placement at this widget's current anchored position.")
        self.free_check.toggled.connect(self._toggle_free)
        selection_panel.addWidget(self.free_check)
        scale_row = QHBoxLayout()
        self.scale_label = text_label("Uniform scale: 100%")
        self.scale_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.scale_slider.setRange(round(100 * CUSTOM_LAYOUT_MIN_RESIZE_SCALE), 200)
        self.scale_slider.setSingleStep(5)
        self.scale_slider.setValue(100)
        self.scale_slider.setToolTip("Uniformly scale the selected widget. Content-sized entries keep following content; explicit entries remain explicit.")
        self.scale_slider.valueChanged.connect(self._scale_selected)
        scale_row.addWidget(self.scale_label); scale_row.addWidget(self.scale_slider, 1)
        selection_panel.addLayout(scale_row)
        selection_panel.addWidget(action("Reset selected", self._reset_selected, secondary=True))
        chooser.addLayout(selection_panel, 2)
        self.body.addLayout(chooser)
        controls = QHBoxLayout()
        self.apply_button = action("Apply", self.apply)
        self.discard_button = action("Discard", self.discard, secondary=True)
        for control in (self.apply_button, self.discard_button): controls.addWidget(control)
        controls.addStretch(); self.body.addLayout(controls)
        slots = QHBoxLayout(); self.slot_combo = StyledComboBox(size_variant="compact"); self.slot_combo.addItems([str(value) for value in range(1, 10)] + ["0"]); self.load_slot_button = action("Load into editor", self._load_slot, secondary=True); self.save_slot_button = action("Save to slot", self._save_slot, secondary=True)
        slot_hint = text_label("On the saver, 1–9 and 0 load a slot; Shift with the same key saves to it. A slot includes fonts, positions, monitors and Clock modes.")
        slot_label = text_label("Layout slot:")
        slots.addWidget(slot_label); slots.addWidget(self.slot_combo); slots.addWidget(self.load_slot_button); slots.addWidget(self.save_slot_button); slots.addStretch(); self.body.addLayout(slots)
        self.body.addWidget(slot_hint)
        # Quick Start has its own Layout Slots area: one slot UI per page.
        for control in (slot_label, self.slot_combo, self.load_slot_button, self.save_slot_button, slot_hint):
            control.setVisible(show_slots)
        self.status = text_label(""); self.body.addWidget(self.status)
        page_ref = weakref.ref(self)
        def _theme_changed(_theme):
            page = page_ref()
            if page is not None and hasattr(page, "canvas"):
                page.canvas.update()
        self._theme_unsubscribe = subscribe_settings_theme(_theme_changed)
        self.destroyed.connect(lambda _obj=None, unsubscribe=self._theme_unsubscribe: unsubscribe())
        self.refresh()

    def _live_displays(self) -> tuple[ArrangeDisplay, ...]:
        raw = self.settings.get("display.show_on_monitors", require_canonical_default("display.show_on_monitors"))
        selected = None if str(raw).upper() == "ALL" else {int(value) for value in raw if str(value).isdigit()} if isinstance(raw, (list, tuple, set)) else set()
        screens = list(QGuiApplication.screens())
        return tuple(ArrangeDisplay(get_screen_signature(screen), get_screen_signature_aliases(screen), QRect(screen.geometry()), str(index + 1)) for index, screen in enumerate(screens) if selected is None or index + 1 in selected)

    def refresh(self):
        if self.model is not None and self.model.pending: return
        widgets = self.settings.get("widgets", {})
        self.model = ArrangeModel(widgets if isinstance(widgets, dict) else {}, self._live_displays())
        while self.canvas_holder.count():
            item = self.canvas_holder.takeAt(0); widget = item.widget()
            if widget is not None:
                # Detach now: deleteLater alone left the old canvas painting
                # under the new one until the next event-loop turn.
                widget.hide(); widget.setParent(None); widget.deleteLater()
        self.canvas = _ArrangeCanvas(self.model)
        self.canvas.changed.connect(self._pending_changed)
        self.canvas.selectionChanged.connect(self._selection_changed)
        self.canvas.dragFinished.connect(self._refresh_item_choices)
        self.canvas_holder.addWidget(self.canvas)
        self._refresh_item_choices()
        self._refresh_slot_choices()
        self._pending_changed()

    def _pending_changed(self):
        pending = bool(self.model and self.model.pending); self.status.setText("Apply or discard this draft before saving a layout slot." if pending else "No pending layout changes."); self.save_slot_button.setEnabled(not pending); self._sync_free_check(); self.pendingChanged.emit(pending)

    def _refresh_slot_choices(self):
        self.slot_combo.blockSignals(True); self.slot_combo.clear()
        for slot_id in [str(value) for value in range(1, 10)] + ["0"]:
            occupied = self.model.slot_is_occupied(slot_id)
            self.slot_combo.addItem(f"{slot_id} — {'occupied' if occupied else 'empty'}", slot_id)
        self.slot_combo.blockSignals(False)

    def _refresh_item_choices(self):
        selected = self._selected().source_key if self._selected() is not None else None
        self.item_list.blockSignals(True)
        self.item_list.clear()
        for item in self.model.session.active_items():
            label = f"{self.model.item_label(item.source_key)} — display {self.model.display_route(item.source_key)}"
            if item.source_key.geometry_variant != "default":
                label += f" · {item.source_key.geometry_variant}"
            row = QListWidgetItem(label)
            row.setData(Qt.ItemDataRole.UserRole, item.source_key)
            self.item_list.addItem(row)
            if item.source_key == selected:
                self.item_list.setCurrentItem(row)
        self.item_list.blockSignals(False)
        self._sync_selected_controls()

    def _selection_changed(self):
        selected = self._selected()
        self.item_list.blockSignals(True)
        for index in range(self.item_list.count()):
            row = self.item_list.item(index)
            if row.data(Qt.ItemDataRole.UserRole) == (selected.source_key if selected else None):
                self.item_list.setCurrentItem(row)
                break
        self.item_list.blockSignals(False)
        self._sync_selected_controls()

    def _select_list_item(self, current, _previous):
        item = self.model.session.item(current.data(Qt.ItemDataRole.UserRole)) if current is not None else None
        self.model.session.select_item(item)
        self.canvas._selected = item
        self.canvas.update()
        self._sync_selected_controls()

    def _sync_selected_controls(self):
        item = self._selected()
        self.free_check.blockSignals(True)
        self.free_check.setEnabled(item is not None)
        self.free_check.setChecked(bool(item and self.model.free_placement(item.source_key)))
        self.free_check.blockSignals(False)
        percent = max(round(100 * CUSTOM_LAYOUT_MIN_RESIZE_SCALE), min(200, round((item.resize_scale if item else 1.0) * 100)))
        self.scale_slider.blockSignals(True)
        self.scale_slider.setEnabled(bool(item and item.resize_capable))
        self.scale_slider.setValue(percent)
        self.scale_slider.blockSignals(False)
        self._scale_value = percent
        if item is None:
            self.selection_hint.setText("Select a widget to arrange it.")
            self.scale_label.setText("Uniform scale: 100%")
        else:
            policy = "size follows content; X/Y reflows with content" if item.content_sized else "explicit size"
            self.selection_hint.setText(f"{self.model.item_label(item.source_key)} on display {self.model.display_route(item.source_key)} · {policy}")
            self.scale_label.setText(f"Uniform scale: {percent}%")

    def _scale_selected(self, value):
        item = self._selected()
        if item is None or not item.resize_capable:
            return
        previous = getattr(self, "_scale_value", 100)
        if value == previous:
            return
        self.model.scale(item.source_key, float(value) / float(previous))
        self._scale_value = int(value)
        self.scale_label.setText(f"Uniform scale: {value}%")
        self.canvas.update()
        self._pending_changed()

    def _sync_free_check(self):
        self._sync_selected_controls()

    def _selected(self): return self.model.session.selected_item() if self.model else None

    def _toggle_free(self, enabled):
        item = self._selected()
        if item is None: return
        self.model.set_free_placement(item.source_key, bool(enabled)); self.canvas.update(); self._sync_selected_controls(); self._pending_changed()

    def _reset_selected(self):
        item = self._selected()
        if item is None: return
        self.model.reset(item.source_key); self.canvas._selected = None; self._refresh_item_choices(); self.canvas.update(); self._pending_changed()

    def _load_slot(self):
        self.load_slot(self.slot_combo.currentData())

    def load_slot(self, slot_id: object) -> bool:
        """Load a slot into this page's draft and publish its new editor state."""

        if self.model is None:
            return False
        if self.model.pending and not StyledPopup.question(self, "Replace draft", "Discard the current Arrange draft and load this slot?", yes_text="Load", no_text="Cancel", default_to_yes=False):
            return False
        if not self.model.load_slot(slot_id):
            return False
        self.canvas._selected = None
        self._refresh_item_choices()
        self.canvas.update()
        self._pending_changed()
        return True

    def _save_slot(self):
        if self.model is None:
            return
        slot_id = self.slot_combo.currentData()
        if self.model.slot_is_occupied(slot_id):
            if not StyledPopup.question(self, "Replace layout slot", f"Replace saved layout slot {slot_id}?", yes_text="Replace", no_text="Cancel", default_to_yes=False):
                return
        if self.model.save_slot(slot_id):
            self.settings.set("widgets", self.model.committed_widgets())
            self.status.setText("Layout slot saved.")
            self._refresh_slot_choices()

    def apply(self) -> bool:
        if self.model is None: return False
        if self.model.pending: self.settings.set("widgets", self.model.apply())
        self._pending_changed(); return True

    def discard(self):
        if self.model is not None: self.model.discard(); self.canvas._selected = None; self._refresh_item_choices(); self.canvas.update(); self._pending_changed()

    def can_continue(self) -> bool: return True
    def leave(self) -> bool: return self.apply()
