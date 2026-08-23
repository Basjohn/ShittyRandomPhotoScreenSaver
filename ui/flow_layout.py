"""Responsive wrapping flow layout for Settings capability surfaces (Phase E2).

A width-driven layout: children are placed left-to-right and wrap onto new rows
when the available width is exhausted, recomputing on resize. It is the shared
responsive primitive behind the Widgets/Transitions SETUP surfaces:

- top pill navigation wraps instead of clipping;
- module/activation lists and the Random Pool become responsive grids (more
  columns when width allows, collapsing toward one when genuinely narrow);
- Enable All / Disable All action rows reflow inward and stay reachable.

It never forces its parent wider than the available viewport, so the styled
frame's right border stays visible and no horizontal scrollbar is required.

This is the standard Qt FlowLayout pattern (heightForWidth-driven).
"""
from __future__ import annotations

from PySide6.QtCore import QMargins, QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QLayoutItem, QSizePolicy, QWidget


class FlowContainer(QWidget):
    """A widget hosting a :class:`FlowLayout` that reports height-for-width.

    Nesting a height-for-width layout inside an ordinary QVBoxLayout only works
    when the host widget advertises height-for-width in its size policy and
    forwards the query; a bare ``QWidget`` collapses to one row and clips the
    rest. Use this as the host for wrapping pill/module rows.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        margin: int = 0,
        h_spacing: int = 12,
        v_spacing: int = 10,
    ) -> None:
        super().__init__(parent)
        self._flow = FlowLayout(
            self, margin=margin, h_spacing=h_spacing, v_spacing=v_spacing
        )
        policy = self.sizePolicy()
        policy.setHorizontalPolicy(QSizePolicy.Policy.Preferred)
        policy.setVerticalPolicy(QSizePolicy.Policy.Minimum)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def addWidget(self, widget: QWidget) -> None:
        self._flow.addWidget(widget)

    @property
    def flow(self) -> "FlowLayout":
        return self._flow

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._flow.heightForWidth(width)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self._flow.sizeHint()

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self._flow.minimumSize()


class FlowLayout(QLayout):
    """A layout that arranges child widgets horizontally and wraps as needed."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        margin: int = 0,
        h_spacing: int = 12,
        v_spacing: int = 10,
    ) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self.setContentsMargins(QMargins(margin, margin, margin, margin))

    # --- QLayout plumbing --------------------------------------------------

    def addItem(self, item: QLayoutItem) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:  # noqa: N802
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:  # noqa: N802
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientations:  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(
            margins.left() + margins.right(),
            margins.top() + margins.bottom(),
        )
        return size

    # --- Layout engine -----------------------------------------------------

    def _do_layout(self, rect: QRect, *, test_only: bool) -> int:
        margins = self.contentsMargins()
        effective = rect.adjusted(
            margins.left(), margins.top(), -margins.right(), -margins.bottom()
        )
        x = effective.x()
        y = effective.y()
        line_height = 0

        for item in self._items:
            widget = item.widget()
            if widget is not None and widget.isHidden():
                # Explicitly hidden items (e.g. deactivated pills / pool rows)
                # take no space, so the remaining items reflow to fill the row.
                # isHidden() (not isVisible()) is used so items still lay out
                # before their top-level window is shown.
                continue
            hint = item.sizeHint()
            next_x = x + hint.width() + self._h_spacing
            if next_x - self._h_spacing > effective.right() + 1 and line_height > 0:
                # Wrap to the next row.
                x = effective.x()
                y = y + line_height + self._v_spacing
                next_x = x + hint.width() + self._h_spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())

        return y + line_height - rect.y() + margins.bottom()
