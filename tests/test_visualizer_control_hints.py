"""Native retained hover expiry and General global-option save ownership.

Use --noconftest -p tools.pytest_qt_noenv; no environment/profile mutations.
"""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest
from PySide6.QtCore import QPoint, QUrl, Qt, QObject, QCoreApplication, QEvent
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtTest import QTest

from core.settings import SettingsManager
from core.settings.models import InputSettings
from core.settings.default_contract import require_canonical_default
from rendering.quick.scene_controller import QuickSceneController
from rendering.quick.state import QuickInputState
from ui.resources.registration import ensure_core_resources

ROOT = Path(__file__).resolve().parents[1]


def test_hint_option_canonical_model_and_cached_scene_projection(qt_app, tmp_path):
    settings = SettingsManager(organization="Test", application="Hints_"+uuid.uuid4().hex,
                               storage_base_dir=tmp_path)
    original = bool(require_canonical_default("input.show_3d_control_hints"))
    assert InputSettings.from_settings(settings).show_3d_control_hints == original
    desired = not original  # test-authored edit, independent of current defaults
    settings.set("input.show_3d_control_hints", desired)
    options = InputSettings.from_settings(settings)
    assert options.to_dict()["input.show_3d_control_hints"] == desired

    from rendering.quick.input_controller import QuickInputController
    controller = QuickInputController(screen_index=0, runtime_generation=1)
    cached = dict(on_hover=False, on_click=False, intensity=0., color=(0,0,0,0),
                  show_3d_control_hints=options.show_3d_control_hints)
    assert controller.configure_widget_glow(**cached)
    assert controller.input_state.show_3d_control_hints == desired
    assert not controller.configure_widget_glow(**cached)
    controller.close_input()
    controller.deleteLater()

    class Root:
        def __init__(self): self.values = {}
        def property(self, name): return self.values.get(name)
        def setProperty(self, name, value): self.values[name] = value
    root = Root()
    state = QuickInputState(0, 1, interaction_mode_enabled=True, show_3d_control_hints=False)
    QuickSceneController._apply_visualizer_input_state(SimpleNamespace(_visualizer_root=root), state)
    assert root.values["show3DControlHints"] is False
    assert root.values["widgetGlowAdmitted"] is True
    QuickSceneController._apply_visualizer_input_state(SimpleNamespace(_visualizer_root=root),
        replace(state, context_menu_active=True, show_3d_control_hints=True))
    assert root.values["show3DControlHints"] is True
    assert root.values["widgetGlowAdmitted"] is False


def test_general_controls_defer_save_and_survive_reopen_reset(qt_app, tmp_path):
    from ui.tabs.widgets_tab import WidgetsTab
    from ui.tabs.display_tab import DisplayTab
    settings = SettingsManager(organization="Test", application="HintGeneral_"+uuid.uuid4().hex,
                               storage_base_dir=tmp_path)
    def open_tab():
        return WidgetsTab(settings, lazy_sections=True, initial_view_state={"subtab_id":"defaults"})
    default_glyphs = bool(require_canonical_default("input.always_show_glyphs"))
    default_hints = bool(require_canonical_default("input.show_3d_control_hints"))
    edited_glyphs, edited_hints = not default_glyphs, not default_hints
    tab = open_tab()
    try:
        assert tab.always_show_glyphs_check.isChecked() == default_glyphs
        assert tab.show_3d_control_hints_check.isChecked() == default_hints
        tab.always_show_glyphs_check.setChecked(edited_glyphs)
        tab.show_3d_control_hints_check.setChecked(edited_hints)
        # Deferred save must not change stored values until flush.
        assert settings.get_bool("input.show_3d_control_hints") == default_hints
        assert settings.get_bool("input.always_show_glyphs") == default_glyphs
        tab.flush_pending_changes()
        assert settings.get_bool("input.show_3d_control_hints") == edited_hints
        assert settings.get_bool("input.always_show_glyphs") == edited_glyphs
    finally:
        tab.deleteLater()
        qt_app.processEvents()
    display = DisplayTab(settings)
    try:
        assert not hasattr(display, "always_show_glyphs_check")
        display._save_settings()
        assert settings.get_bool("input.always_show_glyphs") == edited_glyphs
    finally:
        display.deleteLater()
        qt_app.processEvents()
    assert settings.flush(timeout=2.)
    reopened = SettingsManager(organization="Test", application=settings.get_application_name(),
                               storage_base_dir=tmp_path)
    assert InputSettings.from_settings(reopened).show_3d_control_hints == edited_hints
    assert InputSettings.from_settings(reopened).always_show_glyphs == edited_glyphs
    tab = open_tab()
    try:
        assert tab.always_show_glyphs_check.isChecked() == edited_glyphs
        assert tab.show_3d_control_hints_check.isChecked() == edited_hints
        settings.reset_to_defaults()
        tab.load_from_settings()
        assert tab.always_show_glyphs_check.isChecked() == default_glyphs
        assert tab.show_3d_control_hints_check.isChecked() == default_hints
    finally:
        tab.deleteLater()
        qt_app.processEvents()


