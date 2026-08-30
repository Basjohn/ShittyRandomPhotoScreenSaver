"""Phase-D2 immutable/latest visualizer render-boundary regressions."""

from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError, replace

import pytest

from core.settings.visualizer_mode_registry import (
    VisualizerClipPolicy,
    VisualizerShellPolicy,
    get_visualizer_presentation_policy,
)
from widgets.spotify_visualizer.logical_runtime import LatestStateMailbox
from widgets.spotify_visualizer.render_bridge import VisualizerSnapshotBridge
from widgets.spotify_visualizer.render_state import (
    BubbleFrame,
    DevCurveFrame,
    FrozenFields,
    OscilloscopeFrame,
    ResolvedVisualizerPresentation,
    SineFrame,
    SpectrumFrame,
    VisualizerCommonState,
    VisualizerLogicalFrame,
    VisualizerProtectedEdge,
    VisualizerRenderSnapshot,
    compose_visualizer_render_snapshot,
    freeze_render_fields,
)


def _logical_frame(
    *,
    runtime_generation: int = 0,
    engine_generation: int = 0,
    activation_id: int = 0,
    logical_timestamp: float = 1.0,
    mode_state=None,
    protected_edges=(),
) -> VisualizerLogicalFrame:
    state = mode_state if mode_state is not None else SpectrumFrame()
    return VisualizerLogicalFrame(
        runtime_generation=runtime_generation,
        engine_generation=engine_generation,
        activation_id=activation_id,
        source_generation=-1,
        source_activation_id=-1,
        mode_id=state.mode_id,
        playing=False,
        logical_timestamp=logical_timestamp,
        source_timestamp=None,
        changed=True,
        present_frame=True,
        mode_reveal_ready=False,
        common=VisualizerCommonState(bars=(0.25, 0.75), bar_count=2),
        mode_state=state,
        protected_edges=tuple(protected_edges),
    )


def _presentation(mode_id: str = "spectrum") -> ResolvedVisualizerPresentation:
    return ResolvedVisualizerPresentation(
        shell_policy=VisualizerShellPolicy.CARD,
        clip_policy=VisualizerClipPolicy.CARD_INTERIOR,
        viewport_resize_capable=get_visualizer_presentation_policy(
            mode_id
        ).viewport_resize_capable,
        outer_rect=(1920.0, 120.0, 480.0, 270.0),
        content_rect=(1924.0, 124.0, 472.0, 262.0),
        dpr=1.5,
        baseline_viewport_size=(420.0, 280.0),
        baseline_aspect_ratio=1.5,
        uniform_visual_scale=1.0,
        viewport_extent=(472.0, 262.0),
        current_aspect_ratio=472.0 / 262.0,
        scene_fade=0.8,
        content_fade=0.7,
        border_width=4.0,
        shell_style={"border_color": [20, 30, 40, 255]},
    )


def _snapshot(
    *,
    revision: int = 1,
    **logical_kwargs,
) -> VisualizerRenderSnapshot:
    return compose_visualizer_render_snapshot(
        _logical_frame(**logical_kwargs),
        _presentation(),
        logical_revision=revision,
    )


def test_render_values_are_deeply_detached_from_mutable_sources() -> None:
    from PySide6.QtGui import QColor

    bars = [0.1, 0.2]
    nested = {"points": [[1.0, 2.0]], "color": QColor(10, 20, 30, 40)}
    common = VisualizerCommonState(
        bars=bars,
        bar_count=2,
        style=freeze_render_fields(nested),
    )
    frame = _logical_frame(mode_state=BubbleFrame(positions=bars), logical_timestamp=2.0)
    direct_source = [5.0]
    direct = FrozenFields((("direct", direct_source),))

    bars[0] = 9.0
    nested["points"][0][0] = 99.0
    nested["color"].setRed(200)
    direct_source[0] = 8.0

    assert common.bars == (0.1, 0.2)
    assert common.style["points"] == ((1.0, 2.0),)
    assert common.style["color"] == (10, 20, 30, 40)
    assert frame.mode_state.positions == (0.1, 0.2)
    assert direct["direct"] == (5.0,)
    with pytest.raises(FrozenInstanceError):
        frame.playing = True  # type: ignore[misc]


