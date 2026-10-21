"""Focused native construction smoke for shared hover Edit chrome.

Run from the repo-root .venv with --noconftest and pytest_qt_noenv.
No display runtime, build, global settings or environment mutations.
"""
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem, QQuickWindow

QML = Path(__file__).resolve().parents[1] / 'rendering' / 'quick' / 'qml'


def _create(name):
    engine = QQmlEngine()
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(QML / name)))
    assert component.isReady(), '\n'.join(map(str, component.errors()))
    item = component.create()
    assert isinstance(item, QQuickItem), '\n'.join(map(str, component.errors()))
    return engine, component, item


def test_hover_edit_glyph_component_constructs_and_admits_lock(qt_app):
    engine, component, item = _create('WidgetHoverEditGlyphs.qml')
    # A detached zero-sized QQuickItem is not a valid scene-visibility probe.
    # Check the effective property only after attaching to a real Quick scene.
    window = QQuickWindow()
    item.setParentItem(window.contentItem())
    item.setWidth(180)
    item.setHeight(110)
    window.show()
    qt_app.processEvents()
    try:
        assert not item.isVisible()
        item.setProperty('admitted', True)
        item.setProperty('canLock', True)
        item.setProperty('hovered', True)
        qt_app.processEvents()
        assert item.isVisible()
        assert item.property('canLock') is True
        assert item.property('canRestore') is False
        def walk_qquick(root):
            yield root
            for child in root.childItems():
                yield from walk_qquick(child)
        assert any(child.objectName() == 'hoverEditGlyph-lock' and child.isVisible()
                   for child in walk_qquick(item)), 'admitted Lock must have a real visible QQuick delegate'
        item.setProperty('hovered', False)
        qt_app.processEvents()
        assert item.property('hovered') is False
    finally:
        item.setParentItem(None)
        item.deleteLater()
        window.close()
        window.deleteLater()
        qt_app.processEvents()


def test_existing_ordinary_and_visualizer_roots_load_shared_glyphs(qt_app):
    for name, expected in (
        ('OverlayWidget.qml', 'ordinaryHoverEditGlyphs'),
        ('VisualizerPresentation.qml', 'visualizerHoverEditGlyphs'),
    ):
        engine, component, item = _create(name)
        try:
            # A Loader keeps four glyph items entirely absent at idle.
            assert item.findChild(QQuickItem, expected) is None
            assert not item.property('widgetGlowAdmitted')
            if name == 'OverlayWidget.qml':
                item.setProperty('hoverEditEligible', True)
            else:
                item.setProperty('presentationActive', True)
            item.setProperty('widgetGlowAdmitted', True)
            qt_app.processEvents()
            assert item.findChild(QQuickItem, expected) is not None
        finally:
            item.deleteLater()
            qt_app.processEvents()
