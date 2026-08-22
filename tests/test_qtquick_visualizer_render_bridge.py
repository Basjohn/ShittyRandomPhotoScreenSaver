"""Phase-D2 immutable/latest visualizer render-boundary regressions."""

from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError, replace

import pytest

from core.settings.visualizer_mode_registry import (
    VisualizerClipPolicy,
    VisualizerShellPolicy,
)
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


def _presentation() -> ResolvedVisualizerPresentation:
    return ResolvedVisualizerPresentation(
        shell_policy=VisualizerShellPolicy.CARD,
        clip_policy=VisualizerClipPolicy.CARD_INTERIOR,
        viewport_resize_capable=False,
        outer_rect=(1920.0, 120.0, 480.0, 270.0),
        content_rect=(1924.0, 124.0, 472.0, 262.0),
        dpr=1.5,
        baseline_viewport_size=(480.0, 270.0),
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


@pytest.mark.qt
def test_legacy_capture_publishes_all_five_tagged_immutable_mode_frames(
    qt_app,
    qtbot,
) -> None:
    from PySide6.QtWidgets import QWidget

    from widgets.spotify_visualizer.legacy_render_snapshot_adapter import (
        capture_legacy_visualizer_logical_frame,
    )
    from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

    expected_types = {
        "spectrum": SpectrumFrame,
        "oscilloscope": OscilloscopeFrame,
        "sine_wave": SineFrame,
        "bubble": BubbleFrame,
        "devcurve": DevCurveFrame,
    }
    parent = QWidget()
    qtbot.addWidget(parent)
    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    widget._engine = None

    for mode_id, expected_type in expected_types.items():
        widget.runtime_controller.set_mode(mode_id)
        captured = capture_legacy_visualizer_logical_frame(
            widget,
            now_ts=10.0,
            changed=True,
            mode_reveal_ready=False,
        )
        assert captured.mode_id == mode_id
        assert isinstance(captured.mode_state, expected_type)
        assert isinstance(captured.common.bars, tuple)

    widget._devcurve_draw_order = ["transients", "mids", "vocals", "bass"]
    widget._devcurve_foreground_layer_id = 0
    devcurve = capture_legacy_visualizer_logical_frame(
        widget,
        now_ts=11.0,
        changed=True,
        mode_reveal_ready=False,
    )
    assert isinstance(devcurve.mode_state, DevCurveFrame)
    assert devcurve.mode_state.draw_order == tuple(widget._devcurve_draw_order)
    assert devcurve.mode_state.foreground_layer_id == 0
    widget.cleanup()


@pytest.mark.qt
def test_production_logical_publish_uses_typed_detached_frame(
    qt_app,
    qtbot,
    monkeypatch,
) -> None:
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QWidget

    from widgets.spotify_visualizer import tick_pipeline
    from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

    parent = QWidget()
    qtbot.addWidget(parent)
    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    widget._enabled = True
    widget._engine = None
    widget._waiting_for_fresh_engine_frame = False
    widget._waiting_for_fresh_frame = False
    widget._display_bars[:] = [0.1] * 8
    widget._bar_fill_color = QColor(1, 2, 3, 4)
    monkeypatch.setattr(
        widget,
        "_dynamic_bar_segments",
        lambda: (_ for _ in ()).throw(AssertionError("geometry read off GUI")),
    )
    monkeypatch.setattr(
        tick_pipeline,
        "consume_engine_bars",
        lambda *_args: (False, False),
    )

    produced = tick_pipeline.logical_tick(widget)
    publication = widget._logical_mailbox.peek()
    assert isinstance(produced, VisualizerLogicalFrame)
    assert publication is not None and publication.state is produced

    widget._display_bars[0] = 9.0
    widget._bar_fill_color.setRed(200)
    assert produced.common.bars[0] == 0.1
    assert produced.common.style["fill_color"] == (1, 2, 3, 4)
    widget.cleanup()


@pytest.mark.qt
def test_paused_spectrum_render_identity_does_not_require_source_identity(
    qt_app,
    qtbot,
) -> None:
    from PySide6.QtWidgets import QWidget

    from widgets.spotify_visualizer.legacy_render_snapshot_adapter import (
        capture_legacy_visualizer_logical_frame,
    )
    from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

    parent = QWidget()
    qtbot.addWidget(parent)
    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    engine = widget._engine
    widget._spotify_playing = False
    widget._display_bars_source_generation = -1
    widget._display_bars_source_activation = -1

    captured = capture_legacy_visualizer_logical_frame(
        widget,
        now_ts=12.0,
        changed=False,
        mode_reveal_ready=True,
    )

    assert captured.activation_id == engine.get_activation_id()
    assert captured.engine_generation == engine.get_generation_id()
    assert captured.source_generation == -1
    assert captured.source_activation_id == -1
    assert captured.source_timestamp is None
    widget.cleanup()


@pytest.mark.qt
def test_line_modes_publish_waveform_freshness_identity_and_preserve_zero(
    qt_app,
    qtbot,
) -> None:
    from types import SimpleNamespace

    from PySide6.QtWidgets import QWidget

    from widgets.spotify_visualizer.legacy_render_snapshot_adapter import (
        capture_legacy_visualizer_logical_frame,
    )
    from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

    engine = SimpleNamespace(
        get_generation_id=lambda: 4,
        get_activation_id=lambda: 0,
        get_latest_generation_with_frame=lambda: 3,
        get_latest_generation_with_waveform=lambda: 4,
        get_latest_authoritative_frame=lambda: (20.0, 3, 0),
        get_waveform=lambda: [0.1, -0.2, 0.3],
        get_waveform_count=lambda: 3,
        get_energy_bands=lambda: SimpleNamespace(
            bass=0.2,
            mid=0.3,
            high=0.4,
            overall=0.3,
        ),
        get_transient_energy_bands=lambda: None,
        get_floor_snapshot=lambda: None,
        get_event_scheduler=lambda: None,
    )
    parent = QWidget()
    qtbot.addWidget(parent)
    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    widget.runtime_controller.set_mode("oscilloscope")
    widget._engine = engine

    captured = capture_legacy_visualizer_logical_frame(
        widget,
        now_ts=13.0,
        changed=True,
        mode_reveal_ready=False,
    )

    assert captured.engine_generation == 4
    assert captured.activation_id == 0
    assert captured.source_generation == 4
    assert captured.source_activation_id == 0
    assert captured.source_timestamp is None
    assert captured.common.waveform == (0.1, -0.2, 0.3)
    widget.cleanup()


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
    assert controller.publish_render_snapshot(
        logical,
        _presentation(),
        logical_revision=1,
    ) is True

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
        _presentation(),
        logical_revision=1,
    ) is False