def test_bridge_is_one_latest_slot_with_exact_zero_identity_fencing() -> None:
    bridge = VisualizerSnapshotBridge()
    bridge.begin_activation(
        runtime_generation=0,
        engine_generation=0,
        activation_id=0,
        mode_id="spectrum",
    )

    assert bridge.publish(_snapshot(revision=1, logical_timestamp=1.0)) is True
    assert bridge.publish(_snapshot(revision=2, logical_timestamp=2.0)) is True
    assert bridge.superseded_count == 1

    latest = bridge.take_for_render(
        runtime_generation=0,
        engine_generation=0,
        activation_id=0,
        mode_id="spectrum",
    )
    assert latest is not None
    assert latest.logical_revision == 2
    assert latest.logical.logical_timestamp == 2.0
    assert bridge.take_for_render(
        runtime_generation=0,
        engine_generation=0,
        activation_id=0,
        mode_id="spectrum",
    ) is None


def test_bridge_rejects_stale_generation_and_activation_without_displacing_latest() -> None:
    bridge = VisualizerSnapshotBridge()
    bridge.begin_activation(
        runtime_generation=4,
        engine_generation=7,
        activation_id=9,
        mode_id="spectrum",
    )
    current = _snapshot(
        revision=1,
        runtime_generation=4,
        engine_generation=7,
        activation_id=9,
    )
    stale_generation = _snapshot(
        revision=2,
        runtime_generation=3,
        engine_generation=7,
        activation_id=9,
    )
    stale_activation = _snapshot(
        revision=3,
        runtime_generation=4,
        engine_generation=7,
        activation_id=8,
    )
    stale_mode = _snapshot(
        revision=4,
        runtime_generation=4,
        engine_generation=7,
        activation_id=9,
        mode_state=BubbleFrame(),
    )

    assert bridge.publish(current) is True
    assert bridge.publish(stale_generation) is False
    assert bridge.publish(stale_activation) is False
    assert bridge.publish(stale_mode) is False
    assert bridge.publish(
        _snapshot(
            revision=1,
            runtime_generation=4,
            engine_generation=7,
            activation_id=9,
            logical_timestamp=3.0,
        )
    ) is False
    assert bridge.rejected_count == 4
    assert bridge.peek() is current


def test_protected_result_survives_coalescing_once_without_frame_replay() -> None:
    edge = VisualizerProtectedEdge(
        token=3,
        kind="bubble_visible_impulse",
        authored_timestamp=1.0,
        result_timestamp=1.01,
        result={"centroid": [0.4, 0.6], "radius_delta": 0.08},
    )
    bridge = VisualizerSnapshotBridge()
    bridge.begin_activation(
        runtime_generation=1,
        engine_generation=2,
        activation_id=3,
        mode_id="spectrum",
    )
    assert bridge.publish(
        _snapshot(
            revision=1,
            runtime_generation=1,
            engine_generation=2,
            activation_id=3,
            protected_edges=(edge,),
        )
    )
    assert bridge.publish(
        _snapshot(
            revision=2,
            runtime_generation=1,
            engine_generation=2,
            activation_id=3,
            logical_timestamp=1.02,
        )
    )

    consumed = bridge.take_for_render(
        runtime_generation=1,
        engine_generation=2,
        activation_id=3,
        mode_id="spectrum",
    )
    assert consumed is not None
    assert consumed.logical_revision == 2
    assert consumed.logical.protected_edges == (edge,)

    assert bridge.publish(
        _snapshot(
            revision=3,
            runtime_generation=1,
            engine_generation=2,
            activation_id=3,
            logical_timestamp=1.03,
        )
    )
    next_consumed = bridge.take_for_render(
        runtime_generation=1,
        engine_generation=2,
        activation_id=3,
        mode_id="spectrum",
    )
    assert next_consumed is not None
    assert next_consumed.logical.protected_edges == ()


