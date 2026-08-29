"""H production-cutover integration bars.

These prove the destination pieces connect correctly at the display/runtime owner
before DisplayManager flips to the Quick production route. They assert semantic
owner cardinality and the corrected-G4 visualizer viewport-config ownership
through the real QuickDisplayRuntime + QuickSceneController + runtime controller
chain, not a stand-in sink.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QRect

from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
from rendering.custom_layout_session import (
    CustomLayoutKey,
    CustomLayoutSession,
    CustomLayoutSessionItem,
)
from rendering.quick.runtime import QuickDisplayRuntime
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from rendering.widget_runtime_manager import WidgetRuntimeManager
from widgets.spotify_visualizer.presentation_geometry import (
    resolve_visualizer_presentation,
)
from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController


def _visualizer_item(display_identity: str, extent: tuple[float, float]):
    return CustomLayoutSessionItem(
        source_key=CustomLayoutKey("spotify_visualizer", display_identity),
        model_identity="spotify_visualizer",
        baseline_global_rect=QRect(120, 90, int(extent[0]), int(extent[1])),
        current_global_rect=QRect(120, 90, int(extent[0]), int(extent[1])),
        baseline_size_payload={},
        current_size_payload={},
        baseline_enabled=True,
        current_enabled=True,
        viewport_resize_capable=True,
        baseline_viewport_extent=extent,
    )


def _committed(controller: VisualizerRuntimeController, extent) -> None:
    controller.commit_presentation_metrics(
        resolve_visualizer_presentation(
            policy=get_visualizer_presentation_policy("bubble"),
            display_size=(1920.0, 1080.0),
            outer_origin=(40.0, 60.0),
            viewport_extent=extent,
        )
    )


@pytest.mark.qt
def test_runtime_owns_exactly_one_widget_runtime_manager_and_retires_it(
    qt_app,
) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    factory = QuickSceneFactory()
    runtime = QuickDisplayRuntime(
        screen_index=0,
        runtime_generation=70,
        screen=screen,
        scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    try:
        # Exactly one neutral capability/service owner exists for this display
        # generation, and the accessor returns that same instance every time.
        manager = runtime.widget_runtime_manager
        assert isinstance(manager, WidgetRuntimeManager)
        assert runtime.widget_runtime_manager is manager
        assert manager.is_retired is False

        state = runtime.describe_runtime_state()["widget_runtime_manager"]
        assert state == {
            "present": True,
            "retired": False,
            "has_bound_host": False,
        }
    finally:
        # Closing the runtime retires the neutral owner exactly once. Retirement
        # is idempotent: a second close does not re-run service teardown.
        assert runtime.close_runtime() is True
        assert manager.is_retired is True
        retired_state = runtime.describe_runtime_state()["widget_runtime_manager"]
        assert retired_state["retired"] is True
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_replacement_generation_builds_its_own_widget_runtime_manager(qt_app) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    factory = QuickSceneFactory()
    first = QuickDisplayRuntime(
        screen_index=0,
        runtime_generation=71,
        screen=screen,
        scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    first_manager = first.widget_runtime_manager
    assert first.close_runtime() is True
    assert first_manager.is_retired is True

    second = QuickDisplayRuntime(
        screen_index=0,
        runtime_generation=72,
        screen=screen,
        scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    try:
        # A replacement generation owns its own live neutral manager, never the
        # retired one from the prior generation.
        assert second.widget_runtime_manager is not first_manager
        assert second.widget_runtime_manager.is_retired is False
    finally:
        second.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_runtime_binds_visualizer_render_source_with_exact_identity(qt_app) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    factory = QuickSceneFactory()
    runtime = QuickDisplayRuntime(
        screen_index=0,
        runtime_generation=62,
        screen=screen,
        scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    controller = VisualizerRuntimeController(
        runtime_generation=62,
        bar_count=24,
        initial_mode="bubble",
        engine_factory=lambda _bar_count: object(),
    )
    try:
        identity = runtime.bind_visualizer_render_source(
            controller, engine_generation=3, activation_id=7
        )
        assert identity.runtime_generation == 62
        assert identity.engine_generation == 3
        assert identity.activation_id == 7
        assert identity.mode_id == "bubble"
        # The retained scene item now owns exactly that activation identity.
        assert runtime.scene_controller.visualizer_render_identity == identity
    finally:
        runtime.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_runtime_binds_visualizer_viewport_config_with_committed_and_custom_override(
    qt_app,
) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    factory = QuickSceneFactory()
    runtime = QuickDisplayRuntime(
        screen_index=0,
        runtime_generation=61,
        screen=screen,
        scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    controller = VisualizerRuntimeController(
        runtime_generation=61,
        bar_count=24,
        initial_mode="bubble",
        engine_factory=lambda _bar_count: object(),
    )
    try:
        # Ordinary runtime truth: a saved WIDE committed extent.
        _committed(controller, (630.0, 280.0))
        assert controller.presentation_viewport_extent == (630.0, 280.0)

        # Bind the corrected-G4 config seam once at the display owner. Binding
        # with no CUSTOM session retires any override -> committed still wins.
        runtime.bind_visualizer_viewport_config(controller.set_custom_viewport_override)
        assert controller.presentation_viewport_extent == (630.0, 280.0)

        # Enter CUSTOM; a live edge drag drives only the temporary override.
        session = CustomLayoutSession()
        item = _visualizer_item("display:a", (630.0, 280.0))
        session.add_item(item)
        runtime.scene_controller.bind_custom_layout_session(
            session,
            display_identity="display:a",
            display_origin=QPoint(0, 0),
        )
        assert controller.presentation_viewport_extent == (630.0, 280.0)

        item.set_viewport_extent(840.0, 280.0)
        session.notify_item_changed(item)
        assert controller.presentation_viewport_extent == (840.0, 280.0)

        # An ordinary committed republish during CUSTOM cannot erase the override.
        _committed(controller, (420.0, 280.0))
        assert controller.presentation_viewport_extent == (840.0, 280.0)

        # Ending CUSTOM retires the override -> falls back to committed, never a
        # manufactured canonical.
        runtime.scene_controller.clear_custom_layout_session()
        assert controller.presentation_viewport_extent == (420.0, 280.0)
    finally:
        runtime.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()
