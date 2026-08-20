"""Phase B gates for generation-scoped Quick scene ownership."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from rendering.quick.scene_controller import QuickSceneController, QuickSceneFactory
from rendering.quick.state import QuickSceneReadiness


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
    assert "frameSwapped.connect(" in source
    assert "sceneGraphInvalidated.connect(" in source
    assert "self._retire_qml_objects()" in source
    assert "isSceneGraphInitialized()" in source
    assert "window.update" not in source
    assert "afterRendering" not in source
    assert "afterFrameEnd" not in source
    for forbidden in (
        "QWidget",
        "QQuickWidget",
        "DisplayWidget",
        "WidgetManager",
        "GLCompositorWidget",
        "SettingsManager",
        "provider",
    ):
        assert forbidden not in source


def test_runtime_smoke_delegates_qml_and_items_to_scene_owner():
    source = (ROOT / "tools" / "qtquick_render_node_smoke.py").read_text(
        encoding="utf-8"
    )

    assert "QuickSceneFactory(self)" in source
    assert "QuickSceneController(" in source
    assert "probe.scene.quiesce_for_retirement()" in source
    assert "QQmlEngine(" not in source
    assert "QQmlComponent(" not in source
    assert "BackgroundRenderItem(" not in source
