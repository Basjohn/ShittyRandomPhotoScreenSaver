"""R-173: a hidden display scene retiring with a card surface material active.

What this bar protects: the hidden ``QQuickRenderControl`` scene (the Guided Setup
foundry's ``_HiddenQuickScene``, used by every material/preview harness) retires the way a
production display does. The scene graph goes first, so the backdrop's render node frees
its GL with the context current. Then the QML objects, the window, and the render control
go, and the control takes its imported GL context and offscreen surface (its Qt children)
with it. Everything dies inside ``close()``. Before the fix nothing died there
(``deleteLater`` outside an event loop): the Python-owned GL context died first when the
scene object was dropped, and the control's later destruction corrupted the heap. The next
``QWidget()`` (Widgets tab construction) crashed in 1 run in 3-5.
"""
from __future__ import annotations

import gc

import pytest


@pytest.fixture
def material_scene(qt_app):
    from tools.surface_material_capture import MaterialScene

    if qt_app.platformName().lower() != "windows":
        pytest.skip("hidden GL scene needs the Windows QPA")
    return MaterialScene(640, 360)


def test_a_display_retiring_with_a_material_active_frees_everything_in_order(material_scene, qt_app) -> None:
    import shiboken6
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QColor
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtWidgets import QWidget
    from rendering.quick.widgets.host import OverlayCardStyle, OverlayWidgetGeometry

    scene = material_scene
    scene.host.create_widget(object_name="card", model_identity="clock",
                             geometry=OverlayWidgetGeometry(170, 100, 300, 160),
                             card_style=OverlayCardStyle(background_color=QColor(20, 20, 20, 77)))
    scene.presentations = []
    scene.set_material("glass")
    scene.render(4)
    hidden = scene.scene
    node = scene.owner.item._paint_root.node
    assert node.pipeline.output_texture, "the backdrop must hold GL objects before retirement"
    # The imported context and its surface are owned by the render control, not by Python.
    assert hidden.context.parent() is hidden.control and hidden.surface.parent() is hidden.control

    order: list[str] = []
    watched = {"root": hidden.root, "backdrop": scene.owner.item, "window": hidden.window,
               "control": hidden.control, "context": hidden.context, "surface": hidden.surface}
    for name, obj in watched.items():
        obj.destroyed.connect(lambda *_args, name=name: order.append(name))

    hidden.close()     # retire with the material still active (production never parks first)

    assert sorted(order) == sorted(watched), order          # all of it inside close()
    assert order.index("window") < order.index("control") < order.index("context"), order
    assert node._released and node.pipeline.output_texture == 0   # GL freed with the scene graph
    assert not any(shiboken6.isValid(obj) for obj in watched.values())
    del watched, hidden, scene
    gc.collect()

    # Fresh Qt widgets and QML objects in the same process (where the heap damage showed).
    widgets = [QWidget() for _ in range(64)]
    for widget in widgets:
        widget.deleteLater()
    engine = QQmlEngine()
    component = QQmlComponent(engine)
    component.setData(b"import QtQuick\nItem { width: 10; Rectangle { color: 'red' } }", QUrl())
    item = component.create()
    assert item is not None, component.errorString()
    item.deleteLater()
    engine.deleteLater()
    qt_app.processEvents()
