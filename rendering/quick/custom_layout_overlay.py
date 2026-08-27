"""Retained Qt Quick presentation adapter for one display's CUSTOM session."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from PySide6.QtCore import (
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    QPoint,
    QRect,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtQuick import QQuickItem

from rendering.custom_layout_session import (
    CustomLayoutSession,
    CustomLayoutSessionItem,
)


GeometryResolver = Callable[[CustomLayoutSessionItem, QRect], QRect]
ItemChangePublisher = Callable[[CustomLayoutSessionItem], None]
ResizeBeginHandler = Callable[[CustomLayoutSessionItem, str, QPoint], bool]
ResizeUpdateHandler = Callable[[CustomLayoutSessionItem, str, QPoint, bool], bool]
ResizeWheelHandler = Callable[[CustomLayoutSessionItem, int], bool]


class CustomLayoutOverlayModel(QAbstractListModel):
    """Display-local view over shared, presentation-neutral session items."""

    item_closed = Signal(str, bool, bool)

    _WIDGET_ID_ROLE = int(Qt.ItemDataRole.UserRole) + 1
    _GEOMETRY_X_ROLE = _WIDGET_ID_ROLE + 1
    _GEOMETRY_Y_ROLE = _WIDGET_ID_ROLE + 2
    _GEOMETRY_WIDTH_ROLE = _WIDGET_ID_ROLE + 3
    _GEOMETRY_HEIGHT_ROLE = _WIDGET_ID_ROLE + 4
    _DUPLICATE_ROLE = _WIDGET_ID_ROLE + 5
    _RESIZABLE_ROLE = _WIDGET_ID_ROLE + 6

    def __init__(
        self,
        *,
        session: CustomLayoutSession,
        display_identity: str,
        display_origin: QPoint | None = None,
        geometry_resolver: GeometryResolver | None = None,
        item_change_publisher: ItemChangePublisher | None = None,
        resize_begin_handler: ResizeBeginHandler | None = None,
        resize_update_handler: ResizeUpdateHandler | None = None,
        resize_wheel_handler: ResizeWheelHandler | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._session: CustomLayoutSession | None = session
        self._display_identity = str(display_identity or "").strip()
        if not self._display_identity:
            raise ValueError("display_identity must not be empty")
        self._display_origin = QPoint(display_origin or QPoint())
        self._geometry_resolver = geometry_resolver
        self._item_change_publisher = item_change_publisher
        self._resize_begin_handler = resize_begin_handler
        self._resize_update_handler = resize_update_handler
        self._resize_wheel_handler = resize_wheel_handler
        self._items: list[CustomLayoutSessionItem] = []
        self.refresh()

    def roleNames(self) -> dict[int, QByteArray]:  # type: ignore[override]
        return {
            self._WIDGET_ID_ROLE: QByteArray(b"widgetId"),
            self._GEOMETRY_X_ROLE: QByteArray(b"geometryX"),
            self._GEOMETRY_Y_ROLE: QByteArray(b"geometryY"),
            self._GEOMETRY_WIDTH_ROLE: QByteArray(b"geometryWidth"),
            self._GEOMETRY_HEIGHT_ROLE: QByteArray(b"geometryHeight"),
            self._DUPLICATE_ROLE: QByteArray(b"duplicate"),
            self._RESIZABLE_ROLE: QByteArray(b"resizable"),
        }

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        return 0 if parent.isValid() else len(self._items)

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)) -> Any:  # type: ignore[override]
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        item = self._items[index.row()]
        rect = item.current_global_rect
        if role == self._WIDGET_ID_ROLE:
            return item.source_key.widget_id
        if role == self._GEOMETRY_X_ROLE:
            return rect.x() - self._display_origin.x()
        if role == self._GEOMETRY_Y_ROLE:
            return rect.y() - self._display_origin.y()
        if role == self._GEOMETRY_WIDTH_ROLE:
            return rect.width()
        if role == self._GEOMETRY_HEIGHT_ROLE:
            return rect.height()
        if role == self._DUPLICATE_ROLE:
            return item.is_duplicate
        if role == self._RESIZABLE_ROLE:
            return item.resize_capable
        return None

    @Slot()
    def refresh(self) -> None:
        """Re-evaluate display membership without copying working state."""

        session = self._session
        if session is None:
            return
        session.refresh_duplicate_state()
        next_items = [
            item
            for item in session.items()
            if item.current_display_identity == self._display_identity
            and item.current_enabled
            and not item.removed
        ]
        self.beginResetModel()
        self._items = next_items
        self.endResetModel()
        for item in session.items():
            self._publish_item_change(item)

    @Slot(int, float, float)
    def moveItem(self, row: int, local_x: float, local_y: float) -> None:
        """Move one item through the session's authoritative geometry seam."""

        if not 0 <= int(row) < len(self._items):
            return
        item = self._items[int(row)]
        current = item.current_global_rect
        proposed = QRect(
            self._display_origin.x() + int(round(float(local_x))),
            self._display_origin.y() + int(round(float(local_y))),
            current.width(),
            current.height(),
        )
        resolver = self._geometry_resolver
        resolved = QRect(resolver(item, proposed)) if resolver is not None else proposed
        item.set_geometry(resolved)
        self._publish_item_change(item)
        model_index = self.index(int(row), 0)
        self.dataChanged.emit(
            model_index,
            model_index,
            [self._GEOMETRY_X_ROLE, self._GEOMETRY_Y_ROLE],
        )

    @Slot(int)
    def closeItem(self, row: int) -> None:
        """Apply edit-mode X to working state only."""

        if not 0 <= int(row) < len(self._items):
            return
        session = self._session
        if session is None:
            return
        session.refresh_duplicate_state()
        item = self._items[int(row)]
        widget_id = item.source_key.widget_id
        item.apply_remove_action()
        removed = item.removed
        enabled = item.current_enabled
        session.refresh_duplicate_state()
        self.refresh()
        self.item_closed.emit(widget_id, removed, enabled)

    @Slot(int, str, float, float, result=bool)
    def beginResize(
        self,
        row: int,
        corner: str,
        local_x: float,
        local_y: float,
    ) -> bool:
        """Begin a retained resize through the Python-owned geometry seam."""

        item = self._resizable_item(row)
        handler = self._resize_begin_handler
        if item is None or handler is None:
            return False
        cursor = self._global_point(local_x, local_y)
        return bool(handler(item, str(corner), cursor))

    @Slot(int, str, float, float, bool, result=bool)
    def resizeItem(
        self,
        row: int,
        corner: str,
        local_x: float,
        local_y: float,
        finalize: bool,
    ) -> bool:
        """Apply one live/final retained resize sample without QML geometry ownership."""

        item = self._resizable_item(row)
        handler = self._resize_update_handler
        if item is None or handler is None:
            return False
        cursor = self._global_point(local_x, local_y)
        if not handler(item, str(corner), cursor, bool(finalize)):
            return False
        self._publish_resize(item, row)
        return True

    @Slot(int, int, result=bool)
    def resizeWheel(self, row: int, angle_delta_y: int) -> bool:
        """Apply one uniform wheel-resize request through the canonical owner."""

        item = self._resizable_item(row)
        handler = self._resize_wheel_handler
        if item is None or handler is None:
            return False
        if not handler(item, int(angle_delta_y)):
            return False
        self._publish_resize(item, row)
        return True

    def retire(self) -> None:
        self.beginResetModel()
        self._items = []
        self._session = None
        self._geometry_resolver = None
        self._item_change_publisher = None
        self._resize_begin_handler = None
        self._resize_update_handler = None
        self._resize_wheel_handler = None
        self.endResetModel()

    def _resizable_item(self, row: int) -> CustomLayoutSessionItem | None:
        if not 0 <= int(row) < len(self._items):
            return None
        item = self._items[int(row)]
        return item if item.resize_capable else None

    def _global_point(self, local_x: float, local_y: float) -> QPoint:
        return QPoint(
            self._display_origin.x() + int(round(float(local_x))),
            self._display_origin.y() + int(round(float(local_y))),
        )

    def _publish_resize(self, item: CustomLayoutSessionItem, row: int) -> None:
        self._publish_item_change(item)
        model_index = self.index(int(row), 0)
        self.dataChanged.emit(
            model_index,
            model_index,
            [
                self._GEOMETRY_X_ROLE,
                self._GEOMETRY_Y_ROLE,
                self._GEOMETRY_WIDTH_ROLE,
                self._GEOMETRY_HEIGHT_ROLE,
            ],
        )

    def _publish_item_change(self, item: CustomLayoutSessionItem) -> None:
        publisher = self._item_change_publisher
        if publisher is not None:
            publisher(item)


