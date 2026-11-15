"""The hover glyph set fades out over time and any glyph brings it back (plan 1D.12 B).

One ``HoverGlyphReveal`` per card owns the dwell: card hover reveals the set, after a hold with no glyph under the
pointer it fades out while the card is still hovered, the pointer over any glyph fades the whole set back in and holds
it, and leaving the card keeps the glyphs' own fade-out. A faded glyph stays live. The production QML runs in a
Quick window bound to a render control and never shown; synthetic mouse events exercise Qt Quick's own hover
delivery (``tests/test_visualizer_control_hints.py``). The timings are read from the owner, never pinned here.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, QSizeF, Qt, QUrl
from PySide6.QtGui import QGuiApplication, QMouseEvent
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem, QQuickRenderControl, QQuickWindow
from PySide6.QtTest import QTest

from ui.resources.registration import ensure_core_resources

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "rendering" / "quick" / "qml"
OUTSIDE = QPoint(690, 470)


def _move(window, point) -> None:
    position = QPointF(point)
    QGuiApplication.sendEvent(window, QMouseEvent(QEvent.Type.MouseMove, position, position, Qt.MouseButton.NoButton,
                                                  Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier))


def _frame(window) -> None:
    window._render_control.polishItems()


def _host(qt_app, qml: str, properties: dict, size=(640, 420)):
    ensure_core_resources()
    engine = QQmlEngine()
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(QML / qml)))
    assert component.isReady(), "\n".join(map(str, component.errors()))
    root = component.create()
    assert isinstance(root, QQuickItem)
    control = QQuickRenderControl()
    window = QQuickWindow(control)          # bound to a render control and never shown
    window._render_control = control
    window._component = component           # the created root lives as long as its component
    window.resize(700, 480)
    window.contentItem().setSize(QSizeF(700, 480))
    root.setParentItem(window.contentItem())
    root.setWidth(size[0])
    root.setHeight(size[1])
    for key, value in properties.items():
        root.setProperty(key, value)
    _frame(window)
    _move(window, OUTSIDE)
    QTest.qWait(50)
    assert not window.isVisible()
    return engine, control, window, root


def _close(qt_app, engine, control, window, root) -> None:
    root.setParentItem(None)
    root.deleteLater()
    QCoreApplication.sendPostedEvents(root, QEvent.Type.DeferredDelete)
    window.deleteLater()
    control.deleteLater()
    engine.deleteLater()
    qt_app.processEvents()


@pytest.fixture
def visualizer(qt_app):
    host = _host(qt_app, "VisualizerPresentation.qml", {
        "presentationActive": True, "widgetGlowAdmitted": True, "alwaysShowGlyphs": True,
        "cameraResetAvailable": True, "cardBackgroundColor": "#30445c"})
    try:
        yield host[2], host[3]
    finally:
        _close(qt_app, *host)


@pytest.fixture
def ordinary(qt_app):
    host = _host(qt_app, "OverlayWidget.qml", {
        "widgetGlowAdmitted": True, "alwaysShowGlyphs": True, "hoverEditEligible": True,
        "hoverRestoreEligible": True, "authoredCardWidth": 400.0}, size=(400, 200))
    try:
        yield host[2], host[3]
    finally:
        _close(qt_app, *host)


def _find(root, name) -> QQuickItem | None:
    """The visual tree, not QObject children: Repeater delegates and Loader items are found too."""
    found = root.findChild(QQuickItem, name)
    if found is not None:
        return found
    stack = [root]
    while stack:
        item = stack.pop()
        if item.objectName() == name:
            return item
        stack.extend(item.childItems())
    return None


def _named(root, name) -> QQuickItem:
    item = _find(root, name)
    assert item is not None, name
    return item


def _centre(window, item) -> QPoint:
    point = item.mapToItem(window.contentItem(), QPointF(item.width() / 2.0, item.height() / 2.0))
    return QPoint(round(point.x()), round(point.y()))


def _effective(item) -> float:
    """What the glyph draws at: its own opacity times every ancestor's."""
    value = 1.0
    while item is not None:
        value *= float(item.opacity())
        item = item.parentItem()
    return value


def _dwell(reveal) -> int:
    return int(reveal.property("fadeInMs")) + int(reveal.property("holdMs")) + int(reveal.property("fadeOutMs"))


