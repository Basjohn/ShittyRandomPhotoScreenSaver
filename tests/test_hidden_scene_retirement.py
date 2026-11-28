"""R-173: a hidden display scene retiring with a card surface material active.

What this bar protects: the hidden scene every material/preview harness draws in (since N5.2h the production
``DisplayScene`` in the process's hidden host of the native core, ``tools.surface_material_capture.NativeHiddenScene``)
retires the way a production display does, with the material still active (production never parks first). The QML
objects go inside ``close()`` (deferred deletions delivered there: outside an event loop nothing else delivers them),
and the core frees the backdrop's item, its pyramid and the pyramid's QRhi objects at the sync after them. Before the
R-173 fix nothing died inside ``close()`` and the late teardown corrupted the heap: the next ``QWidget()`` (Widgets tab
construction) crashed in 1 run in 3-5, so the bar ends by building fresh widgets and QML in the same process.
"""
from __future__ import annotations

import gc

import pytest

_BACKDROP_COUNTS = ("backdrop_items", "backdrop_pyramids", "backdrop_resources")
# The background layer's item, its surface and its photo: the core frees them at the same sync.
_LAYER_COUNTS = ("items", "surfaces", "surface_resources", "mode_sources", "mode_resources", "mode_textures")


@pytest.fixture
def material_scene(qt_app):
    from tools.surface_material_capture import MaterialScene

    if qt_app.platformName().lower() != "windows":
        pytest.skip("the hidden native host needs the Windows QPA")
    return MaterialScene(640, 360)


def test_a_display_retiring_with_a_material_active_frees_everything_in_order(material_scene, qt_app) -> None:
    import shiboken6
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QColor
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtWidgets import QWidget
    from rendering.quick import bootstrap
    from rendering.quick.widgets.host import OverlayCardStyle, OverlayWidgetGeometry

    from rendering.quick.image_state import PresentationImage

    scene = material_scene
    width, height = scene.scene.width, scene.scene.height
    scene.set_wallpaper(PresentationImage("retirement-wallpaper", "", (float(width), float(height)), 1.0,
                                          (width, height), width * 4, bytes((40, 60, 90, 255)) * (width * height)))
    scene.host.create_widget(object_name="card", model_identity="clock",
                             geometry=OverlayWidgetGeometry(170, 100, 300, 160),
                             card_style=OverlayCardStyle(background_color=QColor(20, 20, 20, 77)))
    scene.presentations = []
    scene.set_material("glass")
    scene.render(4)
    core = bootstrap.native_core()
    live = core.composite_live()
    missing = [key for key in _BACKDROP_COUNTS + _LAYER_COUNTS if not live.get(key)]
    assert not missing, f"the backdrop and the layer must hold their objects before retirement: {missing}"
    hidden = scene.scene

    order: list[str] = []
    watched = {"root": hidden.root, "backdrop": scene.owner.item, "context": hidden.qml_context,
               "owner": hidden.owner}
    for name, obj in watched.items():
        obj.destroyed.connect(lambda *_args, name=name: order.append(name))

    hidden.close()     # retire with the material still active (production never parks first)

    assert sorted(order) == sorted(watched), order          # all of it inside close()
    assert order.index("backdrop") < order.index("context"), order   # the items before the context they bind
    # The backdrop item is the core's (wrapped from its address, so shiboken never learns of its deletion): its
    # destroyed signal above and the core's counts below are its proof.
    assert not [name for name, obj in watched.items() if name != "backdrop" and shiboken6.isValid(obj)]
    live = core.composite_live()
    held = {key: live.get(key) for key in _BACKDROP_COUNTS + _LAYER_COUNTS if live.get(key)}
    assert not held, f"the core frees the backdrop and the layer at the sync after close(): {held}"
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