def test_logical_mailbox_coalesces_protected_result_only_until_take() -> None:
    edge = VisualizerProtectedEdge(
        token=5,
        kind="bubble_visible_result",
        authored_timestamp=1.0,
        result_timestamp=1.01,
        result={"positions": [0.4, 0.6, 0.08, 1.0]},
    )
    mailbox = LatestStateMailbox()
    mailbox.publish(
        _logical_frame(
            runtime_generation=1,
            engine_generation=2,
            activation_id=3,
            protected_edges=(edge,),
        ),
        generation=1,
        activation_id=3,
    )
    mailbox.publish(
        _logical_frame(
            runtime_generation=1,
            engine_generation=2,
            activation_id=3,
            logical_timestamp=1.02,
        ),
        generation=1,
        activation_id=3,
    )

    publication = mailbox.take()
    assert publication is not None
    assert publication.state.logical_timestamp == 1.02
    assert publication.state.protected_edges == (edge,)

    mailbox.publish(
        _logical_frame(
            runtime_generation=1,
            engine_generation=2,
            activation_id=3,
            logical_timestamp=1.03,
        ),
        generation=1,
        activation_id=3,
    )
    next_publication = mailbox.take()
    assert next_publication is not None
    assert next_publication.state.protected_edges == ()

    mailbox.publish(
        _logical_frame(
            runtime_generation=1,
            engine_generation=2,
            activation_id=3,
            protected_edges=(edge,),
        ),
        generation=1,
        activation_id=3,
    )
    mailbox.publish(
        _logical_frame(
            runtime_generation=1,
            engine_generation=4,
            activation_id=3,
            logical_timestamp=2.0,
        ),
        generation=1,
        activation_id=3,
    )
    replacement_publication = mailbox.take()
    assert replacement_publication is not None
    assert replacement_publication.state.protected_edges == ()


def test_close_and_replacement_generation_remove_old_render_admission() -> None:
    bridge = VisualizerSnapshotBridge()
    bridge.begin_activation(
        runtime_generation=0,
        engine_generation=0,
        activation_id=0,
        mode_id="spectrum",
    )
    assert bridge.publish(_snapshot()) is True
    bridge.close_admission()

    assert bridge.peek() is None
    assert bridge.publish(_snapshot()) is False

    bridge.begin_activation(
        runtime_generation=1,
        engine_generation=0,
        activation_id=0,
        mode_id="spectrum",
    )
    replacement = _snapshot(revision=2, runtime_generation=1)
    assert bridge.publish(replacement) is True
    assert bridge.take_for_render(
        runtime_generation=1,
        engine_generation=0,
        activation_id=0,
        mode_id="spectrum",
    ) is replacement


def test_render_contract_modules_are_qt_and_legacy_presenter_free() -> None:
    from widgets.spotify_visualizer import render_bridge, render_state

    for module in (render_state, render_bridge):
        tree = ast.parse(inspect.getsource(module))
        imports = {
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        imports.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        assert not any(name.startswith("PySide6") for name in imports)
        assert not any(
            name.endswith(("spotify_visualizer_widget", "spotify_bars_gl_overlay"))
            for name in imports
        )


def test_controller_commit_and_retirement_own_render_admission() -> None:
    from widgets.spotify_visualizer.runtime_controller import (
        VisualizerRuntimeController,
    )

    controller = VisualizerRuntimeController(
        runtime_generation=0,
        initial_mode="spectrum",
    )
    controller.committed_activation_identity = (("spectrum",), (0, 0))
    assert controller.render_identity is not None
    assert controller.render_identity.runtime_generation == 0
    assert controller.render_identity.mode_id == "spectrum"
    logical = _logical_frame()
    assert controller.presentation_viewport_extent == (420.0, 280.0)
    assert controller.publish_render_snapshot(
        logical,
        _presentation(),
        logical_revision=1,
    ) is True
    assert controller.presentation_viewport_extent == (472.0, 262.0)

    assert controller.stop_logical_runtime() is True
    assert controller.render_identity is None
    assert controller.render_bridge.peek() is None


def test_mode_change_closes_old_mode_render_admission_until_commit() -> None:
    from widgets.spotify_visualizer.runtime_controller import (
        VisualizerRuntimeController,
    )

    controller = VisualizerRuntimeController(
        runtime_generation=0,
        initial_mode="spectrum",
    )
    controller.committed_activation_identity = (("spectrum",), (0, 0))
    assert controller.render_identity is not None

    controller.set_mode("bubble")

    assert controller.mode_id == "bubble"
    assert controller.render_identity is None
    assert controller.publish_render_snapshot(
        replace(_logical_frame(), mode_id="bubble", mode_state=BubbleFrame()),
        _presentation("bubble"),
        logical_revision=1,
    ) is False
