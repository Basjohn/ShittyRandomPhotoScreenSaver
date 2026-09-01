"""Phase-D3 inline visualizer item/node and local-clip regressions."""

from __future__ import annotations

import inspect

from PySide6.QtQuick import QQuickItem, QSGRenderNode

from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
from rendering.quick.visualizer import (
    VisualizerClipFrame,
    VisualizerClipHost,
    VisualizerRenderItem,
    VisualizerRenderNode,
)
from widgets.spotify_visualizer.presentation_geometry import (
    resolve_visualizer_presentation,
)
from widgets.spotify_visualizer.render_bridge import VisualizerSnapshotBridge
from widgets.spotify_visualizer.render_state import (
    BubbleFrame,
    SpectrumFrame,
    VisualizerCommonState,
    VisualizerLogicalFrame,
    compose_visualizer_render_snapshot,
    freeze_render_fields,
)


def _presentation(*, scale: float = 1.0, origin=(120.0, 80.0)):
    return resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy("spectrum"),
        display_size=(1920.0, 1080.0),
        outer_origin=origin,
        uniform_visual_scale=scale,
    )


def _snapshot(presentation, *, runtime_generation=0, revision=1):
    logical = VisualizerLogicalFrame(
        runtime_generation=runtime_generation,
        engine_generation=0,
        activation_id=0,
        source_generation=-1,
        source_activation_id=-1,
        mode_id="spectrum",
        playing=False,
        logical_timestamp=1.0,
        source_timestamp=None,
        changed=True,
        present_frame=True,
        mode_reveal_ready=True,
        common=VisualizerCommonState(bars=(0.25, 0.75), bar_count=2),
        mode_state=SpectrumFrame(),
    )
    return compose_visualizer_render_snapshot(
        logical,
        presentation,
        logical_revision=revision,
    )


def test_visualizer_item_returns_one_inline_render_node() -> None:
    assert issubclass(VisualizerRenderItem, QQuickItem)
    assert issubclass(VisualizerRenderNode, QSGRenderNode)

    item = VisualizerRenderItem()
    item.set_presentation(_presentation())
    node = item.updatePaintNode(None, None)

    assert isinstance(node, VisualizerRenderNode)
    assert node.rect().width() == 420.0
    assert node.rect().height() == 280.0
    assert isinstance(node.clip_host, VisualizerClipHost)


def test_clip_frame_uses_item_local_inner_chrome_geometry() -> None:
    presentation = _presentation(origin=(530.0, 240.0))
    frame = VisualizerClipFrame.from_presentation(
        presentation,
        matrix_values=tuple(float(index) for index in range(16)),
        viewport=(0, 0, 2880, 1620),
    )

    assert frame.logical_size == (420.0, 280.0)
    assert frame.local_content_rect == (4.0, 4.0, 412.0, 272.0)
    assert frame.inner_corner_radius == 4.0
    assert len(frame.matrix_values) == 16
    assert frame.viewport == (0, 0, 2880, 1620)


def test_item_consumes_exact_bridge_identity_once_and_resets_on_replacement() -> None:
    presentation = _presentation()
    bridge = VisualizerSnapshotBridge()
    identity = bridge.begin_activation(
        runtime_generation=0,
        engine_generation=0,
        activation_id=0,
        mode_id="spectrum",
    )
    snapshot = _snapshot(presentation)
    assert bridge.publish(snapshot)

    item = VisualizerRenderItem()
    item.set_presentation(presentation)
    item.bind_render_source(bridge, identity)
    node = item.updatePaintNode(None, None)

    assert node.snapshot is snapshot
    assert bridge.peek() is None
    reused = item.updatePaintNode(node, None)
    assert reused is node
    assert reused.snapshot is snapshot

    replacement = bridge.begin_activation(
        runtime_generation=1,
        engine_generation=0,
        activation_id=0,
        mode_id="spectrum",
    )
    item.bind_render_source(bridge, replacement)
    item.updatePaintNode(node, None)
    assert node.identity == replacement
    assert node.snapshot is None


