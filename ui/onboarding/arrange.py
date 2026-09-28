"""Lightweight QWidget projection of the canonical CUSTOM layout draft."""
from __future__ import annotations

import weakref

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QListWidget, QListWidgetItem, QSizePolicy, QVBoxLayout, QWidget
from PySide6.QtGui import QGuiApplication

from rendering.custom_layout_contract import get_screen_signature, get_screen_signature_aliases
from rendering.quick.custom_layout_size import CUSTOM_LAYOUT_MIN_RESIZE_SCALE
from ui.widgets.continuous_border import OutlinedListWidget
from core.settings.default_contract import require_canonical_default
from core.settings.layout_slots import get_layout_slot_payload
from core.windows.monitor_resolution import screen_device_size
from rendering.quick.widgets.preferred_size_measurement import OrdinaryPreferredSizeMeter
from ui.onboarding.arrange_model import ArrangeDisplay, ArrangeModel
from ui.onboarding.common import Page, action, checkbox, text_label
from ui.styled_popup import StyledPopup
from ui.settings_theme_runtime import get_active_settings_theme, subscribe_settings_theme
from ui.tabs.shared_styles import NoWheelSlider
from ui.widgets import StyledComboBox


class _ArrangeCanvas(QWidget):
    """A scaled, event-owned projection; it never represents persisted coordinates.

    Drag a box to move it (across displays too), drag a corner handle to scale
    it uniformly, drag a side handle (when the model admits one) to change
    only width or height, Ctrl+wheel scales, arrow keys nudge (Shift for 10 px),
    Delete resets, Escape clears the selection.  Dashed boxes still follow
    their authored anchor; solid boxes are placed.  Every size gesture is
    Runtime Edit's own: scaling keeps the top-centre, and the Visualizer's
    corners change its width and height together.
    """

    changed = Signal()
    selectionChanged = Signal()
    dragFinished = Signal()

    _MIN_HEIGHT = 260
    _MAX_HEIGHT = 560
    _PAD = 10
    _LABEL_BAND = 24  # display names sit below their rectangles, never under widgets
    _HANDLE = 9

    def __init__(self, model: ArrangeModel, parent=None) -> None:
        super().__init__(parent)
        self.model = model
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.setMinimumHeight(self._MIN_HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self._selected = None
        self._hovered = None
        self._drag_origin: QPoint | None = None
        self._original_rect: QRect | None = None
        self._corner: str | None = None
        self._resize_origin = None
        self._side_edge: str | None = None
        self._dragging = False

    # ---- geometry -----------------------------------------------------------
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

    # ---- hit testing --------------------------------------------------------
    def _item_at(self, point: QPoint):
        return next((item for item in reversed(self._paint_order())
                     if self._project(item.current_global_rect).contains(point)), None)

    def _paint_order(self):
        items = list(self.model.session.active_items())
        items.sort(key=lambda item: item is self._selected)  # selected paints (and hits) last
        return items

    def _handles(self, item) -> dict[str, QRectF]:
        rect = QRectF(self._project(item.current_global_rect))
        half = self._HANDLE / 2
        corners = {"top_left": rect.topLeft(), "top_right": rect.topRight(),
                   "bottom_left": rect.bottomLeft(), "bottom_right": rect.bottomRight()}
        return {name: QRectF(corner.x() - half, corner.y() - half, self._HANDLE, self._HANDLE)
                for name, corner in corners.items()}

    def _side_handles(self, item) -> dict[str, QRectF]:
        rect = QRectF(self._project(item.current_global_rect))
        long, short = self._HANDLE * 2, self._HANDLE * 0.75
        centres = {"left": QPointF(rect.left(), rect.center().y()), "right": QPointF(rect.right(), rect.center().y()),
                   "top": QPointF(rect.center().x(), rect.top()), "bottom": QPointF(rect.center().x(), rect.bottom())}
        handles = {}
        for edge in self.model.side_edges(item.source_key):
            width, height = (short, long) if edge in {"left", "right"} else (long, short)
            centre = centres[edge]
            handles[edge] = QRectF(centre.x() - width / 2, centre.y() - height / 2, width, height)
        return handles

    def _side_at(self, point: QPoint) -> str | None:
        item = self._selected
        if item is None:
            return None
        return next((edge for edge, handle in self._side_handles(item).items()
                     if handle.adjusted(-3, -3, 3, 3).contains(QPointF(point))), None)

    def _corner_at(self, point: QPoint) -> str | None:
        item = self._selected
        if item is None or not item.resize_capable:
            return None
        return next((name for name, handle in self._handles(item).items()
                     if handle.adjusted(-3, -3, 3, 3).contains(QPointF(point))), None)

    def _display_under(self, item):
        centre = item.current_global_rect.center()
        return next((display for display in self.model.displays if display.geometry.contains(centre)), None)

    def _describe(self, item) -> str:
        width, height = self.model.device_size(item.source_key)
        state = ("follows its authored anchor (drag to place it freely)" if self.model.is_authored(item.source_key)
                 else "size follows content" if item.content_sized else "placed")
        return (f"{self.model.item_label(item.source_key)} · display {self.model.display_route(item.source_key)}"
                f" · {width} × {height} px · {state}")

    # ---- painting -----------------------------------------------------------
    def paintEvent(self, _event) -> None:
        theme = get_active_settings_theme()
        color = lambda token: QColor(*theme.color(token).as_tuple())
        accent = color("control.list.selected_accent"); accent.setAlpha(255)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color("panel.group.surface"))
        painter.drawRoundedRect(QRectF(self.rect()), 8.0, 8.0)
        small = self.font(); small.setPointSizeF(max(7.0, small.pointSizeF() - 1.0))
        target = self._display_under(self._selected) if (self._dragging and self._selected is not None) else None
        for display in self.model.displays:
            rect = QRectF(self._project(display.geometry)).adjusted(1, 1, -1, -1)
            painter.setPen(QPen(accent if display is target else color("panel.border"), 3.0 if display is target else 2.0))
            painter.setBrush(color("panel.subsection.surface"))
            painter.drawRoundedRect(rect, 4.0, 4.0)
            if display is target:
                # The display a drop would land on.
                wash = QColor(accent); wash.setAlpha(34)
                painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(wash)
                painter.drawRoundedRect(rect, 4.0, 4.0)
        for item in self._paint_order():
            self._paint_item(painter, item, color, accent, small)
        if self._dragging:
            self._paint_guides(painter, accent)
        painter.setFont(small)
        painter.setPen(color("panel.group.text"))
        for display in self.model.displays:
            rect = QRectF(self._project(display.geometry))
            width, height = display.resolution()
            label = f"Display {display.monitor_route}  ·  {width} × {height}"
            painter.drawText(QRectF(rect.left(), rect.bottom() + 4, rect.width(), self._LABEL_BAND - 6),
                             Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, label)
        if self.hasFocus() and self._selected is None and not self.model.session.active_items():
            painter.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignCenter, "No widgets are enabled.")

    def _paint_item(self, painter, item, color, accent, small) -> None:
        rect = QRectF(self._project(item.current_global_rect)).adjusted(0.75, 0.75, -0.75, -0.75)
        selected = item is self._selected
        hovered = item is self._hovered
        authored = self.model.is_authored(item.source_key)
        fill = color("control.list.selected_surface" if selected else "control.button.hover_surface" if hovered else "control.button.surface")
        fill.setAlpha(max(fill.alpha(), 225))
        border = color("control.button.border")
        border.setAlpha(255 if selected else (225 if hovered else 165))
        pen = QPen(border, 2.75 if selected else (2.25 if hovered else 1.75))
        if authored and not selected:
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, 3.0, 3.0)
        if rect.width() >= 28 and rect.height() >= 14:
            painter.setFont(small)
            painter.setPen(color("control.button.text"))
            metrics = painter.fontMetrics()
            name = metrics.elidedText(self.model.item_label(item.source_key), Qt.TextElideMode.ElideRight, int(rect.width() - 8))
            if rect.height() >= 2.4 * metrics.height():
                size = "{} × {}".format(*self.model.device_size(item.source_key))
                painter.drawText(rect.adjusted(4, 2, -4, -rect.height() / 2 + 1), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom, name)
                faint = color("control.button.text"); faint.setAlpha(150)
                painter.setPen(faint)
                painter.drawText(rect.adjusted(4, rect.height() / 2 + 1, -4, -2), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                                 metrics.elidedText(size, Qt.TextElideMode.ElideRight, int(rect.width() - 8)))
            else:
                painter.drawText(rect.adjusted(4, 2, -4, -2), Qt.AlignmentFlag.AlignCenter, name)
        if selected and item.resize_capable:
            painter.setPen(QPen(color("panel.group.surface"), 1.5))
            painter.setBrush(accent)
            for handle in self._handles(item).values():
                painter.drawRoundedRect(handle, 2.0, 2.0)
            for handle in self._side_handles(item).values():
                painter.drawRoundedRect(handle, 2.0, 2.0)

    def _paint_guides(self, painter, accent) -> None:
        snap = self.model.last_snap
        if snap is None:
            return
        identity, vertical, horizontal = snap
        display = next((d for d in self.model.displays if d.identity == identity), None)
        if display is None:
            return
        area = QRectF(self._project(display.geometry))
        scale = self._scale()
        pen = QPen(accent, 1.5, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        for guide in vertical:
            x = area.left() + guide.position * scale
            painter.drawLine(QPointF(x, area.top()), QPointF(x, area.bottom()))
        for guide in horizontal:
            y = area.top() + guide.position * scale
            painter.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))

    # ---- interaction ----------------------------------------------------------
    def _select(self, item) -> None:
        self._selected = item
        self.model.session.select_item(item)
        self.selectionChanged.emit()
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        point = event.position().toPoint()
        edge = self._side_at(point)
        if edge is not None:
            self._side_edge = edge
            self._drag_origin = point; self._original_rect = QRect(self._selected.current_global_rect)
            self._dragging = False
            return
        corner = self._corner_at(point)
        if corner is not None:
            # Runtime Edit's corner gesture, measured from its start.
            self._corner = corner
            self._resize_origin = self.model.resize_origin(self._selected.source_key)
            self._drag_origin = point
            self._dragging = False
            return
        item = self._item_at(point)
        self._select(item)
        if item is not None:
            self._drag_origin = point; self._original_rect = QRect(item.current_global_rect)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event) -> None:
        point = event.position().toPoint()
        if self._corner is not None and self._selected is not None and self._resize_origin is not None:
            self._dragging = True
            delta = self._unproject_delta(point - self._drag_origin)
            self.model.corner_resize(self._selected.source_key, self._corner, self._resize_origin, delta)
            self.changed.emit(); self.update()
            return
        if self._side_edge is not None and self._selected is not None and self._original_rect is not None:
            self._dragging = True
            delta = self._unproject_delta(point - self._drag_origin)
            self.model.resize_edge(self._selected.source_key, self._side_edge, self._original_rect, delta)
            self.changed.emit(); self.update()
            return
        if self._selected is not None and self._drag_origin is not None and self._original_rect is not None:
            if not self._dragging and (point - self._drag_origin).manhattanLength() < 3:
                return
            self._dragging = True
            delta = self._unproject_delta(point - self._drag_origin)
            rect = QRect(self._original_rect); rect.translate(delta)
            self.model.move(self._selected.source_key, rect, cursor_global=self._unproject_point(point))
            self.changed.emit(); self.update()
            return
        hovered = self._item_at(point)
        if hovered is not self._hovered:
            self._hovered = hovered
            self.setToolTip(self._describe(hovered) if hovered is not None else "")
            self.update()
        edge = self._side_at(point)
        if edge is not None:
            self.setCursor(Qt.CursorShape.SizeHorCursor if edge in {"left", "right"} else Qt.CursorShape.SizeVerCursor)
        elif (corner := self._corner_at(point)) is not None:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor if corner in {"top_left", "bottom_right"}
                           else Qt.CursorShape.SizeBDiagCursor)
        elif hovered is not None:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.unsetCursor()

    def mouseReleaseEvent(self, _event) -> None:
        was_editing = self._dragging
        self._drag_origin = None; self._original_rect = None
        self._corner = None; self._resize_origin = None; self._side_edge = None; self._dragging = False
        self.model.last_snap = None
        self.unsetCursor()
        self.update()
        if was_editing:
            self.dragFinished.emit()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        if self._hovered is not None:
            self._hovered = None; self.update()

    def wheelEvent(self, event) -> None:
        item = self._selected
        if item is not None and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if item.resize_capable and event.angleDelta().y():
                # Runtime Edit's wheel: 5% of scale per notch, top-centre fixed.
                self.model.wheel_scale(item.source_key, event.angleDelta().y())
                self.changed.emit(); self.update()
                self.dragFinished.emit()
            event.accept()
            return
        super().wheelEvent(event)

    def keyPressEvent(self, event) -> None:
        item = self._selected
        key = event.key()
        if key == Qt.Key.Key_Escape and item is not None:
            self._select(None); return
        if item is None:
            super().keyPressEvent(event); return
        step = 10 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
        offsets = {Qt.Key.Key_Left: (-step, 0), Qt.Key.Key_Right: (step, 0), Qt.Key.Key_Up: (0, -step), Qt.Key.Key_Down: (0, step)}
        if key in offsets:
            dx, dy = offsets[key]
            rect = QRect(item.current_global_rect); rect.translate(dx, dy)
            self.model.move(item.source_key, rect, snap=False)
            self.changed.emit(); self.dragFinished.emit(); self.update()
            return
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.model.reset(item.source_key)
            self.changed.emit(); self.dragFinished.emit(); self.update()
            return
        super().keyPressEvent(event)