def _check_dwell(window, root, reveal, glyph, card_point, qtbot) -> None:
    timeout = _dwell(reveal) + 1500
    _move(window, card_point)
    qtbot.waitUntil(lambda: _effective(glyph) > 0.8, timeout=2000)            # card hover reveals the set
    qtbot.waitUntil(lambda: _effective(glyph) < 0.01, timeout=timeout)         # the dwell fades it, still hovered
    qtbot.waitUntil(lambda: float(reveal.property("level")) == 0.0, timeout=timeout)   # fully out
    QTest.qWait(int(reveal.property("fadeOutMs")))          # it stays out: any glyph-own easing has long settled
    assert _effective(glyph) < 0.01
    assert reveal.property("cardHovered") is True
    assert reveal.property("animating") is False                               # out: nothing runs
    assert glyph.isEnabled()                                                   # a faded glyph stays live
    assert float(glyph.opacity()) > 0.8                                        # its own hover opacity is unchanged
    _move(window, _centre(window, glyph))                                      # pointer over any glyph
    qtbot.waitUntil(lambda: _effective(glyph) > 0.8, timeout=2000)
    QTest.qWait(_dwell(reveal) + 300)                                          # held while a glyph is hovered
    assert _effective(glyph) > 0.8
    assert reveal.property("animating") is False                               # holding: nothing runs
    _move(window, card_point)                                                  # off the glyph, still on the card
    qtbot.waitUntil(lambda: _effective(glyph) < 0.01, timeout=timeout)
    _move(window, _centre(window, glyph))
    qtbot.waitUntil(lambda: _effective(glyph) > 0.8, timeout=2000)
    _move(window, OUTSIDE)                                                     # leaving the card: today's fade-out
    qtbot.waitUntil(lambda: _effective(glyph) < 0.01, timeout=3000)
    assert reveal.property("cardHovered") is False
    assert reveal.property("animating") is False                               # at rest: nothing runs


@pytest.mark.qt
def test_visualizer_row_glyphs_dwell_out_and_a_glyph_brings_the_set_back(visualizer, qtbot):
    window, root = visualizer
    reveal = _named(root, "visualizerHoverGlyphReveal")
    glyph = _named(root, "visualizerCameraResetGlyph")
    _check_dwell(window, root, reveal, glyph, QPoint(200, 150), qtbot)


@pytest.mark.qt
def test_visualizer_edit_glyphs_share_the_cards_dwell(visualizer, qtbot):
    window, root = visualizer
    reveal = _named(root, "visualizerHoverGlyphReveal")
    _move(window, QPoint(200, 150))
    qtbot.waitUntil(lambda: _find(root, "hoverEditGlyph-restore") is not None, timeout=2000)
    restore = _named(root, "hoverEditGlyph-restore")
    row = _named(root, "visualizerCameraResetGlyph")
    qtbot.waitUntil(lambda: _effective(restore) > 0.8 and _effective(row) > 0.8, timeout=2000)
    qtbot.waitUntil(lambda: _effective(restore) < 0.01 and _effective(row) < 0.01, timeout=_dwell(reveal) + 1500)
    _move(window, _centre(window, restore))                 # an Edit glyph brings the row back too: one set
    qtbot.waitUntil(lambda: _effective(restore) > 0.8 and _effective(row) > 0.8, timeout=2000)


@pytest.mark.qt
def test_ordinary_card_glyphs_dwell_out_and_a_glyph_brings_the_set_back(ordinary, qtbot):
    window, root = ordinary
    reveal = _named(root, "ordinaryHoverGlyphReveal")
    _move(window, QPoint(200, 60))
    qtbot.waitUntil(lambda: _find(root, "hoverEditGlyph-close") is not None, timeout=2000)
    glyph = _named(root, "hoverEditGlyph-close")
    _check_dwell(window, root, reveal, glyph, QPoint(200, 60), qtbot)


@pytest.mark.qt
def test_without_show_glyphs_nothing_reveals_or_runs(visualizer, qtbot):
    """Negative control: the owner never runs while its card's glyph set is not admitted."""
    window, root = visualizer
    root.setProperty("alwaysShowGlyphs", False)
    reveal = _named(root, "visualizerHoverGlyphReveal")
    glyph = _named(root, "visualizerCameraResetGlyph")
    _move(window, QPoint(200, 150))
    QTest.qWait(300)
    assert reveal.property("cardHovered") is False
    assert reveal.property("animating") is False
    assert _effective(glyph) < 0.01