@pytest.fixture
def hint_scene(qt_app):
    ensure_core_resources()
    engine = QQmlEngine()
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(ROOT/"rendering/quick/qml/VisualizerPresentation.qml")))
    assert component.isReady(), "\n".join(map(str, component.errors()))
    root = component.create()
    assert isinstance(root, QQuickItem)
    window = QQuickWindow()
    window.resize(700, 480)
    root.setParentItem(window.contentItem())
    root.setWidth(640)
    root.setHeight(420)
    for key, value in {"presentationActive":True, "controlHintsAvailable":True,
                       "widgetGlowAdmitted":True, "cardBackgroundColor":"#30445c"}.items():
        root.setProperty(key, value)
    window.show()
    assert QTest.qWaitForWindowExposed(window)
    QTest.mouseMove(window, QPoint(680,460))
    QTest.qWait(50)
    observer = window.contentItem().findChild(QObject, "visualizerControlHintWindowHover")
    assert observer is not None
    try:
        yield window, root
    finally:
        import shiboken6
        observers = window.contentItem().findChildren(QObject, "visualizerControlHintWindowHover")
        root.setParentItem(None)
        root.deleteLater()
        QCoreApplication.sendPostedEvents(root, QEvent.Type.DeferredDelete)
        for observer in observers:
            if shiboken6.isValid(observer):
                QCoreApplication.sendPostedEvents(observer, QEvent.Type.DeferredDelete)
            assert not shiboken6.isValid(observer), "window-level hover observer outlived its QML component"
        window.close()
        window.deleteLater()
        qt_app.processEvents()


def test_native_hover_expires_without_internal_movement_restart_and_reenters(hint_scene):
    window, root = hint_scene
    hint = root.findChild(QQuickItem, "visualizerControlHint")
    QTest.mouseMove(window, QPoint(200,150))
    QTest.qWait(850)
    assert root.property("controlHintHovered") is True
    assert hint.opacity() > .85
    assert hint.isEnabled() is False
    assert hint.x() > root.width()*.8 and hint.y() >= 12
    assert 48 <= hint.width() <= 84
    assert hint.implicitWidth() == 332 and hint.implicitHeight() == 468
    QTest.qWait(2200)
    QTest.mouseMove(window, QPoint(260,180))
    QTest.qWait(3100)
    assert root.property("controlHintHovered") is True
    assert hint.opacity() == pytest.approx(0., abs=.005)
    QTest.mouseMove(window, QPoint(680,460))
    QTest.qWait(400)
    QTest.mouseMove(window, QPoint(220,160))
    QTest.qWait(850)
    assert hint.opacity() > .85


