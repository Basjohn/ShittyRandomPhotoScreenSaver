"""An open context menu takes hover too, not only presses.

With only presses blocked, the cursor over the menu still lit the widget row
behind it (hover passed through). The window here is bound to a render control
and never shown; a synthetic mouse move exercises Qt Quick's hover delivery.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt, QUrl
from PySide6.QtGui import QGuiApplication, QMouseEvent
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem, QQuickRenderControl, QQuickWindow

from rendering.quick.bootstrap import quick_qml_root
from rendering.quick.context_menu import QuickContextMenuEntry, QuickContextMenuModel

_SCENE = b"""
import QtQuick
import "QML_ROOT"
Item {
    width: 640; height: 480
    required property var menuModel
    readonly property bool behindHovered: behindHover.hovered
    Rectangle { anchors.fill: parent; color: "transparent"; HoverHandler { id: behindHover } }
    ContextMenu { z: 300; contextMenuModel: menuModel }
}
"""


def _move(window, x: float, y: float) -> None:
    point = QPointF(x, y)
    QGuiApplication.sendEvent(window, QMouseEvent(QEvent.Type.MouseMove, point, point, Qt.MouseButton.NoButton,
                                                  Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier))


@pytest.mark.qt
def test_an_open_menu_keeps_hover_from_the_widgets_behind_it(qt_app) -> None:
    engine = QQmlEngine()
    engine.addImportPath(str(quick_qml_root()))
    control = QQuickRenderControl()
    window = QQuickWindow(control)  # never shown
    window.resize(640, 480)
    model = QuickContextMenuModel(screen_index=0, runtime_generation=1)
    model.replace_entries((QuickContextMenuEntry("settings", "Settings"), QuickContextMenuEntry("edit_layout", "Edit")))
    component = QQmlComponent(engine)
    component.setData(_SCENE.replace(b"QML_ROOT", quick_qml_root().as_uri().encode()), QUrl())
    root = component.createWithInitialProperties({"menuModel": model})
    assert root is not None, component.errorString()
    try:
        root.setParentItem(window.contentItem())
        _move(window, 600.0, 440.0)
        assert root.property("behindHovered") is True  # closed menu: the widget gets hover

        model.open_at(40.0, 40.0)
        control.polishItems()
        # A row, the menu's blank padding, and elsewhere in the scene.
        for x, y in ((120.0, 60.0), (46.0, 44.0), (600.0, 440.0)):
            _move(window, x, y)
            assert root.property("behindHovered") is False, (x, y)

        # The menu's own row still lights under the cursor.
        _move(window, 120.0, 60.0)
        items, pending = [], [root]
        while pending:
            item = pending.pop()
            items.append(item)
            pending.extend(item.childItems())
        row = next(item for item in items if item.inherits("QQuickText")
                   and item.property("text") == "Settings").parentItem()
        assert row.property("color") == root.findChild(QQuickItem, "retainedContextMenu").property("selectedSurfaceColor")
    finally:
        root.setParentItem(None)
        root.deleteLater()
        window.deleteLater()
        control.deleteLater()
        engine.deleteLater()
        qt_app.processEvents()