class RetainedCustomLayoutOverlay:
    """Own the model bound to the scene's single retained edit-overlay item."""

    def __init__(self, item: QQuickItem) -> None:
        self._item: QQuickItem | None = item
        self._model: CustomLayoutOverlayModel | None = None

    @property
    def item(self) -> QQuickItem:
        item = self._item
        if item is None:
            raise RuntimeError("CUSTOM layout overlay has retired")
        return item

    @property
    def model(self) -> CustomLayoutOverlayModel:
        model = self._model
        if model is None:
            raise RuntimeError("CUSTOM layout overlay has no bound session")
        return model

    def bind_session(
        self,
        session: CustomLayoutSession,
        *,
        display_identity: str,
        display_origin: QPoint | None = None,
        geometry_resolver: GeometryResolver | None = None,
        item_change_publisher: ItemChangePublisher | None = None,
        resize_begin_handler: ResizeBeginHandler | None = None,
        resize_update_handler: ResizeUpdateHandler | None = None,
        resize_wheel_handler: ResizeWheelHandler | None = None,
    ) -> CustomLayoutOverlayModel:
        self.clear_session()
        model = CustomLayoutOverlayModel(
            session=session,
            display_identity=display_identity,
            display_origin=display_origin,
            geometry_resolver=geometry_resolver,
            item_change_publisher=item_change_publisher,
            resize_begin_handler=resize_begin_handler,
            resize_update_handler=resize_update_handler,
            resize_wheel_handler=resize_wheel_handler,
            parent=self.item,
        )
        self._model = model
        self.item.setProperty("sessionModel", model)
        self.item.setProperty("editActive", True)
        return model

    def set_guides(
        self,
        *,
        vertical: Sequence[tuple[int, str]] = (),
        horizontal: Sequence[tuple[int, str]] = (),
    ) -> None:
        self.item.setProperty(
            "verticalGuides",
            [
                {"position": int(position), "kind": str(kind)}
                for position, kind in vertical
            ],
        )
        self.item.setProperty(
            "horizontalGuides",
            [
                {"position": int(position), "kind": str(kind)}
                for position, kind in horizontal
            ],
        )

    def clear_session(self) -> None:
        item = self._item
        model = self._model
        self._model = None
        if item is not None:
            item.setProperty("editActive", False)
            item.setProperty("sessionModel", None)
            item.setProperty("verticalGuides", [])
            item.setProperty("horizontalGuides", [])
        if model is not None:
            model.retire()
            model.deleteLater()

    def retire(self) -> None:
        self.clear_session()
        self._item = None
