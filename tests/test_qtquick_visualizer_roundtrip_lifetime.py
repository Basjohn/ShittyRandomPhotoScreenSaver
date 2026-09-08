"""Isolated real-Qt hop/deferred-deletion regression (fresh process target)."""
import pytest
from rendering.quick.runtime import QuickDisplayRuntime
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from rendering.quick.widgets.host import OverlayWidgetGeometry
from widgets.spotify_visualizer.presentation_geometry import resolve_visualizer_presentation
from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner
from tests.test_qtquick_custom_layout_owner import _configure_visualizer, _LiveCommitEngine


def test_visualizer_custom_transfer_retargets_same_owner_publication(qt_app) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    factory = QuickSceneFactory()
    source = QuickDisplayRuntime(
        screen_index=0,
        runtime_generation=814,
        screen=screen,
        scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    target = QuickDisplayRuntime(
        screen_index=1,
        runtime_generation=814,
        screen=screen,
        scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    owner = QuickDisplayVisualizerOwner(
        source,
        bar_count=24,
        initial_mode="bubble",
        card_shadow_kwargs={
            "background_color": (0, 0, 0, 0), "border_color": (255, 255, 255, 255),
            "border_width": 4., "corner_radius": 6., "content_inset": 14.,
            "shadow_enabled": False, "shadow_color": (0, 0, 0, 0),
            "shadow_blur": 0., "shadow_offset": (0., 0.), "shadow_spread": 0.,
            "shadow_extensions": (0., 0., 0., 0.),
        },
        engine_factory=lambda _count: _LiveCommitEngine(),
    )
    try:
        _configure_visualizer(owner)
        owner.configure_committed_layout(
            local_rect=(120.0, 80.0, 630.0, 280.0),
            viewport_extent=(630.0, 280.0),
        )
        # Recreation regression: if an intermediate construction publication
        # temporarily commits canonical metrics, the persisted CUSTOM extent must
        # still hydrate the first retained presentation. A cold app restart was
        # masking this by rebuilding directly from persisted truth.
        owner.controller.commit_presentation_metrics(
            resolve_visualizer_presentation(
                policy=owner.controller.presentation_policy,
                display_size=(1920.0, 1080.0),
                viewport_extent=(420.0, 280.0),
                **owner._card_shadow_kwargs,
            )
        )
        owner.bind(engine_generation=3, activation_id=5)
        first = owner._resolve_current_presentation()
        assert first.viewport_extent == (630.0, 280.0)
        owner._apply_resolved_presentation(first)
        admission = object()
        middle_admission = object()
        source.scene_controller.set_visualizer_double_click_admission(admission)
        source.scene_controller.set_visualizer_middle_click_admission(
            middle_admission
        )

        source.scene_controller.transfer_visualizer_to(target.scene_controller)
        assert owner.set_presentation_runtime(target) is True
        assert owner.presentation_runtime is target
        assert owner._runtime is target
        second = resolve_visualizer_presentation(
            policy=owner.controller.presentation_policy,
            display_size=(1920.0, 1080.0),
            outer_origin=(260.0, 190.0),
            viewport_extent=(630.0, 280.0),
            **owner._card_shadow_kwargs,
        )
        owner._apply_resolved_presentation(second)

        assert source.scene_controller._visualizer_item.render_identity is None
        assert target.scene_controller.visualizer_item is not None
        assert target.scene_controller.visualizer_item.presentation is second
        assert target.scene_controller._visualizer_double_click_admission is admission
        assert (
            target.scene_controller._visualizer_middle_click_admission
            is middle_admission
        )
        assert owner.controller.committed_viewport_extent == (630.0, 280.0)
        from PySide6.QtCore import QCoreApplication, QEvent, QRect
        from shiboken6 import isValid
        from rendering.custom_layout_session import CustomLayoutSession
        from tests.test_qtquick_custom_layout_overlay import _item
        import gc

        protected = [screen]
        probes = []
        for index, runtime in enumerate((source, target)):
            scene = runtime.scene_controller
            protected.extend([scene._scene_root, scene._visualizer_loader,
                              scene.custom_layout_overlay.item])
            probe = scene.ordinary_widget_host.create_widget(model_identity="weather",
                geometry=OverlayWidgetGeometry(10., 10., 100., 100.))
            protected.append(probe.item)
            session = CustomLayoutSession()
            session.add_item(_item("weather", str(index), QRect(10, 10, 100, 100), resizable=True))
            scene.bind_custom_layout_session(session, display_identity=str(index))
            probes.append(probe)
        current = target
        shells = [runtime.scene_controller._visualizer_item for runtime in (source, target)]
        for destination in (source, target, source, target):
            current.scene_controller.transfer_visualizer_to(destination.scene_controller)
            assert owner.set_presentation_runtime(destination)
            owner._apply_resolved_presentation(second)
            assert all(isValid(obj) for obj in protected), "transfer"
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            assert all(isValid(obj) for obj in protected), "deferred deletion"
            qt_app.processEvents()
            assert all(isValid(obj) for obj in protected), "events"
            factory._engine.collectGarbage()
            assert all(isValid(obj) for obj in protected), "QML GC"
            gc.collect()
            assert all(isValid(obj) for obj in protected)
            assert [runtime.scene_controller._visualizer_item for runtime in (source, target)] == shells
            current.scene_controller.set_custom_layout_guides()
            destination.scene_controller.set_custom_layout_guides()
            for runtime, probe in zip((source, target), probes):
                model = runtime.scene_controller.custom_layout_overlay.model
                model.moveItem(0, 40., 50., 45., 55.)
                assert (probe.item.x(), probe.item.y()) == (40., 50.)
                model.finishMove()
            current = destination
    finally:
        owner.retire()
        source.close_runtime()
        target.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()
