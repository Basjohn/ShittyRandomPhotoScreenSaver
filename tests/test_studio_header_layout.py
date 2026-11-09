"""Header hit areas stay disjoint at the native Studio minimum; never render or show a window."""
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPointF, QCoreApplication, QEvent
from PySide6.QtQuick import QQuickItem, QQuickWindow

from ui.studio.registry import create_adapter, studio_modes


class Store:
    def __init__(self, mode):
        from core.settings.visualizer_presets import resolve_visualizer_activation_payload
        self.values = resolve_visualizer_activation_payload({"mode": mode, f"preset_{mode}": 0}).resolved_config

    def snapshot(self):
        return self.values

    def commit(self, values, changed):
        self.values.update(values)
        return self.values

    def preset_label(self):
        return "A deliberately long preset title for camera authoring"

    def presets(self):
        return [self.preset_label(), "Custom"]

    def preset_index(self):
        return 0

    def save_current(self):
        pass

    def save_camera(self, values):
        pass


@pytest.fixture
def header(qt_app):
    from ui.studio.controller import StudioBridge, StudioController
    from ui.studio.session import StudioEditSession
    from ui.studio.surface import StudioShellHost
    built = []

    def build(mode, *, multiple=True, store=None, dirty=False):
        adapter = create_adapter(mode)
        store = Store(mode) if store is None else store
        modes = lambda: tuple((m.mode_id, m.title) for m in studio_modes()) if multiple else ()
        controller = StudioController(adapter, store, SimpleNamespace(), lambda c: None, modes=modes)
        controller.session = StudioEditSession(adapter.schema(), store)
        controller.evaluator = adapter.create_evaluator()
        if dirty:
            from ui.studio.schema import SCALAR
            prop = next(p for p in controller.session.schema.properties
                        if p.instrument == SCALAR and len(p.path) == 1 and not p.view_pose)
            current = controller.session.values[prop.path[0]]
            target = prop.minimum if current != prop.minimum else prop.maximum
            controller.session.set(prop.path, target, "Header edit")
        controller.bridge = StudioBridge(controller)
        window = QQuickWindow()
        window.resize(960, 600)                 # StudioWindowSurface's declared minimum
        host = StudioShellHost(window, controller.bridge, lambda: None)
        # An unshown window has no scene update to polish its Row positioners. Polish only geometry,
        # children first, until nested implicit sizes have propagated; never request or render a frame.
        def polish(item):
            for child in item.childItems():
                polish(child)
            item.ensurePolished()
        for _ in range(3):
            polish(host.root)
            QCoreApplication.processEvents()
        built.append((controller, window, host))
        return controller, host.root

    yield build
    for controller, window, host in built:
        host.retire()
        window.deleteLater()
        host.release_engine()
        controller.evaluator.release()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qt_app.processEvents()


def _named(root, name):
    return root.findChild(QQuickItem, name)


def _rect(item):
    point = item.mapToScene(QPointF(0., 0.))
    return point.x(), point.y(), point.x() + item.width(), point.y() + item.height()


def _overlaps(a, b):
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


@pytest.mark.parametrize("mode", [entry.mode_id for entry in studio_modes()])
@pytest.mark.parametrize("multiple", (False, True))
@pytest.mark.parametrize("dirty", (False, True))
def test_header_hit_areas_fit_at_native_minimum(header, mode, multiple, dirty):
    controller, root = header(mode, multiple=multiple, dirty=dirty)
    actions = [_named(root, name) for name in ("presetPill", "saveCameraButton", "savePresetAsButton", "saveCurrentButton", "closeButton")]
    mode_item = _named(root, "studioModePicker" if multiple else "studioTitle")
    assert mode_item is not None
    actions.append(mode_item)
    rects = [_rect(item) for item in actions]
    for item, rect in zip(actions, rects):
        assert rect[0] >= 0 and rect[2] <= 960, (mode, item.objectName(), rect)
    for i, first in enumerate(rects):
        for j, second in enumerate(rects[i + 1:], start=i + 1):
            assert not _overlaps(first, second), (mode, actions[i].objectName(), actions[j].objectName(), first, second)


def test_store_without_save_actions_has_disabled_buttons_and_explains_direct_requests(header):
    store = Store("sphere")
    store.save_current = None
    store.save_camera = None
    controller, root = header("sphere", store=store)
    assert not controller.bridge.canSave and not controller.bridge.canSaveCamera
    assert not _named(root, "saveCurrentButton").property("enabledState")
    assert not _named(root, "saveCameraButton").property("enabledState")
    notices = []
    controller.bridge.notify = lambda message: notices.append(message)
    controller.bridge.saveCurrent()
    controller.bridge.saveCamera()
    assert len(notices) == 2 and all("not available" in message for message in notices)