class ArrangePage(Page):
    """Shared Guided Setup/Quick Start draft editor; writes only on Apply/leave."""

    pendingChanged = Signal(bool)

    def __init__(self, settings, parent=None, *, show_slots: bool = True) -> None:
        super().__init__(settings, parent)
        self.model: ArrangeModel | None = None
        # One size meter for this page's lifetime: every draft reuses its
        # memoized measurements, and nothing is measured before Arrange opens.
        self._size_meter = OrdinaryPreferredSizeMeter()
        self.destroyed.connect(lambda _obj=None, meter=self._size_meter: meter.close())
        # Hardware display changes arrive as events; nothing polls.
        app = QGuiApplication.instance()
        page_ref = weakref.ref(self)

        def _screens_changed(*_args):
            page = page_ref()
            if page is not None:
                page._sync_displays()

        app.screenAdded.connect(_screens_changed)
        app.screenRemoved.connect(_screens_changed)

        def _disconnect(_obj=None, handler=_screens_changed, application=app):
            for signal in (application.screenAdded, application.screenRemoved):
                try:
                    signal.disconnect(handler)
                except (RuntimeError, TypeError):
                    pass

        self.destroyed.connect(_disconnect)
        self.body.addWidget(text_label("Arrange widgets freely. Changes stay in this draft until you apply them.", heading=True))
        self.canvas_holder = QVBoxLayout(); self.body.addLayout(self.canvas_holder)
        self.body.addWidget(text_label("Drag a box to move it, including onto another display. Drag a corner, or Ctrl+scroll, to scale (the Visualizer's corners change width and height together); drag a side handle to change only width or height. Sizing works exactly as in the saver's Edit mode. Arrow keys nudge (Shift for 10 px), Delete resets. Dashed boxes show where the saver places them now; once you move anything, Apply keeps every box where you see it."))
        chooser = QHBoxLayout()
        self.item_list = OutlinedListWidget()
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
        selection_panel.addWidget(action("Reset selected", self._reset_selected))
        chooser.addLayout(selection_panel, 2)
        self.body.addLayout(chooser)
        controls = QHBoxLayout()
        self.apply_button = action("Apply", self.apply)
        self.discard_button = action("Discard", self.discard)
        for control in (self.apply_button, self.discard_button): controls.addWidget(control)
        controls.addStretch(); self.body.addLayout(controls)
        slots = QHBoxLayout(); self.slot_combo = StyledComboBox(size_variant="compact"); self.slot_combo.addItems([str(value) for value in range(1, 10)] + ["0"]); self.load_slot_button = action("Load into editor", self._load_slot); self.save_slot_button = action("Save to slot", self._save_slot)
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
        return tuple(
            ArrangeDisplay(
                get_screen_signature(screen), get_screen_signature_aliases(screen), QRect(screen.geometry()),
                str(index + 1), float(screen.devicePixelRatio() or 1.0), screen_device_size(screen),
            )
            for index, screen in enumerate(screens) if selected is None or index + 1 in selected
        )

    def refresh(self):
        displays = self._live_displays()
        if self.model is not None and self.model.pending:
            # Keep the draft; only follow a changed display set.
            if self.model.replace_displays(displays):
                self._rebuild_canvas()
            return
        widgets = self.settings.get("widgets", {})
        self.model = ArrangeModel(
            widgets if isinstance(widgets, dict) else {}, displays, meter=self._size_meter
        )
        self._rebuild_canvas()

    def _sync_displays(self, *_args) -> None:
        """Follow display changes made while Settings is open (selection or hardware)."""

        if self.model is not None and self._live_displays() != self.model.displays:
            self.refresh()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync_displays()

    def _rebuild_canvas(self) -> None:
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
            policy = "size follows content" if item.content_sized else "explicit size"
            note = self.model.side_edges_note(item.source_key)
            if note:
                policy += f" · {note}"
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
            widgets = self.model.committed_widgets()
            self.settings.set("widgets", widgets)
            # Save to Slot is an explicit save: in Guided Setup it writes the
            # slots straight through while the rest of the draft waits for Finish.
            persist_now = getattr(self.settings, "persist_now", None)
            if callable(persist_now):
                from core.settings.layout_slots import LAYOUT_SLOTS_SETTINGS_KEY
                persist_now(f"widgets.{LAYOUT_SLOTS_SETTINGS_KEY}", widgets[LAYOUT_SLOTS_SETTINGS_KEY])
            self.status.setText("Layout slot saved.")
            self._refresh_slot_choices()

    def apply(self) -> bool:
        if self.model is None: return False
        # Merge onto current Settings: other pages may have written meanwhile.
        if self.model.pending: self.settings.set("widgets", self.model.apply(base=self.settings.get("widgets")))
        self._pending_changed(); return True

    def discard(self):
        if self.model is not None: self.model.discard(); self.canvas._selected = None; self._refresh_item_choices(); self.canvas.update(); self._pending_changed()

    def resolve_pending(self) -> bool:
        """Before leaving Arrange with an unapplied draft: Apply, Discard or Stay.

        Returns False only when the operator chooses to stay. Closing the popup
        is not a decision, so it stays too.
        """

        if self.model is None or not self.model.pending:
            return True
        popup = StyledPopup(
            self.window(), "Unsaved Arrange Changes",
            "You changed widgets in Arrange without applying them. Apply them to the saver, or discard them?",
            icon_type="question",
            buttons=[("Apply Changes", "apply"), ("Discard Changes", "discard"), ("Stay In Arrange", "stay")],
            default_button_index=0)
        popup.exec()
        choice = popup.result_value or "stay"
        if choice == "apply":
            return self.apply()
        if choice == "discard":
            self.discard()
            return True
        return False

    def can_continue(self) -> bool: return True
    def leave(self) -> bool: return self.apply()