@pytest.mark.qt
def test_production_publication_to_controller_bridge_preserves_edge_once(
    qt_app,
    qtbot,
) -> None:
    from PySide6.QtWidgets import QWidget

    from widgets.spotify_visualizer import tick_pipeline
    from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

    parent = QWidget()
    parent._runtime_generation = 0
    qtbot.addWidget(parent)
    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    controller = widget.runtime_controller
    controller.set_mode("bubble")
    engine = widget._engine
    controller.begin_render_activation(
        engine_generation=engine.get_generation_id(),
        activation_id=engine.get_activation_id(),
    )
    edge = VisualizerProtectedEdge(
        token=1,
        kind="bubble_visible_result",
        authored_timestamp=30.0,
        result_timestamp=30.01,
        result={"positions": [0.1, 0.2, 0.3, 1.0]},
    )

    first = tick_pipeline._publish_logical_state(
        widget,
        30.01,
        changed=True,
        mode_reveal_ready=False,
        protected_edges=(edge,),
    )
    first_publication = widget._logical_mailbox.take()
    assert first_publication is not None and first_publication.state is first
    assert controller.publish_render_snapshot(
        first,
        _presentation(),
        logical_revision=first_publication.revision,
    )

    second = tick_pipeline._publish_logical_state(
        widget,
        30.02,
        changed=True,
        mode_reveal_ready=False,
    )
    second_publication = widget._logical_mailbox.take()
    assert second_publication is not None and second_publication.state is second
    assert controller.publish_render_snapshot(
        second,
        _presentation(),
        logical_revision=second_publication.revision,
    )

    consumed = controller.render_bridge.take_for_render(
        runtime_generation=0,
        engine_generation=engine.get_generation_id(),
        activation_id=engine.get_activation_id(),
        mode_id="bubble",
    )
    assert consumed is not None
    assert consumed.logical_revision == second_publication.revision
    assert consumed.logical.protected_edges == (edge,)

    third = tick_pipeline._publish_logical_state(
        widget,
        30.03,
        changed=True,
        mode_reveal_ready=False,
    )
    third_publication = widget._logical_mailbox.take()
    assert third_publication is not None
    assert controller.publish_render_snapshot(
        third,
        _presentation(),
        logical_revision=third_publication.revision,
    )
    next_consumed = controller.render_bridge.take_for_render(
        runtime_generation=0,
        engine_generation=engine.get_generation_id(),
        activation_id=engine.get_activation_id(),
        mode_id="bubble",
    )
    assert next_consumed is not None
    assert next_consumed.logical.protected_edges == ()
    widget.cleanup()
