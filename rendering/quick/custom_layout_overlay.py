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


class CustomLayoutOverlayModel(QAbstractListModel):
    """Display-local view over shared, presentation-neutral session items."""

    item_closed = Signal(str, bool, bool)

    _WIDGET_ID_ROLE = int(Qt.ItemDataRole.UserRole) + 1
    _GEOMETRY_X_ROLE = _WIDGET_ID_ROLE + 1
    _GEOMETRY_Y_ROLE = _WIDGET_ID_ROLE + 2
    _GEOMETRY_WIDTH_ROLE = _WIDGET_ID_ROLE + 3
    _GEOMETRY_HEIGHT_ROLE = _WIDGET_ID_ROLE + 4
    _DUPLICATE_ROLE = _WIDGET_ID_ROLE + 5

    def __init__(
        self,
        *,
        session: CustomLayoutSession,
        display_identity: str,
        display_origin: QPoint | None = None,
        geometry_resolver: GeometryResolver | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._session = session
        self._display_identity = str(display_identity or "").strip()
        if not self._display_identity:
            raise ValueError("display_identity must not be empty")
        self._display_origin = QPoint(display_origin or QPoint())
        self._geometry_resolver = geometry_resolver
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
        return None

    @Slot()
    def refresh(self) -> None:
        """Re-evaluate display membership without copying working state."""

        next_items = [
            item
            for item in self._session.items()
            if item.current_display_identity == self._display_identity
            and item.current_enabled
            and not item.removed
        ]
        self.beginResetModel()
        self._items = next_items
        self.endResetModel()

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
        item = self._items[int(row)]
        widget_id = item.source_key.widget_id
        item.apply_remove_action()
        removed = item.removed
        enabled = item.current_enabled
        self.refresh()
        self.item_closed.emit(widget_id, removed, enabled)


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
    ) -> CustomLayoutOverlayModel:
        self.clear_session()
        model = CustomLayoutOverlayModel(
            session=session,
            display_identity=display_identity,
            display_origin=display_origin,
            geometry_resolver=geometry_resolver,
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
            model.deleteLater()

    def retire(self) -> None:
        self.clear_session()
        self._item = None