def test_native_hint_admission_suppresses_edit_menu_borderless_other_mode_and_toggle(hint_scene):
    window, root = hint_scene
    hint = root.findChild(QQuickItem, "visualizerControlHint")
    QTest.mouseMove(window, QPoint(200,150))
    QTest.qWait(850)
    assert hint.isVisible()
    # A real content MouseArea still receives clicks through the artwork.
    content = root.findChild(QQuickItem, "visualizerContentHost")
    engine = QQmlEngine.contextForObject(root).engine()
    component = QQmlComponent(engine)
    component.setData(b'import QtQuick; MouseArea { anchors.fill: parent; property int presses: 0; onPressed: presses += 1 }', QUrl())
    area = component.create()
    area.setParentItem(content)
    QTest.mouseClick(window, Qt.MouseButton.LeftButton,
                     pos=QPoint(round(hint.x()+hint.width()/2), round(hint.y()+hint.height()/2)))
    assert area.property("presses") == 1
    for key in ("show3DControlHints", "controlHintsAvailable", "volumeWheelEnabled",
                "widgetGlowAdmitted", "cardShellEnabled", "presentationActive"):
        root.setProperty(key, False)
        QTest.qWait(30)
        assert not hint.isVisible(), key
        assert root.property("controlHintEligible") is False
        root.setProperty(key, True)
        QTest.qWait(30)
    # Hints are independently switchable; turning off action glyphs does not
    # disable the hint's nonblocking hover observation.
    root.setProperty("alwaysShowGlyphs", False)
    QTest.qWait(850)
    assert hint.isVisible()


def _manager_method(name):
    import ast
    import weakref
    tree = ast.parse((ROOT/"engine/display_manager.py").read_text(encoding="utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "DisplayManager")
    node = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == name)
    scope = {"QuickDisplayUnit": object, "weakref": weakref}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), "<actual manager method>", "exec"), scope)
    return scope[name]


@pytest.mark.parametrize("mode,retired,expected", [
    ("extruded_bubble",False,True), ("shockwave_grid",False,True),
    ("bubble",False,False), (None,False,False), ("extruded_bubble",True,False),
])
def test_new_display_bind_seeds_hint_capability_with_existing_owner(mode, retired, expected):
    from tests.test_neon_settings_lifecycle_and_editor import FakeUnit
    unit = FakeUnit()
    projected = {}
    unit.runtime.input_controller.set_framed_flight_enabled = lambda value: None
    unit.runtime.input_controller.set_scene_transform_enabled = lambda value, **kw: projected.update(transform=value)
    unit.runtime.scene_controller.set_visualizer_camera_reset_available = lambda value: None
    unit.runtime.scene_controller.set_visualizer_control_hints_available = lambda value: projected.update(hint=value)

    class Manager:
        _quick_view_orbit_admitted = _manager_method("_quick_view_orbit_admitted")
        _configure_quick_visualizer_input_admission = _manager_method("_configure_quick_visualizer_input_admission")
        def __init__(self):
            self._quick_visualizer_owner = None if mode is None else SimpleNamespace(
                is_retired=retired, controller=SimpleNamespace(mode_id=mode))
            self._quick_readiness_by_screen = {}
            self._quick_custom_layout_owner = SimpleNamespace(undo_last_change=lambda: None)
        def __getattr__(self, name):
            if name in ("previous_requested", "next_requested", "cycle_transition_requested", "jedi_mode_requested"):
                return SimpleNamespace(emit=lambda *a: None)
            return lambda *a, **kw: None
    _manager_method("_connect_quick_runtime")(Manager(), unit, startup_generation=0)
    assert projected == {"hint":expected, "transform":expected}


def test_lazy_visualizer_root_retains_initial_hint_capability(qt_app):
    from rendering.quick.scene_controller import QuickSceneFactory
    from rendering.quick.state import QuickWindowPolicy
    from rendering.quick.window import QuickDisplayWindow
    factory = QuickSceneFactory()
    window = QuickDisplayWindow(screen_index=0, runtime_generation=0, screen=qt_app.primaryScreen(),
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False))
    scene = QuickSceneController(window=window, factory=factory)
    try:
        assert scene._visualizer_root is None
        scene.set_visualizer_control_hints_available(True)
        scene._ensure_visualizer_items()
        assert scene._visualizer_root.property("controlHintsAvailable") is True
        scene.set_visualizer_control_hints_available(False)
        assert scene._visualizer_root.property("controlHintsAvailable") is False
    finally:
        scene.quiesce_for_retirement()
        window.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()


