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
from shiboken6 import isValid as _is_valid_qobject

from rendering.custom_layout_session import (
    CustomLayoutSession,
    CustomLayoutSessionItem,
)


GeometryResolver = Callable[[CustomLayoutSessionItem, QRect, QPoint], QRect]
ItemChangePublisher = Callable[[CustomLayoutSessionItem], None]
ResizeBeginHandler = Callable[[CustomLayoutSessionItem, str, QPoint], bool]
ResizeUpdateHandler = Callable[[CustomLayoutSessionItem, str, QPoint, bool], bool]
ResizeWheelHandler = Callable[[CustomLayoutSessionItem, int], bool]
MoveFinishedHandler = Callable[[], None]
DisplayTransferCapability = Callable[[CustomLayoutSessionItem, str], bool]
DisplayTransferHandler = Callable[[CustomLayoutSessionItem, str], bool]
SizeResetHandler = Callable[[CustomLayoutSessionItem], bool]
ContentRotationHandler = Callable[[CustomLayoutSessionItem], bool]
PresentationItemResolver = Callable[[CustomLayoutSessionItem], QQuickItem | None]
ChildResizeBeginHandler = Callable[
    [CustomLayoutSessionItem, str, str, QPoint, float, float], bool
]
ChildResizeUpdateHandler = Callable[
    [CustomLayoutSessionItem, str, str, QPoint, bool], bool
]
ChildContentExtentHandler = Callable[[CustomLayoutSessionItem, float, float], bool]

# Semantic handle ids for the shared edit chrome. Side edges are one-axis
# viewport/content-extent gestures. Ordinary square corners retain uniform scale;
# the separate ``content_*`` diagonal handles opt into two-axis content reflow.
# QML emits semantic ids verbatim and never owns the geometry math.
_VIEWPORT_EDGE_HANDLES = frozenset({"left", "right", "top", "bottom"})
_CONTENT_CORNER_HANDLES = frozenset(
    {
        "content_top_left",
        "content_top_right",
        "content_bottom_left",
        "content_bottom_right",
    }
)


def _is_viewport_edge_handle(handle: str) -> bool:
    return str(handle) in _VIEWPORT_EDGE_HANDLES


