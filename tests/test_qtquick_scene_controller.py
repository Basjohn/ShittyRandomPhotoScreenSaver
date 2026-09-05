"""Phase B gates for generation-scoped Quick scene ownership."""

from __future__ import annotations

from types import SimpleNamespace

from dataclasses import replace
import json
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QPointF, QRect
from PySide6.QtQml import QQmlEngine
from PySide6.QtQuick import QQuickItem

from rendering.quick.scene_controller import (
    QuickSceneController,
    QuickSceneFactory,
    _custom_visualizer_relative_scale,
)
from rendering.quick.custom_layout_owner import (
    QuickCustomLayoutOwner,
    _DisplayBinding,
)
from rendering.custom_layout_session import (
    CustomLayoutKey,
    CustomLayoutSession,
    CustomLayoutSessionItem,
)
from rendering.widget_descriptors import get_widget_runtime_descriptor
from rendering.quick.state import QuickSceneReadiness, QuickWindowPolicy
from rendering.quick.window import QuickDisplayWindow
from widgets.spotify_visualizer.presentation_geometry import (
    resolve_visualizer_presentation,
    resize_visualizer_presentation,
)
from widgets.spotify_visualizer.render_bridge import VisualizerSnapshotBridge
from core.settings.visualizer_mode_registry import (
    VISUALIZER_MODE_IDS,
    get_visualizer_presentation_policy,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("mode_id", VISUALIZER_MODE_IDS)
def test_custom_visualizer_working_rect_survives_fresh_committed_snapshot(mode_id):
    """All modes retain an active edge preview over a committed-size snapshot."""
    policy = get_visualizer_presentation_policy(mode_id)
    # This is the normal-snapshot state during an active right-edge edit: the
    # owner has incorporated the new 840-wide logical extent but still resolves
    # it through the committed 420px physical rectangle.
    committed_snapshot = resolve_visualizer_presentation(
        policy=policy,
        display_size=(1920.0, 1080.0),
        outer_origin=(130.0, 90.0),
        viewport_extent=(840.0, 280.0),
        uniform_visual_scale=0.5,
    )
    relative_scale = _custom_visualizer_relative_scale(
        baseline=committed_snapshot,
        viewport_extent=(840.0, 280.0),
        working_width=840.0,
        working_height=280.0,
    )
    assert relative_scale == pytest.approx(2.0)
    working = resize_visualizer_presentation(
        committed_snapshot,
        display_size=(1920.0, 1080.0),
        outer_origin=(130.0, 90.0),
        viewport_extent=(840.0, 280.0),
        relative_scale=relative_scale,
    )
    assert working.outer_rect == pytest.approx((130.0, 90.0, 840.0, 280.0))


@pytest.mark.parametrize("mode_id", VISUALIZER_MODE_IDS)
def test_custom_visualizer_huge_world_matches_same_visible_edit_footprint(mode_id):
    """Saving/re-entering a huge world must retain the same visible rectangle."""
    policy = get_visualizer_presentation_policy(mode_id)
    visible = (1398.5560481317289, 268.0)
    huge = resolve_visualizer_presentation(
        policy=policy,
        display_size=(1400.0, 268.0),
        viewport_extent=(8240.0, 1579.0),
        uniform_visual_scale=1.0,
    )
    direct = resolve_visualizer_presentation(
        policy=policy,
        display_size=visible,
        viewport_extent=visible,
        uniform_visual_scale=1.0,
    )
    huge_relative_scale = _custom_visualizer_relative_scale(
        baseline=huge,
        viewport_extent=(8240.0, 1579.0),
        working_width=huge.outer_rect[2],
        working_height=huge.outer_rect[3],
    )
    direct_relative_scale = _custom_visualizer_relative_scale(
        baseline=direct,
        viewport_extent=visible,
        working_width=direct.outer_rect[2],
        working_height=direct.outer_rect[3],
    )
    assert huge_relative_scale == pytest.approx(1.0)
    assert direct_relative_scale == pytest.approx(1.0)
    assert huge.outer_rect[2:] == pytest.approx(direct.outer_rect[2:])


def test_custom_visualizer_rejects_incoherent_working_axes():
    baseline = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy("spectrum"),
        display_size=(1920.0, 1080.0),
        viewport_extent=(420.0, 280.0),
    )
    with pytest.raises(RuntimeError, match="not uniformly scaled"):
        _custom_visualizer_relative_scale(
            baseline=baseline,
            viewport_extent=(840.0, 280.0),
            working_width=840.0,
            working_height=300.0,
        )