def test_native_menu_ctrl_changes_do_not_restart_current_or_expired_visit(hint_scene):
    window, root = hint_scene
    hint = root.findChild(QQuickItem, "visualizerControlHint")
    QTest.mouseMove(window, QPoint(200,150))
    QTest.qWait(850)
    assert hint.opacity() > .85
    # Both menu visibility and Ctrl/interaction admission project through this
    # existing flag. The pointer remains physically inside throughout.
    for iteration in range(2):
        root.setProperty("widgetGlowAdmitted", False)
        # A retained menu can cover the card with another hover-enabled input
        # surface. It must not manufacture a new physical visit on dismissal.
        cover = None
        if iteration == 0:
            component = QQmlComponent(QQmlEngine.contextForObject(root).engine())
            component.setData(b'import QtQuick; MouseArea { width: 640; height: 420; z: 100; hoverEnabled: true }', QUrl())
            cover = component.create()
            cover.setParentItem(window.contentItem())
            QTest.mouseMove(window, QPoint(205,155))
        QTest.qWait(600)
        assert not hint.isVisible()
        assert root.property("controlHintVisitStarted") is True
        if cover is not None:
            cover.setParentItem(None)
            cover.deleteLater()
        root.setProperty("widgetGlowAdmitted", True)
        QTest.qWait(600)
    QTest.qWait(3000)
    assert root.property("controlHintHovered") is True
    assert hint.opacity() == pytest.approx(0., abs=.005)
    root.setProperty("widgetGlowAdmitted", False)
    QTest.qWait(50)
    root.setProperty("widgetGlowAdmitted", True)
    QTest.qWait(850)
    assert hint.opacity() == pytest.approx(0., abs=.005)
    # A genuine exit/re-entry while suppressed rearms the next admitted visit.
    root.setProperty("widgetGlowAdmitted", False)
    QTest.mouseMove(window, QPoint(680,460))
    QTest.qWait(60)
    QTest.mouseMove(window, QPoint(220,160))
    QTest.qWait(60)
    root.setProperty("widgetGlowAdmitted", True)
    QTest.qWait(850)
    assert hint.opacity() > .85


def test_native_disabled_hidden_and_retired_hint_observer_is_dormant_and_rearms(hint_scene):
    import shiboken6
    window, root = hint_scene
    hint = root.findChild(QQuickItem, "visualizerControlHint")
    loader = root.findChild(QQuickItem, "visualizerControlHintVisitObserver")
    for key in ("show3DControlHints", "presentationActive", "controlHintsAvailable"):
        QTest.mouseMove(window, QPoint(680,460))
        QTest.qWait(40)
        QTest.mouseMove(window, QPoint(200,150))
        QTest.qWait(850)
        assert root.property("controlHintVisitStarted") is True
        assert hint.opacity() > .85
        observer = window.contentItem().findChild(QObject, "visualizerControlHintWindowHover")
        assert observer is not None
        root.setProperty(key, False)
        QTest.qWait(40)
        assert root.property("controlHintVisitTracking") is False
        assert root.property("controlHintVisitStarted") is False
        assert root.property("controlHintOpacity") == 0.
        assert loader.property("active") is False
        assert loader.property("item") is None
        if shiboken6.isValid(observer):
            QCoreApplication.sendPostedEvents(observer, QEvent.Type.DeferredDelete)
        assert not shiboken6.isValid(observer), key
        # Pointer movement while disabled has no hint handler to invoke.
        QTest.mouseMove(window, QPoint(240,180))
        QTest.qWait(40)
        assert window.contentItem().findChild(QObject, "visualizerControlHintWindowHover") is None
        QTest.mouseMove(window, QPoint(680,460))
        root.setProperty(key, True)
        QTest.qWait(40)
        assert loader.property("active") is True
        assert root.property("controlHintVisitStarted") is False
        QTest.mouseMove(window, QPoint(220,160))
        QTest.qWait(850)
        assert root.property("controlHintVisitStarted") is True
        assert hint.opacity() > .85
