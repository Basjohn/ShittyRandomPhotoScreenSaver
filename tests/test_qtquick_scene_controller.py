"""Phase B gates for generation-scoped Quick scene ownership."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest
from PySide6.QtQml import QQmlEngine
from PySide6.QtQuick import QQuickItem

from rendering.quick.scene_controller import QuickSceneController, QuickSceneFactory
from rendering.quick.state import QuickSceneReadiness, QuickWindowPolicy
from rendering.quick.window import QuickDisplayWindow
from widgets.spotify_visualizer.presentation_geometry import (
    resolve_visualizer_presentation,
)
from widgets.spotify_visualizer.render_bridge import VisualizerSnapshotBridge
from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy


ROOT = Path(__file__).resolve().parents[1]


def test_scene_readiness_preserves_generation_zero_and_requires_intentional_frame():
    initial = QuickSceneReadiness(screen_index=0, runtime_generation=0)
    ready = replace(
        initial,
        qml_root_created=True,
        scene_graph_initialized=True,
        background_renderer_ready=True,
        intentional_base_frame_ready=True,
    )

    assert initial.ready_for_reveal is False
    assert ready.runtime_generation == 0
    assert ready.ready_for_reveal is True
    assert replace(ready, admission_open=False).ready_for_reveal is False
    assert replace(ready, scene_graph_invalidated=True).ready_for_reveal is False


def test_factory_shares_only_qml_compile_state_and_creates_per_display_contexts():
    source = (ROOT / "rendering" / "quick" / "scene_controller.py").read_text(
        encoding="utf-8"
    )

    assert source.count("self._engine = QQmlEngine(self)") == 1
    assert "QQmlContext(self._engine.rootContext(), owner)" in source
    assert "createWithInitialProperties(" in source
    assert '"screenIndex": int(screen_index)' in source
    assert '"runtimeGeneration": runtime_generation' in source
    assert "QQmlEngine.ObjectOwnership.CppOwnership" in source
    assert not hasattr(QuickSceneFactory, "_scene_roots")


def test_scene_controller_is_the_narrow_quick_item_owner():
    assert QuickSceneController.__mro__[1].__name__ == "QObject"
    source = (ROOT / "rendering" / "quick" / "scene_controller.py").read_text(
        encoding="utf-8"
    )

    assert source.count("BackgroundRenderItem(") == 1
    assert source.count("VisualizerRenderItem(") == 1
    assert "frameSwapped.connect(" in source
    assert "sceneGraphInvalidated.connect(" in source
    assert "self._retire_qml_objects()" in source
    assert "isSceneGraphInitialized()" in source
    assert "set_transition_run" in source
    assert "self._last_transition_run_id" in source
    assert "window.update" not in source
    assert "afterRendering" not in source
    assert "afterFrameEnd" not in source
    assert source.count("MediaArtworkImageProvider()") == 1
    assert source.count("addImageProvider(") == 1
    for forbidden in (
        "QWidget",
        "QQuickWidget",
        "DisplayWidget",
        "WidgetManager",
        "GLCompositorWidget",
        "SettingsManager",
        "provider_runtime",
        "set_provider_runtime",
        "MediaRuntimeService",
    ):
        assert forbidden not in source


@pytest.mark.qt
def test_display_scene_keeps_visualizer_qml_dormant_until_explicit_activation(
    qt_app,
) -> None:
    factory = QuickSceneFactory()
    context, root = factory.create_display_root(
        owner=factory,
        screen_index=0,
        runtime_generation=0,
    )
    loader = root.findChild(QQuickItem, "visualizerPresentationLoader")

    assert loader is not None
    assert loader.property("active") is False
    assert loader.property("item") is None
    assert loader.clip() is False

    loader.setProperty("active", True)
    visualizer_root = loader.property("item")
    assert isinstance(visualizer_root, QQuickItem)
    QQmlEngine.setObjectOwnership(
        visualizer_root,
        QQmlEngine.ObjectOwnership.CppOwnership,
    )
    assert visualizer_root.objectName() == "visualizerPresentationRoot"
    content_host = visualizer_root.findChild(QQuickItem, "visualizerContentHost")
    assert content_host is not None
    assert visualizer_root.clip() is False
    assert content_host.clip() is False
    assert visualizer_root.property("presentationActive") is False

    root.deleteLater()
    context.deleteLater()
    qt_app.processEvents()


@pytest.mark.qt
def test_scene_controller_applies_one_geometry_record_to_lazy_shell_and_item(
    qt_app,
) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    window = QuickDisplayWindow(
        screen_index=0,
        runtime_generation=0,
        screen=screen,
        policy=QuickWindowPolicy(
            always_on_top=False,
            blank_cursor=False,
        ),
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

    assert controller.describe_scene_state()["visualizer"]["instantiated"] is False
    controller.apply_visualizer_presentation(presentation)
    item = controller.visualizer_item
    loader = controller.scene_root.findChild(
        QQuickItem,
        "visualizerPresentationLoader",
    )
    assert loader is not None and loader.property("active") is True
    assert loader.x() == 207.0
    assert loader.y() == 310.0
    assert loader.width() == 630.0
    assert loader.height() == 420.0
    assert item.presentation is presentation
    assert item.width() == 630.0
    assert item.height() == 420.0

    bridge = VisualizerSnapshotBridge()
    identity = bridge.begin_activation(
        runtime_generation=0,
        engine_generation=0,
        activation_id=0,
        mode_id="spectrum",
    )
    controller.set_visualizer_render_source(bridge, identity)
    assert item.render_identity == identity
    json.dumps(controller.describe_scene_state())

    controller.quiesce_for_retirement()
    assert controller.readiness.qml_objects_retired is True
    window.deleteLater()
    factory.deleteLater()
    qt_app.processEvents()


def test_runtime_smoke_delegates_qml_and_items_to_scene_owner():
    source = (ROOT / "tools" / "qtquick_render_node_smoke.py").read_text(
        encoding="utf-8"
    )
    runtime_source = (ROOT / "rendering" / "quick" / "runtime.py").read_text(
        encoding="utf-8"
    )

    assert "QuickSceneFactory(self)" in source
    assert "QuickDisplayRuntime(" in source
    assert "probe.runtime.close_runtime()" in source
    assert "QuickSceneController(" in runtime_source
    assert "QQmlEngine(" not in source
    assert "QQmlComponent(" not in source
    assert "BackgroundRenderItem(" not in source