def test_custom_visualizer_relative_scale_accepts_independently_rounded_tall_rect():
    """One axis cannot reject a valid integer-rounded CUSTOM session QRect."""
    baseline = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy("spectrum"),
        display_size=(1920.0, 1080.0),
        viewport_extent=(1.0, 10000.0),
    )
    # The height is an independently rounded projection of the same scale.
    # A one-pixel comparison against the width-derived height is invalid here:
    # its uncertainty expands with the 1:10000 aspect ratio.
    relative_scale = _custom_visualizer_relative_scale(
        baseline=baseline,
        viewport_extent=(1.0, 10000.0),
        working_width=1.0,
        working_height=10001.0,
    )
    assert relative_scale * baseline.uniform_visual_scale == pytest.approx(
        1.0001,
        abs=0.0001,
    )


def _assert_custom_visualizer_rect(
    controller: QuickSceneController,
    item: CustomLayoutSessionItem,
    display_origin: QPoint,
) -> None:
    """Assert the retained renderer follows the active session rectangle."""
    presentation = controller.visualizer_item.presentation
    expected = item.current_global_rect
    assert presentation.outer_rect == pytest.approx(
        (
            float(expected.x() - display_origin.x()),
            float(expected.y() - display_origin.y()),
            float(expected.width()),
            float(expected.height()),
        )
    )


