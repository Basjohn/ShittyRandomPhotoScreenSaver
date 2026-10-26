"""Native Quick glyph pixels/hit targets; physical hotplug remains separate."""
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop, QPointF, QTimer, QUrl, Qt
from PySide6.QtGui import QColor
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtTest import QSignalSpy, QTest


def _wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def _find(root, name):
    if root.objectName() == name:
        return root
    for child in root.childItems():
        found = _find(child, name)
        if found is not None:
            return found
    return None


def test_transfer_glyphs_are_absent_when_ineligible_and_use_real_native_hits(qt_app, tmp_path):
    engine = QQmlEngine()
    path = Path(__file__).resolve().parents[1] / "rendering/quick/qml/WidgetHoverEditGlyphs.qml"
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(path)))
    assert component.isReady(), component.errors()
    item = component.create()
    assert isinstance(item, QQuickItem), component.errors()
    window = QQuickWindow()
    screen = qt_app.screens()[-1]
    origin = screen.geometry().topLeft()
    window.setFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                    Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
    window.setGeometry(origin.x()+100, origin.y()+100, 500, 300)
    window.setColor(QColor("#20232c"))
    item.setParentItem(window.contentItem())
    item.setWidth(500)
    item.setHeight(300)
    item.setProperty("admitted", True)
    item.setProperty("hovered", True)
    spy = QSignalSpy(item.actionRequested)
    window.show()
    try:
        _wait(750)
        assert _find(item, "hoverEditGlyph-transfer_left") is None
        assert _find(item, "hoverEditGlyph-transfer_right") is None
        item.setProperty("canTransferRight", True)
        _wait(80)
        left, right = (_find(item, "hoverEditGlyph-transfer_"+direction) for direction in ("left", "right"))
        assert not left.isVisible() and right.isVisible()
        point = right.mapToScene(QPointF(right.width()/2, right.height()/2)).toPoint()
        QTest.mouseMove(window, point)
        _wait(1850)
        assert item.property("activeTip") == "MOVE TO NEXT DISPLAY"
        QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=point)
        assert spy.count() == 1 and spy.at(0) == ["transfer_right"]
        item.setProperty("canTransferLeft", True)
        _wait(100)
        assert left.isVisible() and left.y() == right.y()
        assert left.x() == 500 - right.x() - right.width()
        assert window.grabWindow().save(str(tmp_path / "transfer_glyphs.png"))
        item.setProperty("canTransferRight", False)
        assert item.property("activeTip") == "", "topology loss retires the active tooltip"
        item.setProperty("canTransferRight", True)
        item.setProperty("hovered", False)
        QTest.mouseClick(window, Qt.MouseButton.LeftButton, pos=point)
        assert spy.count() == 1, "a fading glyph must not accept a late click"
        item.setProperty("canTransferLeft", False)
        item.setProperty("canTransferRight", False)
        _wait(20)
        assert _find(item, "hoverEditGlyph-transfer_right") is None
    finally:
        item.setParentItem(None)
        item.deleteLater()
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
