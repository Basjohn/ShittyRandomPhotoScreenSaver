"""Compact all-mode Phase-D lifecycle and source-admission regressions."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from core.settings.visualizer_mode_registry import (
    get_visualizer_presentation_policy,
)
from rendering.quick.visualizer import render_host as render_host_module
from rendering.quick.visualizer.implementation_registry import (
    iter_quick_visualizer_implementations,
)
from rendering.quick.visualizer.render_contract import (
    snapshot_is_render_admissible,
)
from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
from widgets.spotify_visualizer.bubble_frame_runtime import BubbleFrameRuntime
from widgets.spotify_visualizer.devcurve_frame_runtime import (
    DevCurveFrameRuntime,
)
from widgets.spotify_visualizer.oscilloscope_frame_runtime import (
    OscilloscopeFrameRuntime,
)
from widgets.spotify_visualizer.logical_runtime import LatestStateMailbox
from widgets.spotify_visualizer.presentation_geometry import (
    resolve_visualizer_presentation,
)
from widgets.spotify_visualizer.render_state import (
    BubbleFrame,
    DevCurveFrame,
    OscilloscopeFrame,
    SineFrame,
    SphereFrame,
    SpectrumFrame,
    VisualizerCommonState,
    VisualizerEnergyState,
    VisualizerLogicalFrame,
    VisualizerTransientState,
    compose_visualizer_render_snapshot,
    freeze_render_fields,
)
from widgets.spotify_visualizer.runtime_controller import (
    VisualizerRuntimeController,
)
from widgets.spotify_visualizer.sine_frame_runtime import SineFrameRuntime
from widgets.spotify_visualizer.spectrum_frame_runtime import (
    SpectrumFrameRuntime,
)
from widgets.spotify_visualizer.sphere_frame_runtime import SphereFrameRuntime


_MODE_STATES = {
    "spectrum": SpectrumFrame,
    "oscilloscope": OscilloscopeFrame,
    "sine_wave": SineFrame,
    "bubble": BubbleFrame,
    "devcurve": DevCurveFrame,
    "sphere": SphereFrame,
}
_MODE_IDS = tuple(
    descriptor.mode_id
    for descriptor in iter_quick_visualizer_implementations()
)


class _BubbleSimulation:
    count = 0

    @staticmethod
    def tick(_dt, _energy, _settings) -> None:
        return None

    @staticmethod
    def snapshot(**_pulse):
        return (), (), ()

    @staticmethod
    def reset() -> None:
        return None


def _runtime(mode_id: str):
    if mode_id == "spectrum":
        return SpectrumFrameRuntime()
    if mode_id == "oscilloscope":
        return OscilloscopeFrameRuntime()
    if mode_id == "sine_wave":
        return SineFrameRuntime()
    if mode_id == "bubble":
        return BubbleFrameRuntime(simulation_factory=_BubbleSimulation)
    if mode_id == "devcurve":
        return DevCurveFrameRuntime()
    if mode_id == "sphere":
        return SphereFrameRuntime()
    raise AssertionError(f"unhandled test mode: {mode_id}")


def _drive_runtime(
    mode_id: str,
    runtime: Any,
    *,
    now_ts: float,
    playing: bool,
    fresh_source: bool,
):
    source_generation = 5 if fresh_source else 4
    source_activation_id = 7 if fresh_source else 6
    if not playing:
        source_generation = -1
        source_activation_id = -1

    identity = {
        "runtime_generation": 2,
        "engine_generation": 5,
        "activation_id": 7,
        "source_generation": source_generation,
        "source_activation_id": source_activation_id,
        "playing": playing,
    }
    if mode_id == "spectrum":
        return runtime.resolve(
            (0.2, 0.6),
            bar_count=2,
            now_ts=now_ts,
            first_frame=False,
            smoothing_enabled=False,
            smoothing_strength=0.0,
            single_piece=False,
            segments=8,
            ghosting_enabled=False,
            ghost_decay=0.4,
            animation_enabled=False,
            **identity,
        )
    if mode_id == "oscilloscope":
        return runtime.resolve(
            (0.1, -0.1),
            waveform_count=2,
            now_ts=now_ts,
            line_speed=1.0,
            ghosting_enabled=False,
            ghost_decay=0.4,
            energy=VisualizerEnergyState(bass=0.5, overall=0.5),
            kick_event=0.0,
            snare_event=0.0,
            transient_width_mix=0.35,
            base_sensitivity=3.0,
            animation_enabled=False,
            **identity,
        )
    if mode_id == "sine_wave":
        return runtime.resolve(
            now_ts=now_ts,
            energy=VisualizerEnergyState(bass=0.5, overall=0.5),
            kick_event=0.0,
            snare_event=0.0,
            ghosting_enabled=False,
            ghost_decay=0.4,
            line_count=2,
            line_speed=0.5,
            travels=(0.0,) * 6,
            line_shifts=(0.0,) * 6,
            transient_width_mix=0.4,
            base_width_reaction=0.0,
            base_sensitivity=1.0,
            base_heartbeat=0.0,
            heartbeat_slider=0.0,
            **identity,
        )
    if mode_id == "bubble":
        return runtime.advance(
            dt=0.016,
            energy={"bass": 0.5},
            settings={},
            pulse={"bass": 0.5},
            source_timestamp=now_ts - 0.01,
            authored_timestamp=now_ts,
            source_ready=fresh_source and playing,
            edge_token=1,
            **identity,
        )
    if mode_id == "devcurve":
        return runtime.advance(
            now_ts=now_ts,
            source_timestamp=now_ts - 0.01,
            energy=VisualizerEnergyState(bass=0.5, overall=0.5),
            transient=VisualizerTransientState(bass=0.4),
            layer_shape_nodes={},
            parameters={},
            **identity,
        )
    if mode_id == "sphere":
        resolved = runtime.resolve(
            now_ts=now_ts,
            energy=VisualizerEnergyState(bass=0.5, mid=0.4, high=0.3, overall=0.4),
            parameters=freeze_render_fields({"sphere_material": "Chrome"}),
            runtime_generation=identity["runtime_generation"],
            engine_generation=identity["engine_generation"],
            activation_id=identity["activation_id"],
        )
        if resolved is None:
            return None
        # Sphere keeps source identity on the enclosing logical frame rather
        # than duplicating it in its authored payload.
        return SimpleNamespace(
            frame=resolved,
            reactive_source_ready=bool(fresh_source and playing),
        )
    raise AssertionError(f"unhandled test mode: {mode_id}")


def _has_current_source(resolved: Any) -> bool:
    reactive = getattr(resolved, "reactive_source_ready", None)
    if reactive is not None:
        return bool(reactive)
    return bool(
        resolved.source_generation == resolved.engine_generation
        and resolved.source_activation_id == resolved.activation_id
    )


@pytest.mark.parametrize("mode_id", _MODE_IDS)
def test_all_registered_modes_keep_one_runtime_across_pause_play_and_retire_terminally(
    mode_id: str,
) -> None:
    controller = VisualizerRuntimeController(
        runtime_generation=2,
        initial_mode=mode_id,
    )
    runtime = _runtime(mode_id)
    assert controller.resolve_logical_mode_state(mode_id, lambda: runtime) is runtime

    controller.playing = False
    paused = _drive_runtime(
        mode_id,
        runtime,
        now_ts=1.0,
        playing=False,
        fresh_source=False,
    )
    assert paused is not None
    assert _has_current_source(paused) is False

    controller.playing = True
    fresh = _drive_runtime(
        mode_id,
        runtime,
        now_ts=1.1,
        playing=True,
        fresh_source=True,
    )
    assert fresh is not None
    assert _has_current_source(fresh) is True
    assert controller.resolve_logical_mode_state(mode_id, lambda: object()) is runtime

    stale = _drive_runtime(
        mode_id,
        runtime,
        now_ts=1.2,
        playing=True,
        fresh_source=False,
    )
    assert stale is not None
    assert _has_current_source(stale) is False

    replacement = "bubble" if mode_id == "spectrum" else "spectrum"
    controller.set_mode(replacement)
    assert controller.peek_logical_mode_state(mode_id) is None
    assert _drive_runtime(
        mode_id,
        runtime,
        now_ts=1.3,
        playing=True,
        fresh_source=True,
    ) is None


@pytest.mark.parametrize("race_point", ("before_resolve", "after_resolve"))
def _snapshot(
    mode_id: str,
    *,
    playing: bool = True,
    source_generation: int = 5,
    source_activation_id: int = 7,
):
    logical = VisualizerLogicalFrame(
        runtime_generation=2,
        engine_generation=5,
        activation_id=7,
        source_generation=source_generation,
        source_activation_id=source_activation_id,
        mode_id=mode_id,
        playing=playing,
        logical_timestamp=2.0,
        source_timestamp=1.99,
        changed=True,
        present_frame=True,
        mode_reveal_ready=True,
        common=VisualizerCommonState(bars=(), bar_count=0),
        mode_state=_MODE_STATES[mode_id](),
    )
    presentation = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy(mode_id),
        display_size=(1920.0, 1080.0),
    )
    return compose_visualizer_render_snapshot(
        logical,
        presentation,
        logical_revision=1,
    )


@pytest.mark.parametrize("mode_id", _MODE_IDS)
def test_all_registered_modes_apply_generic_source_admission_without_dispatch(
    mode_id: str,
) -> None:
    paused = _snapshot(
        mode_id,
        playing=False,
        source_generation=-1,
        source_activation_id=-1,
    )
    current = _snapshot(mode_id)
    stale = _snapshot(
        mode_id,
        source_generation=4,
        source_activation_id=6,
    )

    assert snapshot_is_render_admissible(paused) is True
    assert snapshot_is_render_admissible(current) is True
    assert snapshot_is_render_admissible(stale) is (mode_id != "spectrum")


@dataclass
class _FakeRenderer:
    mode_id: str
    render_count: int = 0
    release_count: int = 0
    _has_resources: bool = False

    @property
    def has_resources(self) -> bool:
        return self._has_resources

    def render(self, _frame) -> None:
        self.render_count += 1
        self._has_resources = True

    def release_resources(self) -> None:
        self.release_count += 1
        self._has_resources = False


def test_one_render_host_lazily_resolves_all_modes_once_and_releases_every_owner(
    monkeypatch,
) -> None:
    host = QuickVisualizerRenderHost()
    renderers: dict[str, _FakeRenderer] = {}
    renderer_instances: list[_FakeRenderer] = []
    resolutions: list[str] = []
    restores: list[bool] = []
    deleted_buffers: list[tuple[object, ...]] = []
    deleted_vertex_arrays: list[tuple[object, ...]] = []

    def _resolve(mode_id: str) -> _FakeRenderer:
        resolutions.append(mode_id)
        renderer = _FakeRenderer(mode_id)
        renderers[mode_id] = renderer
        renderer_instances.append(renderer)
        return renderer

    def _ensure_quad() -> None:
        host._quad_vao = 11
        host._quad_vbo = 12

    class _InheritedState:
        def restore(self) -> None:
            restores.append(True)

    monkeypatch.setattr(
        render_host_module,
        "resolve_quick_visualizer_renderer",
        _resolve,
    )
    monkeypatch.setattr(host, "_ensure_quad", _ensure_quad)
    monkeypatch.setattr(
        render_host_module._InheritedGlState,
        "capture",
        lambda: _InheritedState(),
    )
    monkeypatch.setattr(
        render_host_module,
        "QOpenGLContext",
        type("_Context", (), {"currentContext": staticmethod(object)}),
    )
    for name in (
        "glEnable",
        "glBlendEquationSeparate",
        "glBlendFuncSeparate",
        "glDisable",
        "glDepthMask",
        "glViewport",
    ):
        monkeypatch.setattr(render_host_module.gl, name, lambda *_args: None)
    monkeypatch.setattr(
        render_host_module.gl,
        "glDeleteBuffers",
        lambda *args: deleted_buffers.append(args),
    )
    monkeypatch.setattr(
        render_host_module.gl,
        "glDeleteVertexArrays",
        lambda *args: deleted_vertex_arrays.append(args),
    )

    sequence = (*_MODE_IDS, "spectrum")
    assert _MODE_IDS == tuple(_MODE_STATES)
    for mode_id in sequence:
        assert host.render(
            snapshot=_snapshot(mode_id),
            viewport=(0, 0, 420, 280),
            logical_size=(420.0, 280.0),
            matrix_values=(1.0,) * 16,
        ) == mode_id

    assert resolutions == [*_MODE_IDS, "spectrum"]
    assert host.resolved_mode_ids == frozenset({"spectrum"})
    assert renderers["spectrum"].render_count == 1
    assert all(renderer.release_count == 1 for renderer in renderer_instances[:-1])
    assert renderer_instances[-1].release_count == 0
    assert len(restores) == len(sequence)
    assert host.has_resources is True

    host.release_resources()

    assert all(renderer.release_count == 1 for renderer in renderer_instances)
    assert all(renderer.has_resources is False for renderer in renderer_instances)
    assert host.resolved_mode_ids == frozenset()
    assert host.has_resources is False
    assert deleted_buffers == [(1, [12])]
    assert deleted_vertex_arrays == [(1, [11])]