@pytest.mark.qt
@pytest.mark.parametrize("mode_id", VISUALIZER_MODE_IDS)
def test_scene_controller_keeps_all_custom_edge_wheel_cancel_and_save_geometry(
    qt_app,
    mode_id,
) -> None:
    """Exercise the real retained scene seam across every visualizer policy.

    A normal renderer publication during an active edit resolves the freshly
    changed world through its committed rectangle.  Before this regression the
    controller reapplied that smaller rectangle at the active edit origin,
    producing the top-left thumbnail seen in the operator capture.
    """
    screen = qt_app.primaryScreen()
    assert screen is not None
    screen_geometry = screen.geometry()
    origin = screen_geometry.topLeft()
    window = QuickDisplayWindow(
        screen_index=0,
        runtime_generation=0,
        screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    factory = QuickSceneFactory()
    controller = QuickSceneController(window=window, factory=factory)
    policy = get_visualizer_presentation_policy(mode_id)
    committed = resolve_visualizer_presentation(
        policy=policy,
        display_size=(float(screen_geometry.width()), float(screen_geometry.height())),
        outer_origin=(80.0, 90.0),
        viewport_extent=(480.0, 160.0),
        uniform_visual_scale=0.5,
    )
    controller.apply_visualizer_presentation(committed)
    key = CustomLayoutKey("spotify_visualizer", "test-display")
    baseline_rect = QRect(origin.x() + 80, origin.y() + 90, 480, 160)
    payload = {"width": 480, "height": 160, "viewport_extent": [480.0, 160.0]}
    item = CustomLayoutSessionItem(
        source_key=key,
        model_identity="spotify_visualizer",
        baseline_global_rect=baseline_rect,
        current_global_rect=baseline_rect,
        baseline_size_payload=payload,
        current_size_payload=payload,
        baseline_enabled=True,
        current_enabled=True,
        resize_capable=True,
        viewport_resize_capable=True,
        baseline_viewport_extent=(480.0, 160.0),
    )
    session = CustomLayoutSession()
    session.add_item(item)
    controller.bind_custom_layout_session(
        session,
        display_identity="test-display",
        display_origin=origin,
    )
    descriptor = get_widget_runtime_descriptor("spotify_visualizer")
    assert descriptor is not None
    owner = QuickCustomLayoutOwner(
        settings_manager=None,
        participants_provider=lambda: (),
        visualizer_provider=lambda: (None, None),
        reload_request=lambda _reason: None,
    )
    owner._bindings["test-display"] = _DisplayBinding(
        identity="test-display",
        monitor_route="1",
        unit=SimpleNamespace(
            runtime=SimpleNamespace(scene_controller=controller),
        ),
        screen=screen,
        geometry=QRect(screen_geometry),
    )
    owner._descriptors[key] = descriptor
    # Production seeds the one stable pixels-per-world authority when the visualizer
    # item is admitted (QuickCustomLayoutOwner._admit_visualizer_item). This test
    # constructs the owner state directly, so seed the same authority the current
    # begin_resize/wheel gestures require; otherwise resize raises "no stable
    # pixels-per-world authority".
    owner._visualizer_pixels_per_world[key] = owner._pixels_per_world_from_geometry(
        baseline_rect, (480.0, 160.0)
    )

    def publish_and_interleave_normal_frame() -> None:
        session.notify_item_changed(item)
        # This is the production interleave: the live renderer publishes a
        # fresh committed-size presentation while the edit session remains on.
        controller.apply_visualizer_presentation(committed)
        _assert_custom_visualizer_rect(controller, item, origin)

    # Each semantic edge changes one logical world axis while the opposite
    # physical edge remains fixed.  The session notification travels through
    # the retained overlay model into _sync_custom_layout_visualizer.
    edge_cases = (
        ("left", QPoint(baseline_rect.x(), baseline_rect.center().y()), QPoint(baseline_rect.x() - 20, baseline_rect.center().y()), "right"),
        ("right", QPoint(baseline_rect.right(), baseline_rect.center().y()), QPoint(baseline_rect.right() + 20, baseline_rect.center().y()), "left"),
        ("top", QPoint(baseline_rect.center().x(), baseline_rect.y()), QPoint(baseline_rect.center().x(), baseline_rect.y() - 20), "bottom"),
        ("bottom", QPoint(baseline_rect.center().x(), baseline_rect.bottom()), QPoint(baseline_rect.center().x(), baseline_rect.bottom() + 20), "top"),
    )
    for edge, start, end, fixed_side in edge_cases:
        session.restore_baseline()
        fixed = getattr(baseline_rect, fixed_side)()
        assert owner.begin_resize(item, edge, start) is True
        assert owner.update_resize(item, edge, end, finalize=True) is True
        if fixed_side == "left":
            assert item.current_global_rect.left() == fixed
        elif fixed_side == "right":
            assert item.current_global_rect.right() == fixed
        elif fixed_side == "top":
            assert item.current_global_rect.top() == fixed
        else:
            assert item.current_global_rect.bottom() == fixed
        publish_and_interleave_normal_frame()

    session.restore_baseline()
    assert owner.resize_wheel(item, 120) is True
    assert item.current_global_rect.width() > baseline_rect.width()
    assert item.current_global_rect.height() > baseline_rect.height()
    # Wheel preserves the edge-edited world and applies its whole-card scale
    # uniformly; only an edge drag changes the corresponding world axis.
    assert item.current_viewport_extent == (480.0, 160.0)
    publish_and_interleave_normal_frame()

    # Cancel restores the exact admission rectangle through the same active
    # retained route.  Saving ends CUSTOM, so the committed publication itself
    # must retain the final session rectangle once the session is cleared.
    session.restore_baseline()
    _assert_custom_visualizer_rect(controller, item, origin)
    assert owner.resize_wheel(item, 120) is True
    saved_rect = QRect(item.current_global_rect)
    saved_extent = item.current_viewport_extent
    assert saved_extent is not None
    controller.clear_custom_layout_session()
    saved = resolve_visualizer_presentation(
        policy=policy,
        display_size=(float(screen_geometry.width()), float(screen_geometry.height())),
        outer_origin=(
            float(saved_rect.x() - origin.x()),
            float(saved_rect.y() - origin.y()),
        ),
        viewport_extent=saved_extent,
        uniform_visual_scale=float(saved_rect.width()) / saved_extent[0],
    )
    controller.apply_visualizer_presentation(saved)
    # The session item carries an integer QRect, so a uniform wheel scale rounds
    # width and height independently; the presentation re-derived from the width
    # scale can therefore differ from the rounded rect by up to half a pixel on
    # one axis. Accept that integer-rounding envelope (the same tolerance the live
    # edge-drag assertions above already use) rather than exact float equality.
    assert controller.visualizer_item.presentation.outer_rect == pytest.approx(
        (
            float(saved_rect.x() - origin.x()),
            float(saved_rect.y() - origin.y()),
            float(saved_rect.width()),
            float(saved_rect.height()),
        ),
        abs=0.500001,
    )
    controller.quiesce_for_retirement()
    window.deleteLater()
    factory.deleteLater()
    qt_app.processEvents()


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
    assert controller.visualizer_contains_scene_position(QPointF(208.0, 311.0)) is True
    assert controller.visualizer_contains_scene_position(QPointF(10.0, 10.0)) is False
    controller.set_visualizer_presentation_active(False)
    assert controller.visualizer_contains_scene_position(QPointF(208.0, 311.0)) is False
    controller.set_visualizer_presentation_active(True)

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
