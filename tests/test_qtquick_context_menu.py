"""Phase G7 gates for the retained Quick context menu."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QEventLoop, QObject, QPointF, QSize, QTimer, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtQuick import QQuickItem, QQuickWindow

from rendering.quick.context_menu import (
    QuickContextMenuEntry,
    QuickContextMenuModel,
    build_quick_context_menu_entries,
)
from rendering.quick.runtime import QuickDisplayRuntime
from rendering.quick.scene_controller import QuickSceneController, QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from rendering.quick.window import QuickDisplayWindow


def _entries(*, edit_mode: bool = False) -> tuple[QuickContextMenuEntry, ...]:
    return build_quick_context_menu_entries(
        transition_names=("Crossfade", "Wipe"),
        current_transition="Wipe",
        random_enabled=False,
        random_selectable=False,
        visualizer_modes=(("spectrum", "Spectrum"), ("bubble", "Bubble")),
        current_visualizer="bubble",
        visualizer_available=True,
        dimming_enabled=True,
        interaction_mode_enabled=False,
        interaction_mode_locked=False,
        edit_mode_active=edit_mode,
    )


def test_context_menu_builder_preserves_admitted_product_structure() -> None:
    entries = _entries()
    labels = [entry.label for entry in entries]
    assert labels[:2] == ["◂  Previous Image", "▸  Next Image"]
    assert "⚙  Settings" in labels
    assert "✥  Edit Widget Layout" in labels
    assert "✓  Save Widget Layout" not in labels
    assert labels[-1] == "✕  Exit Screensaver"

    transition_menu = next(
        entry for entry in entries if entry.label == "⟳  Change Transition"
    )
    assert [(child.payload, child.enabled, child.checked) for child in transition_menu.children] == [
        ("Random", False, False),
        ("Crossfade", True, False),
        ("Wipe", True, True),
    ]
    visualizer_menu = next(
        entry for entry in entries if entry.label == "⟳  Change Visualizer"
    )
    assert [(child.payload, child.checked) for child in visualizer_menu.children] == [
        ("spectrum", False),
        ("bubble", True),
    ]

    active_labels = [entry.label for entry in _entries(edit_mode=True)]
    assert "✥  Edit Widget Layout" not in active_labels
    assert "✓  Save Widget Layout" in active_labels
    assert "↺  Cancel Widget Layout" in active_labels
    assert "⟲  Reset To Saved Layout" in active_labels


def test_context_menu_model_admits_only_live_enabled_semantic_actions() -> None:
    model = QuickContextMenuModel(screen_index=2, runtime_generation=7)
    routed = []
    visibility = []
    model.visibilityChanged.connect(visibility.append)
    model.set_action_handler(
        lambda action_id, payload: routed.append((action_id, payload)) or True
    )
    assert model.replace_entries(_entries()) is True
    assert model.open_at(120.0, 80.0) is True
    assert visibility == [True]

    assert model.requestAction("transition", "Random", True) is False
    assert routed == []
    assert model.menuVisible is True
    assert model.requestAction("transition", "Wipe", True) is True
    assert routed == [("transition", "Wipe")]
    assert visibility == [True, False]
    assert model.menuVisible is False

    assert model.open_at(5.0, 6.0) is True
    assert model.requestAction("toggle_dimming", "", False) is True
    assert routed[-1] == ("toggle_dimming", "false")
    assert model.open_at(5.0, 6.0) is True
    assert model.requestAction("not-an-action", "", True) is False
    assert model.close() is True
    assert model.open_at(1.0, 1.0) is False


def test_scene_binds_only_matching_context_menu_generation(qt_app) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    window = QuickDisplayWindow(
        screen_index=0,
        runtime_generation=12,
        screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    factory = QuickSceneFactory()
    controller = QuickSceneController(window=window, factory=factory)
    matching = QuickContextMenuModel(
        screen_index=0,
        runtime_generation=12,
        parent=controller,
    )
    stale = QuickContextMenuModel(
        screen_index=0,
        runtime_generation=11,
        parent=controller,
    )
    try:
        root = controller.scene_root
        item = root.findChild(QQuickItem, "retainedContextMenu")
        assert item is not None
        assert controller.bind_context_menu_model(stale) is False
        assert root.property("contextMenuModel") is None
        assert controller.bind_context_menu_model(matching) is True
        assert root.property("contextMenuModel") is matching
    finally:
        controller.quiesce_for_retirement()
        window.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()


def test_runtime_right_click_opens_retained_menu_and_action_closes_admission(
    qt_app,
) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    factory = QuickSceneFactory()
    runtime = QuickDisplayRuntime(
        screen_index=0,
        runtime_generation=23,
        screen=screen,
        scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
        interaction_mode_provider=lambda: True,
    )
    routed = []
    model = runtime.context_menu_model
    model.replace_entries(_entries())
    model.set_action_handler(
        lambda action_id, payload: routed.append((action_id, payload)) or True
    )
    runtime.window.setGeometry(0, 0, 640, 480)
    try:
        event = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(110.0, 90.0),
            QPointF(110.0, 90.0),
            Qt.MouseButton.RightButton,
            Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.NoModifier,
        )
        runtime.window.mousePressEvent(event)

        assert event.isAccepted() is True
        assert model.menuVisible is True
        assert model.anchorX == 110.0
        assert model.anchorY == 90.0
        assert runtime.input_controller.input_state.context_menu_active is True
        assert model.requestAction("next", "", True) is True
        assert routed == [("next", "")]
        assert model.menuVisible is False
        assert runtime.input_controller.input_state.context_menu_active is False
    finally:
        runtime.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()


def test_retained_context_menu_draws_real_quick_pixels_and_clamps(qt_app) -> None:
    owner = QObject()
    factory = QuickSceneFactory(owner)
    window = QQuickWindow()
    window.resize(640, 480)
    context, root = factory.create_display_root(
        owner=owner,
        screen_index=0,
        runtime_generation=1,
    )
    root.setParent(window.contentItem())
    root.setParentItem(window.contentItem())
    root.setWidth(640.0)
    root.setHeight(480.0)
    model = QuickContextMenuModel(
        screen_index=0,
        runtime_generation=1,
        parent=owner,
    )
    model.replace_entries(_entries(edit_mode=True))
    root.setProperty("contextMenuModel", model)
    menu = root.findChild(QQuickItem, "retainedContextMenu")
    surface = root.findChild(QQuickItem, "retainedContextMenuSurface")
    assert menu is not None
    assert surface is not None
    try:
        window.show()
        assert model.open_at(635.0, 475.0) is True
        settle = QEventLoop()
        QTimer.singleShot(250, settle.quit)
        settle.exec()
        assert surface.x() >= 4.0
        assert surface.y() >= 4.0
        assert surface.x() + surface.width() <= 636.0
        assert surface.y() + surface.height() <= 476.0

        result = surface.grabToImage(
            QSize(int(surface.width()), int(surface.height()))
        )
        loop = QEventLoop()
        timeout = QTimer()
        timeout.setSingleShot(True)
        timeout.timeout.connect(loop.quit)
        result.ready.connect(loop.quit)
        timeout.start(5_000)
        loop.exec()
        timeout.stop()
        image = result.image()
        assert not image.isNull()
        visible_pixels = sum(
            image.pixelColor(x, y).alpha() > 8
            for y in range(image.height())
            for x in range(image.width())
        )
        assert visible_pixels > image.width() * image.height() * 0.5
    finally:
        window.hide()
        root.setParentItem(None)
        root.setParent(None)
        root.deleteLater()
        context.deleteLater()
        window.deleteLater()
        owner.deleteLater()
        qt_app.processEvents()


def test_quick_context_menu_has_no_settings_or_qwidget_authority() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source = (root / "rendering" / "quick" / "context_menu.py").read_text(
        encoding="utf-8"
    )
    qml = (root / "rendering" / "quick" / "qml" / "ContextMenu.qml").read_text(
        encoding="utf-8"
    )
    for forbidden in ("QWidget", "QMenu", "QAction", "SettingsManager"):
        assert forbidden not in source
        assert forbidden not in qml
    assert "requestAction(" in qml
    assert "MouseArea" in qml
    assert "Window {" not in qml