def _is_content_corner_handle(handle: str) -> bool:
    return str(handle) in _CONTENT_CORNER_HANDLES


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
    _VIEWPORT_RESIZE_ROLE = _WIDGET_ID_ROLE + 7
    _RESIZE_SCALE_ROLE = _WIDGET_ID_ROLE + 8
    _CAN_TRANSFER_LEFT_ROLE = _WIDGET_ID_ROLE + 9
    _CAN_TRANSFER_RIGHT_ROLE = _WIDGET_ID_ROLE + 10
    _CONTENT_EXTENT_AXES_ROLE = _WIDGET_ID_ROLE + 11
    _SIZE_RESET_CAPABLE_ROLE = _WIDGET_ID_ROLE + 12
    _CONTENT_ROTATION_CAPABLE_ROLE = _WIDGET_ID_ROLE + 13
    _SELECTED_FOR_CHILD_EDIT_ROLE = _WIDGET_ID_ROLE + 14
    _PRESENTATION_ITEM_ROLE = _WIDGET_ID_ROLE + 15

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
        move_finished_handler: MoveFinishedHandler | None = None,
        display_transfer_capability: DisplayTransferCapability | None = None,
        display_transfer_handler: DisplayTransferHandler | None = None,
        size_reset_handler: SizeResetHandler | None = None,
        content_rotation_handler: ContentRotationHandler | None = None,
        presentation_item_resolver: PresentationItemResolver | None = None,
        child_resize_begin_handler: ChildResizeBeginHandler | None = None,
        child_resize_update_handler: ChildResizeUpdateHandler | None = None,
        child_content_extent_handler: ChildContentExtentHandler | None = None,
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
        self._move_finished_handler = move_finished_handler
        self._display_transfer_capability = display_transfer_capability
        self._display_transfer_handler = display_transfer_handler
        self._size_reset_handler = size_reset_handler
        self._content_rotation_handler = content_rotation_handler
        self._presentation_item_resolver = presentation_item_resolver
        self._child_resize_begin_handler = child_resize_begin_handler
        self._child_resize_update_handler = child_resize_update_handler
        self._child_content_extent_handler = child_content_extent_handler
        self._items: list[CustomLayoutSessionItem] = []
        session.subscribe_changes(self._on_session_item_changed)
        session.subscribe_selection(self._on_session_selection_changed)
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
            self._VIEWPORT_RESIZE_ROLE: QByteArray(b"viewportResizeCapable"),
            self._RESIZE_SCALE_ROLE: QByteArray(b"resizeScale"),
            self._CAN_TRANSFER_LEFT_ROLE: QByteArray(b"canTransferLeft"),
            self._CAN_TRANSFER_RIGHT_ROLE: QByteArray(b"canTransferRight"),
            self._CONTENT_EXTENT_AXES_ROLE: QByteArray(b"contentExtentAxes"),
            self._SIZE_RESET_CAPABLE_ROLE: QByteArray(b"sizeResetCapable"),
            self._CONTENT_ROTATION_CAPABLE_ROLE: QByteArray(b"contentRotationCapable"),
            self._SELECTED_FOR_CHILD_EDIT_ROLE: QByteArray(b"selectedForChildEdit"),
            self._PRESENTATION_ITEM_ROLE: QByteArray(b"presentationItem"),
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
        if role == self._VIEWPORT_RESIZE_ROLE:
            return item.viewport_resize_capable
        if role == self._RESIZE_SCALE_ROLE:
            return float(item.resize_scale)
        if role == self._CAN_TRANSFER_LEFT_ROLE:
            return self._can_transfer(item, "left")
        if role == self._CAN_TRANSFER_RIGHT_ROLE:
            return self._can_transfer(item, "right")
        if role == self._CONTENT_EXTENT_AXES_ROLE:
            return sorted(item.content_extent_axes)
        if role == self._SIZE_RESET_CAPABLE_ROLE:
            return bool(item.size_reset_capable)
        if role == self._CONTENT_ROTATION_CAPABLE_ROLE:
            return bool(item.content_rotation_capable)
        if role == self._SELECTED_FOR_CHILD_EDIT_ROLE:
            session = self._session
            return bool(session is not None and session.selected_item() is item)
        if role == self._PRESENTATION_ITEM_ROLE:
            resolver = self._presentation_item_resolver
            if resolver is None:
                return None
            try:
                target = resolver(item)
                return target if target is not None and _is_valid_qobject(target) else None
            except (RuntimeError, TypeError):
                return None
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

    @Slot(int, float, float, float, float)
    def moveItem(
        self,
        row: int,
        local_x: float,
        local_y: float,
        cursor_local_x: float,
        cursor_local_y: float,
    ) -> None:
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
        cursor = self._global_point(cursor_local_x, cursor_local_y)
        resolved = (
            QRect(resolver(item, proposed, cursor))
            if resolver is not None
            else proposed
        )
        item.set_geometry(resolved)
        session = self._session
        if session is not None:
            session.notify_item_changed(item)

    @Slot(int, result=bool)
    def selectItem(self, row: int) -> bool:
        """Select one parent for transient child/edit-chrome focus."""

        if not 0 <= int(row) < len(self._items):
            return False
        session = self._session
        if session is None:
            return False
        return bool(session.select_item(self._items[int(row)]))

    @Slot()
    def finishMove(self) -> None:
        """Clear transient alignment guides at a move ownership boundary."""

        handler = self._move_finished_handler
        if handler is not None:
            handler()

    @Slot(int, str, result=bool)
    def transferItem(self, row: int, direction: str) -> bool:
        """Move the Visualizer to the adjacent display through the owner seam.

        This is a discrete alternative to dragging across native QQuickWindow
        boundaries. QML supplies only ``left``/``right`` intent; Python owns
        target selection, geometry projection and the retained-scene transfer.
        """

        if not 0 <= int(row) < len(self._items):
            return False
        item = self._items[int(row)]
        direction = str(direction or "").strip().lower()
        if direction not in {"left", "right"} or not self._can_transfer(item, direction):
            return False
        handler = self._display_transfer_handler
        if handler is None or not handler(item, direction):
            return False
        session = self._session
        if session is None:
            return False
        session.notify_item_changed(item)
        return True

    @Slot(int, result=bool)
    def restoreSize(self, row: int) -> bool:
        """Restore one widget's authored size/shape without leaving CUSTOM."""

        if not 0 <= int(row) < len(self._items):
            return False
        item = self._items[int(row)]
        handler = self._size_reset_handler
        if not item.size_reset_capable or handler is None:
            return False
        return bool(handler(item))

    @Slot(int, result=bool)
    def rotateContent(self, row: int) -> bool:
        """Advance one eligible item's layout-owned content quarter-turn."""

        if not 0 <= int(row) < len(self._items):
            return False
        item = self._items[int(row)]
        handler = self._content_rotation_handler
        if not item.content_rotation_capable or handler is None:
            return False
        return bool(handler(item))

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
        session.notify_all_items_changed()
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

        item = self._resize_handle_item(row, corner)
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

        item = self._resize_handle_item(row, corner)
        handler = self._resize_update_handler
        if item is None or handler is None:
            return False
        cursor = self._global_point(local_x, local_y)
        if not handler(item, str(corner), cursor, bool(finalize)):
            return False
        self._notify_resize(item)
        return True

    @Slot(int, str, str, float, float, float, float, result=bool)
    def beginChildResize(
        self,
        row: int,
        role_id: str,
        handle: str,
        local_x: float,
        local_y: float,
        visible_width: float,
        visible_height: float,
    ) -> bool:
        if not 0 <= int(row) < len(self._items):
            return False
        item = self._items[int(row)]
        if item.child_role(role_id) is None:
            return False
        handler = self._child_resize_begin_handler
        if handler is None:
            return False
        cursor = self._global_point(local_x, local_y)
        return bool(
            handler(
                item,
                str(role_id),
                str(handle),
                cursor,
                float(visible_width),
                float(visible_height),
            )
        )

    @Slot(int, str, str, float, float, bool, result=bool)
    def resizeChild(
        self,
        row: int,
        role_id: str,
        handle: str,
        local_x: float,
        local_y: float,
        finalize: bool,
    ) -> bool:
        if not 0 <= int(row) < len(self._items):
            return False
        item = self._items[int(row)]
        if item.child_role(role_id) is None:
            return False
        handler = self._child_resize_update_handler
        if handler is None:
            return False
        cursor = self._global_point(local_x, local_y)
        if not handler(
            item, str(role_id), str(handle), cursor, bool(finalize)
        ):
            return False
        self._notify_resize(item)
        return True

    @Slot(int, str, result="QVariantList")
    def childResizeHandles(self, row: int, role_id: str) -> list[str]:
        """Return descriptor-owned handles for one focused child role."""

        if not 0 <= int(row) < len(self._items):
            return []
        role = self._items[int(row)].child_role(role_id)
        return list(role.resize_handles) if role is not None else []


    @Slot(int, float, float, result=bool)
    def ensureChildContentExtent(
        self, row: int, required_width: float, required_height: float
    ) -> bool:
        """Grow an ordinary parent's logical content box after a child edit.

        Families may report a retained minimum requirement, but QML never owns
        the outer rectangle.  The shared Python owner admits growth only; a
        smaller child never collapses the user's outer CUSTOM geometry.
        """

        if not 0 <= int(row) < len(self._items):
            return False
        item = self._items[int(row)]
        handler = self._child_content_extent_handler
        if handler is None or not item.child_geometry_capable:
            return False
        if not handler(item, float(required_width), float(required_height)):
            return False
        self._notify_resize(item)
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
        self._notify_resize(item)
        return True

    def retire(self) -> None:
        session = self._session
        if session is not None:
            session.unsubscribe_changes(self._on_session_item_changed)
            session.unsubscribe_selection(self._on_session_selection_changed)
        self.beginResetModel()
        self._items = []
        self._session = None
        self._geometry_resolver = None
        self._item_change_publisher = None
        self._resize_begin_handler = None
        self._resize_update_handler = None
        self._resize_wheel_handler = None
        self._move_finished_handler = None
        self._display_transfer_capability = None
        self._display_transfer_handler = None
        self._size_reset_handler = None
        self._content_rotation_handler = None
        self._presentation_item_resolver = None
        self._child_resize_begin_handler = None
        self._child_resize_update_handler = None
        self._child_content_extent_handler = None
        self.endResetModel()

    def _resizable_item(self, row: int) -> CustomLayoutSessionItem | None:
        if not 0 <= int(row) < len(self._items):
            return None
        item = self._items[int(row)]
        return item if item.resize_capable else None

    def _resize_handle_item(
        self,
        row: int,
        handle: str,
    ) -> CustomLayoutSessionItem | None:
        """Gate a resize handle by its semantic role.

        Side handles require their declared viewport/content axis. Existing
        square corners remain available to every resizable item and keep their
        established Visualizer-viewport / ordinary-uniform semantics. Distinct
        ``content_*`` diagonal corners require both ordinary content axes.
        """

        if not 0 <= int(row) < len(self._items):
            return None
        item = self._items[int(row)]
        if _is_viewport_edge_handle(handle):
            if item.viewport_resize_capable:
                return item
            axis = "horizontal" if str(handle) in {"left", "right"} else "vertical"
            return item if axis in item.content_extent_axes else None
        if _is_content_corner_handle(handle):
            return (
                item
                if not item.viewport_resize_capable
                and {"horizontal", "vertical"}.issubset(item.content_extent_axes)
                else None
            )
        return item if item.resize_capable else None

    def _can_transfer(self, item: CustomLayoutSessionItem, direction: str) -> bool:
        if item.model_identity != "spotify_visualizer":
            return False
        capability = self._display_transfer_capability
        return bool(capability is not None and capability(item, str(direction)))

    def _global_point(self, local_x: float, local_y: float) -> QPoint:
        return QPoint(
            self._display_origin.x() + int(round(float(local_x))),
            self._display_origin.y() + int(round(float(local_y))),
        )

    def _notify_resize(self, item: CustomLayoutSessionItem) -> None:
        session = self._session
        if session is not None:
            session.notify_item_changed(item)

    def _on_session_item_changed(self, item: CustomLayoutSessionItem) -> None:
        prior_row = next(
            (index for index, entry in enumerate(self._items) if entry is item),
            None,
        )
        belongs_here = (
            item.current_display_identity == self._display_identity
            and item.current_enabled
            and not item.removed
        )
        if (prior_row is None) != (not belongs_here):
            self.refresh()
            return
        self._publish_item_change(item)
        if prior_row is None:
            return
        model_index = self.index(prior_row, 0)
        self.dataChanged.emit(
            model_index,
            model_index,
            [
                self._GEOMETRY_X_ROLE,
                self._GEOMETRY_Y_ROLE,
                self._GEOMETRY_WIDTH_ROLE,
                self._GEOMETRY_HEIGHT_ROLE,
                self._DUPLICATE_ROLE,
                self._RESIZABLE_ROLE,
                self._VIEWPORT_RESIZE_ROLE,
                self._RESIZE_SCALE_ROLE,
                self._CAN_TRANSFER_LEFT_ROLE,
                self._CAN_TRANSFER_RIGHT_ROLE,
                self._CONTENT_EXTENT_AXES_ROLE,
                self._SIZE_RESET_CAPABLE_ROLE,
                self._CONTENT_ROTATION_CAPABLE_ROLE,
            ],
        )

    def _on_session_selection_changed(
        self,
        _selected: CustomLayoutSessionItem | None,
    ) -> None:
        if not self._items:
            return
        first = self.index(0, 0)
        last = self.index(len(self._items) - 1, 0)
        self.dataChanged.emit(
            first,
            last,
            [self._SELECTED_FOR_CHILD_EDIT_ROLE],
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
        move_finished_handler: MoveFinishedHandler | None = None,
        display_transfer_capability: DisplayTransferCapability | None = None,
        display_transfer_handler: DisplayTransferHandler | None = None,
        size_reset_handler: SizeResetHandler | None = None,
        content_rotation_handler: ContentRotationHandler | None = None,
        presentation_item_resolver: PresentationItemResolver | None = None,
        child_resize_begin_handler: ChildResizeBeginHandler | None = None,
        child_resize_update_handler: ChildResizeUpdateHandler | None = None,
        child_content_extent_handler: ChildContentExtentHandler | None = None,
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
            move_finished_handler=move_finished_handler,
            display_transfer_capability=display_transfer_capability,
            display_transfer_handler=display_transfer_handler,
            size_reset_handler=size_reset_handler,
            content_rotation_handler=content_rotation_handler,
            presentation_item_resolver=presentation_item_resolver,
            child_resize_begin_handler=child_resize_begin_handler,
            child_resize_update_handler=child_resize_update_handler,
            child_content_extent_handler=child_content_extent_handler,
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

    def clear_session(self) -> bool:
        """Clear edit projection, returning False if the retained item was dead."""

        item = self._item
        model = self._model
        self._model = None
        item_alive = False
        if item is not None:
            try:
                item_alive = bool(_is_valid_qobject(item))
            except (RuntimeError, TypeError):
                item_alive = False
        if item_alive:
            item.setProperty("editActive", False)
            item.setProperty("sessionModel", None)
            item.setProperty("verticalGuides", [])
            item.setProperty("horizontalGuides", [])
        if model is not None:
            model.retire()
            try:
                if _is_valid_qobject(model):
                    model.deleteLater()
            except (RuntimeError, TypeError):
                pass
        return item_alive or item is None

    def retire(self) -> None:
        self.clear_session()
        self._item = None
