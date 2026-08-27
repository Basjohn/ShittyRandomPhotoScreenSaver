"""G2 gates for the retained, session-backed CUSTOM edit overlay."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QObject, QPoint, QRect
from PySide6.QtGui import QColor
from PySide6.QtQuick import QQuickItem

from rendering.custom_layout_session import (
    CustomLayoutKey,
    CustomLayoutSession,
    CustomLayoutSessionItem,
)
from rendering.quick.custom_layout_overlay import (
    CustomLayoutOverlayModel,
    RetainedCustomLayoutOverlay,
)
from rendering.quick.custom_layout_scene import QuickCustomLayoutSceneCoordinator
from rendering.quick.scene_controller import QuickSceneController, QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from rendering.quick.widgets.host import OverlayWidgetGeometry
from rendering.quick.window import QuickDisplayWindow
from widgets.spotify_visualizer.presentation_geometry import (
    resolve_visualizer_presentation,
)
from widgets.spotify_visualizer.render_bridge import VisualizerSnapshotBridge
from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy


ROOT = Path(__file__).resolve().parents[1]


def _quick_items_named(root: QQuickItem, object_name: str) -> list[QQuickItem]:
    matches: list[QQuickItem] = []
    for child in root.childItems():
        if child.objectName() == object_name:
            matches.append(child)
        matches.extend(_quick_items_named(child, object_name))
    return matches


def _item(
    widget_id: str,
    display_identity: str,
    rect: QRect,
    *,
    duplicate: bool = False,
    resizable: bool = False,
) -> CustomLayoutSessionItem:
    return CustomLayoutSessionItem(
        source_key=CustomLayoutKey(widget_id, display_identity),
        model_identity=widget_id,
        baseline_global_rect=rect,
        current_global_rect=rect,
        baseline_size_payload={},
        current_size_payload={},
        baseline_enabled=True,
        current_enabled=True,
        is_duplicate=duplicate,
        resize_capable=resizable,
    )


def test_overlay_model_mutates_shared_session_items_without_copying_authority() -> None:
    session = CustomLayoutSession()
    singleton = _item("clock", "display:a", QRect(110, 220, 180, 80))
    duplicate = _item(
        "weather",
        "display:a",
        QRect(320, 240, 220, 100),
        duplicate=True,
    )
    foreign = _item(
        "weather",
        "display:b",
        QRect(900, 40, 220, 100),
        duplicate=True,
    )
    for item in (singleton, duplicate, foreign):
        session.add_item(item)

    model = CustomLayoutOverlayModel(
        session=session,
        display_identity="display:a",
        display_origin=QPoint(100, 200),
    )

    assert model.rowCount() == 2
    singleton_identity = id(singleton)
    model.moveItem(0, 36.0, 48.0, 50.0, 60.0)
    assert id(session.item(singleton.source_key)) == singleton_identity
    assert singleton.current_global_rect == QRect(136, 248, 180, 80)

    model.closeItem(0)
    assert singleton.current_enabled is False
    assert singleton.removed is False
    assert model.rowCount() == 1

    model.closeItem(0)
    assert duplicate.current_enabled is True
    assert duplicate.removed is True
    assert model.rowCount() == 0
    assert foreign.current_enabled is True
    assert foreign.removed is False


def test_overlay_resize_requests_route_through_python_and_keep_item_identity() -> None:
    session = CustomLayoutSession()
    clock = _item(
        "clock",
        "display:a",
        QRect(110, 220, 180, 80),
        resizable=True,
    )
    session.add_item(clock)
    events: list[tuple[object, ...]] = []

    def _begin(item, corner, cursor):
        events.append(("begin", id(item), corner, QPoint(cursor)))
        return True

    def _update(item, corner, cursor, finalize):
        events.append(("update", id(item), corner, QPoint(cursor), finalize))
        item.set_geometry(
            QRect(100, 200, 270, 120),
            size_payload={"font_size": 72},
            resize_scale=1.5,
        )
        return True

    def _wheel(item, delta):
        events.append(("wheel", id(item), delta))
        item.set_geometry(
            QRect(95, 200, 288, 128),
            size_payload={"font_size": 77},
            resize_scale=1.6,
        )
        return True

    model = CustomLayoutOverlayModel(
        session=session,
        display_identity="display:a",
        display_origin=QPoint(100, 200),
        resize_begin_handler=_begin,
        resize_update_handler=_update,
        resize_wheel_handler=_wheel,
    )
    identity = id(clock)

    assert model.beginResize(0, "bottom_right", 190.0, 100.0) is True
    assert model.resizeItem(0, "bottom_right", 280.0, 140.0, False) is True
    assert model.resizeWheel(0, 120) is True

    assert events == [
        ("begin", identity, "bottom_right", QPoint(290, 300)),
        ("update", identity, "bottom_right", QPoint(380, 340), False),
        ("wheel", identity, 120),
    ]
    assert id(session.item(clock.source_key)) == identity
    assert clock.current_global_rect == QRect(95, 200, 288, 128)
    assert clock.current_size_payload == {"font_size": 77}
    assert clock.resize_scale == pytest.approx(1.6)

    clock.resize_capable = False
    assert model.beginResize(0, "bottom_right", 0.0, 0.0) is False
    assert model.resizeItem(0, "bottom_right", 0.0, 0.0, True) is False
    assert model.resizeWheel(0, -120) is False


def test_shared_session_transfer_moves_frame_between_display_models_and_cancel_restores() -> None:
    session = CustomLayoutSession()
    clock = _item("clock", "display:a", QRect(120, 80, 180, 80))
    session.add_item(clock)
    source_publications: list[int] = []
    target_publications: list[int] = []
    transfer_cursors: list[QPoint] = []

    def _resolve_transfer(item, proposed, cursor):
        transfer_cursors.append(QPoint(cursor))
        item.set_current_display("display:b", monitor_route="2")
        return QRect(proposed)

    source = CustomLayoutOverlayModel(
        session=session,
        display_identity="display:a",
        geometry_resolver=_resolve_transfer,
        item_change_publisher=lambda item: source_publications.append(id(item)),
    )
    target = CustomLayoutOverlayModel(
        session=session,
        display_identity="display:b",
        display_origin=QPoint(800, 0),
        item_change_publisher=lambda item: target_publications.append(id(item)),
    )
    identity = id(clock)

    assert source.rowCount() == 1
    assert target.rowCount() == 0
    source.moveItem(0, 860.0, 120.0, 900.0, 150.0)

    assert source.rowCount() == 0
    assert target.rowCount() == 1
    assert clock.current_display_identity == "display:b"
    assert clock.current_monitor_route == "2"
    assert clock.current_global_rect == QRect(860, 120, 180, 80)
    assert transfer_cursors == [QPoint(900, 150)]
    assert source_publications[-1] == identity
    assert target_publications[-1] == identity

    session.restore_baseline()

    assert source.rowCount() == 1
    assert target.rowCount() == 0
    assert clock.current_display_identity == "display:a"
    assert clock.current_monitor_route == "ALL"
    assert clock.current_global_rect == QRect(120, 80, 180, 80)
    assert id(session.item(clock.source_key)) == identity

    source.retire()
    target.retire()


@pytest.mark.qt
def test_display_scene_has_one_retained_overlay_with_red_center_guides(qt_app) -> None:
    owner = QObject()
    factory = QuickSceneFactory()
    context, root = factory.create_display_root(
        owner=owner,
        screen_index=0,
        runtime_generation=71,
    )
    root.setWidth(800.0)
    root.setHeight(600.0)
    overlay_items = root.findChildren(QQuickItem, "customLayoutOverlay")
    assert len(overlay_items) == 1
    overlay_item = overlay_items[0]
    retained_identity = id(overlay_item)
    overlay = RetainedCustomLayoutOverlay(overlay_item)

    session = CustomLayoutSession()
    clock = _item("clock", "display:a", QRect(20, 30, 180, 80))
    session.add_item(clock)
    overlay.bind_session(session, display_identity="display:a")
    overlay.set_guides(
        vertical=((400, "display_center"), (260, "peer")),
        horizontal=((300, "peer_center"),),
    )
    qt_app.processEvents()

    assert overlay_item.property("editActive") is True
    assert overlay_item.isVisible() is True
    assert id(overlay.item) == retained_identity
    assert _quick_items_named(overlay_item, "customLayoutEditFrame-clock")

    vertical = _quick_items_named(overlay_item, "customLayoutVerticalGuide")
    horizontal = _quick_items_named(overlay_item, "customLayoutHorizontalGuide")
    assert {line.property("guideKind") for line in vertical} == {
        "display_center",
        "peer",
    }
    center_vertical = next(
        line for line in vertical if line.property("guideKind") == "display_center"
    )
    peer_vertical = next(
        line for line in vertical if line.property("guideKind") == "peer"
    )
    assert center_vertical.property("color") == QColor("#ff3b30")
    assert peer_vertical.property("color") == QColor(180, 110, 255, 235)
    assert horizontal[0].property("color") == QColor("#ff3b30")

    overlay.model.moveItem(0, 70.0, 90.0, 85.0, 105.0)
    qt_app.processEvents()
    assert clock.current_global_rect == QRect(70, 90, 180, 80)
    assert id(overlay.item) == retained_identity

    overlay.model.closeItem(0)
    qt_app.processEvents()
    assert clock.current_enabled is False
    assert clock.removed is False
    assert not _quick_items_named(overlay_item, "customLayoutEditFrame-clock")
    assert id(overlay.item) == retained_identity

    overlay.clear_session()
    assert overlay_item.property("editActive") is False
    assert id(overlay.item) == retained_identity

    root.deleteLater()
    context.deleteLater()
    factory.deleteLater()
    owner.deleteLater()
    qt_app.processEvents()


@pytest.mark.qt
def test_scene_controller_owns_overlay_for_exact_display_generation(qt_app) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    window = QuickDisplayWindow(
        screen_index=0,
        runtime_generation=83,
        screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    factory = QuickSceneFactory()
    controller = QuickSceneController(window=window, factory=factory)
    overlay = controller.custom_layout_overlay
    item = overlay.item

    assert item.objectName() == "customLayoutOverlay"
    assert item.parentItem() is controller.scene_root

    controller.quiesce_for_retirement()
    assert controller.readiness.qml_objects_retired is True
    with pytest.raises(RuntimeError):
        _ = overlay.item
    with pytest.raises(RuntimeError):
        _ = controller.custom_layout_overlay

    window.deleteLater()
    factory.deleteLater()
    qt_app.processEvents()


@pytest.mark.qt
def test_scene_binding_moves_hides_and_restores_same_retained_family_item(qt_app) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    window = QuickDisplayWindow(
        screen_index=0,
        runtime_generation=97,
        screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    factory = QuickSceneFactory()
    controller = QuickSceneController(window=window, factory=factory)
    presentation = controller.ordinary_widget_host.create_widget(
        object_name="clock",
        model_identity="clock",
        geometry=OverlayWidgetGeometry(4.0, 5.0, 180.0, 80.0),
        fade_opacity=0.35,
    )
    presentation_item = presentation.item
    retained_identity = id(presentation_item)

    session = CustomLayoutSession()
    clock = _item(
        "clock",
        "display:a",
        QRect(130, 250, 200, 90),
        resizable=True,
    )
    session.add_item(clock)
    model = controller.bind_custom_layout_session(
        session,
        display_identity="display:a",
        display_origin=QPoint(100, 200),
    )

    assert controller.ordinary_widget_host.presentation_for_model_identity("clock") is presentation
    assert (presentation_item.x(), presentation_item.y()) == (30.0, 50.0)
    assert (presentation_item.width(), presentation_item.height()) == (200.0, 90.0)
    assert presentation_item.property("workingVisible") is True
    assert presentation_item.opacity() == pytest.approx(0.35)
    qt_app.processEvents()
    resize_handles = [
        item
        for item in _quick_items_named(
            controller.custom_layout_overlay.item,
            "customLayoutResize-clock-top_left",
        )
    ]
    assert len(resize_handles) == 1
    assert sum(
        len(
            _quick_items_named(
                controller.custom_layout_overlay.item,
                f"customLayoutResize-clock-{corner}",
            )
        )
        for corner in ("top_left", "top_right", "bottom_left", "bottom_right")
    ) == 4

    model.moveItem(0, 70.0, 95.0, 85.0, 110.0)
    assert clock.current_global_rect == QRect(170, 295, 200, 90)
    assert (presentation_item.x(), presentation_item.y()) == (70.0, 95.0)
    assert id(presentation.item) == retained_identity

    model.closeItem(0)
    assert clock.current_enabled is False
    assert presentation_item.property("workingVisible") is False
    assert presentation_item.opacity() == pytest.approx(0.35)
    assert id(presentation.item) == retained_identity

    session.restore_baseline()
    controller.refresh_custom_layout_session()
    assert clock.current_enabled is True
    assert presentation_item.property("workingVisible") is True
    assert (presentation_item.x(), presentation_item.y()) == (30.0, 50.0)
    assert id(presentation.item) == retained_identity

    controller.clear_custom_layout_session()
    assert controller.custom_layout_overlay.item.property("editActive") is False
    assert presentation_item.property("workingVisible") is True
    assert id(presentation.item) == retained_identity

    controller.quiesce_for_retirement()
    window.deleteLater()
    factory.deleteLater()
    qt_app.processEvents()


@pytest.mark.qt
def test_cross_display_transfer_flips_one_visible_retained_family_owner(qt_app) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    factory = QuickSceneFactory()
    source_window = QuickDisplayWindow(
        screen_index=0,
        runtime_generation=101,
        screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    target_window = QuickDisplayWindow(
        screen_index=1,
        runtime_generation=101,
        screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    source_controller = QuickSceneController(window=source_window, factory=factory)
    target_controller = QuickSceneController(window=target_window, factory=factory)
    source_presentation = source_controller.ordinary_widget_host.create_widget(
        object_name="clock-source",
        model_identity="clock",
        geometry=OverlayWidgetGeometry(120.0, 80.0, 180.0, 80.0),
    )
    target_presentation = target_controller.ordinary_widget_host.create_widget(
        object_name="clock-target",
        model_identity="clock",
        geometry=OverlayWidgetGeometry(40.0, 120.0, 180.0, 80.0),
    )
    source_identity = id(source_presentation.item)
    target_identity = id(target_presentation.item)

    session = CustomLayoutSession()
    clock = _item("clock", "display:a", QRect(120, 80, 180, 80))
    session.add_item(clock)

    def _transfer(item, proposed, _cursor):
        item.set_current_display("display:b", monitor_route="2")
        return QRect(proposed)

    source_model = source_controller.bind_custom_layout_session(
        session,
        display_identity="display:a",
        geometry_resolver=_transfer,
    )
    target_controller.bind_custom_layout_session(
        session,
        display_identity="display:b",
        display_origin=QPoint(800, 0),
    )

    assert source_presentation.item.property("workingVisible") is True
    assert target_presentation.item.property("workingVisible") is False
    source_model.moveItem(0, 860.0, 120.0, 900.0, 150.0)

    assert source_presentation.item.property("workingVisible") is False
    assert target_presentation.item.property("workingVisible") is True
    assert (target_presentation.item.x(), target_presentation.item.y()) == (
        60.0,
        120.0,
    )
    assert id(source_presentation.item) == source_identity
    assert id(target_presentation.item) == target_identity

    session.restore_baseline()
    assert source_presentation.item.property("workingVisible") is True
    assert target_presentation.item.property("workingVisible") is False
    assert id(source_presentation.item) == source_identity
    assert id(target_presentation.item) == target_identity

    source_controller.quiesce_for_retirement()
    target_controller.quiesce_for_retirement()
    source_window.deleteLater()
    target_window.deleteLater()
    factory.deleteLater()
    qt_app.processEvents()


@pytest.mark.qt
def test_visualizer_cross_display_transfer_rehomes_one_render_admission(
    qt_app,
    monkeypatch,
) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    factory = QuickSceneFactory()
    source_window = QuickDisplayWindow(
        screen_index=0,
        runtime_generation=107,
        screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    target_window = QuickDisplayWindow(
        screen_index=1,
        runtime_generation=107,
        screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    source_controller = QuickSceneController(window=source_window, factory=factory)
    target_controller = QuickSceneController(window=target_window, factory=factory)
    monkeypatch.setattr(
        target_controller,
        "_display_device_pixel_ratio",
        lambda: 2.25,
    )
    presentation = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy("spectrum"),
        display_size=(1920.0, 1080.0),
        outer_origin=(120.0, 90.0),
        uniform_visual_scale=1.5,
        scene_fade=0.8,
    )
    _outer_x, _outer_y, outer_width, outer_height = presentation.outer_rect

    session = CustomLayoutSession()
    visualizer = _item(
        "spotify_visualizer",
        "display:a",
        QRect(120, 90, int(outer_width), int(outer_height)),
        resizable=True,
    )
    session.add_item(visualizer)
    coordinator = QuickCustomLayoutSceneCoordinator(session)
    coordinator.register_scene("display:a", source_controller)
    coordinator.register_scene("display:b", target_controller)

    def _transfer(item, proposed, _cursor):
        item.set_current_display("display:b", monitor_route="2")
        return QRect(proposed)

    source_model = source_controller.bind_custom_layout_session(
        session,
        display_identity="display:a",
        geometry_resolver=_transfer,
    )
    target_controller.bind_custom_layout_session(
        session,
        display_identity="display:b",
        display_origin=QPoint(800, 0),
    )

    bridge = VisualizerSnapshotBridge()
    render_identity = bridge.begin_activation(
        runtime_generation=107,
        engine_generation=9,
        activation_id=13,
        mode_id="spectrum",
    )
    source_controller.set_visualizer_render_source(bridge, render_identity)
    source_controller.apply_visualizer_presentation(presentation)
    source_item_identity = id(source_controller.visualizer_item)

    source_model.moveItem(0, 860.0, 140.0, 900.0, 170.0)

    source_state = source_controller.describe_scene_state()["visualizer"]
    target_state = target_controller.describe_scene_state()["visualizer"]
    assert source_state["instantiated"] is False
    assert source_state["render_identity"] is None
    assert target_state["instantiated"] is True
    assert target_controller.visualizer_item.render_identity == render_identity
    assert target_controller.visualizer_item.presentation is not None
    assert target_controller.visualizer_item.presentation.dpr == pytest.approx(2.25)
    assert bridge.identity == render_identity
    assert id(target_controller.visualizer_item) != source_item_identity
    target_loader = target_controller.scene_root.findChild(
        QQuickItem,
        "visualizerPresentationLoader",
    )
    assert target_loader is not None
    target_root = target_loader.property("item")
    assert target_root is not None
    assert (target_loader.x(), target_loader.y()) == (60.0, 140.0)
    assert target_root.property("presentationActive") is True
    assert target_root.property("customLayoutWorkingVisible") is True

    session.restore_baseline()
    assert target_root.property("customLayoutWorkingVisible") is False
    source_state = source_controller.describe_scene_state()["visualizer"]
    target_state = target_controller.describe_scene_state()["visualizer"]
    assert source_state["instantiated"] is True
    assert target_state["instantiated"] is False
    assert target_state["render_identity"] is None
    assert source_controller.visualizer_item.render_identity == render_identity
    assert source_controller.visualizer_item.presentation is not None
    assert source_controller.visualizer_item.presentation.dpr == pytest.approx(
        source_window.devicePixelRatio()
    )
    assert bridge.identity == render_identity
    source_loader = source_controller.scene_root.findChild(
        QQuickItem,
        "visualizerPresentationLoader",
    )
    assert source_loader is not None
    source_root = source_loader.property("item")
    assert source_root is not None
    assert (source_loader.x(), source_loader.y()) == (120.0, 90.0)
    assert source_root.property("presentationActive") is True
    assert source_root.property("customLayoutWorkingVisible") is True

    coordinator.retire()
    source_controller.quiesce_for_retirement()
    target_controller.quiesce_for_retirement()
    source_window.deleteLater()
    target_window.deleteLater()
    factory.deleteLater()
    qt_app.processEvents()


@pytest.mark.qt
def test_visualizer_custom_session_preserves_retained_item_and_render_identity(qt_app) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    window = QuickDisplayWindow(
        screen_index=0,
        runtime_generation=109,
        screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    factory = QuickSceneFactory()
    controller = QuickSceneController(window=window, factory=factory)
    presentation = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy("spectrum"),
        display_size=(1920.0, 1080.0),
        outer_origin=(207.0, 310.0),
        uniform_visual_scale=1.5,
        scene_fade=0.75,
    )
    outer_x, outer_y, outer_width, outer_height = presentation.outer_rect

    session = CustomLayoutSession()
    visualizer = _item(
        "spotify_visualizer",
        "display:a",
        QRect(
            100 + int(outer_x),
            200 + int(outer_y),
            int(outer_width),
            int(outer_height),
        ),
        resizable=True,
    )
    foreign_duplicate = _item(
        "spotify_visualizer",
        "display:b",
        QRect(1300, 400, int(outer_width), int(outer_height)),
        duplicate=True,
    )
    session.add_item(visualizer)
    session.add_item(foreign_duplicate)
    def _resize_wheel(item, _delta):
        rect = item.current_global_rect
        item.set_geometry(
            QRect(rect.x(), rect.y(), int(outer_width * 1.5), int(outer_height * 1.5)),
            size_payload={
                "width": int(outer_width * 1.5),
                "height": int(outer_height * 1.5),
            },
            resize_scale=1.5,
        )
        return True

    model = controller.bind_custom_layout_session(
        session,
        display_identity="display:a",
        display_origin=QPoint(100, 200),
        resize_wheel_handler=_resize_wheel,
    )
    assert controller.describe_scene_state()["visualizer"]["instantiated"] is False

    bridge = VisualizerSnapshotBridge()
    render_identity = bridge.begin_activation(
        runtime_generation=109,
        engine_generation=5,
        activation_id=7,
        mode_id="spectrum",
    )
    controller.set_visualizer_render_source(bridge, render_identity)
    controller.apply_visualizer_presentation(presentation)
    render_item = controller.visualizer_item
    render_item_identity = id(render_item)
    visualizer_root = controller.scene_root.findChild(
        QQuickItem,
        "visualizerPresentationRoot",
    )
    loader = controller.scene_root.findChild(
        QQuickItem,
        "visualizerPresentationLoader",
    )
    assert visualizer_root is not None and loader is not None
    root_identity = id(visualizer_root)

    assert (loader.x(), loader.y()) == (outer_x, outer_y)
    assert visualizer_root.property("presentationActive") is True
    assert visualizer_root.property("customLayoutWorkingVisible") is True
    assert render_item.presentation is presentation
    assert render_item.render_identity == render_identity

    assert model.resizeWheel(0, 120) is True
    resized_presentation = render_item.presentation
    assert resized_presentation is not None
    assert resized_presentation.uniform_visual_scale == pytest.approx(2.25)
    assert resized_presentation.viewport_extent == presentation.viewport_extent
    assert (loader.width(), loader.height()) == pytest.approx(
        (outer_width * 1.5, outer_height * 1.5)
    )
    assert id(controller.visualizer_item) == render_item_identity
    assert render_item.render_identity == render_identity

    model.moveItem(
        0,
        outer_x + 80.0,
        outer_y + 45.0,
        outer_x + 100.0,
        outer_y + 65.0,
    )
    assert (loader.x(), loader.y()) == (outer_x + 80.0, outer_y + 45.0)
    assert id(controller.visualizer_item) == render_item_identity
    assert id(visualizer_root) == root_identity
    moved_presentation = render_item.presentation
    assert moved_presentation is not None
    assert moved_presentation.uniform_visual_scale == pytest.approx(2.25)
    assert moved_presentation.viewport_extent == resized_presentation.viewport_extent
    assert render_item.render_identity == render_identity

    model.closeItem(0)
    assert visualizer.removed is True
    assert visualizer.current_enabled is True
    assert visualizer_root.property("presentationActive") is True
    assert visualizer_root.property("customLayoutWorkingVisible") is False
    assert id(controller.visualizer_item) == render_item_identity
    assert render_item.render_identity == render_identity

    session.restore_baseline()
    controller.refresh_custom_layout_session()
    assert visualizer.current_enabled is True
    assert visualizer_root.property("customLayoutWorkingVisible") is True
    assert (loader.x(), loader.y()) == (outer_x, outer_y)
    assert id(controller.visualizer_item) == render_item_identity
    assert render_item.render_identity == render_identity
    restored_presentation = render_item.presentation
    assert restored_presentation is not None
    assert restored_presentation.uniform_visual_scale == pytest.approx(1.5)
    assert restored_presentation.viewport_extent == presentation.viewport_extent

    controller.clear_custom_layout_session()
    assert visualizer_root.property("customLayoutWorkingVisible") is True
    assert id(visualizer_root) == root_identity
    assert id(controller.visualizer_item) == render_item_identity

    controller.quiesce_for_retirement()
    window.deleteLater()
    factory.deleteLater()
    qt_app.processEvents()


def test_quick_custom_layout_overlay_is_presentation_only() -> None:
    source = (
        ROOT / "rendering" / "quick" / "custom_layout_overlay.py"
    ).read_text(encoding="utf-8")
    qml = (
        ROOT / "rendering" / "quick" / "qml" / "CustomLayoutOverlay.qml"
    ).read_text(encoding="utf-8")

    for forbidden in (
        "QWidget",
        "QQuickWidget",
        "SettingsManager",
        "provider",
        "capability",
        "QQmlEngine(",
        "QQuickWindow(",
    ):
        assert forbidden not in source
    assert "CustomLayoutSessionItem" in source
    assert "item.apply_remove_action()" in source
    assert "drag.target" not in qml
    assert "sessionModel.moveItem(" in qml
    assert "sessionModel.closeItem(" in qml