def test_bubble_retained_sync_logs_logical_and_device_radius(
    monkeypatch,
) -> None:
    from rendering.quick.visualizer import item as item_module

    presentation = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy("bubble"),
        display_size=(1920.0, 1080.0),
        outer_origin=(120.0, 80.0),
        dpr=1.5,
        viewport_extent=(1275.1714285714286, 772.8311688311688),
        border_width=4.0,
        corner_radius=8.0,
    )
    logical = VisualizerLogicalFrame(
        runtime_generation=0,
        engine_generation=0,
        activation_id=0,
        source_generation=0,
        source_activation_id=0,
        mode_id="bubble",
        playing=True,
        logical_timestamp=1.0,
        source_timestamp=0.99,
        changed=True,
        present_frame=True,
        mode_reveal_ready=True,
        common=VisualizerCommonState(bars=(), bar_count=0),
        mode_state=BubbleFrame(
            positions=(0.5, 0.5, 0.10, 1.0),
            extras=(1.0, 0.0, 0.0, 0.0),
            bubble_count=1,
            simulation_timestamp=1.0,
            geometry_diagnostics=freeze_render_fields(
                {
                    "final_big_max_radius": 0.10,
                    "frozen_big_max_radius": 0.10,
                    "frozen_max_alpha": 1.0,
                    "domain_h": 2.7601113172541742,
                    "tracked_big_token": 12.0,
                    "tracked_big_index": 3.0,
                    "tracked_big_target_radius": 0.11,
                    "tracked_big_display_radius": 0.10,
                    "tracked_big_target_delta": 0.01,
                    "tracked_big_smoothing_step": 0.002,
                    "tracked_big_smoothing_rate_hz": 14.0,
                    "tracked_big_smoothing_mix": 0.28,
                    "motion_event_strength": 0.9,
                    "motion_transient_envelope": 0.72,
                    "stream_burst_speed": 0.70,
                    "transient_drift_drive": 0.14,
                    "stream_step_mean": 0.004,
                    "drift_step_mean": 0.002,
                }
            ),
        ),
    )
    snapshot = compose_visualizer_render_snapshot(
        logical,
        presentation,
        logical_revision=7,
    )
    bridge = VisualizerSnapshotBridge()
    identity = bridge.begin_activation(
        runtime_generation=0,
        engine_generation=0,
        activation_id=0,
        mode_id="bubble",
    )
    assert bridge.publish(snapshot)
    messages: list[str] = []
    monkeypatch.setattr(item_module, "is_viz_diagnostics_enabled", lambda: True)
    monkeypatch.setattr(
        item_module.logger,
        "debug",
        lambda message, *args: messages.append(message % args),
    )

    item = VisualizerRenderItem()
    item.set_presentation(presentation)
    item.bind_render_source(bridge, identity)
    item.updatePaintNode(None, None)

    geometry_message = next(message for message in messages if "stage=B8" in message)
    logical_radius = 0.10 * presentation.content_rect[3]
    assert f"radius_logical_px={logical_radius:.2f}" in geometry_message
    assert f"radius_device_px={logical_radius * 1.5:.2f}" in geometry_message
    assert "dpr=1.500" in geometry_message
    assert "track(token=12 index=3" in geometry_message
    assert "target=0.11000 display=0.10000 delta=0.01000" in geometry_message
    assert "step=0.00200 rate_hz=14.000 mix=0.280" in geometry_message
    assert "motion(event=0.900 envelope=0.720 burst=0.700" in geometry_message
    assert "drift=0.140 stream_step=0.004000 drift_step=0.002000" in geometry_message


def test_mismatched_snapshot_geometry_fails_closed() -> None:
    committed = _presentation()
    bridge = VisualizerSnapshotBridge()
    identity = bridge.begin_activation(
        runtime_generation=0,
        engine_generation=0,
        activation_id=0,
        mode_id="spectrum",
    )
    assert bridge.publish(_snapshot(_presentation(scale=1.25)))
    item = VisualizerRenderItem()
    item.set_presentation(committed)
    item.bind_render_source(bridge, identity)

    node = item.updatePaintNode(None, None)

    assert node.snapshot is None
    assert bridge.presentation_mismatch_count == 1
    # Fail closed without throwing away the newest logical snapshot. A later
    # coherent presentation may consume the same slot.
    assert bridge.peek() is not None


def test_custom_layout_presentation_authority_rebases_fresh_logical_snapshot() -> None:
    working = _presentation(origin=(640.0, 220.0), scale=1.25)
    producer_presentation = _presentation(origin=(120.0, 80.0), scale=1.0)
    bridge = VisualizerSnapshotBridge()
    identity = bridge.begin_activation(
        runtime_generation=0,
        engine_generation=0,
        activation_id=0,
        mode_id="spectrum",
    )
    original = _snapshot(producer_presentation, revision=9)
    assert bridge.publish(original)

    item = VisualizerRenderItem()
    item.set_presentation(working)
    item.set_custom_layout_presentation_authority(True)
    item.bind_render_source(bridge, identity)
    node = item.updatePaintNode(None, None)

    assert node.snapshot is not None
    assert node.snapshot.logical is original.logical
    assert node.snapshot.logical_revision == original.logical_revision
    assert node.snapshot.presentation == working
    assert bridge.presentation_mismatch_count == 0
    assert bridge.peek() is None


def test_direct_invalidation_releases_current_node_once_without_resources() -> None:
    item = VisualizerRenderItem()
    item.set_presentation(_presentation())
    item.updatePaintNode(None, None)

    item._retirement.invalidate()
    item._retirement.invalidate()

    telemetry = item.telemetry.snapshot()
    assert telemetry.invalidation_count == 2
    assert telemetry.release_count == 1


def test_local_clip_is_the_only_path_and_restores_temporary_stencil_contents() -> None:
    from rendering.quick.visualizer import clip_host, item

    item_source = inspect.getsource(item)
    clip_source = inspect.getsource(clip_host)
    assert "QSGClipNode" not in item_source
    assert "VisualizerClipHost" in item_source or "clip_host" in inspect.getsource(
        VisualizerRenderNode
    )
    assert "glClear" not in clip_source
    assert "GL_INCR" in clip_source
    assert "GL_DECR" in clip_source
    assert "glStencilMask(0x00)" in clip_source
    assert "inherited.restore()" in clip_source
    assert "QQuickWidget" not in item_source + clip_source

    begin_source = inspect.getsource(VisualizerClipHost.begin)
    assert begin_source.index("self._active_run = run") < begin_source.index(
        "self._draw_mask(frame)"
    )
    assert "self.end(run)" in begin_source
    assert "stencil rollback both failed" in begin_source
